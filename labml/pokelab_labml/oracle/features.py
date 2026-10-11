"""Oracle features (§7.1.1): turns the FIRST part of a curve into a
fixed-size vector so a model can forecast "will this succeed (reach its
target metric), and when" long before the run finishes — the entire
point of Oracle existing (an early stop / early warning an LLM can't
give with calibrated confidence).

`curve_features` is the generic form (P11.5): ANY kit's two curves
(a "primary" metric to forecast, a "secondary" one that signals
overfitting/saturation) work, not just grokking's test_acc/train_acc —
see oracle/kit_adapters.py for the per-kit metric-name mapping.
`early_curve_features` is kept as the grokking-specific name the
original P7.1 code and its tests already call.
"""
from __future__ import annotations

import numpy as np


def curve_features(
    steps: list[int],
    primary: list[float],
    secondary: list[float],
    cutoff_step: int,
    secondary_saturation_threshold: float = 0.99,
) -> dict[str, float]:
    """Only uses points with step <= cutoff_step — simulating "what did we
    know this early." Safe to call on a still-running job."""
    assert len(steps) == len(primary) == len(secondary)
    idx = [i for i, s in enumerate(steps) if s <= cutoff_step]
    if not idx:
        return {
            "primary_last": 0.0, "primary_slope": 0.0,
            "secondary_last": 0.0, "secondary_saturated": 0.0, "n_evals": 0.0,
        }

    pr = [primary[i] for i in idx]
    sec = [secondary[i] for i in idx]
    st = [steps[i] for i in idx]

    slope = 0.0
    if len(idx) >= 2:
        slope = float(np.polyfit(st, pr, 1)[0])

    return {
        "primary_last": pr[-1],
        "primary_slope": slope,
        "secondary_last": sec[-1],
        "secondary_saturated": 1.0 if sec[-1] >= secondary_saturation_threshold else 0.0,
        "n_evals": float(len(idx)),
    }


def early_curve_features(
    steps: list[int],
    test_acc: list[float],
    train_acc: list[float],
    cutoff_step: int = 800,
) -> dict[str, float]:
    generic = curve_features(steps, test_acc, train_acc, cutoff_step)
    return {
        "test_acc_last": generic["primary_last"],
        "test_acc_slope": generic["primary_slope"],
        "train_acc_last": generic["secondary_last"],
        "train_saturated": generic["secondary_saturated"],
        "n_evals": generic["n_evals"],
    }


FEATURE_ORDER = ["test_acc_last", "test_acc_slope", "train_acc_last", "train_saturated", "n_evals"]
GENERIC_FEATURE_ORDER = ["primary_last", "primary_slope", "secondary_last", "secondary_saturated", "n_evals"]


def to_vector(features: dict[str, float]) -> np.ndarray:
    order = FEATURE_ORDER if "test_acc_last" in features else GENERIC_FEATURE_ORDER
    return np.array([features[k] for k in order], dtype=np.float64)
