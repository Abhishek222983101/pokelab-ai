#!/usr/bin/env python
"""Item 1: cold vs warm start.  (No torch import here; this is the parent/harness.)
 A. cold_minimal : wall of `python -c "import torch; torch.zeros(1,device='cuda')"` (N runs)
 B. cold_job     : spawn worker + send job immediately -> parent sees first training step (N runs)
 C. warm worker  : spawn worker, wait READY (pool-fill cost), measure idle RSS/PSS/VRAM, then send jobs one by one
                   and measure job send -> first training step (worker-side and parent-side), with/without prewarm.
usage: startup_bench.py PYTHON [N_COLD]
Prints only `METRIC {json}` lines.
"""
import json
import os
import subprocess
import sys
import time

PY = sys.argv[1]
N = int(sys.argv[2]) if len(sys.argv) > 2 else 5
HERE = os.path.dirname(os.path.abspath(__file__))
WORKER = os.path.join(HERE, "warm_worker.py")
T0 = time.perf_counter()
JOB = {"model": "mlp", "p": 113, "frac": 0.3, "steps": 300, "lr": 3e-3, "wd": 1.0}


def emit(step, **kw):
    print("METRIC " + json.dumps({"step": step, **kw, "wall_s": round(time.perf_counter() - T0, 3)}), flush=True)


def mem(pid):
    out = {}
    try:
        for line in open(f"/proc/{pid}/status"):
            if line.startswith("VmRSS"):
                out["rss_MB"] = round(int(line.split()[1]) / 1024, 1)
        for line in open(f"/proc/{pid}/smaps_rollup"):
            if line.startswith("Pss:"):
                out["pss_MB"] = round(int(line.split()[1]) / 1024, 1)
    except Exception as e:  # noqa: BLE001
        out["mem_err"] = str(e)
    try:
        q = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=10).stdout
        for row in q.strip().splitlines():
            ppid, used = [x.strip() for x in row.split(",")]
            if int(ppid) == pid:
                out["vram_MiB"] = int(used)
    except Exception as e:  # noqa: BLE001
        out["vram_err"] = str(e)
    return out


def read_metric(proc, want):
    for line in proc.stdout:
        if line.startswith("METRIC"):
            m = json.loads(line[7:])
            if m["step"] == want:
                return m
    raise RuntimeError(f"worker exited before {want}")


def main():
    env = dict(os.environ)
    # A. minimal cold start, exactly the command in the brief
    for i in range(N):
        t = time.perf_counter()
        r = subprocess.run([PY, "-c", "import torch; torch.zeros(1,device='cuda')"], capture_output=True, timeout=120)
        emit("cold_minimal", run=i, rc=r.returncode, launch_to_exit_s=round(time.perf_counter() - t, 3))
    # B. cold job: process spawn -> first training step of the tiny job
    for i in range(max(3, N // 2)):
        t = time.perf_counter()
        proc = subprocess.Popen([PY, WORKER], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env=env)
        proc.stdin.write(json.dumps({**JOB, "id": f"cold{i}"}) + "\n")
        proc.stdin.flush()
        ready = read_metric(proc, "ready")
        first = read_metric(proc, "first_step")
        t_first = time.perf_counter() - t
        done = read_metric(proc, "job_done")
        proc.stdin.write('{"cmd":"exit"}\n')
        proc.stdin.close()
        proc.wait(timeout=60)
        emit("cold_job", run=i, spawn_to_first_step_s=round(t_first, 3), import_s=ready["import_s"],
             cuda_init_s=ready["cuda_init_s"], recv_to_first_step_s=first["recv_to_first_step_s"],
             steps_per_s=done["steps_per_s_after_first"])
    # C. warm worker, with and without prewarm
    for prewarm in (False, True):
        t = time.perf_counter()
        args = [PY, WORKER] + (["--prewarm"] if prewarm else [])
        proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env=env)
        ready = read_metric(proc, "ready")
        emit("warm_ready", prewarm=prewarm, spawn_to_ready_s=round(time.perf_counter() - t, 3),
             import_s=ready["import_s"], cuda_init_s=ready["cuda_init_s"], prewarm_s=ready["prewarm_s"])
        time.sleep(2.0)
        emit("warm_idle_mem", prewarm=prewarm, **mem(proc.pid))
        for j in range(4):
            t = time.perf_counter()
            proc.stdin.write(json.dumps({**JOB, "id": j, "seed": j}) + "\n")
            proc.stdin.flush()
            first = read_metric(proc, "first_step")
            t_first = time.perf_counter() - t
            done = read_metric(proc, "job_done")
            emit("warm_job", prewarm=prewarm, job=j, send_to_first_step_s=round(t_first, 4),
                 recv_to_build_s=first["recv_to_build_s"], recv_to_first_step_s=first["recv_to_first_step_s"],
                 steps_per_s=done["steps_per_s_after_first"])
            time.sleep(0.5)
        emit("warm_after_jobs_mem", prewarm=prewarm, **mem(proc.pid))
        proc.stdin.write('{"cmd":"exit"}\n')
        proc.stdin.close()
        proc.wait(timeout=60)


if __name__ == "__main__":
    main()
