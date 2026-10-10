"""Reward v1 (§6.11): how good was this result relative to the paper's
claim? A simple normalized gap — this is intentionally not sophisticated
yet (no shaping, no credit assignment across multi-step plans); it exists
so Selector/Scout (P5) have *something* real to learn from, and gets
replaced by reward v2 in P6.5 once there's lifecycle behaviour to shape.
"""
from __future__ import annotations

from pokelab_brain.papers.packs import PaperPack


def compute_reward(achieved_value: float | None, pack: PaperPack) -> float:
    """1.0 if we met or beat the paper's primary claim, scaled down
    linearly toward 0.0 the further short we fell. None (job failed /
    metric missing) scores 0.0."""
    if achieved_value is None or not pack.claims:
        return 0.0
    target = pack.claims[0].value
    if target <= 0:
        return 0.0
    if achieved_value >= target:
        return 1.0
    return max(0.0, achieved_value / target)
