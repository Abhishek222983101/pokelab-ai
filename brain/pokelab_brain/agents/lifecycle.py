"""Lifecycle triggers (§6.8.1) — evaluated after every reward and on a
30 s tick. Every trigger is a closed-form check over data we already
have (Scout's gaps, Selector's Beta posteriors, a capability Jaccard
index) — an LLM is only ever called AFTER a trigger fires, to draft the
spawn/refine/merge content itself (spawn.py / refine.py / merge.py).
"""
from __future__ import annotations

from dataclasses import dataclass

from scipy import stats

from pokelab_labml.scout.coverage import CoverageGap
from pokelab_labml.selector.thompson import AgentArm


@dataclass
class SpawnTrigger:
    should_spawn: bool
    capability: str | None
    reason: str


def check_spawn(gaps: list[CoverageGap], min_requests: int = 2, min_coverage: float = 0.55) -> SpawnTrigger:
    """§6.8.1: Scout coverage of a required capability < 0.55 (here: the
    gap was requested at least `min_requests` times with zero coverage —
    the simplest honest reading of "coverage < threshold" when the
    capability has no coverage at all yet)."""
    candidates = [g for g in gaps if g.requested_count >= min_requests]
    if not candidates:
        return SpawnTrigger(False, None, "no capability gap requested often enough")
    worst = candidates[0]  # find_gaps already sorts by -requested_count
    return SpawnTrigger(
        True, worst.capability,
        f"{worst.capability} requested {worst.requested_count} times with 0.0 coverage (< {min_coverage})",
    )


@dataclass
class RefineTrigger:
    should_refine: bool
    reason: str


def check_refine(
    n_tasks: int, failure_rate: float, format_error_rate: float,
    min_tasks: int = 4, failure_threshold: float = 0.40, format_error_threshold: float = 0.20,
) -> RefineTrigger:
    """§6.8.1: an agent with >= 4 tasks and (failure rate >= 40% or
    format-error rate >= 20%)."""
    if n_tasks < min_tasks:
        return RefineTrigger(False, f"only {n_tasks} tasks, need >= {min_tasks}")
    if failure_rate >= failure_threshold:
        return RefineTrigger(True, f"failure rate {failure_rate:.0%} >= {failure_threshold:.0%}")
    if format_error_rate >= format_error_threshold:
        return RefineTrigger(True, f"format-error rate {format_error_rate:.0%} >= {format_error_threshold:.0%}")
    return RefineTrigger(False, "below both failure and format-error thresholds")


@dataclass
class MergeTrigger:
    should_merge: bool
    reason: str


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def check_merge(
    caps_a: list[str], caps_b: list[str],
    assignment_frac_a: float, assignment_frac_b: float,
    spec_cosine: float,
    min_jaccard: float = 0.6, min_cosine: float = 0.85, max_assignment_frac: float = 0.25,
) -> MergeTrigger:
    """§6.8.1: capability Jaccard >= 0.6, spec-embedding cosine >= 0.85,
    both agents under 25% of their capability's assignments recently."""
    jaccard = _jaccard(set(caps_a), set(caps_b))
    if jaccard < min_jaccard:
        return MergeTrigger(False, f"capability Jaccard {jaccard:.2f} < {min_jaccard}")
    if spec_cosine < min_cosine:
        return MergeTrigger(False, f"spec cosine {spec_cosine:.2f} < {min_cosine}")
    if assignment_frac_a >= max_assignment_frac or assignment_frac_b >= max_assignment_frac:
        return MergeTrigger(False, "at least one agent is still heavily assigned to this capability")
    return MergeTrigger(True, f"Jaccard {jaccard:.2f}, cosine {spec_cosine:.2f}, both under-assigned")


@dataclass
class RetireTrigger:
    should_retire: bool
    reason: str


def check_retire(
    arm: AgentArm, n_tasks: int, dominated_by: list[tuple[str, float]] | None = None,
    min_tasks: int = 5, low_reward_threshold: float = 0.35, low_reward_confidence: float = 0.9,
    dominance_confidence: float = 0.95,
) -> RetireTrigger:
    """§6.8.1: >= 5 tasks and P(mean reward < 0.35) >= 0.9 under the Beta
    posterior, OR dominated by another agent with P(mu_other > mu_this)
    >= 0.95 for all its capabilities. `dominated_by` is a precomputed list
    of (other_agent_id, p_dominates) the caller supplies — the Beta-vs-Beta
    dominance probability itself belongs with Selector, not duplicated here.
    """
    if n_tasks < min_tasks:
        return RetireTrigger(False, f"only {n_tasks} tasks, need >= {min_tasks}")

    p_low = float(stats.beta.cdf(low_reward_threshold, arm.alpha, arm.beta))
    if p_low >= low_reward_confidence:
        return RetireTrigger(True, f"P(mean reward < {low_reward_threshold}) = {p_low:.2f} >= {low_reward_confidence}")

    for other_id, p_dominates in dominated_by or []:
        if p_dominates >= dominance_confidence:
            return RetireTrigger(True, f"dominated by {other_id} (P={p_dominates:.2f} >= {dominance_confidence})")

    return RetireTrigger(False, f"P(mean reward < {low_reward_threshold}) = {p_low:.2f}, not dominated")
