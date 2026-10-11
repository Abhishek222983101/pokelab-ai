"""Oak's live loop end to end against a REAL labd + warm pool: a researcher types "Reproduce
grokking" (the real client `request` command), and the brain — the same `run()` the demo starts —
seeds the team, plans, runs every step through real executors (a real smoke job, a real grokking
job), judges the real number against the curated claim and awards the badge. Every link the game
binds to is checked as an event on the log.
"""
import os
os.environ.setdefault("POKELAB_STEP_DWELL_S", "0")
import asyncio
import json
import os
import socket
import subprocess
import time

import pytest
import websockets

from pokelab_brain.main import run

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LABD_BIN = os.path.join(ROOT, "core", "target", "debug", "labd")
WORKERS_PYTHON = os.path.join(ROOT, "workers", ".venv", "bin", "python")
WORKERS_CWD = os.path.join(ROOT, "workers")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_port(port: int, timeout_s: float = 10.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            try:
                s.connect(("127.0.0.1", port))
                return
            except OSError:
                time.sleep(0.1)
    raise TimeoutError(f"labd never opened port {port}")


@pytest.mark.skipif(not os.path.exists(LABD_BIN), reason="labd not built")
@pytest.mark.skipif(not os.path.exists(WORKERS_PYTHON), reason="workers/.venv not found")
def test_a_typed_request_becomes_a_reproduced_paper_with_a_badge(tmp_path):
    port = _free_port()
    secret = "oak-runtime-secret"
    env = {
        **os.environ, "LABD_PORT": str(port), "LABD_DB_PATH": str(tmp_path / "lab.db"),
        "LABD_BRAIN_SECRET": secret, "LABD_PAIRING_SECRET": "p", "WANDB_MODE": "disabled",
        "LABD_WORKERS_PYTHON": WORKERS_PYTHON, "LABD_WORKERS_CWD": WORKERS_CWD, "LABD_POOL_SIZE": "1",
    }
    proc = subprocess.Popen([LABD_BIN], cwd=os.path.join(ROOT, "core"), env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        _wait_for_port(port)

        async def scenario():
            brain = asyncio.create_task(run(f"ws://127.0.0.1:{port}/internal/brain", secret, with_oak=True))
            events: list[dict] = []
            async with websockets.connect(f"ws://127.0.0.1:{port}/api/ws") as ws:
                await ws.send(json.dumps({"type": "hello", "since": 0}))
                await asyncio.sleep(1.5)  # brain connects, sees an empty log, seeds the team
                await ws.send(json.dumps({"type": "command", "command": "request", "text": "Reproduce grokking please"}))
                deadline = time.monotonic() + 240
                while time.monotonic() < deadline:
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=240))
                    if msg.get("type") != "event":
                        continue
                    events.append(msg["e"])
                    if msg["e"]["kind"] == "project.completed":
                        await asyncio.sleep(0.5)  # let the badge (published right after) arrive
                        try:
                            while True:
                                m = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.0))
                                if m.get("type") == "event":
                                    events.append(m["e"])
                        except asyncio.TimeoutError:
                            pass
                        break
            brain.cancel()
            return events

        events = asyncio.run(scenario())
    finally:
        proc.terminate()
        proc.wait(timeout=10)

    kinds = [e["kind"] for e in events]
    # the team really exists, as events
    spawned = {e["payload"]["agent_id"] for e in events if e["kind"] == "agent.spawned"}
    assert {"pikachu", "charmander", "porygon", "abra", "hoothoot"} <= spawned
    # the request became a project with a real plan
    created = next(e for e in events if e["kind"] == "project.created")
    assert created["payload"]["paper"] == "grokking" and len(created["payload"]["plan"]) == 9
    # every step was started by a real agent chosen for its capability, and finished
    started = [e["payload"] for e in events if e["kind"] == "agent.task_started"]
    by_cap = {p["capability"]: p["agent_id"] for p in started}
    assert by_cap["paper_read"] == "pikachu" and by_cap["run_experiment"] == "porygon" and by_cap["report_write"] == "hoothoot"
    assert kinds.count("agent.task_finished") == 9 and "agent.task_failed" not in kinds
    assert kinds.count("agent.rewarded") == 9
    # a real grokking job ran and its number decided the verdict
    done = next(e for e in events if e["kind"] == "project.completed")["payload"]
    assert done["verdict"] == "REPRODUCED" and done["value"] >= 0.95, done
    job_done = [e for e in events if e["kind"] == "job.done" and e["payload"]["job_id"] == done["job_id"]]
    assert job_done and job_done[0]["payload"]["final"]["test_acc"] >= 0.95
    assert "project.badge_awarded" in kinds
