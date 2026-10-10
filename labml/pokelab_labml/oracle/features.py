"""Oracle features (§7.1.1): turns the FIRST part of a curve into a
fixed-size vector so a model can forecast "will this grok, and when" long
before the run finishes — the entire point of Oracle existing (an early
stop / early warning an LLM can't give with calibrated confidence).
"""
from __future__ import annotations

import numpy as np


def early_curve_features(
    steps: list[int],
    test_acc: list[float],
    train_acc: list[float],
    cutoff_step: int = 800,
) -> dict[str, float]:
    """Only uses points with step <= cutoff_step — simulating "what did we
    know this early." Safe to call on a still-running job."""
    assert len(steps) == len(test_acc) == len(train_acc)
    idx = [i for i, s in enumerate(steps) if s <= cutoff_step]
    if not idx:
        return {
            "test_acc_last": 0.0, "test_acc_slope": 0.0,
            "train_acc_last": 0.0, "train_saturated": 0.0, "n_evals": 0.0,
        }

    ta = [test_acc[i] for i in idx]
    tr = [train_acc[i] for i in idx]
    st = [steps[i] for i in idx]

    slope = 0.0
    if len(idx) >= 2:
        slope = float(np.polyfit(st, ta, 1)[0])

    return {
        "test_acc_last": ta[-1],
        "test_acc_slope": slope,
        "train_acc_last": tr[-1],
        "train_saturated": 1.0 if tr[-1] >= 0.99 else 0.0,
        "n_evals": float(len(idx)),
    }


FEATURE_ORDER = ["test_acc_last", "test_acc_slope", "train_acc_last", "train_saturated", "n_evals"]


def to_vector(features: dict[str, float]) -> np.ndarray:
    return np.array([features[k] for k in FEATURE_ORDER], dtype=np.float64)
