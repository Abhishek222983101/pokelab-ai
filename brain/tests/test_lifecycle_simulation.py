"""P6.6 — the lifecycle simulation test. Runs spawn -> refine -> merge ->
retire against REAL labd (events really published and replayable) and
REAL LLM calls for every generative step (spawn draft, refine reflection,
merge synthesis). Task *outcomes* are seeded/simulated — generating
enough real GPU runs to naturally hit every trigger threshold would take
far longer than a test should; the triggers and the LLM calls around them
are 100% real.
"""
import asyncio
import os
import socket
import subprocess
import time

import pytest

from pokelab_brain.agents.lifecycle import check_merge, check_refine, check_retire, check_spawn
from pokelab_brain.agents.merge import decide_merge, synthesize
from pokelab_brain.agents.refine import decide_promotion, reflect_and_rewrite
from pokelab_brain.agents.retire import apply_retirement, plan_retirement
from pokelab_brain.agents.spawn import draft_spec
from pokelab_brain.agents.spec import AgentSpec
from pokelab_brain.bus import BrainBus
from pokelab_brain.llm.providers import GroqProvider
from pokelab_brain.llm.router import LlmRouter
from pokelab_labml.scout.coverage import find_gaps
from pokelab_labml.selector.thompson import AgentArm

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LABD_BIN = os.path.join(ROOT, "core", "target", "debug", "labd")


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
def test_full_lifecycle_spawn_refine_merge_retire(tmp_path):
    port = _free_port()
    secret = "lifecycle-secret"
    env = {
        **os.environ, "LABD_PORT": str(port), "LABD_DB_PATH": str(tmp_path / "lab.db"),
        "LABD_BRAIN_SECRET": secret, "LABD_PAIRING_SECRET": "p",
    }
    proc = subprocess.Popen([LABD_BIN], cwd=os.path.join(ROOT, "core"), env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        _wait_for_port(port)

        async def drive():
            bus = BrainBus(f"ws://127.0.0.1:{port}/internal/brain", secret)
            await bus.connect()
            router = LlmRouter(
                providers={"groq": GroqProvider(GROQ_KEY)},
                cache_db=tmp_path / "llm_cache.db", budget_db=tmp_path / "brain.db",
            )
            published_kinds = []

            async def publish(kind: str, payload: dict):
                req = f"req-{kind}-{len(published_kinds)}"
                await bus.publish([{"kind": kind, "v": 1, "project": "lifecycle-demo", "actor": "oak",
                                     "corr": None, "causation": None, "payload": payload, "display": None}], req)
                published_kinds.append(kind)

            try:
                # --- 1. SPAWN: a real coverage gap, a real LLM draft ---
                gaps = find_gaps(["analyze_3d"] * 3, agent_capabilities={})
                spawn_trigger = check_spawn(gaps)
                assert spawn_trigger.should_spawn
                new_spec, prompt_summary = draft_spec(
                    router, route=["groq"], capability=spawn_trigger.capability,
                    nearest_agents=[], past_spawns=[], new_id="eevee-3d-1",
                    model="openai/gpt-oss-20b", reasoning_effort="low",
                )
                await publish("agent.spawned", {"agent_id": new_spec.id, "capability": spawn_trigger.capability,
                                                 "prompt_summary": prompt_summary})

                # --- 2. REFINE: a struggling agent, a real reflection call ---
                refine_trigger = check_refine(n_tasks=6, failure_rate=0.5, format_error_rate=0.1)
                assert refine_trigger.should_refine
                traces = [
                    {"task": "run_kit grokking", "success": False, "reward": 0.1, "medic_class": "unknown_kit"},
                    {"task": "run_kit grokking", "success": False, "reward": 0.15, "medic_class": "unknown_kit"},
                    {"task": "run_kit smoke", "success": True, "reward": 0.9, "medic_class": "none"},
                ]
                new_prompt = reflect_and_rewrite(
                    router, route=["groq"], current_prompt="You are a research agent. Use run_kit.",
                    traces=traces, model="openai/gpt-oss-20b", reasoning_effort="low",
                )
                assert len(new_prompt) > 10
                # simulated shadow-eval outcome: the new prompt does better,
                # Pareto-clean (this part is seeded, see module docstring)
                promo = decide_promotion(old_rewards=[0.1, 0.15, 0.9], new_rewards=[0.3, 0.4, 0.92])
                assert promo.promote
                await publish("agent.evolved", {"agent_id": "struggling-1", "delta": promo.mean_delta,
                                                 "new_prompt_len": len(new_prompt)})

                # --- 3. MERGE: two similar underused agents, real synthesis ---
                a = AgentSpec(id="eevee-a", species="eevee", role="reader", capabilities=["read_paper", "run_kit", "analyze"], prompt_ref="a.md")
                b = AgentSpec(id="eevee-b", species="eevee", role="runner", capabilities=["read_paper", "run_kit"], prompt_ref="b.md")
                merge_trigger = check_merge(a.capabilities, b.capabilities, assignment_frac_a=0.1, assignment_frac_b=0.15, spec_cosine=0.9)
                assert merge_trigger.should_merge
                merged_spec, merge_summary = synthesize(
                    router, route=["groq"], agent_a=a, prompt_a="Read carefully.",
                    agent_b=b, prompt_b="Run precisely.", new_id="eevee-merged-1",
                    model="openai/gpt-oss-20b", reasoning_effort="low",
                )
                merge_decision = decide_merge(merged_rewards=[0.68, 0.70], parent_a_mean=0.65, parent_b_mean=0.60)
                assert merge_decision.accept
                await publish("agent.merged", {"parents": [a.id, b.id], "child": merged_spec.id})

                # --- 4. RETIRE: a consistently bad agent ---
                bad_arm = AgentArm(agent_id="bad-1", alpha=1.0, beta=15.0)
                retire_trigger = check_retire(bad_arm, n_tasks=10)
                assert retire_trigger.should_retire
                bad_agent = AgentSpec(id="bad-1", species="eevee", role="x", capabilities=["run_kit"], prompt_ref="x.md", status="active")
                plan = plan_retirement(bad_agent, retire_trigger, pending_task_ids=["t9"], posterior={"alpha": 1.0, "beta": 15.0})
                retired_agent = apply_retirement(bad_agent)
                assert retired_agent.status == "retired"
                await publish("agent.retired", plan.event_payload)

            finally:
                router.close()
                await bus.close()

            return published_kinds

        kinds = asyncio.run(drive())
        assert kinds == ["agent.spawned", "agent.evolved", "agent.merged", "agent.retired"]

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
