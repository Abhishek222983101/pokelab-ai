"""The scheduler publishes the §2.7 binding-table causes as steps really run: who was chosen (and
from which candidates), whether the step passed its real checks, and the reward it earned. The game
moves agents to stations ONLY on these events, so their order and content are part of the contract.
"""
import asyncio

import numpy as np

from pokelab_brain.oak.planner import PlanStep
from pokelab_brain.oak.scheduler import run_plan
from pokelab_labml.selector.thompson import ThompsonSelector


def _run(steps, caps, configs):
    events: list[tuple[str, dict]] = []

    async def emit(kind, payload):
        events.append((kind, payload))

    result = asyncio.run(run_plan(steps, caps, ThompsonSelector(rng=np.random.default_rng(0)), configs, emit=emit, project_id="p1"))
    return result, events


def test_each_step_emits_started_then_finished_then_rewarded():
    steps = [
        PlanStep(id="s1", cap="paper_read", title="Read the paper", accept=[]),
        PlanStep(id="s2", cap="analyze", title="Compare", accept=[], after=["s1"]),
    ]
    caps = {"pikachu-1": ["paper_read"], "abra-1": ["analyze"]}
    result, events = _run(steps, caps, {})
    assert result.completed == ["s1", "s2"]
    kinds = [k for k, _ in events]
    assert kinds == [
        "agent.task_started", "agent.task_finished", "agent.rewarded",
        "agent.task_started", "agent.task_finished", "agent.rewarded",
    ]
    started = events[0][1]
    assert started["agent_id"] == "pikachu-1" and started["capability"] == "paper_read"
    assert started["title"] == "Read the paper" and started["project_id"] == "p1"
    assert started["candidates"] == [{"agent_id": "pikachu-1", "posterior_mean": 0.5}]
    rewarded = events[2][1]
    assert 0.0 <= rewarded["reward"] <= 1.0
    assert set(rewarded["breakdown"]) == {"quality", "success", "timeliness", "cost", "human"}


def test_a_failing_check_emits_task_failed_for_every_attempt():
    steps = [PlanStep(id="s1", cap="analyze", title="Needs an artifact", accept=["file_exists:missing.csv"])]
    result, events = _run(steps, {"abra-1": ["analyze"]}, {})
    assert result.failed == ["s1"]
    failed = [p for k, p in events if k == "agent.task_failed"]
    assert [p["attempt"] for p in failed] == [1, 2, 3]  # first try + 2 retries (MAX_RETRIES)
    assert not any(k == "agent.task_finished" for k, _ in events)


def test_no_emit_keeps_the_scheduler_silent():
    steps = [PlanStep(id="s1", cap="paper_read", title="Read", accept=[])]
    result = asyncio.run(run_plan(steps, {"a": ["paper_read"]}, ThompsonSelector(rng=np.random.default_rng(0)), {}))
    assert result.completed == ["s1"]
