"""The real `materials` kit (P11.3) on the real superconductor dataset.
Small n_estimators keeps this CI-fast; a full run (docs/_parts) uses the
default 300 trees for the curated [MEASURED] R^2 ~0.90-0.92 claim.
"""
from pokelab_workers.kits.base import KitContext, SimpleStopToken
from pokelab_workers.kits.materials.spec import kit as materials_kit


def test_materials_kit_trains_on_real_superconductor_data():
    emits = []
    ctx = KitContext(
        job_id="t1",
        config={"n_estimators": 20, "trees_per_step": 10},
        emit=lambda s, k, v: emits.append((s, k, v)),
        stop=SimpleStopToken(),
    )
    final = materials_kit.run(ctx)

    assert final["n_trees"] == 20
    assert final["n_train"] > 15000  # the real 21263-row dataset, 80/20 split
    assert 0.0 < final["test_r2"] < 1.0  # a real, non-trivial fit — not 0, not a cheat
    assert final["test_rmse"] > 0
    keys = {k for _, k, _ in emits}
    assert {"train_r2", "test_r2", "test_rmse"} <= keys


def test_materials_kit_honours_stop():
    ctx = KitContext(
        job_id="t2",
        config={"n_estimators": 10_000, "trees_per_step": 10},
        emit=lambda s, k, v: None,
        stop=_AlwaysStopAfterFirstCheck(),
    )
    final = materials_kit.run(ctx)
    assert "stopped_at_trees" in final
    assert final["stopped_at_trees"] == 0


class _AlwaysStopAfterFirstCheck:
    def is_set(self) -> bool:
        return True
