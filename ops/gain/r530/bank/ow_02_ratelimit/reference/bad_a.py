"""Known-bad A: reads the wall clock and uses a fixed window counter.

Two errors that travel together in real code: the injected clock is accepted and
then ignored, and the window is a bucket that resets rather than one that slides.
"""

import time


class RateLimiter(object):
    def __init__(self, window_s, max_events, clock=None):
        self._window_s = window_s
        self._max_events = max_events
        self._clock = clock
        self._bucket_start = {}
        self._count = {}

    def allow(self, key):
        now = time.time()
        start = self._bucket_start.get(key)
        if start is None or now - start >= self._window_s:
            self._bucket_start[key] = now
            self._count[key] = 0
        if self._count[key] >= self._max_events:
            return False
        self._count[key] += 1
        return True

    def retry_after(self, key):
        start = self._bucket_start.get(key)
        if start is None:
            return 0.0
        if self._count.get(key, 0) < self._max_events:
            return 0.0
        return self._window_s

    def reset(self, key=None):
        if key is None:
            self._bucket_start.clear()
            self._count.clear()
        else:
            self._bucket_start.pop(key, None)
            self._count.pop(key, None)
