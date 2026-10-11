"""The `arena` kit (P11.4, comparison arena) — reproduces the Grinsztajn
et al. 2022 "tree-based models still beat deep learning on tabular
data" claim with a real paired statistical test, not an eyeballed
number. Runs k-fold cross-validation for a tree-based model
(HistGradientBoostingClassifier) and a deep model (an MLP behind a
QuantileTransformer, matching the paper's own preprocessing) on the
SAME folds of a real OpenML table, then a paired t-test across folds —
satisfying oak/templates/compare.yaml's `metric_present:p_value` accept
check with a real computed value, not a stub.

Also reproduces the paper's robustness finding: an `+noise` and
`rotated` variant of the same table (uninformative Gaussian features
appended / a random orthogonal rotation) degrade the MLP's score more
than the tree model's — this kit's `variant` config switches between
them, ported from scripts/reference/kitbench/arena_quick.py.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from pokelab_workers.kits.base import KitContext, register

# sklearn.ensemble/model_selection/neural_network and scipy.stats cost
# ~0.6s to import cold (they pull in scipy's compiled extensions) — kept
# lazy (imported inside the functions below) so the warm pool's startup
# handshake (registering ALL kits) stays fast; only a job that actually
# dispatches to this kit pays the cost, once.


def _apply_variant(X: np.ndarray, variant: str, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    if variant == "base":
        return X
    if variant == "+noise":
        noise = rng.normal(size=(len(X), X.shape[1]))
        return np.hstack([X, noise])
    if variant == "rotated":
        Xs = (X - X.mean(0)) / (X.std(0) + 1e-9)
        Q, _ = np.linalg.qr(rng.normal(size=(X.shape[1], X.shape[1])))
        return Xs @ Q
    raise ValueError(f"unknown variant {variant!r}")


def _make_mlp(seed: int):
    from sklearn.neural_network import MLPClassifier
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import QuantileTransformer

    return make_pipeline(
        QuantileTransformer(output_distribution="normal", random_state=seed),
        MLPClassifier((64, 64), early_stopping=True, max_iter=200, random_state=seed),
    )


class ArenaKit:
    name = "arena"
    version = "1"

    def run(self, ctx: KitContext) -> dict[str, Any]:
        from scipy import stats
        from sklearn.ensemble import HistGradientBoostingClassifier
        from sklearn.model_selection import StratifiedKFold

        from pokelab_workers.kits.arena.data import load_dataset

        cfg = ctx.config
        dataset = cfg.get("dataset", "magictelescope")
        variant = cfg.get("variant", "base")
        n_folds = int(cfg.get("n_folds", 5))
        seed = int(cfg.get("seed", 0))
        n_subsample = int(cfg.get("n_subsample", 4000))  # keeps the MLP's fit CPU-fast

        X, y = load_dataset(dataset)
        rng = np.random.default_rng(seed)
        if len(X) > n_subsample:
            idx = rng.choice(len(X), size=n_subsample, replace=False)
            X, y = X[idx], y[idx]
        X = _apply_variant(X, variant, seed)

        kfold = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=seed)
        tree_scores: list[float] = []
        mlp_scores: list[float] = []

        step = 0
        for fold_idx, (train_idx, test_idx) in enumerate(kfold.split(X, y)):
            if ctx.stop.is_set():
                return {"stopped_at_fold": fold_idx, "tree_scores": tree_scores, "mlp_scores": mlp_scores}
            X_tr, X_te = X[train_idx], X[test_idx]
            y_tr, y_te = y[train_idx], y[test_idx]

            tree = HistGradientBoostingClassifier(random_state=seed)
            tree.fit(X_tr, y_tr)
            tree_score = tree.score(X_te, y_te)
            tree_scores.append(tree_score)

            mlp = _make_mlp(seed)
            mlp.fit(X_tr, y_tr)
            mlp_score = mlp.score(X_te, y_te)
            mlp_scores.append(mlp_score)

            step += 1
            ctx.emit(step, "tree_fold_acc", tree_score)
            ctx.emit(step, "mlp_fold_acc", mlp_score)

        t_stat, p_value = stats.ttest_rel(tree_scores, mlp_scores)
        winner = "tree" if float(np.mean(tree_scores)) > float(np.mean(mlp_scores)) else "mlp"

        return {
            "dataset": dataset,
            "variant": variant,
            "n_folds": n_folds,
            "tree_scores": tree_scores,
            "mlp_scores": mlp_scores,
            "tree_mean": float(np.mean(tree_scores)),
            "mlp_mean": float(np.mean(mlp_scores)),
            "t_stat": float(t_stat),
            "p_value": float(p_value),
            "winner": winner,
            "significant_at_0.05": bool(p_value < 0.05),
        }


kit = register(ArenaKit())
