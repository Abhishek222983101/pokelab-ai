"""Commands over `/internal/brain` (§5.4.3) — only the ones actually
implemented in lab-gateway/src/ws.rs today. The architecture doc
describes a larger set (human.* commands routed through labd); those
aren't wired up yet (see docs/PROGRESS.md P10.4) and are deliberately
left out here rather than specified ahead of the code.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from pokelab_contracts.envelope import NewEvent


class PublishCommand(BaseModel):
    type: Literal["publish"] = "publish"
    events: list[NewEvent]
    req: str


class JobSubmitCommand(BaseModel):
    type: Literal["job_submit"] = "job_submit"
    req: str
    kit: str
    config: dict[str, Any]
    project: str | None = None


class SubscribeCommand(BaseModel):
    type: Literal["subscribe"] = "subscribe"
    since: int = 0


class HelloCommand(BaseModel):
    """The /api/ws client-facing equivalent of subscribe (§5.4.2)."""
    type: Literal["hello"] = "hello"
    since: int = 0
