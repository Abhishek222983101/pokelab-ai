"""Proves {"t":"stop"} actually interrupts a RUNNING job, not just one
that's already finished. Runs the real pool_main.py as a subprocess
(not a mock), starts a deliberately long grokking run, sends stop after
a short delay, and checks it stopped well short of the full step count.
"""
import json
import subprocess
import sys
import threading
import time


def test_stop_interrupts_a_running_job_before_it_finishes():
    proc = subprocess.Popen(
        [sys.executable, "-I", "-m", "pokelab_workers.pool_main", "--slot", "test", "--device", "cpu"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, bufsize=1,
    )

    # a long-running config: many steps, cheap eval, CPU, p small so each
    # step is fast but the TOTAL would take a while if not interrupted
    job = {"t": "job", "job_id": "long1", "kit": "grokking",
           "config": {"model": "mlp", "p": 53, "frac": 0.5, "steps": 200000,
                      "eval_every": 50, "device": "cpu", "d_hidden": 32, "d_emb": 16}}

    lines = []

    def read_output():
        for line in proc.stdout:
            lines.append(line.strip())

    reader = threading.Thread(target=read_output, daemon=True)
    reader.start()

    proc.stdin.write(json.dumps(job) + "\n")
    proc.stdin.flush()

    # Margin bumped from 1.5s to 3s (P12.1): under heavy system load (many
    # other processes contending for CPU) the pool's cold-import handshake
    # can itself take close to 1.5s, racing the stop command against job
    # dispatch rather than against real training. 3s gives real headroom
    # without weakening what the test actually proves (steps_run far below
    # the 200000-step budget either way).
    time.sleep(3.0)
    proc.stdin.write(json.dumps({"t": "stop", "job_id": "long1"}) + "\n")
    proc.stdin.flush()

    proc.stdin.close()
    proc.wait(timeout=20)
    reader.join(timeout=2)

    parsed = [json.loads(l) for l in lines if l]
    done = [p for p in parsed if p.get("t") == "done"]
    assert done, f"never got a done line; stderr={proc.stderr.read()}"
    assert done[0]["status"] == "stopped"
    assert done[0]["final"]["steps_run"] < 200000, "job should have been interrupted, not run to completion"
    # loose upper bound: 1.5s of CPU MLP steps is nowhere near 200k steps
    assert done[0]["final"]["steps_run"] < 50000, f"stop took far too long to take effect: {done[0]['final']}"
