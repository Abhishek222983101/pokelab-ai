"""A sliding-window limiter the router checks BEFORE calling a provider,
so we hit our own 429 locally instead of burning a real one. Numbers are
measured, not guessed: Elevate ~10 calls/min before 429 (§13.0.4); Groq
8000 tokens/min PER ORG, shared across both keys.
"""
from __future__ import annotations

import time
from collections import deque


class SlidingWindowLimiter:
    def __init__(self, max_events: float, window_s: float = 60.0):
        self.max_events = max_events
        self.window_s = window_s
        self._events: deque[tuple[float, float]] = deque()  # (ts, weight)

    def _prune(self, now: float) -> None:
        while self._events and now - self._events[0][0] > self.window_s:
            self._events.popleft()

    def current_usage(self) -> float:
        self._prune(time.monotonic())
        return sum(w for _, w in self._events)

    def would_exceed(self, weight: float = 1.0) -> bool:
        return self.current_usage() + weight > self.max_events

    def record(self, weight: float = 1.0) -> None:
        self._events.append((time.monotonic(), weight))

    def seconds_until_available(self, weight: float = 1.0) -> float:
        """0 if calling now would fit; otherwise how long until the oldest
        event(s) age out enough to make room."""
        now = time.monotonic()
        self._prune(now)
        if self.current_usage() + weight <= self.max_events:
            return 0.0
        # walk the window forward until enough weight has expired
        running = self.current_usage()
        for ts, w in self._events:
            running -= w
            if running + weight <= self.max_events:
                return max(0.0, (ts + self.window_s) - now)
        return self.window_s
