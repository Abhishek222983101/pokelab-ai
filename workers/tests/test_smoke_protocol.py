import json
import subprocess
import sys

import pytest


def run_pool(lines_in: list[dict]) -> list[dict]:
    payload = "\n".join(json.dumps(l) for l in lines_in) + "\n"
    proc = subprocess.run(
        [sys.executable, "-I", "-m", "pokelab_workers.pool_main", "--slot", "test", "--device", "cpu"],
        input=payload,
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    assert proc.stderr == "", proc.stderr
    return [json.loads(l) for l in proc.stdout.strip().splitlines()]


def test_ready_then_metrics_then_done():
    out = run_pool([{"t": "job", "job_id": "j1", "kit": "smoke", "config": {"n_steps": 5}}])
    ready = out[0]
    assert ready["t"] == "ready"
    assert ready["device"] == "cpu"
    assert isinstance(ready["torch"], bool)  # True once torch is installed, False before — both valid
    metrics = [m for m in out if m["t"] == "metric"]
    assert len(metrics) == 5
    assert metrics[0]["step"] == 1
    assert metrics[-1]["step"] == 5
    done = out[-1]
    assert done["t"] == "done"
    assert done["status"] == "ok"
    assert done["final"]["n_steps"] == 5


def test_two_jobs_same_warm_process():
    out = run_pool([
        {"t": "job", "job_id": "j1", "kit": "smoke", "config": {"n_steps": 3}},
        {"t": "job", "job_id": "j2", "kit": "smoke", "config": {"n_steps": 3}},
    ])
    done_events = [e for e in out if e["t"] == "done"]
    assert [d["job_id"] for d in done_events] == ["j1", "j2"]


def test_unknown_kit_fails_job_not_process():
    out = run_pool([{"t": "job", "job_id": "jx", "kit": "nope", "config": {}}])
    done = [e for e in out if e["t"] == "done"][0]
    assert done["status"] == "error"
    assert "unknown_kit" in done["error_sig"]
