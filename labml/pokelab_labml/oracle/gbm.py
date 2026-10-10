"""Oracle's classifier: "will this run eventually grok (reach the target
test accuracy)?" from early-curve features alone. Named `gbm.py` per the
architecture's module layout; the actual estimator is a small gradient-
boosted classifier when there's enough data, falling back to logistic
regression below `MIN_SAMPLES_FOR_GBM` — sklearn's GBM needs more rows
than we currently have real curves for (§5.1's full sweep is hundreds of
runs; today we have a handful — see docs/PROGRESS.md P5.1/P5.2).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression

from pokelab_labml.oracle.features import to_vector

MIN_SAMPLES_FOR_GBM = 50


@dataclass
class OracleModel:
    estimator: object
    n_train: int

    def predict_proba_grok(self, features: dict[str, float]) -> float:
        x = to_vector(features).reshape(1, -1)
        proba = self.estimator.predict_proba(x)[0]
        classes = list(self.estimator.classes_)
        return float(proba[classes.index(1)]) if 1 in classes else 0.0


def train(feature_rows: list[dict[str, float]], labels: list[int]) -> OracleModel:
    """`labels[i] == 1` means run i eventually grokked (reached the run's
    target test accuracy); 0 means it didn't within its step budget."""
    assert len(feature_rows) == len(labels)
    x = np.stack([to_vector(f) for f in feature_rows])
    y = np.array(labels)

    if len(y) >= MIN_SAMPLES_FOR_GBM and len(set(y.tolist())) > 1:
        model = GradientBoostingClassifier(n_estimators=50, max_depth=2, random_state=0)
    else:
        # tiny-n fallback: logistic regression doesn't overfit as wildly,
        # and (crucially) still produces calibrated-ish probabilities even
        # from a handful of real curves rather than refusing to fit.
        model = LogisticRegression(max_iter=1000)

    if len(set(y.tolist())) < 2:
        raise ValueError("need at least one grokked and one non-grokked example to train Oracle")

    model.fit(x, y)
    return OracleModel(estimator=model, n_train=len(y))
