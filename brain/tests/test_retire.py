from pokelab_brain.agents.lifecycle import RetireTrigger
from pokelab_brain.agents.retire import apply_retirement, plan_retirement
from pokelab_brain.agents.spec import AgentSpec


def test_plan_retirement_builds_a_complete_payload():
    agent = AgentSpec(id="bad-1", species="eevee", role="x", capabilities=["run_kit"], prompt_ref="x.md")
    trigger = RetireTrigger(should_retire=True, reason="P(mean reward < 0.35) = 0.95 >= 0.9")
    plan = plan_retirement(agent, trigger, pending_task_ids=["t1", "t2"], posterior={"alpha": 1.0, "beta": 11.0})
    assert plan.agent_id == "bad-1"
    assert plan.reassign_task_ids == ["t1", "t2"]
    assert plan.event_payload["reason"] == trigger.reason


def test_apply_retirement_returns_new_spec_with_status_retired():
    agent = AgentSpec(id="bad-1", species="eevee", role="x", capabilities=["run_kit"], prompt_ref="x.md", status="active")
    retired = apply_retirement(agent)
    assert retired.status == "retired"
    assert agent.status == "active"  # original untouched
    assert retired.id == agent.id
