"""P11.5 — Oracle and Navigator, proven on a SECOND real kit (materials),
not just grokking. fixtures/materials_sweep.json is a real 5-point
max_depth sweep captured from workers/kits/materials (depth 2-6,
n_estimators=60) — the same kind of real-curve fixture grok_sweep.json
is for grokking, generalized via oracle/kit_adapters.py's primary/
secondary metric mapping instead of grokking's hardcoded test_acc/
train_acc names.
"""
import json
import os

from pokelab_labml.navigator.gp import Navigator
from pokelab_labml.oracle.features import curve_features, to_vector
from pokelab_labml.oracle.gbm import train
from pokelab_labml.oracle.kit_adapters import get_adapter

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "materials_sweep.json")


def _load_sweep():
    with open(FIXTURE) as f:
        return json.load(f)


def test_curve_features_work_on_a_non_grokking_kit():
    sweep = _load_sweep()
    adapter = get_adapter("materials")
    job = sweep["depth_6"]

    feats = curve_features(job["steps"], job[adapter.primary_key], job[adapter.secondary_key], cutoff_step=30)
    assert 0.0 < feats["primary_last"] < 1.0  # a real R^2, not a placeholder
    assert feats["n_evals"] > 0
    vec = to_vector(feats)
    assert vec.shape == (5,)


def test_oracle_trains_on_real_materials_curves():
    sweep = _load_sweep()
    adapter = get_adapter("materials")
    rows, labels = [], []
    for job in sweep.values():
        feats = curve_features(job["steps"], job[adapter.primary_key], job[adapter.secondary_key], cutoff_step=30)
        rows.append(feats)
        labels.append(1 if job["final"]["test_r2"] >= 0.85 else 0)

    assert len(set(labels)) > 1, "the real sweep should straddle the threshold (it does: depth 2-3 below, 4-6 above)"
    model = train(rows, labels)
    for feats in rows:
        p = model.predict_proba_grok(feats)
        assert 0.0 <= p <= 1.0
    assert model.n_train == len(sweep)


def test_navigator_fits_real_materials_sweep():
    sweep = _load_sweep()
    x = [job["max_depth"] for job in sweep.values()]
    y = [job["final"]["test_r2"] for job in sweep.values()]

    nav = Navigator()
    nav.fit(x, y)

    mean_at_6, _ = nav.predict(6.0)
    mean_at_2, _ = nav.predict(2.0)
    assert mean_at_6 > mean_at_2, "GP should reflect the real sweep: deeper trees really did fit better here"

    suggestion = nav.suggest_next([2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
    assert suggestion.x in {2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0}
