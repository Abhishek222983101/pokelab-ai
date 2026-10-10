#!/usr/bin/env python3
"""A trivial script that proves a remote runner's plumbing without
needing our full package shipped to the remote VM — it emits the exact
JSON-lines protocol shape pokelab_workers.protocol would, by hand."""
import json
import platform

print(json.dumps({"t": "ready", "torch": False, "device": "cpu", "pid": 0}))
for step in range(1, 4):
    print(json.dumps({"t": "metric", "job_id": "remote-smoke", "step": step, "k": "loss", "v": 1.0 / step}))
print(json.dumps({"t": "done", "job_id": "remote-smoke", "status": "ok",
                   "final": {"platform": platform.platform()}, "error_sig": None}))
