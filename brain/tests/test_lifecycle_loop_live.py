"""THE autonomy test: a plan runs through the real scheduler against a
REAL labd + warm pool, and the roster evolves ON ITS OWN while it runs —
no test code calls spawn/retire directly. One agent deliberately fails
5 real smoke-kit jobs in a row and gets retired by the live loop purely
from its own accumulated Beta posterior; a second batch of steps asks
for a capability nobody has, and after the second live request the loop
drafts a brand new agent with a REAL Groq call and hands it the next
step — all of it driven by what actually happened during this one run.
"""
import asyncio
import os
import socket
import subprocess
import time

import pytest

from pokelab_brain.agents.tools.jobs import ToolContext
from pokelab_brain.agents.spec import AgentSpec
from pokelab_brain.bus import BrainBus
from pokelab_brain.llm.providers import GroqProvider
from pokelab_brain.llm.router import LlmRouter
from pokelab_brain.oak.lifecycle_loop import LifecycleLoop
from pokelab_brain.oak.planner import PlanStep
from pokelab_brain.oak.scheduler import run_plan
from pokelab_brain.state import StateProjection
from pokelab_labml.selector.thompson import ThompsonSelector

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LABD_BIN = os.path.join(ROOT, "core", "target", "debug", "labd")
WORKERS_PYTHON = os.path.join(ROOT, "workers", ".venv", "bin", "python")
WORKERS_CWD = os.path.join(ROOT, "workers")


def _load_env_key(name: str) -> str | None:
    if os.environ.get(name):
        return os.environ[name]
    env_path = os.path.join(ROOT, ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.strip().startswith(f"{name}="):
                    return line.strip().split("=", 1)[1]
    return None


GROQ_KEY = _load_env_key("GROQ_API_KEY_1")


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


@pytest.mark.skipif(GROQ_KEY is None, reason="no GROQ_API_KEY_1 available")
@pytest.mark.skipif(not os.path.exists(LABD_BIN), reason="labd not built")
@pytest.mark.skipif(not os.path.exists(WORKERS_PYTHON), reason="workers/.venv not found")
def test_the_roster_evolves_on_its_own_during_one_real_run(tmp_path):
    port = _free_port()
    secret = "evolve-secret"
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
            published_kinds: list[str] = []

            async def pump():
                async for event in bus.subscribe(since=0):
                    state.apply(event)

            pump_task = asyncio.create_task(pump())

            async def publish(kind: str, payload: dict) -> None:
                published_kinds.append(kind)
                await bus.publish(
                    [{"kind": kind, "v": 1, "project": "evolve-demo", "actor": "oak.lifecycle",
                      "corr": None, "causation": None, "payload": payload, "display": None}],
                    req=f"req-{kind}-{len(published_kinds)}",
                )

            roster = {
                "eevee-1": AgentSpec(id="eevee-1", species="eevee", role="runner",
                                      capabilities=["run_experiment"], prompt_ref="x.md", status="active"),
            }
            selector = ThompsonSelector()
            router = LlmRouter(
                providers={"groq": GroqProvider(GROQ_KEY)},
                cache_db=tmp_path / "llm_cache.db", budget_db=tmp_path / "brain.db",
            )
            loop = LifecycleLoop(
                roster=roster, selector=selector, router=router, route=["groq"], publish=publish,
                llm_kwargs={"model": "openai/gpt-oss-20b", "reasoning_effort": "low"},
            )
            tool_ctx = ToolContext(bus=bus, state=state, project="evolve-demo", timeout_s=30.0)

            # batch 1: eevee-1 fails an impossible threshold on REAL
            # smoke-kit jobs, repeatedly -> should get retired on its own.
            # [MEASURED]: a "fast cheap failure" floors at reward=0.2 by
            # compute_reward_v2's own formula (success=0, cost=0 ->
            # r_base = 0.2*(1-0) = 0.2) — the Beta posterior needs ~20
            # such observations before P(mean<0.35)>=0.9 (verified with
            # scipy.stats.beta.cdf before picking this number, not guessed).
            # That's a real, deliberately conservative property of the
            # design (one unlucky streak shouldn't retire an agent), not a
            # bug — 5 wasn't a safe assumption, so the test was wrong, not
            # the retire trigger.
            N_FAILURES = 20
            fail_steps = [
                PlanStep(
                    id=f"fail-{i}", cap="run_experiment", title=f"doomed run {i}",
                    accept=["metric_threshold:final_loss,<=,0.0001"],  # smoke kit can never hit this
                    after=[f"fail-{i-1}"] if i > 0 else [],
                )
                for i in range(N_FAILURES)
            ]
            # batch 2: a capability nobody covers, requested twice in a row
            # (Scout's spawn threshold) -> the SECOND request should trigger
            # a real spawn and hand that step to the new agent
            gap_steps = [
                PlanStep(id="gap-0", cap="analyze_3d", title="needs a new specialist", accept=["job_completed:gap-0"], after=[f"fail-{N_FAILURES - 1}"]),
                PlanStep(id="gap-1", cap="analyze_3d", title="needs a new specialist again", accept=["job_completed:gap-1"], after=["gap-0"]),
            ]
            steps = fail_steps + gap_steps
            step_configs = {s.id: {"kit": "smoke", "config": {"n_steps": 3}} for s in fail_steps}
            step_configs["gap-0"] = {"final": {}}
            step_configs["gap-1"] = {"final": {}}

            try:
                result = await run_plan(
                    steps, loop.active_capabilities(), selector, step_configs, tool_ctx=tool_ctx,
                    on_capability_gap=loop.on_capability_gap, on_task_outcome=loop.on_task_outcome,
                )
            finally:
                pump_task.cancel()
                try:
                    await pump_task
                except asyncio.CancelledError:
                    pass
                router.close()
                await bus.close()

            return result, roster, published_kinds

        result, roster, published_kinds = asyncio.run(drive())

        # eevee-1 failed its way into retirement, with nobody telling it to
        assert roster["eevee-1"].status == "retired", "eevee-1 should have been autonomously retired"
        assert "agent.retired" in published_kinds

        # a brand new agent was drafted live from a real capability gap
        new_agents = [aid for aid, a in roster.items() if aid != "eevee-1"]
        assert len(new_agents) == 1, f"expected exactly one spawned agent, got {new_agents}"
        assert roster[new_agents[0]].status == "active"
        assert "analyze_3d" in roster[new_agents[0]].capabilities
        assert "agent.spawned" in published_kinds

        # and the plan still finished — the escalated first gap step is
        # expected (no one covered it yet), everything after self-healed
        assert "gap-1" in result.completed

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
