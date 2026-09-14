"""Reference solution for ow_02_ratelimit (gauge only; never enters a workspace)."""


class RateLimiter(object):
    def __init__(self, window_s, max_events, clock):
        if window_s <= 0:
            raise ValueError("window_s must be positive, got %r" % (window_s,))
        if max_events < 0:
            raise ValueError("max_events must not be negative, got %r" % (max_events,))
        self._window_s = window_s
        self._max_events = max_events
        self._clock = clock
        self._events = {}

    def _counted(self, key, now):
        """Events inside (now - window_s, now]. Left-open, so an event sitting
        exactly window_s ago has already left."""
        floor = now - self._window_s
        stamps = self._events.get(key, [])
        # Drop what can never come back; a rewound clock leaves future stamps alone.
        stamps[:] = [t for t in stamps if t > floor]
        return sorted(t for t in stamps if t <= now)

    def allow(self, key):
        now = self._clock()
        counted = self._counted(key, now)
        if len(counted) >= self._max_events:
            return False
        self._events.setdefault(key, []).append(now)
        return True

    def retry_after(self, key):
        if self._max_events == 0:
            return float("inf")
        now = self._clock()
        counted = self._counted(key, now)
        if len(counted) < self._max_events:
            return 0.0
        leaving = counted[len(counted) - self._max_events]
        return leaving + self._window_s - now

    def reset(self, key=None):
        if key is None:
            self._events.clear()
        else:
            self._events.pop(key, None)
