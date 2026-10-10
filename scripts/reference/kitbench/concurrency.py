#!/usr/bin/env python
"""Item 2: GPU concurrency. Launch N identical copies of grok.py at once (each killed at --cap seconds),
sample per-PID VRAM (nvidia-smi), per-PID RSS/PSS, GPU util and system MemAvailable every 0.5 s.
grok.py prints `METRIC k=v ...`; this harness re-emits everything as `METRIC {json}`.

usage: concurrency.py --n 3 --cap 120 --tag mlp -- PYTHON grok.py [grok args...]
"""
import argparse
import json
import subprocess
import threading
import time

T0 = time.perf_counter()


def emit(step, **kw):
    print("METRIC " + json.dumps({"step": step, **kw, "wall_s": round(time.perf_counter() - T0, 3)}), flush=True)


def kv(line):
    out = {}
    for tok in line.split()[1:]:
        if "=" in tok:
            k, v = tok.split("=", 1)
            try:
                out[k] = float(v) if any(c in v for c in ".e") or v.lstrip("-").isdigit() else v
                if isinstance(out[k], float) and out[k].is_integer() and "." not in v:
                    out[k] = int(out[k])
            except ValueError:
                out[k] = v
    return out


def proc_mem(pid):
    rss = pss = 0.0
    try:
        for line in open(f"/proc/{pid}/status"):
            if line.startswith("VmRSS"):
                rss = int(line.split()[1]) / 1024
        for line in open(f"/proc/{pid}/smaps_rollup"):
            if line.startswith("Pss:"):
                pss = int(line.split()[1]) / 1024
    except Exception:  # noqa: BLE001
        pass
    return rss, pss


def cpu_ticks(pid):
    try:
        st = open(f"/proc/{pid}/stat").read().rsplit(")", 1)[1].split()
        return int(st[11]) + int(st[12])
    except Exception:  # noqa: BLE001
        return None


def cpu_freqs_mhz():
    import glob
    out = []
    for f in glob.glob("/sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_cur_freq"):
        try:
            out.append(int(open(f).read()) / 1000)
        except Exception:  # noqa: BLE001
            pass
    return out


def mem_available_mb():
    for line in open("/proc/meminfo"):
        if line.startswith("MemAvailable"):
            return int(line.split()[1]) / 1024
    return -1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--cap", type=float, default=120)
    ap.add_argument("--tag", default="run")
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    cmd = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
    mem0 = mem_available_mb()
    t_launch = time.perf_counter()
    procs = [subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
             for _ in range(a.n)]
    pids = [p.pid for p in procs]
    peak = {pid: {"vram": 0, "rss": 0.0, "pss": 0.0} for pid in pids}
    gpu_util, mem_avail, freq_max, freq_mean = [], [], [], []
    TCK = __import__("os").sysconf("SC_CLK_TCK")
    cpu_first, cpu_last = {}, {}
    stop = threading.Event()

    def sampler():
        while not stop.is_set():
            try:
                q = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"],
                                   capture_output=True, text=True, timeout=5).stdout
                for row in q.strip().splitlines():
                    ppid, used = [x.strip() for x in row.split(",")]
                    if int(ppid) in peak and used.isdigit():
                        peak[int(ppid)]["vram"] = max(peak[int(ppid)]["vram"], int(used))
                u = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,clocks.sm,power.draw", "--format=csv,noheader,nounits"],
                                   capture_output=True, text=True, timeout=5).stdout.strip().split(",")
                gpu_util.append((int(u[0]), float(u[1]), float(u[2]) if u[2].strip() not in ("[N/A]", "N/A") else -1))
            except Exception:  # noqa: BLE001
                pass
            fr = cpu_freqs_mhz()
            if fr:
                freq_max.append(max(fr))
                freq_mean.append(sum(fr) / len(fr))
            for pid in pids:
                tk = cpu_ticks(pid)
                if tk is not None:
                    cpu_first.setdefault(pid, (tk, time.perf_counter()))
                    cpu_last[pid] = (tk, time.perf_counter())
                rss, pss = proc_mem(pid)
                peak[pid]["rss"] = max(peak[pid]["rss"], rss)
                peak[pid]["pss"] = max(peak[pid]["pss"], pss)
            mem_avail.append(mem_available_mb())
            stop.wait(0.5)

    th = threading.Thread(target=sampler, daemon=True)
    th.start()
    results = [{} for _ in procs]

    def reader(i, p):
        r = results[i]
        r["first99"] = None
        for line in p.stdout:
            if not line.startswith("METRIC"):
                continue
            m = kv(line)
            now = time.perf_counter() - t_launch
            if "event" in m and m["event"] == "start":
                r["train_start_abs"] = now
                r["import_s"] = m.get("import_s")
            elif "event" in m and m["event"] == "done":
                r["done"] = m
                r["end_abs"] = now
            elif "step" in m:
                r["last"] = m
                r["last_abs"] = now
                if r["first99"] is None and m.get("test_acc", 0) >= 0.99:
                    r["first99"] = (m["step"], m.get("wall_s"))
                emit("grok_eval", tag=a.tag, n=a.n, run=i, grok_step=m["step"], test_acc=m.get("test_acc"),
                     train_acc=m.get("train_acc"), train_wall_s=m.get("wall_s"))

    readers = [threading.Thread(target=reader, args=(i, p), daemon=True) for i, p in enumerate(procs)]
    for t in readers:
        t.start()
    timers = [threading.Timer(a.cap, p.kill) for p in procs]
    for t in timers:
        t.start()
    for p in procs:
        p.wait()
    for t in timers:
        t.cancel()
    for t in readers:
        t.join(timeout=5)
    stop.set()
    th.join(timeout=5)
    makespan = time.perf_counter() - t_launch
    sum_sps, tot_steps, starts, ends = 0.0, 0, [], []
    for i, (p, r) in enumerate(zip(procs, results)):
        last = r.get("last", {})
        steps_done = last.get("step", 0)
        train_wall = last.get("wall_s", 0)
        sps = steps_done / train_wall if train_wall else 0.0  # same definition as grok.py's steps_per_s
        sum_sps += sps
        tot_steps += steps_done
        if "train_start_abs" in r:
            starts.append(r["train_start_abs"])
            ends.append(r.get("end_abs", r.get("last_abs", makespan)))
        emit("run_summary", tag=a.tag, n=a.n, run=i, rc=p.returncode, killed_at_cap=p.returncode == -9,
             steps_run=steps_done, steps_per_s=round(sps, 1), final_test_acc=last.get("test_acc"),
             test99_step=r["first99"][0] if r["first99"] else None,
             test99_train_s=r["first99"][1] if r["first99"] else None,
             train_loop_s=train_wall, import_s=r.get("import_s"),
             launch_to_train_start_s=round(r.get("train_start_abs", -1), 2),
             launch_to_end_s=round(r.get("end_abs", r.get("last_abs", -1)), 2),
             peak_vram_MiB=peak[p.pid]["vram"], peak_rss_MB=round(peak[p.pid]["rss"]),
             peak_pss_MB=round(peak[p.pid]["pss"]),
             cpu_pct_avg=round(100 * (cpu_last[p.pid][0] - cpu_first[p.pid][0]) / TCK /
                               max(cpu_last[p.pid][1] - cpu_first[p.pid][1], 1e-9)) if p.pid in cpu_last else None)
    overlap = (min(ends) - max(starts)) if starts else 0
    utils = [u[0] for u in gpu_util]
    clocks = [u[1] for u in gpu_util]
    power = [u[2] for u in gpu_util if u[2] >= 0]
    emit("agg_summary", tag=a.tag, n=a.n, sum_steps_per_s=round(sum_sps, 1), total_steps=tot_steps,
         makespan_s=round(makespan, 2), full_overlap_s=round(overlap, 2),
         gpu_util_avg=round(sum(utils) / max(len(utils), 1), 1), gpu_util_max=max(utils or [0]),
         sm_clock_avg_MHz=round(sum(clocks) / max(len(clocks), 1)), gpu_power_avg_W=round(sum(power) / max(len(power), 1), 1),
         mem_available_before_MB=round(mem0), mem_available_min_MB=round(min(mem_avail or [mem0])),
         host_ram_used_by_runs_MB=round(mem0 - min(mem_avail or [mem0])),
         sum_peak_pss_MB=round(sum(v["pss"] for v in peak.values())),
         sum_peak_vram_MiB=sum(v["vram"] for v in peak.values()),
         cpu_freq_max_avg_MHz=round(sum(freq_max) / max(len(freq_max), 1)),
         cpu_freq_mean_avg_MHz=round(sum(freq_mean) / max(len(freq_mean), 1)))


if __name__ == "__main__":
    main()
