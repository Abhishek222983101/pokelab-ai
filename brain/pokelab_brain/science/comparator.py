"""Comparator v1 (§7.1): did our reproduction match the paper? A plain,
auditable comparison — v2 (P7.1) adds the richer diagnostics (per-metric
breakdowns, failure classification); this just answers the one question
a judge will actually ask: "did it work, and by how much."
"""
from __future__ import annotations

from dataclasses import dataclass

from pokelab_brain.papers.packs import PaperPack
from pokelab_brain.reward import compute_reward


@dataclass
class ComparisonReport:
    matched: bool
    achieved_value: float | None
    target_value: float
    target_condition: str | None
    gap: float
    reward: float
    narrative: str


def compare(final_result: dict | None, metric_key: str, pack: PaperPack) -> ComparisonReport:
    achieved = None
    if final_result is not None:
        achieved = final_result.get(metric_key)

    target = pack.claims[0] if pack.claims else None
    target_value = target.value if target else 0.0
    gap = (target_value - achieved) if achieved is not None else target_value
    matched = achieved is not None and achieved >= target_value
    reward = compute_reward(achieved, pack)

    if achieved is None:
        narrative = f"No {metric_key} was produced — the run did not complete cleanly."
    elif matched:
        narrative = (
            f"Reproduced: {metric_key}={achieved:.4f} meets the paper's claim of "
            f"{target_value:.4f}{f' ({target.condition})' if target and target.condition else ''}."
        )
    else:
        narrative = (
            f"Short of the paper's claim: {metric_key}={achieved:.4f} vs target {target_value:.4f} "
            f"(gap {gap:.4f})."
        )

    return ComparisonReport(
        matched=matched,
        achieved_value=achieved,
        target_value=target_value,
        target_condition=target.condition if target else None,
        gap=gap,
        reward=reward,
        narrative=narrative,
    )
