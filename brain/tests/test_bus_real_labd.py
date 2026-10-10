"""A REAL labd binary is spawned as a subprocess, with a real warm pool
pointed at workers/.venv. The brain connects over the actual
/internal/brain WebSocket, submits a real `smoke` job, and folds the
resulting events into StateProjection — the full P1<->P3 integration, no
mocks on either side.
"""
import asyncio
import os
import socket
import subprocess
import time

import pytest

from pokelab_brain.bus import BrainBus
from pokelab_brain.state import StateProjection

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


@pytest.fixture
def running_labd(tmp_path):
    if not os.path.exists(LABD_BIN):
        pytest.skip("labd binary not built — run `cargo build` in core/")
    if not os.path.exists(WORKERS_PYTHON):
        pytest.skip("workers/.venv not found — run `uv sync` in workers/")

    port = _free_port()
    secret = "test-bus-secret"
    env = {
        **os.environ,
        "LABD_PORT": str(port),
        "LABD_DB_PATH": str(tmp_path / "lab.db"),
        "LABD_BRAIN_SECRET": secret,
        "LABD_PAIRING_SECRET": "test-pairing-secret",
        "LABD_WORKERS_PYTHON": WORKERS_PYTHON,
        "LABD_WORKERS_CWD": WORKERS_CWD,
        "LABD_POOL_SIZE": "1",
    }
    proc = subprocess.Popen(
        [LABD_BIN],
        cwd=os.path.join(ROOT, "core"),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        _wait_for_port(port)
        yield port, secret
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.mark.asyncio
async def test_brain_submits_job_and_projects_state(running_labd):
    port, secret = running_labd
    bus = BrainBus(f"ws://127.0.0.1:{port}/internal/brain", secret)
    await bus.connect()
    try:
        job_id = await bus.job_submit("smoke", {"n_steps": 5}, req="r1")
        assert job_id.startswith("job-")

        state = StateProjection()
        seen_done = False
        async for event in bus.subscribe(since=0):
            state.apply(event)
            job = state.jobs.get(job_id)
            if job and job.status == "ok":
                seen_done = True
                break
        assert seen_done
        job = state.jobs[job_id]
        assert job.final["n_steps"] == 5
        assert len(job.metrics["loss"]) == 5
    finally:
        await bus.close()
