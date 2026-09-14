"""Known-bad B: sliding window, but three ordinary slips.

It closes the window on the left (`now - t <= window_s`), it records the event
even when the answer is no, and `retry_after` hands back the window length as a
fixed guess instead of the time that is actually left.
"""


class RateLimiter(object):
    def __init__(self, window_s, max_events, clock):
        if window_s <= 0 or max_events < 0:
            raise ValueError("bad configuration")
        self._window_s = window_s
        self._max_events = max_events
        self._clock = clock
        self._hits = {}

    def _live(self, key, now):
        hits = self._hits.setdefault(key, [])
        hits[:] = [t for t in hits if now - t <= self._window_s]
        return hits

    def allow(self, key):
        now = self._clock()
        hits = self._live(key, now)
        hits.append(now)
        return len(hits) <= self._max_events

    def retry_after(self, key):
        now = self._clock()
        hits = self._live(key, now)
        if len(hits) < self._max_events:
            return 0.0
        return self._window_s

    def reset(self, key=None):
        if key is None:
            self._hits.clear()
        else:
            self._hits.pop(key, None)
