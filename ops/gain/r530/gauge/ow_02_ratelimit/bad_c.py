"""Known-bad C: the skeleton. Every name exists, almost nothing happens."""
class RateLimiter(object):
    def __init__(self, window_s, max_events, clock):
        self.window_s = window_s
        self.max_events = max_events
        self.clock = clock

    def allow(self, key):
        return True

    def retry_after(self, key):
        return 0.0

    def reset(self, key=None):
        return None
