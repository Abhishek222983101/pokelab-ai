"""AgentSpec: an agent as data (§6.3), not a class — spawning, refining,
merging and retiring are all just writes to this struct, recorded as
events, never a new code path. `load_roster` reads the seed agents from
config/roster.toml.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import tomllib
from pydantic import BaseModel, Field


class AgentSpec(BaseModel):
    id: str
    species: str
    role: str
    capabilities: list[str] = Field(default_factory=list)
    prompt_ref: str
    status: str = "active"  # active | shadow | retired
    parent_ids: list[str] = Field(default_factory=list)  # non-empty after a merge
    generation: int = 0  # bumped on refine/evolve
    created_seq: int | None = None


def load_roster(roster_toml: str | Path) -> list[AgentSpec]:
    with open(roster_toml, "rb") as f:
        data: dict[str, Any] = tomllib.load(f)
    agents = data.get("agent", [])
    specs = []
    for i, a in enumerate(agents):
        specs.append(
            AgentSpec(
                id=a.get("id", f"{a['species']}-{i}"),
                species=a["species"],
                role=a["role"],
                capabilities=a.get("capabilities", []),
                prompt_ref=a["prompt_ref"],
            )
        )
    return specs


def load_prompt(prompts_dir: str | Path, prompt_ref: str) -> str:
    path = Path(prompts_dir) / prompt_ref
    if not path.exists():
        raise FileNotFoundError(f"prompt file not found: {path}")
    return path.read_text()


def render_prompt(template: str, tool_list: str, task: str) -> str:
    """Plain `.replace()`, not `.format()` — role prompts are full of
    literal JSON braces (the protocol examples), which `.format()` would
    try to parse as its own placeholders."""
    return template.replace("__TOOL_LIST__", tool_list).replace("__TASK__", task)
