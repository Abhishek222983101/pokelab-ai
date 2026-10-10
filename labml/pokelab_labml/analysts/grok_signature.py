"""Grok-signature analyst (§7.8, a stand-in for the fuller grok_fourier.py
weight analysis): detects the actual shape that makes grokking grokking
— train accuracy saturates near-perfectly long before test accuracy
moves, then test accuracy transitions sharply. A generic "did loss go
down" check would miss this; this is the one chart worth narrating.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GrokSignature:
    grokked: bool
    train_saturation_step: int | None  # first step train_acc >= train_threshold
    test_transition_step: int | None  # first step test_acc >= test_threshold
    memorization_gap_steps: int | None  # test_transition_step - train_saturation_step
    narrative: str


def detect(
    steps: list[int],
    train_acc: list[float],
    test_acc: list[float],
    train_threshold: float = 0.99,
    test_threshold: float = 0.95,
) -> GrokSignature:
    assert len(steps) == len(train_acc) == len(test_acc), "series must be aligned"

    train_sat = next((s for s, a in zip(steps, train_acc) if a >= train_threshold), None)
    test_trans = next((s for s, a in zip(steps, test_acc) if a >= test_threshold), None)

    if train_sat is None or test_trans is None:
        return GrokSignature(
            grokked=False,
            train_saturation_step=train_sat,
            test_transition_step=test_trans,
            memorization_gap_steps=None,
            narrative="did not reach both thresholds in this run",
        )

    gap = test_trans - train_sat
    grokked = gap > 0  # the defining shape: train saturates well before test does

    if grokked:
        narrative = (
            f"classic grokking shape: train accuracy saturated at step {train_sat}, "
            f"but test accuracy didn't cross {test_threshold:.0%} until step {test_trans} "
            f"— a {gap}-step memorization-then-generalization gap."
        )
    else:
        narrative = (
            f"NOT grokking-shaped: test accuracy reached {test_threshold:.0%} at step {test_trans}, "
            f"at or before train saturation (step {train_sat}) — looks like ordinary learning."
        )

    return GrokSignature(
        grokked=grokked,
        train_saturation_step=train_sat,
        test_transition_step=test_trans,
        memorization_gap_steps=gap,
        narrative=narrative,
    )
