from pokelab_brain.papers.packs import get_pack
from pokelab_brain.reward import compute_reward
from pokelab_brain.science.comparator import compare


def test_reward_full_credit_when_meeting_target():
    pack = get_pack("grokking")
    assert compute_reward(0.96, pack) == 1.0


def test_reward_partial_credit_when_short():
    pack = get_pack("grokking")
    r = compute_reward(0.475, pack)  # half of the 0.95 target
    assert 0.49 < r < 0.51


def test_reward_zero_when_no_result():
    pack = get_pack("grokking")
    assert compute_reward(None, pack) == 0.0


def test_comparator_matched():
    pack = get_pack("grokking")
    report = compare({"test_acc": 0.965}, "test_acc", pack)
    assert report.matched
    assert "Reproduced" in report.narrative
    assert report.reward == 1.0


def test_comparator_not_matched():
    pack = get_pack("grokking")
    report = compare({"test_acc": 0.5}, "test_acc", pack)
    assert not report.matched
    assert "Short of" in report.narrative


def test_comparator_no_result():
    pack = get_pack("grokking")
    report = compare(None, "test_acc", pack)
    assert not report.matched
    assert report.achieved_value is None
