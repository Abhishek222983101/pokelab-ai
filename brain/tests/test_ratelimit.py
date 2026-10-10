import time

from pokelab_brain.llm.ratelimit import SlidingWindowLimiter


def test_allows_up_to_the_limit():
    lim = SlidingWindowLimiter(max_events=3, window_s=60)
    for _ in range(3):
        assert not lim.would_exceed()
        lim.record()
    assert lim.would_exceed()


def test_token_weighted_limit():
    lim = SlidingWindowLimiter(max_events=8000, window_s=60)
    lim.record(weight=7000)
    assert not lim.would_exceed(weight=900)
    assert lim.would_exceed(weight=1500)


def test_window_expires_events():
    lim = SlidingWindowLimiter(max_events=1, window_s=0.05)
    lim.record()
    assert lim.would_exceed()
    time.sleep(0.07)
    assert not lim.would_exceed()


def test_seconds_until_available_is_nonzero_when_full():
    lim = SlidingWindowLimiter(max_events=1, window_s=1.0)
    lim.record()
    wait = lim.seconds_until_available()
    assert 0 < wait <= 1.0
