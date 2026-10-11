"""The real `arena` kit (P11.4) — a small/fast config (2000-row
subsample, 3 folds) against the real MagicTelescope table, just to keep
CI fast; the curated [MEASURED] numbers in docs/_parts use the full
config across both real datasets and all three variants.
"""
from pokelab_workers.kits.base import KitContext, SimpleStopToken
from pokelab_workers.kits.arena.spec import kit as arena_kit


def test_arena_kit_computes_a_real_paired_pvalue():
    emits = []
    ctx = KitContext(
        job_id="t1",
        config={"dataset": "magictelescope", "variant": "base", "n_folds": 3, "n_subsample": 1200},
        emit=lambda s, k, v: emits.append((s, k, v)),
        stop=SimpleStopToken(),
    )
    final = arena_kit.run(ctx)

    assert final["n_folds"] == 3
    assert len(final["tree_scores"]) == 3
    assert len(final["mlp_scores"]) == 3
    assert 0.0 <= final["p_value"] <= 1.0
    assert final["winner"] in {"tree", "mlp"}
    keys = {k for _, k, _ in emits}
    assert {"tree_fold_acc", "mlp_fold_acc"} <= keys


def test_arena_kit_variants_are_distinguishable():
    from pokelab_workers.kits.arena.data import load_dataset
    from pokelab_workers.kits.arena.spec import _apply_variant

    X, _ = load_dataset("magictelescope")
    base = _apply_variant(X, "base", seed=0)
    noisy = _apply_variant(X, "+noise", seed=0)
    rotated = _apply_variant(X, "rotated", seed=0)

    assert noisy.shape[1] == base.shape[1] * 2  # real extra noise columns, not a relabel
    assert rotated.shape == base.shape
