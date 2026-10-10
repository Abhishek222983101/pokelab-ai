"""Merge (§6.8.4): a real LLM synthesis call unions two similar, under-
used agents into one child spec, keeping each parent's best-scoring
instructions. Acceptance uses the same shadow-eval shape as refine.py —
accept if the merged agent's shadow performance is >= max(parent means)
- 0.03.
"""
from __future__ import annotations

from dataclasses import dataclass

from pokelab_brain.agents.spec import AgentSpec
from pokelab_brain.llm.jsonio import extract_json
from pokelab_brain.llm.router import LlmRouter

_SYNTHESIS_PROMPT = """Two agents are similar enough to merge into one specialist.

Agent A ({id_a}, role={role_a}): capabilities={caps_a}
Agent A's best-scoring prompt instructions:
{prompt_a}

Agent B ({id_b}, role={role_b}): capabilities={caps_b}
Agent B's best-scoring prompt instructions:
{prompt_b}

Write a merged specification. Reply with ONLY a JSON object (no prose,
no code fence) shaped exactly like:
{{"role": "<short role name>", "capabilities": [<union of both agents' capabilities>],
  "prompt_summary": "<2-4 sentences merging the best of both agents' instructions>"}}
"""


def synthesize(
    router: LlmRouter,
    route: list[str],
    agent_a: AgentSpec,
    prompt_a: str,
    agent_b: AgentSpec,
    prompt_b: str,
    new_id: str,
    **llm_kwargs,
) -> tuple[AgentSpec, str]:
    prompt = _SYNTHESIS_PROMPT.format(
        id_a=agent_a.id, role_a=agent_a.role, caps_a=agent_a.capabilities, prompt_a=prompt_a,
        id_b=agent_b.id, role_b=agent_b.role, caps_b=agent_b.capabilities, prompt_b=prompt_b,
    )
    result = router.complete(messages=[{"role": "user", "content": prompt}], route=route, max_tokens=500, **llm_kwargs)

    parsed = extract_json(result.content)
    if not isinstance(parsed, dict) or "capabilities" not in parsed:
        raise ValueError(f"merge synthesis did not return a valid spec JSON: {result.content!r}")

    union_caps = sorted(set(agent_a.capabilities) | set(agent_b.capabilities) | set(parsed.get("capabilities", [])))
    species = agent_a.species  # caller resolves this to "the higher-reward parent's line" before calling, if needed
    spec = AgentSpec(
        id=new_id,
        species=species,
        role=parsed.get("role", f"{agent_a.role}+{agent_b.role}"),
        capabilities=union_caps,
        prompt_ref=f"{new_id}.md",
        status="proposed",
        parent_ids=[agent_a.id, agent_b.id],
        generation=max(agent_a.generation, agent_b.generation) + 1,
    )
    return spec, str(parsed.get("prompt_summary", ""))


@dataclass
class MergeDecision:
    accept: bool
    merged_mean: float
    best_parent_mean: float
    reason: str


def decide_merge(merged_rewards: list[float], parent_a_mean: float, parent_b_mean: float, tolerance: float = 0.03) -> MergeDecision:
    """§6.8.4: accept if merged shadow performance >= max(parent means) - 0.03."""
    assert merged_rewards, "need at least one shadow-eval reward for the merged agent"
    merged_mean = sum(merged_rewards) / len(merged_rewards)
    best_parent = max(parent_a_mean, parent_b_mean)
    if merged_mean >= best_parent - tolerance:
        return MergeDecision(True, merged_mean, best_parent, f"merged mean {merged_mean:.3f} >= {best_parent - tolerance:.3f}")
    return MergeDecision(False, merged_mean, best_parent, f"merged mean {merged_mean:.3f} < {best_parent - tolerance:.3f}")
