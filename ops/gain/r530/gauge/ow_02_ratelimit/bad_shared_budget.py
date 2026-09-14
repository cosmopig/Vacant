"""已知壞樁 3：所有 key 共用同一個預算（忘了 per-caller）＋ 沒有參數檢查。

擋得住它的是 `check_three_keys_do_not_share_a_budget` 與兩條 ValueError。
goal 的 "counted separately per caller" 是一句話，而漏掉它的程式仍然
「會動」——這正是為什麼那一句要有一條對應的驗收。
"""
import math


class RateLimiter:
    def __init__(self, window_s, max_events, clock):
        self.window_s = float(window_s)
        self.max_events = int(max_events)
        self.clock = clock
        self._events = []                       # ← 一份，不分 key

    def _live(self, now):
        lo = now - self.window_s
        return [t for t in self._events if lo < t <= now]

    def allow(self, key):
        now = self.clock()
        if len(self._live(now)) >= self.max_events:
            return False
        self._events.append(now)
        return True

    def retry_after(self, key):
        if self.max_events == 0:
            return math.inf
        now = self.clock()
        live = sorted(self._live(now))
        if len(live) < self.max_events:
            return 0.0
        return max(0.0, live[len(live) - self.max_events] + self.window_s - now)

    def reset(self, key=None):
        self._events = []
