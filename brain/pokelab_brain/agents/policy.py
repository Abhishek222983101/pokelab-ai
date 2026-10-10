"""Policy & approvals (§6.8, config `lab.toml [autonomy]`): some lifecycle
actions need a human nod before they happen; others are safe to
auto-approve. This is intentionally tiny — the interesting logic is the
trigger math (lifecycle.py) and the drafting (spawn/refine/merge.py);
this module just gates "does this action fire immediately, or does it
wait."
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class ApprovalPolicy:
    require_approval_for: set[str] = field(default_factory=lambda: {"retire", "merge"})
    auto_approve: set[str] = field(default_factory=lambda: {"spawn_shadow"})
    default_timeout_s: float = 300.0  # §11.2: an expired approval gets the policy default

    def needs_approval(self, action: str) -> bool:
        if action in self.auto_approve:
            return False
        return action in self.require_approval_for


@dataclass
class PendingApproval:
    approval_id: str
    action: str
    payload: dict
    requested_at: float
    status: str = "pending"  # pending | approved | rejected | expired
    note: str | None = None

    def is_expired(self, timeout_s: float, now: float | None = None) -> bool:
        now = now if now is not None else time.monotonic()
        return self.status == "pending" and (now - self.requested_at) > timeout_s


class ApprovalStore:
    """In-memory; every transition is also published as a `human.*` event
    by the caller (this class holds no bus/store reference on purpose —
    event publishing stays the caller's job, this is pure bookkeeping)."""

    def __init__(self, policy: ApprovalPolicy | None = None):
        self.policy = policy or ApprovalPolicy()
        self._pending: dict[str, PendingApproval] = {}

    def request(self, approval_id: str, action: str, payload: dict) -> PendingApproval:
        pa = PendingApproval(approval_id=approval_id, action=action, payload=payload, requested_at=time.monotonic())
        self._pending[approval_id] = pa
        return pa

    def decide(self, approval_id: str, approved: bool, note: str | None = None) -> PendingApproval:
        pa = self._pending[approval_id]
        pa.status = "approved" if approved else "rejected"
        pa.note = note
        return pa

    def expire_overdue(self, default_approved: bool = False) -> list[PendingApproval]:
        """§11.2: 'expired ones get the policy default.' Returns every
        approval that just transitioned out of `pending`."""
        expired = []
        for pa in self._pending.values():
            if pa.is_expired(self.policy.default_timeout_s):
                pa.status = "approved" if default_approved else "rejected"
                pa.note = f"expired after {self.policy.default_timeout_s}s, policy default applied"
                expired.append(pa)
        return expired

    def get(self, approval_id: str) -> PendingApproval:
        return self._pending[approval_id]
