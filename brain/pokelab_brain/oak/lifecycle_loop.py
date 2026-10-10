"""The live lifecycle loop (§6.1: `oak.lifecycle` fires "after each
reward + 30s tick"). This is the piece that makes the agent team
actually DYNAMIC — not a script that calls spawn/refine/merge/retire by
hand, but something that watches real task outcomes as they happen and
decides on its own.

Scoped honestly: SPAWN and RETIRE fire from data this process already
has for real (a live capability gap, a live Beta posterior). REFINE and
MERGE still need the shadow-eval replay infra from P4.6/P4.7 to decide
safely in the moment — until that exists, this loop logs them as
*recommended* (so a human or a later pass can act on them) rather than
mutating the roster on unverified LLM output.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from pokelab_brain.agents.lifecycle import check_merge, check_refine, check_retire
from pokelab_brain.agents.spawn import draft_spec
from pokelab_brain.agents.spec import AgentSpec
from pokelab_brain.agents.retire import apply_retirement, plan_retirement
from pokelab_brain.llm.router import LlmRouter
from pokelab_labml.scout.coverage import find_gaps, should_spawn
from pokelab_labml.selector.thompson import ThompsonSelector

logger = logging.getLogger(__name__)

PublishFn = Callable[[str, dict[str, Any]], Awaitable[None]]


@dataclass
class LifecycleEvent:
    kind: str  # "agent.spawned" | "agent.retired" | "agent.refine_recommended" | "agent.merge_recommended"
    payload: dict[str, Any]


@dataclass
class LifecycleLoop:
    roster: dict[str, AgentSpec]
    selector: ThompsonSelector
    router: LlmRouter
    route: list[str]
    publish: PublishFn
    task_counts: dict[str, int] = field(default_factory=dict)
    requested_capabilities: list[str] = field(default_factory=list)
    llm_kwargs: dict[str, Any] = field(default_factory=dict)

    def active_capabilities(self) -> dict[str, list[str]]:
        return {aid: a.capabilities for aid, a in self.roster.items() if a.status == "active"}

    async def on_capability_gap(self, cap: str) -> AgentSpec | None:
        """Called by the scheduler the moment a step has NO candidate
        agent — a real, live coverage gap, not a simulated one. §6.8.1's
        spawn trigger (repeat-requested, uncovered) decides whether to
        actually draft a new agent."""
        self.requested_capabilities.append(cap)
        gaps = find_gaps(self.requested_capabilities, self.active_capabilities())
        to_spawn = should_spawn(gaps, min_requests_to_act=2)
        if cap not in to_spawn:
            return None

        nearest = list(self.roster.values())[:3]
        new_id = f"eevee-{cap}-{len(self.roster) + 1}"
        try:
            spec, prompt_summary = draft_spec(
                self.router, self.route, cap, nearest, past_spawns=[], new_id=new_id, **self.llm_kwargs,
            )
        except (ValueError, KeyError) as e:
            logger.warning("spawn draft failed for gap %r: %s", cap, e)
            return None

        spec = spec.model_copy(update={"status": "active"})
        self.roster[spec.id] = spec
        await self.publish("agent.spawned", {
            "agent_id": spec.id, "capability": cap, "prompt_summary": prompt_summary,
            "reason": f"live coverage gap: {cap!r} requested with no active agent covering it",
        })
        return spec

    async def on_task_outcome(self, agent_id: str, success: bool, reward: float) -> None:
        """Called after every real step completes — §6.1's cadence."""
        self.task_counts[agent_id] = self.task_counts.get(agent_id, 0) + 1
        n_tasks = self.task_counts[agent_id]

        arm = self.selector.ensure_arm(agent_id)
        retire_trigger = check_retire(arm, n_tasks)
        if retire_trigger.should_retire and agent_id in self.roster:
            agent = self.roster[agent_id]
            if agent.status == "active":
                plan = plan_retirement(agent, retire_trigger, pending_task_ids=[], posterior={"alpha": arm.alpha, "beta": arm.beta})
                self.roster[agent_id] = apply_retirement(agent)
                await self.publish("agent.retired", plan.event_payload)

        recent_failure_rate = 1.0 - self.selector.mean_estimate(agent_id)
        refine_trigger = check_refine(n_tasks, failure_rate=recent_failure_rate, format_error_rate=0.0)
        if refine_trigger.should_refine:
            await self.publish("agent.refine_recommended", {
                "agent_id": agent_id, "reason": refine_trigger.reason,
                "note": "shadow-eval replay infra not built — a human or a later pass decides whether to act",
            })

    async def check_merge_candidates(self) -> None:
        """§6.1's 30s-tick half — merge needs comparing EVERY active pair,
        so it's a periodic sweep rather than an after-every-reward check."""
        active = [a for a in self.roster.values() if a.status == "active"]
        for i, a in enumerate(active):
            for b in active[i + 1 :]:
                trigger = check_merge(
                    a.capabilities, b.capabilities,
                    assignment_frac_a=self._assignment_frac(a.id), assignment_frac_b=self._assignment_frac(b.id),
                    spec_cosine=0.9,  # real embedding cosine needs fastembed — tracked gap, see P7.3
                )
                if trigger.should_merge:
                    await self.publish("agent.merge_recommended", {
                        "parents": [a.id, b.id], "reason": trigger.reason,
                        "note": "shadow-eval replay infra not built — a human or a later pass decides whether to act",
                    })

    def _assignment_frac(self, agent_id: str) -> float:
        total = sum(self.task_counts.values()) or 1
        return self.task_counts.get(agent_id, 0) / total
