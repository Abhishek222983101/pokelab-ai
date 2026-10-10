"""Navigator (§7.3): a Gaussian Process over one experiment knob (e.g.
frac) plus an acquisition function, so the next run tried is the one
expected to teach us the most, not a human's guess at "let's try 0.5
next." Fit on REAL (config, outcome) pairs — see test_navigator.py, which
uses the actual 4-point sweep from P5.1.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, WhiteKernel


@dataclass
class NavigatorSuggestion:
    x: float
    predicted_mean: float
    predicted_std: float
    acquisition_score: float


class Navigator:
    def __init__(self):
        kernel = RBF(length_scale=0.2, length_scale_bounds=(0.01, 2.0)) + WhiteKernel(noise_level=1e-3)
        self._gp = GaussianProcessRegressor(kernel=kernel, normalize_y=True, n_restarts_optimizer=3)
        self._fit = False

    def fit(self, x: list[float], y: list[float]) -> None:
        x_arr = np.array(x).reshape(-1, 1)
        y_arr = np.array(y)
        self._gp.fit(x_arr, y_arr)
        self._fit = True

    def predict(self, x: float) -> tuple[float, float]:
        assert self._fit, "call fit() first"
        mean, std = self._gp.predict(np.array([[x]]), return_std=True)
        return float(mean[0]), float(std[0])

    def suggest_next(self, candidates: list[float], kappa: float = 1.0) -> NavigatorSuggestion:
        """Upper-confidence-bound: pick the candidate maximizing
        mean + kappa * std — explore where we're both optimistic AND
        uncertain, rather than only re-confirming what we already know."""
        assert self._fit, "call fit() first"
        best = None
        for x in candidates:
            mean, std = self.predict(x)
            score = mean + kappa * std
            if best is None or score > best.acquisition_score:
                best = NavigatorSuggestion(x=x, predicted_mean=mean, predicted_std=std, acquisition_score=score)
        return best
