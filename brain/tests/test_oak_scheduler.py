"""The scheduler against a REAL labd + REAL warm pool: a 3-step plan
(trivial -> run_experiment (real smoke-kit job) -> trivial, verifying the
real job's output) runs through run_plan() end to end.
"""
import asyncio
import os
import socket
import subprocess
import time

import pytest

from pokelab_brain.agents.tools.jobs import ToolContext
from pokelab_brain.bus import BrainBus
from pokelab_brain.oak.planner import PlanStep
from pokelab_brain.oak.scheduler import run_plan
from pokelab_brain.state import StateProjection
from pokelab_labml.selector.thompson import ThompsonSelector

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
def test_scheduler_runs_a_real_smoke_job_as_part_of_a_plan(tmp_path):
    port = _free_port()
    secret = "scheduler-secret"
    env = {
        **os.environ, "LABD_PORT": str(port), "LABD_DB_PATH": str(tmp_path / "lab.db"),
        "LABD_BRAIN_SECRET": secret, "LABD_PAIRING_SECRET": "p",
        "LABD_WORKERS_PYTHON": WORKERS_PYTHON, "LABD_WORKERS_CWD": WORKERS_CWD,
        "LABD_POOL_SIZE": "1",
    }
    proc = subprocess.Popen([LABD_BIN], cwd=os.path.join(ROOT, "core"), env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        _wait_for_port(port)

        async def drive():
            bus = BrainBus(f"ws://127.0.0.1:{port}/internal/brain", secret)
            await bus.connect()
            state = StateProjection()
            pump = asyncio.create_task(_pump(bus, state))
            tool_ctx = ToolContext(bus=bus, state=state, project="scheduler-test", timeout_s=30.0)

            steps = [
                PlanStep(id="s1", cap="paper_read", title="ingest", accept=["job_completed:s1"], after=[]),
                PlanStep(id="s2", cap="run_experiment", title="smoke run", accept=["job_completed:s2", "metric_present:final_loss"], after=["s1"]),
                PlanStep(id="s3", cap="analyze", title="analyse", accept=["job_completed:s3"], after=["s2"]),
            ]
            agent_capabilities = {"eevee-1": ["paper_read", "run_experiment", "analyze"]}
            selector = ThompsonSelector()
            step_configs = {
                "s1": {"final": {}},
                "s2": {"kit": "smoke", "config": {"n_steps": 5}},
                "s3": {"final": {}},
            }

            try:
                result = await run_plan(steps, agent_capabilities, selector, step_configs, tool_ctx=tool_ctx)
            finally:
                pump.cancel()
                try:
                    await pump
                except asyncio.CancelledError:
                    pass
                await bus.close()
            return result

        result = asyncio.run(drive())

        assert result.completed == ["s1", "s2", "s3"]
        assert result.failed == []
        assert result.escalated == []
        # s2's checks passed, which means the REAL smoke job actually ran
        # and the scheduler correctly fed its final result into the verifier
        assert "final_loss" in result.outcomes["s2"].final
        assert all(o.reward is not None and o.reward > 0.5 for o in result.outcomes.values())

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


async def _pump(bus: BrainBus, state) -> None:
    async for event in bus.subscribe(since=0):
        state.apply(event)
