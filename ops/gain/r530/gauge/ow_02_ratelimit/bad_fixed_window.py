"""已知壞樁 1：固定窗（counter + 週期重置）而不是滑動窗。

擋得住它的是兩條邊界條件——goal 講的是「how long a window」，
契約把「窗」逐字釘成 `now - window_s < t <= now`。固定窗在窗的交界處
會一次放行兩倍的量，那正是 goal 第一句的 "hammered by bursts"。
"""


class RateLimiter:
    def __init__(self, window_s, max_events, clock):
        if window_s <= 0:
            raise ValueError("window_s")
        if max_events < 0:
            raise ValueError("max_events")
        self.window_s = float(window_s)
        self.max_events = int(max_events)
        self.clock = clock
        self._bucket = {}

    def _slot(self, now):
        return int(now // self.window_s)

    def allow(self, key):
        now = self.clock()
        slot = self._slot(now)
        cur_slot, count = self._bucket.get(key, (slot, 0))
        if cur_slot != slot:
            cur_slot, count = slot, 0
        if count >= self.max_events:
            self._bucket[key] = (cur_slot, count)
            return False
        self._bucket[key] = (cur_slot, count + 1)
        return True

    def retry_after(self, key):
        now = self.clock()
        slot = self._slot(now)
        cur_slot, count = self._bucket.get(key, (slot, 0))
        if cur_slot != slot or count < self.max_events:
            return 0.0
        return (slot + 1) * self.window_s - now

    def reset(self, key=None):
        if key is None:
            self._bucket.clear()
        else:
            self._bucket.pop(key, None)
