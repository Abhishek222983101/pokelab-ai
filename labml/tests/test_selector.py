import numpy as np

from pokelab_labml.selector.thompson import ThompsonSelector


def test_untried_agents_are_roughly_equal_at_first():
    sel = ThompsonSelector(rng=np.random.default_rng(0))
    counts = {"a": 0, "b": 0}
    for _ in range(200):
        counts[sel.select(["a", "b"])] += 1
    # no prior evidence -> neither should dominate heavily
    assert 60 <= counts["a"] <= 140
    assert 60 <= counts["b"] <= 140


def test_converges_to_the_better_agent_over_many_outcomes():
    sel = ThompsonSelector(rng=np.random.default_rng(1))
    # agent "good" succeeds 90% of the time, "bad" succeeds 10% of the time
    rng = np.random.default_rng(2)
    for _ in range(200):
        sel.record_outcome("good", 1.0 if rng.random() < 0.9 else 0.0)
        sel.record_outcome("bad", 1.0 if rng.random() < 0.1 else 0.0)

    counts = {"good": 0, "bad": 0}
    for _ in range(200):
        counts[sel.select(["good", "bad"])] += 1
    assert counts["good"] > counts["bad"] * 3

    assert sel.mean_estimate("good") > 0.7
    assert sel.mean_estimate("bad") < 0.3


def test_record_outcome_accepts_soft_rewards():
    sel = ThompsonSelector()
    sel.record_outcome("x", 0.7)
    arm = sel.ensure_arm("x")
    assert arm.alpha == 1.7
    assert arm.beta == 1.3
