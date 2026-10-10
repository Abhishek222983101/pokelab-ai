"""Retire (§6.8.5): once lifecycle.check_retire fires, this just builds
the retirement event payload and the reassignment list — the agent's
history is never deleted (it keeps feeding Scout/Selector priors, §6.8.5
"stays in Bill's PC"), only its `status` changes.
"""
from __future__ import annotations

from dataclasses import dataclass

from pokelab_brain.agents.lifecycle import RetireTrigger
from pokelab_brain.agents.spec import AgentSpec


@dataclass
class RetirementPlan:
    agent_id: str
    reason: str
    reassign_task_ids: list[str]
    event_payload: dict


def plan_retirement(agent: AgentSpec, trigger: RetireTrigger, pending_task_ids: list[str], posterior: dict) -> RetirementPlan:
    assert trigger.should_retire, "plan_retirement called without a firing trigger"
    return RetirementPlan(
        agent_id=agent.id,
        reason=trigger.reason,
        reassign_task_ids=list(pending_task_ids),
        event_payload={
            "agent_id": agent.id,
            "reason": trigger.reason,
            "posterior": posterior,
            "last_tasks": pending_task_ids[-5:],
        },
    )


def apply_retirement(agent: AgentSpec) -> AgentSpec:
    """Returns a NEW AgentSpec with status flipped — AgentSpec is treated
    as immutable data (§6.4.2), every lifecycle transition is a fresh
    value, never a mutation, so the event log and the in-memory copy can
    never silently diverge."""
    return agent.model_copy(update={"status": "retired"})
