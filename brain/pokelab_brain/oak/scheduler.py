"""The scheduler (§6.2.4): advances a plan DAG. Ready steps (deps done,
not started) get an agent via the Selector; `run_experiment` steps go
through the REAL run_kit tool (a real job, through the real labd warm
pool); every other capability is dispatched generically — this scheduler
doesn't know what any capability DOES, only how to sequence, verify and
score it. On failure: retry <= 2 (re-selection allowed), then escalate.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

from pokelab_brain.agents.tools.jobs import ToolContext, run_kit
from pokelab_brain.agents.verifiers import run_all_checks
from pokelab_brain.oak.planner import PlanStep, ready_steps
from pokelab_brain.reward_v2 import compute_reward_v2
from pokelab_labml.selector.thompson import ThompsonSelector

MAX_RETRIES = 2

StepExecutor = Callable[[PlanStep, dict[str, Any]], Awaitable[dict[str, Any]]]

# (kind, payload) -> None: the same publish shape the lifecycle loop uses (bus-backed in production)
EmitFn = Callable[[str, dict[str, Any]], Awaitable[None]]


@dataclass
class StepOutcome:
    step_id: str
    status: str  # "completed" | "failed" | "escalated"
    attempts: int
    final: dict[str, Any] = field(default_factory=dict)
    agent_id: str | None = None
    reward: float | None = None


@dataclass
class SchedulerResult:
    completed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    escalated: list[str] = field(default_factory=list)
    outcomes: dict[str, StepOutcome] = field(default_factory=dict)


async def _default_run_experiment_executor(step: PlanStep, step_config: dict[str, Any], tool_ctx: ToolContext) -> dict[str, Any]:
    kit = step_config.get("kit", "smoke")
    config = step_config.get("config", {})
    return await run_kit({"kit": kit, "config": config}, tool_ctx)


async def _trivial_executor(step: PlanStep, step_config: dict[str, Any]) -> dict[str, Any]:
    """Every capability this scheduler doesn't have a real tool for yet
    (paper_read, analyze, report_write, ...) completes with whatever
    static "final" the step's own config already carries — honest about
    what's wired (run_experiment, for real) vs. what's a placeholder."""
    return {"status": "ok", "final": step_config.get("final", {})}


async def run_plan(
    steps: list[PlanStep],
    agent_capabilities: dict[str, list[str]],
    selector: ThompsonSelector,
    step_configs: dict[str, dict[str, Any]],
    tool_ctx: ToolContext | None = None,
    max_parallel: int = 4,
    on_capability_gap: Callable[[str], Awaitable[Any]] | None = None,
    on_task_outcome: Callable[[str, bool, float], Awaitable[None]] | None = None,
    emit: EmitFn | None = None,
    project_id: str | None = None,
    executors: dict[str, StepExecutor] | None = None,
) -> SchedulerResult:
    """`on_capability_gap` and `on_task_outcome` are the live lifecycle
    loop's hooks (§6.1: evaluated "after each reward"). Passing neither
    keeps this exactly the P4.7 scheduler; passing both is what turns a
    one-off plan run into a team that spawns/retires in response to what
    actually happened — no simulation, no hand-invoked trigger.

    `emit` publishes the §2.7 binding-table causes as they really happen:
    `agent.task_started` (who Oak chose and from which candidates, with
    their posterior means), `agent.task_finished` / `agent.task_failed`,
    and `agent.rewarded` with the full reward breakdown. Without it the
    scheduler behaves exactly as before."""
    result = SchedulerResult()
    attempts: dict[str, int] = {}
    semaphore = asyncio.Semaphore(max_parallel)

    async def run_one(step: PlanStep) -> None:
        async with semaphore:
            attempts[step.id] = attempts.get(step.id, 0) + 1
            candidates = [a for a, caps in agent_capabilities.items() if step.cap in caps]
            if not candidates and on_capability_gap is not None:
                new_agent = await on_capability_gap(step.cap)
                if new_agent is not None:
                    agent_capabilities[new_agent.id] = new_agent.capabilities
                    candidates = [new_agent.id]
            if not candidates:
                result.outcomes[step.id] = StepOutcome(step.id, "escalated", attempts[step.id])
                result.escalated.append(step.id)
                return

            agent_id = selector.select(candidates)
            step_config = step_configs.get(step.id, {})
            base = {"agent_id": agent_id, "step_id": step.id, "capability": step.cap, "project_id": project_id}
            if emit is not None:
                await emit("agent.task_started", {
                    **base, "title": step.title, "attempt": attempts[step.id],
                    "kit": step_config.get("kit") if step.cap == "run_experiment" else None,
                    "candidates": [{"agent_id": c, "posterior_mean": round(selector.mean_estimate(c), 4)} for c in candidates],
                })

            executor = (executors or {}).get(step.cap)
            if executor is not None:
                # a real per-capability executor (oak/executors.py): it returns its own context —
                # jobs it ran (keyed by the labels its accept checks name), artifacts it wrote, etc.
                tool_result = await executor(step, step_config)
            elif step.cap == "run_experiment" and tool_ctx is not None:
                tool_result = await _default_run_experiment_executor(step, step_config, tool_ctx)
            else:
                tool_result = await _trivial_executor(step, step_config)
            job_status = tool_result.get("status")
            final = tool_result.get("final") or {}

            context = {
                "jobs": {step.id: {"status": job_status}, **tool_result.get("jobs", {})},
                "final": final,
                "artifacts": {**step_config.get("artifacts", {}), **tool_result.get("artifacts", {})},
                "report_text": tool_result.get("report_text", step_config.get("report_text", "")),
                **{k: tool_result[k] for k in ("kit", "known_kits", "claim_guard_passed") if k in tool_result},
            }
            passed, _check_results = run_all_checks(step.accept, context)

            reward_breakdown = compute_reward_v2(
                success=passed, quality=1.0 if passed else 0.0,
                latency_s=1.0, latency_budget_s=max(step.budget.max_gpu_s, 1.0),
                tokens_used=0, token_budget=max(step.budget.max_tokens, 1),
                gpu_s=0.0, gpu_budget_s=max(step.budget.max_gpu_s, 1.0),
            )
            selector.record_outcome(agent_id, reward_breakdown.reward)
            if emit is not None:
                job_id = tool_result.get("job_id") if isinstance(tool_result, dict) else None
                await emit("agent.task_finished" if passed else "agent.task_failed", {
                    **base, "attempt": attempts[step.id], "job_id": job_id, "status": job_status,
                    "checks_passed": passed,
                })
                await emit("agent.rewarded", {
                    **base, "reward": round(reward_breakdown.reward, 4),
                    "breakdown": {"quality": reward_breakdown.quality, "success": reward_breakdown.success,
                                  "timeliness": reward_breakdown.timeliness, "cost": reward_breakdown.cost,
                                  "human": reward_breakdown.human_feedback},
                    "posterior_mean": round(selector.mean_estimate(agent_id), 4),
                })
            if on_task_outcome is not None:
                await on_task_outcome(agent_id, passed, reward_breakdown.reward)

            if passed:
                result.outcomes[step.id] = StepOutcome(step.id, "completed", attempts[step.id], final, agent_id, reward_breakdown.reward)
                result.completed.append(step.id)
            elif attempts[step.id] <= MAX_RETRIES:
                await run_one(step)  # retry with re-selection
            else:
                result.outcomes[step.id] = StepOutcome(step.id, "failed", attempts[step.id], final, agent_id, reward_breakdown.reward)
                result.failed.append(step.id)

    completed_ids: set[str] = set()
    started_ids: set[str] = set()
    remaining = {s.id: s for s in steps}

    while remaining:
        ready = ready_steps(list(remaining.values()), completed_ids, started_ids)
        if not ready:
            break  # nothing more can proceed (either done, or blocked by a failure/escalation upstream)

        for step in ready:
            started_ids.add(step.id)
        await asyncio.gather(*(run_one(step) for step in ready))

        for step in ready:
            completed_ids.add(step.id)  # "done" for dependency purposes whether it passed or not
            remaining.pop(step.id, None)

    return result
