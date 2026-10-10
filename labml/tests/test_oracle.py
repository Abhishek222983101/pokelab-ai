"""Oracle trained on REAL curves from a genuine (small) sweep run on this
GPU — see tests/fixtures/grok_sweep.json. n=4 is nowhere near the hundreds
of runs the full curve-library sweep (§5.1) calls for, so this test
checks the PIPELINE works end to end (features extract correctly, the
model fits and predicts probabilities in [0,1]), not that Oracle is
accurate yet — that claim needs the real sweep, tracked in PROGRESS.md.
"""
import json
import os

from pokelab_labml.oracle.features import early_curve_features
from pokelab_labml.oracle.gbm import train

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "grok_sweep.json")


def _load_sweep():
    with open(FIXTURE) as f:
        return json.load(f)


def test_feature_extraction_on_real_curves():
    sweep = _load_sweep()
    job = sweep["j_0.5"]
    steps = [s for s, _ in job["test_acc"]]
    test_acc = [v for _, v in job["test_acc"]]
    train_acc = [v for _, v in job["train_acc"]]

    feats = early_curve_features(steps, test_acc, train_acc, cutoff_step=800)
    assert 0.0 <= feats["test_acc_last"] <= 1.0
    assert feats["n_evals"] > 0


def test_oracle_trains_and_predicts_on_real_small_sweep():
    sweep = _load_sweep()
    rows, labels = [], []
    for job_id, job in sweep.items():
        steps = [s for s, _ in job["test_acc"]]
        test_acc = [v for _, v in job["test_acc"]]
        train_acc = [v for _, v in job["train_acc"]]
        rows.append(early_curve_features(steps, test_acc, train_acc, cutoff_step=800))
        # ground truth: did the FULL run reach >= 0.95 test acc by the end?
        labels.append(1 if job["final"]["test_acc"] >= 0.95 else 0)

    assert len(set(labels)) > 1, "fixture should contain both outcomes (it does: j_0.3 didn't grok)"

    model = train(rows, labels)
    for feats, label in zip(rows, labels):
        p = model.predict_proba_grok(feats)
        assert 0.0 <= p <= 1.0

    # the one honest accuracy claim we can make at n=4: the model at
    # least fits without error and returns valid probabilities — NOT a
    # claim about real-world forecasting accuracy (needs the full sweep)
    assert model.n_train == 4
