"""Reward v2 (§6.9): the full formula, replacing reward.py's placeholder
once there's real lifecycle behaviour to shape. Every term is computed by
code, never by the LLM — the only subjective input is human feedback H.

    S = 1 if the verifier passed all accept checks else 0
    Q = capability-specific quality in [0, 1]
    T = 1 - min(1, latency / latency_budget)      # timeliness, success only
    C = min(1, tokens / token_budget) * 0.5 + min(1, gpu_s / gpu_budget) * 0.5
    r_base = 0.40*Q + 0.20*S + 0.20*S*T + 0.20*(1 - C)
    r = 0.5*r_base + 0.5*H   if human feedback H is present, else r_base
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RewardBreakdown:
    quality: float
    success: float
    timeliness: float
    cost: float
    r_base: float
    human_feedback: float | None
    reward: float


def compute_reward_v2(
    *,
    success: bool,
    quality: float,
    latency_s: float,
    latency_budget_s: float,
    tokens_used: int,
    token_budget: int,
    gpu_s: float,
    gpu_budget_s: float,
    human_feedback: float | None = None,
) -> RewardBreakdown:
    quality = max(0.0, min(1.0, quality))
    s = 1.0 if success else 0.0

    timeliness = 0.0
    if success and latency_budget_s > 0:
        timeliness = 1.0 - min(1.0, latency_s / latency_budget_s)

    token_frac = min(1.0, tokens_used / token_budget) if token_budget > 0 else 0.0
    gpu_frac = min(1.0, gpu_s / gpu_budget_s) if gpu_budget_s > 0 else 0.0
    cost = token_frac * 0.5 + gpu_frac * 0.5

    r_base = 0.40 * quality + 0.20 * s + 0.20 * s * timeliness + 0.20 * (1.0 - cost)

    reward = r_base
    if human_feedback is not None:
        h = max(0.0, min(1.0, human_feedback))
        reward = 0.5 * r_base + 0.5 * h

    return RewardBreakdown(
        quality=quality, success=s, timeliness=timeliness, cost=cost,
        r_base=r_base, human_feedback=human_feedback, reward=reward,
    )


def quality_run_experiment(achieved_value: float, target_value: float, tolerance: float) -> float:
    """§6.9's `run_experiment` quality: 1 minus the normalized gap to the
    paper's claim, clamped to [0, 1]."""
    if tolerance <= 0:
        return 1.0 if achieved_value >= target_value else 0.0
    gap = abs(achieved_value - target_value) / tolerance
    return max(0.0, 1.0 - min(1.0, gap))


def quality_implement(job_status: str, metric_present: bool) -> float:
    """§6.9's `implement` quality: smoke run passes (1) / runs but metric
    missing (0.5) / crashes (0)."""
    if job_status != "ok":
        return 0.0
    return 1.0 if metric_present else 0.5
