import json
import os

from pokelab_labml.analysts.grok_signature import detect

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "grok_metrics.json")


def _load_real_metrics():
    with open(FIXTURE) as f:
        rows = json.load(f)
    by_key: dict[str, list[tuple[int, float]]] = {}
    for r in rows:
        by_key.setdefault(r["k"], []).append((r["step"], r["v"]))
    return by_key


def test_detects_real_grokking_run():
    """FIXTURE is a real metric stream from an actual GPU run of the
    grokking kit (captured once, committed, not regenerated per test —
    the training itself is tested elsewhere; this tests the analyst)."""
    by_key = _load_real_metrics()
    steps = [s for s, _ in by_key["train_acc"]]
    train_acc = [v for _, v in by_key["train_acc"]]
    test_acc = [v for _, v in by_key["test_acc"]]

    sig = detect(steps, train_acc, test_acc)
    assert sig.grokked is True
    assert sig.train_saturation_step is not None
    assert sig.test_transition_step is not None
    assert sig.test_transition_step > sig.train_saturation_step
    assert "grokking shape" in sig.narrative


def test_ordinary_learning_is_not_flagged_as_grokking():
    steps = [0, 100, 200, 300]
    train_acc = [0.2, 0.6, 0.98, 1.0]
    test_acc = [0.2, 0.6, 0.97, 0.99]  # tracks train closely — not grokking
    sig = detect(steps, train_acc, test_acc)
    assert sig.grokked is False


def test_never_reaching_threshold_is_not_grokked():
    steps = [0, 100]
    train_acc = [0.1, 0.2]
    test_acc = [0.1, 0.15]
    sig = detect(steps, train_acc, test_acc)
    assert sig.grokked is False
    assert sig.train_saturation_step is None
