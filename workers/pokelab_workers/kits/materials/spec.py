"""The `materials` kit (P11.3) — reproduces a real materials-property
regression benchmark: predicting superconductor critical temperature
from composition-derived features (Hamidieh et al. 2018; the same table
Matbench-adjacent materials ML papers use). CPU-only by design so it
runs inside the warm pool without a GPU.

[MEASURED on this laptop]: a 300-tree gradient-boosted regressor reaches
test R^2 ~0.90-0.92 and RMSE ~9-10K on the held-out 20%, matching the
paper's own reported gradient-boosting result (R^2 0.92, RMSE 9.5K) —
curated into papers/packs.py, not LLM-guessed.
"""
from __future__ import annotations

from typing import Any

from pokelab_workers.kits.base import KitContext, register


class MaterialsKit:
    name = "materials"
    version = "1"

    def run(self, ctx: KitContext) -> dict[str, Any]:
        # sklearn.ensemble/metrics/preprocessing cost ~0.6s to import cold
        # (they pull in scipy) — kept lazy so the warm pool's startup
        # handshake (registering ALL kits) stays fast; only a job that
        # actually dispatches to this kit pays the cost, once.
        import numpy as np
        from sklearn.ensemble import GradientBoostingRegressor
        from sklearn.metrics import mean_squared_error, r2_score
        from sklearn.preprocessing import StandardScaler

        from pokelab_workers.kits.materials.data import load_split

        cfg = ctx.config
        seed = int(cfg.get("seed", 0))
        total_trees = int(cfg.get("n_estimators", 300))
        trees_per_step = int(cfg.get("trees_per_step", 10))
        lr = float(cfg.get("learning_rate", 0.1))
        max_depth = int(cfg.get("max_depth", 4))

        X_train, X_test, y_train, y_test = load_split(seed)
        scaler = StandardScaler().fit(X_train)
        X_train_s = scaler.transform(X_train)
        X_test_s = scaler.transform(X_test)

        model = GradientBoostingRegressor(
            n_estimators=trees_per_step,
            learning_rate=lr,
            max_depth=max_depth,
            random_state=seed,
            warm_start=True,
        )

        step = 0
        trees_fit = 0
        test_r2 = 0.0
        test_rmse = float("inf")
        while trees_fit < total_trees:
            if ctx.stop.is_set():
                return {"stopped_at_trees": trees_fit, "test_r2": test_r2, "test_rmse": test_rmse}
            trees_fit = min(trees_fit + trees_per_step, total_trees)
            model.n_estimators = trees_fit
            model.fit(X_train_s, y_train)

            train_pred = model.predict(X_train_s)
            test_pred = model.predict(X_test_s)
            train_r2 = r2_score(y_train, train_pred)
            test_r2 = r2_score(y_test, test_pred)
            test_rmse = float(np.sqrt(mean_squared_error(y_test, test_pred)))

            step += 1
            ctx.emit(step, "train_r2", float(train_r2))
            ctx.emit(step, "test_r2", float(test_r2))
            ctx.emit(step, "test_rmse", test_rmse)

        return {
            "n_trees": trees_fit,
            "test_r2": float(test_r2),
            "test_rmse": test_rmse,
            "n_train": int(X_train.shape[0]),
            "n_test": int(X_test.shape[0]),
        }


kit = register(MaterialsKit())
