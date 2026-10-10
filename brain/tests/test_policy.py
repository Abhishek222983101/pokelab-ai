import time

from pokelab_brain.agents.policy import ApprovalPolicy, ApprovalStore


def test_auto_approve_actions_need_no_approval():
    policy = ApprovalPolicy()
    assert not policy.needs_approval("spawn_shadow")


def test_configured_actions_need_approval():
    policy = ApprovalPolicy()
    assert policy.needs_approval("retire")
    assert policy.needs_approval("merge")


def test_request_and_approve_flow():
    store = ApprovalStore()
    store.request("a1", "retire", {"agent_id": "x"})
    decided = store.decide("a1", approved=True, note="fine by me")
    assert decided.status == "approved"
    assert store.get("a1").status == "approved"


def test_request_and_reject_flow():
    store = ApprovalStore()
    store.request("a1", "retire", {"agent_id": "x"})
    decided = store.decide("a1", approved=False, note="not yet")
    assert decided.status == "rejected"


def test_expired_approval_gets_policy_default():
    policy = ApprovalPolicy(default_timeout_s=0.05)
    store = ApprovalStore(policy)
    store.request("a1", "merge", {})
    time.sleep(0.07)
    expired = store.expire_overdue(default_approved=False)
    assert len(expired) == 1
    assert expired[0].status == "rejected"
    assert "expired" in expired[0].note


def test_non_expired_approval_is_left_pending():
    policy = ApprovalPolicy(default_timeout_s=10.0)
    store = ApprovalStore(policy)
    store.request("a1", "merge", {})
    expired = store.expire_overdue()
    assert expired == []
    assert store.get("a1").status == "pending"
