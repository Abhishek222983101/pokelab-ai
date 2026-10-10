"""Refine — GEPA-lite (§6.8.3, Agrawal et al. ICLR 2026): a real LLM
reflection call rewrites an agent's system prompt from its own failed/
succeeded traces, then a shadow evaluation decides whether to promote it.

The reflection call is real (this module). Shadow evaluation's *inputs*
(replaying recorded tasks against the new prompt) need the task-replay
infra from P4.6/P4.7, which isn't built yet — `decide_promotion` below is
the real, tested decision rule; wiring it to live replay is tracked in
docs/PROGRESS.md same as P4.6/P4.7.
"""
from __future__ import annotations

from dataclasses import dataclass

from pokelab_brain.llm.router import LlmRouter

_REFLECT_PROMPT = """You are improving your own system prompt based on how you performed.

Your CURRENT system prompt:
---
{current_prompt}
---

Your last {n_traces} task traces (success/failure, and why):
{traces}

Diagnose what's going wrong (or confirm what's working) and rewrite your
system prompt to do better. Keep everything that worked. Reply with ONLY
the new system prompt text — no JSON, no commentary, no code fence.
"""


def reflect_and_rewrite(
    router: LlmRouter,
    route: list[str],
    current_prompt: str,
    traces: list[dict],
    **llm_kwargs,
) -> str:
    traces_text = "\n".join(
        f"- task={t.get('task')} success={t.get('success')} reward={t.get('reward'):.2f} "
        f"medic_class={t.get('medic_class', 'none')}"
        for t in traces[-8:]  # §6.8.3 step 1: last <= 8 traces
    ) or "(no traces yet)"

    prompt = _REFLECT_PROMPT.format(current_prompt=current_prompt, n_traces=len(traces[-8:]), traces=traces_text)
    result = router.complete(messages=[{"role": "user", "content": prompt}], route=route, max_tokens=800, **llm_kwargs)
    return result.content.strip()


@dataclass
class PromotionDecision:
    promote: bool
    mean_delta: float
    max_regression: float
    reason: str


def decide_promotion(
    old_rewards: list[float], new_rewards: list[float],
    min_mean_improvement: float = 0.05, max_allowed_regression: float = 0.10,
) -> PromotionDecision:
    """§6.8.3 step 4: promote only if mean reward improves by >= 0.05 AND
    no single task regresses by > 0.1 (Pareto-style, not just on average —
    a prompt that helps most tasks but badly breaks one is rejected)."""
    assert len(old_rewards) == len(new_rewards) and old_rewards, "need paired, non-empty reward lists"

    deltas = [new - old for old, new in zip(old_rewards, new_rewards)]
    mean_delta = sum(deltas) / len(deltas)
    max_regression = -min(deltas)  # positive number = how much the worst task got worse

    if mean_delta < min_mean_improvement:
        return PromotionDecision(False, mean_delta, max_regression, f"mean improvement {mean_delta:.3f} < {min_mean_improvement}")
    if max_regression > max_allowed_regression:
        return PromotionDecision(False, mean_delta, max_regression, f"a task regressed by {max_regression:.3f} > {max_allowed_regression}")
    return PromotionDecision(True, mean_delta, max_regression, f"mean +{mean_delta:.3f}, worst regression {max_regression:.3f} — promoted")
