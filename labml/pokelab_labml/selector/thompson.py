"""Selector (§7.2): which agent gets the next task. Thompson sampling
over a Beta(success, failure) per agent — this is the textbook case for
"an LLM would be worse here": an LLM can't maintain calibrated per-agent
win-rates across hundreds of past assignments, a few floats can.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class AgentArm:
    agent_id: str
    alpha: float = 1.0  # prior successes + 1
    beta: float = 1.0  # prior failures + 1

    def update(self, reward: float) -> None:
        """`reward` in [0, 1] (the same scale as reward.py's output) is
        treated as a soft Bernoulli trial: it adds `reward` to alpha and
        `1 - reward` to beta, so a 0.7 result nudges both, not just one."""
        self.alpha += reward
        self.beta += 1.0 - reward


@dataclass
class ThompsonSelector:
    arms: dict[str, AgentArm] = field(default_factory=dict)
    rng: np.random.Generator = field(default_factory=lambda: np.random.default_rng())

    def ensure_arm(self, agent_id: str) -> AgentArm:
        return self.arms.setdefault(agent_id, AgentArm(agent_id=agent_id))

    def select(self, candidate_ids: list[str]) -> str:
        if not candidate_ids:
            raise ValueError("no candidates to select from")
        samples = {}
        for agent_id in candidate_ids:
            arm = self.ensure_arm(agent_id)
            samples[agent_id] = self.rng.beta(arm.alpha, arm.beta)
        return max(samples, key=samples.get)

    def record_outcome(self, agent_id: str, reward: float) -> None:
        self.ensure_arm(agent_id).update(reward)

    def mean_estimate(self, agent_id: str) -> float:
        arm = self.ensure_arm(agent_id)
        return arm.alpha / (arm.alpha + arm.beta)
