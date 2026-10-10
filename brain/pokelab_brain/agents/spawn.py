"""Spawn (§6.8.2): drafts a brand-new AgentSpec for a coverage gap, via a
real LLM call (ADAS-style — the prompt includes the gap, nearby agents as
"stepping stones", and past spawn outcomes). Output is parsed and
validated as a real AgentSpec; a malformed draft is a hard failure here
(spawning a broken agent is worse than not spawning), not something we
silently patch.
"""
from __future__ import annotations

from pokelab_brain.agents.spec import AgentSpec
from pokelab_brain.llm.jsonio import extract_json
from pokelab_brain.llm.router import LlmRouter

_DRAFT_PROMPT = """You are drafting a new specialist research agent for a capability gap.

Gap (capability no active agent covers): {capability}

Nearby agents (stepping stones — reuse what's relevant from these):
{nearest_agents}

Past spawn attempts for similar gaps and their outcomes:
{past_spawns}

Reply with ONLY a JSON object (no prose, no code fence) shaped exactly like:
{{"species": "eevee", "role": "<short role name>", "capabilities": ["{capability}", ...other relevant ones],
  "prompt_summary": "<2-3 sentences describing what this agent's system prompt should emphasize>"}}
"""


def draft_spec(
    router: LlmRouter,
    route: list[str],
    capability: str,
    nearest_agents: list[AgentSpec],
    past_spawns: list[dict] | None = None,
    new_id: str | None = None,
    **llm_kwargs,
) -> tuple[AgentSpec, str]:
    """Returns (the new AgentSpec, the prompt_summary to render into its
    actual system prompt file — writing that file is the caller's job,
    since it's a filesystem concern, not a drafting one)."""
    nearest_text = "\n".join(f"- {a.id} ({a.role}): {a.capabilities}" for a in nearest_agents) or "(none yet)"
    past_text = "\n".join(
        f"- gap={p.get('capability')} outcome={p.get('outcome')}" for p in (past_spawns or [])
    ) or "(no past spawns)"

    prompt = _DRAFT_PROMPT.format(capability=capability, nearest_agents=nearest_text, past_spawns=past_text)
    result = router.complete(messages=[{"role": "user", "content": prompt}], route=route, max_tokens=500, **llm_kwargs)

    parsed = extract_json(result.content)
    if not isinstance(parsed, dict) or "capabilities" not in parsed:
        raise ValueError(f"spawn draft did not return a valid spec JSON: {result.content!r}")

    agent_id = new_id or f"{parsed.get('species', 'eevee')}-{abs(hash(capability)) % 10000}"
    spec = AgentSpec(
        id=agent_id,
        species=parsed.get("species", "eevee"),
        role=parsed.get("role", capability),
        capabilities=list(parsed.get("capabilities", [capability])),
        prompt_ref=f"{agent_id}.md",  # the caller writes this file from prompt_summary
        status="proposed",
        generation=0,
    )
    return spec, str(parsed.get("prompt_summary", ""))
