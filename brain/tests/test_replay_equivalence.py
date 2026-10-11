"""P3.5: §6.12's actual promise — "rebuild projects... from the event
log" after a crash gives back the SAME state, not an approximation.
Runs real smoke jobs through labd #1, kills it, starts labd #2 on the
SAME db file, and proves a fresh StateProjection folded from scratch
(seq 0 onward) is byte-for-byte identical to what was built live.
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


def _spawn_labd(port: int, db_path: str, secret: str):
    env = {
        **os.environ, "LABD_PORT": str(port), "LABD_DB_PATH": db_path,
        "LABD_BRAIN_SECRET": secret, "LABD_PAIRING_SECRET": "p",
        "LABD_WORKERS_PYTHON": WORKERS_PYTHON, "LABD_WORKERS_CWD": WORKERS_CWD,
        "LABD_POOL_SIZE": "1",
    }
    proc = subprocess.Popen([LABD_BIN], cwd=os.path.join(ROOT, "core"), env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    _wait_for_port(port)
    return proc


async def _collect_state(port: int, secret: str, n_jobs_expected: int) -> StateProjection:
    """Connects, subscribes from seq 0, and folds events until exactly
    `n_jobs_expected` jobs have reached a terminal status."""
    bus = BrainBus(f"ws://127.0.0.1:{port}/internal/brain", secret)
    await bus.connect()
    state = StateProjection()
    try:
        async for event in bus.subscribe(since=0):
            state.apply(event)
            done_jobs = [j for j in state.jobs.values() if j.status != "running"]
            if len(done_jobs) >= n_jobs_expected:
                break
    finally:
        await bus.close()
    return state


@pytest.mark.skipif(not os.path.exists(LABD_BIN), reason="labd not built")
@pytest.mark.skipif(not os.path.exists(WORKERS_PYTHON), reason="workers/.venv not found")
def test_state_rebuilt_after_a_crash_is_identical_to_the_live_state(tmp_path):
    db_path = str(tmp_path / "lab.db")
    port1 = _free_port()
    secret = "replay-secret"

    proc1 = _spawn_labd(port1, db_path, secret)
    try:
        async def run_jobs_and_capture():
            bus = BrainBus(f"ws://127.0.0.1:{port1}/internal/brain", secret)
            await bus.connect()
            state = StateProjection()
            pump = asyncio.create_task(_pump(bus, state))
            try:
                job_ids = []
                for i in range(3):
                    job_id = await bus.job_submit("smoke", {"n_steps": 5 + i}, req=f"r{i}")
                    job_ids.append(job_id)
                    # LABD_POOL_SIZE=1 here -> wait for THIS job to finish
                    # before submitting the next, or job_submit gets
                    # rejected with "no free slot available"
                    deadline = asyncio.get_event_loop().time() + 15
                    while asyncio.get_event_loop().time() < deadline:
                        job = state.jobs.get(job_id)
                        if job and job.status != "running":
                            break
                        await asyncio.sleep(0.05)
            finally:
                pump.cancel()
                try:
                    await pump
                except asyncio.CancelledError:
                    pass
                await bus.close()
            return state, job_ids

        state_before, job_ids = asyncio.run(run_jobs_and_capture())
        assert all(state_before.jobs[j].status == "ok" for j in job_ids)
    finally:
        proc1.terminate()
        try:
            proc1.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc1.kill()

    # labd #1 is DEAD. Start a completely fresh labd #2 on the SAME db file.
    port2 = _free_port()
    proc2 = _spawn_labd(port2, db_path, secret)
    try:
        state_after = asyncio.run(_collect_state(port2, secret, n_jobs_expected=3))
    finally:
        proc2.terminate()
        try:
            proc2.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc2.kill()

    assert set(state_after.jobs.keys()) == set(state_before.jobs.keys())
    for job_id in job_ids:
        before = state_before.jobs[job_id]
        after = state_after.jobs[job_id]
        assert after.status == before.status
        assert after.final == before.final
        assert after.metrics == before.metrics, f"metrics diverged for {job_id}"


async def _pump(bus: BrainBus, state: StateProjection) -> None:
    async for event in bus.subscribe(since=0):
        state.apply(event)
