"""AgentSpec (§6.4.2) and the lifecycle event payloads actually emitted
by oak/lifecycle_loop.py — kept in sync by hand with
brain/pokelab_brain/agents/spec.py, which is pydantic too; this is the
language-neutral statement of the same shape.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class AgentSpec(BaseModel):
    id: str
    species: str
    role: str
    capabilities: list[str] = Field(default_factory=list)
    prompt_ref: str
    status: str = "active"
    parent_ids: list[str] = Field(default_factory=list)
    generation: int = 0
    created_seq: int | None = None


class AgentSpawnedPayload(BaseModel):
    agent_id: str
    capability: str
    prompt_summary: str
    reason: str


class AgentRetiredPayload(BaseModel):
    agent_id: str
    reason: str
    posterior: dict
    last_tasks: list[str]
