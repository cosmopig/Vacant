"""ow_02_ratelimit 的參考解——量具的正向那一半。**必須全過**可見與隱藏。"""
import bisect
import math


class RateLimiter:
    def __init__(self, window_s, max_events, clock):
        if window_s <= 0:
            raise ValueError("window_s must be greater than 0")
        if max_events < 0:
            raise ValueError("max_events must not be negative")
        self.window_s = float(window_s)
        self.max_events = int(max_events)
        self.clock = clock
        self._events = {}

    # 落在 (now - window_s, now] 之內的事件時間戳，排序後回傳。
    def _live(self, key, now):
        stamps = self._events.get(key)
        if not stamps:
            return []
        lo = now - self.window_s
        return [t for t in stamps if lo < t <= now]

    def allow(self, key):
        now = self.clock()
        live = self._live(key, now)
        if len(live) >= self.max_events:
            return False
        bisect.insort(self._events.setdefault(key, []), now)
        return True

    def retry_after(self, key):
        if self.max_events == 0:
            return math.inf
        now = self.clock()
        live = self._live(key, now)
        if len(live) < self.max_events:
            return 0.0
        # 要放行必須先讓 len(live) - max_events + 1 個事件落出窗；
        # 第 (len(live) - max_events) 個（0-indexed）落出的那一刻就是答案。
        pivot = live[len(live) - self.max_events]
        return max(0.0, pivot + self.window_s - now)

    def reset(self, key=None):
        if key is None:
            self._events.clear()
        else:
            self._events.pop(key, None)
