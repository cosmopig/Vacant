"""模型端點怎麼挑的，要說得出來（2026-09-20 拓樸釐清後補）。

這支在架構裡承重什麼：展場搬去的實體機器是 **1003（Windows）**，而 `vacant-dev`
是**跑在它上面的 VMware 虛擬機**（`systemd-detect-virt` ⇒ vmware）。實測
`192.168.76.1:1234`（VMware 主機介面）與 `100.119.113.56:1234`（Tailscale）
**回傳逐 byte 相同**，負控制 1004 不同 ⇒ 是同一台。

⚠ 人類 2026-09-20 澄清展場**會有網路**（他要遠端桌面進 1003），所以優先本機
**不是**在解離線紅線——理由窄一點但仍成立：少一層會自己壞掉的中間人。
"""
import os
import pytest
from ops.exhibit.twin import twinlink as T


def test_explicit_wins_and_says_so():
    r = T.resolve_endpoint("http://given/v1")
    assert r["url"] == "http://given/v1" and r["how"] == "explicit"


def test_env_var_beats_probing(monkeypatch):
    monkeypatch.setenv("VACANT_TWIN_ENDPOINT", "http://fromenv/v1")
    r = T.resolve_endpoint()
    assert r["url"] == "http://fromenv/v1"
    assert r["how"] == "env:VACANT_TWIN_ENDPOINT"


def test_candidate_order_prefers_same_machine():
    """127.0.0.1 → VMware 主機介面 → Tailscale。順序本身是判準。"""
    urls = [c[0] for c in T.ENDPOINT_CANDIDATES]
    assert "127.0.0.1" in urls[0]
    assert "192.168.76.1" in urls[1]
    assert "100.119.113.56" in urls[2]
    # 只有最後一個標成「需要網路」
    assert [c[2] for c in T.ENDPOINT_CANDIDATES] == [False, False, True]


def test_nothing_reachable_reports_none_not_false(monkeypatch):
    """🔴 三態：一個都探不到 ⇒ `reachable` 是 **None**，不是 False。

    「探不到」與「探到是壞的」是兩件事。寫 False 等於宣稱量到了。
    """
    def boom(*a, **k):
        raise OSError("no route")
    monkeypatch.delenv("VACANT_TWIN_ENDPOINT", raising=False)
    monkeypatch.setattr(T.urllib.request, "urlopen", boom)
    r = T.resolve_endpoint(timeout=0.1)
    assert r["reachable"] is None
    assert r["reachable"] is not False          # 明寫，免得日後有人「修」成 False
    assert r["how"] == "none_reachable"
    assert len(r["tried"]) == len(T.ENDPOINT_CANDIDATES)   # 每一個都真的試過


def test_negative_control_probe_actually_probes(monkeypatch):
    """**負控制**：把探測關掉，`tried` 必須是空的。

    沒有這一條，上面那個 `len(tried)==3` 跟一個「假裝試過」的實作長得一樣。
    """
    monkeypatch.delenv("VACANT_TWIN_ENDPOINT", raising=False)
    r = T.resolve_endpoint(probe=False)
    assert r["tried"] == []
    assert r["how"] == "fallback_unprobed"
    assert r["reachable"] is None


def test_first_reachable_wins(monkeypatch):
    """第一個通的就用它，後面的不必再試——而且要說出用了哪一個。"""
    class Resp:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): return False
    seen = []
    def fake(url, timeout=None):
        seen.append(url)
        if "192.168.76.1" in url:
            return Resp()
        raise OSError("nope")
    monkeypatch.delenv("VACANT_TWIN_ENDPOINT", raising=False)
    monkeypatch.setattr(T.urllib.request, "urlopen", fake)
    r = T.resolve_endpoint()
    assert "192.168.76.1" in r["url"]
    assert r["reachable"] is True and r["how"] == "probed"
    assert r["needs_network"] is False
    assert len(seen) == 2          # 試到第二個就停，沒有多打 Tailscale 那一發
