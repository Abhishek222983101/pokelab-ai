"""Compute Router (§7.7): local GPU vs Kaggle/Colab. A small, explicit
rule set beats an LLM here because the inputs are a handful of numbers
(estimated runtime, queue depth, local VRAM headroom) and the decision
needs to be instant and auditable, not reasoned about in prose.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PlacementDecision:
    target: str  # "local" | "kaggle" | "colab"
    reason: str


def choose_placement(
    estimated_wall_s: float,
    local_free_slots: int,
    local_vram_headroom_mib: float,
    required_vram_mib: float,
    remote_available: bool = True,
) -> PlacementDecision:
    if local_free_slots > 0 and local_vram_headroom_mib >= required_vram_mib:
        return PlacementDecision("local", "a warm local slot has enough free VRAM")

    if not remote_available:
        return PlacementDecision("local", "no remote slots configured; queueing locally despite contention")

    # [MEASURED, §5.5.1]: a 3rd concurrent local job on this laptop REDUCES
    # throughput (0.96x) — past 2 concurrent, remote is strictly better,
    # not just "available."
    if estimated_wall_s > 60.0:
        return PlacementDecision("kaggle", "long-running job with no local slot free; Kaggle gives 30h/week T4")

    return PlacementDecision("colab", "short job with no local slot free; Colab's quicker cold start wins")
