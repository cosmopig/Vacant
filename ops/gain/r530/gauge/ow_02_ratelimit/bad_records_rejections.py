"""已知壞樁 2：被拒絕的請求也記進窗裡（於是被擋的人永遠出不來）。

擋得住它的是 `check_blocked_calls_do_not_extend_the_window`——
契約那一句 "It records an event only when it returns True" 逐字對應它。
這個壞法在真實系統裡很常見，而且它「看起來會動」：allow 的回傳值全對，
只有「被擋之後多久才放行」是錯的。
"""
import math


class RateLimiter:
    def __init__(self, window_s, max_events, clock):
        if window_s <= 0:
            raise ValueError("window_s")
        if max_events < 0:
            raise ValueError("max_events")
        self.window_s = float(window_s)
        self.max_events = int(max_events)
        self.clock = clock
        self._events = {}

    def _live(self, key, now):
        lo = now - self.window_s
        return [t for t in self._events.get(key, []) if lo < t <= now]

    def allow(self, key):
        now = self.clock()
        live = self._live(key, now)
        self._events.setdefault(key, []).append(now)   # ← 不管過不過都記
        return len(live) < self.max_events

    def retry_after(self, key):
        if self.max_events == 0:
            return math.inf
        now = self.clock()
        live = sorted(self._live(key, now))
        if len(live) < self.max_events:
            return 0.0
        pivot = live[len(live) - self.max_events]
        return max(0.0, pivot + self.window_s - now)

    def reset(self, key=None):
        if key is None:
            self._events.clear()
        else:
            self._events.pop(key, None)
