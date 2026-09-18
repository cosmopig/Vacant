"""`requests_seen` 不准少算——它是「中介真的發生了」的**唯一**證據。

這支在架構裡承重什麼
────────────────────
`docs/VACANT_RUN.md` §4.5 的紀律是：「我設了設定」不是證據，`requests_seen`
才是。那句話成立的前提是這個數字**不會少算**。

但計數發生在**回應送出之後**（`_handle_inner` 尾端的 `stats[...] += 1`），
而呼叫端是在 agent 行程結束的當下讀 `stats`。agent 拿到回應 → 寫檔 → 退出
這段期間，handler 執行緒可以還沒跑到那一行。2026-09-18 在 CI（ubuntu py3.13）
上就這樣紅過一次：`requests_seen` 逐次 [1, 1, 0]，而第三通其實有發生。

修法是 `quiesce()`：讀 `stats` 之前先等在途請求結束。排不空要**落盤**
（`stats["quiesce_timeout"]`），不可以把不完整的數字當成就是這麼多通。
"""
from __future__ import annotations

import threading
import time

from vacant.vrun import wireproxy


class _SlowProxy(wireproxy.WireProxy):
    """把「回應已送出、但計數還沒發生」那個窗口**放大成可觀測**。"""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.released = threading.Event()
        self.entered = threading.Event()

    def _handle_inner(self, h, method):     # noqa: ARG002
        self.entered.set()
        self.released.wait(5)
        with self._lock:                    # 真正的計數點就長這樣
            self.stats["requests_seen"] += 1


def _mk(tmp_path) -> _SlowProxy:
    return _SlowProxy(wire_dir=tmp_path / "w", upstreams={}, keys={},
                      sentinel="x", mode="tee")


def test_quiesce_waits_for_the_inflight_handler(tmp_path):
    p = _mk(tmp_path)
    t = threading.Thread(target=p._handle, args=(None, "POST"), daemon=True)
    t.start()
    assert p.entered.wait(5), "handler 沒起來，這個測試沒測到東西"

    # ⚠ 不排空就讀＝CI 上那個紅的形狀
    assert p.stats["requests_seen"] == 0, "窗口沒打開，測試失效"
    assert p.quiesce(timeout_s=0.2) is False, "還有在途請求卻說排空了"

    p.released.set()
    assert p.quiesce(timeout_s=5) is True
    assert p.stats["requests_seen"] == 1, "排空之後數字還是少算的"
    t.join(5)


def test_quiesce_returns_true_when_there_is_nothing_in_flight(tmp_path):
    p = _mk(tmp_path)
    t0 = time.time()
    assert p.quiesce(timeout_s=5) is True
    assert time.time() - t0 < 1, "沒有在途請求卻等了"


def test_stop_records_the_timeout_instead_of_swallowing_it(tmp_path):
    """排不空 ⇒ `quiesce_timeout` 要是 True。**不完整要看得見。**"""
    p = _mk(tmp_path)
    p.quiesce = lambda *a, **k: False       # type: ignore[method-assign]
    assert p.stats["quiesce_timeout"] is False
    p.stop()
    assert p.stats["quiesce_timeout"] is True


def test_inflight_is_released_even_when_the_handler_raises(tmp_path):
    """handler 炸掉也要把 `_inflight` 還回去，否則 `quiesce` 會永遠等。"""
    class _Boom(wireproxy.WireProxy):
        def _handle_inner(self, h, method):  # noqa: ARG002
            raise RuntimeError("boom")

    p = _Boom(wire_dir=tmp_path / "w2", upstreams={}, keys={},
              sentinel="x", mode="tee")
    try:
        p._handle(None, "POST")
    except RuntimeError:
        pass
    assert p.quiesce(timeout_s=1) is True, "例外之後 `_inflight` 沒還回去"


def test_launcher_records_whether_the_wire_was_quiesced():
    """`rec["wire_quiesced"]` 要真的被寫進每一次嘗試——沒有它就看不出少算。"""
    from vacant.vrun import launcher
    src = launcher.__loader__.get_source("vacant.vrun.launcher") or ""
    assert 'rec["wire_quiesced"] = proxy.quiesce()' in src
    i_q = src.index('rec["wire_quiesced"]')
    i_r = src.index('rec["requests_seen"] = proxy.stats')
    assert i_q < i_r, "排空要排在讀 stats **之前**，否則修了等於沒修"
