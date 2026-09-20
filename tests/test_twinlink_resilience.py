"""twinlink 失效路徑的判準（2026-09-20 無人值守演練之後補上）。

守的是展場硬約束 2：**沒有解說員**。所以這裡每一條都在問同一件事——
出事的時候 loop 會不會整個死掉，死了就沒有人會去把它拉起來，
而**所有**觀眾的卡都不再上螢幕（不只那一張出事的）。

演練本體與負控制在 `ops/exhibit/twin/resilience_check.sh`（第 6 節）；
這一份是把那一節裡撞出來的每一種死法釘成可回歸的測試。

紀律：每一組「現在不會死了」都配一個**負控制**——證明那個輸入真的是會咬人的
（`.strip()` 真的會炸、`append` 真的擋不下、量具真的分得出來）。
只證明修好之後是綠的，等於沒測。
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.exhibit.twin import twinlink  # noqa: E402
from ops.exhibit.twin.twinstore import (  # noqa: E402
    KIND_ERROR, KIND_GENERATED, KIND_SUBMITTED, TwinStore,
)

DEAD_ENDPOINT = "http://127.0.0.1:1/v1"   # 一定連不上 ⇒ 一定走退化路徑
LONE_SURROGATE = json.loads('"\\ud800"')  # Node 的 JSON.stringify 會原樣送過來


@pytest.fixture()
def store(tmp_path: pathlib.Path):
    s = TwinStore(tmp_path / "t.sqlite3")
    yield s
    s.close()


def _cloud(monkeypatch, items):
    """把 `/api/all` 換成罐頭回應。不起伺服器，測的是解析與寫入那一段。"""
    def fake(url, payload=None, timeout=30.0, method=None):  # noqa: ANN001
        return 200, {"items": items}
    monkeypatch.setattr(twinlink, "_http_json", fake)


# ---------------------------------------------------------------------------
# 1. 卡的欄位不是字串 —— 只在「1003 已經斷了」的時候才咬人的那一種
# ---------------------------------------------------------------------------

def test_hostile_cards_really_are_hostile() -> None:
    """🔴 負控制：先證明這些輸入真的會炸，否則下面的綠燈是廢話。"""
    with pytest.raises(AttributeError):
        (({"need": 123}).get("need") or "").strip()
    with pytest.raises(AttributeError):
        ("我是字串" or {}).get("need")


@pytest.mark.parametrize("card", [
    {"need": 123},
    {"need": "x", "vibe": {"a": 1}},
    {"need": "x", "first_line": 5},
    {"need": ["清單"], "shape": 7},
    "我是字串不是物件",
    ["我是陣列"],
    None,
])
def test_fallback_twin_never_raises(card) -> None:
    """退化路徑是**最後一張網**，它自己不可以破。

    這幾種卡在修之前會讓 `fallback_twin` 丟 AttributeError，而那個例外
    是在 `generate_one` 的 except 區塊裡丟出來的 ⇒ 直接炸穿整個 loop。
    """
    t = twinlink.fallback_twin(card)
    assert t["engine"] == "fallback_deterministic"
    assert all(isinstance(t[k], str) and t[k] for k in ("arrival", "working", "handover"))


@pytest.mark.parametrize("card", [{"need": 123}, "我是字串", ["陣列"], {"vibe": {"a": 1}}])
def test_generate_one_degrades_instead_of_crashing(card) -> None:
    """1003 不通 ＋ 卡的形狀不對 ⇒ 要退化，不要死。"""
    t = twinlink.generate_one(card, "需求：整理桌面", DEAD_ENDPOINT, "nope", timeout=1.0)
    assert t["engine"] == "fallback_deterministic"
    assert t.get("degrade_reason")


def test_build_prompt_still_rejects_non_dict_card() -> None:
    """🔴 負控制：`build_prompt` 本身**沒有**被改寬。

    救下 loop 的是「把它包進 try、退化接住」，不是「把壞輸入變成好輸入」。
    這兩件事的差別在於：前者留下 degrade_reason，後者會安靜地假裝沒事。
    """
    with pytest.raises(AttributeError):
        twinlink.build_prompt("我是字串不是物件", None)


# ---------------------------------------------------------------------------
# 2. ingest：壞卡不可以帶走乾淨的鄰居
# ---------------------------------------------------------------------------

def test_bad_id_cannot_be_appended(store: TwinStore) -> None:
    """🔴 負控制：含換行的 sub_id 真的進不了事件流（雜湊鏈用換行當分隔）。"""
    with pytest.raises(ValueError, match="換行"):
        store.append(KIND_SUBMITTED, "a\nb", {"card": None}, source="t")


def test_lone_surrogate_really_breaks_append(store: TwinStore) -> None:
    """🔴 負控制：落單代理對真的會讓 append 炸（雜湊在算 utf-8 編碼）。"""
    with pytest.raises(UnicodeEncodeError):
        store.append(KIND_SUBMITTED, "v1", {"card_text": LONE_SURROGATE}, source="t")


@pytest.mark.parametrize("bad", [
    {"id": "bad\nid", "card": {"need": "x"}},
    {"id": "bad-surrogate", "card": {"need": LONE_SURROGATE}},
])
def test_ingest_keeps_going_after_a_bad_card(store: TwinStore, monkeypatch, bad) -> None:
    """壞卡記一列 error，**乾淨的鄰居照樣進得來**。

    這一條就是展場的判準本身：修之前，鄰居那張卡拿不到分身
    （`resilience_check.sh` §6 的 `neighbour_has_twin=0`）。
    """
    good = {"id": "neighbour", "card": {"need": "整理桌面"}, "card_text": "需求：整理桌面"}
    _cloud(monkeypatch, [bad, good])
    r = twinlink.ingest(store, "http://cloud.invalid", "t")
    assert r["ok"] is True
    assert r["pulled"] == 1          # 鄰居進來了
    assert r["rejected"] == 1        # 壞卡被擋下，而且**有講**
    assert store.sub_ids() == ["neighbour"]
    errs = [e for e in store.events(kind=KIND_ERROR)
            if (e["payload"] or {}).get("step") == "ingest"]
    assert len(errs) == 1
    # 連「記下這張卡壞掉」都不可以把鏈弄壞（錯誤訊息裡可能帶著那個代理對）
    assert store.verify()["ok"] is True


def test_ingest_does_not_relog_the_same_bad_card(store: TwinStore, monkeypatch) -> None:
    """同一張壞卡每輪記一次 ⇒ 無人值守一天就是幾十萬列。只准記一次。"""
    bad = {"id": "bad-surrogate", "card": {"need": LONE_SURROGATE}}
    _cloud(monkeypatch, [bad])
    twinlink.ingest(store, "http://cloud.invalid", "t")
    twinlink.ingest(store, "http://cloud.invalid", "t")
    twinlink.ingest(store, "http://cloud.invalid", "t")
    errs = [e for e in store.events(kind=KIND_ERROR)
            if (e["payload"] or {}).get("step") == "ingest"]
    assert len(errs) == 1


def test_ingest_does_not_swallow_store_failures(store: TwinStore, monkeypatch) -> None:
    """🔴 這一條跟上面三條是相反方向的，兩邊都要成立。

    磁碟滿／庫壞**不是**「一張卡的問題」。把它吞成「跳過一張卡」，
    loop 會空轉一整天而沒有人知道——展場最壞的一種壞法。要炸出去。
    """
    _cloud(monkeypatch, [{"id": "v1", "card": {"need": "x"}}])

    def boom(*a, **k):  # noqa: ANN001, ANN002, ANN003
        raise sqlite3.OperationalError("database or disk is full")

    monkeypatch.setattr(store, "append", boom)
    with pytest.raises(sqlite3.OperationalError):
        twinlink.ingest(store, "http://cloud.invalid", "t")


# ---------------------------------------------------------------------------
# 3. generate：最後一道網，而且不可以讓那張卡每輪再炸一次
# ---------------------------------------------------------------------------

def test_generate_last_resort_net(store: TwinStore, monkeypatch) -> None:
    store.append(KIND_SUBMITTED, "v1", {"card": {"need": "整理桌面"}}, source="t")

    def boom(*a, **k):  # noqa: ANN001, ANN002, ANN003
        raise ValueError("假裝算不出來")

    monkeypatch.setattr(twinlink, "generate_one", boom)
    r = twinlink.generate(store, DEAD_ENDPOINT, "nope", timeout=1.0)
    assert r["failed"] == 1
    assert r["generated"] == 1        # 照樣寫一列 generated
    assert r["remaining"] == 0        # ⇒ 下一輪不會再撿起同一張卡再炸一次
    gen = [e for e in store.events(kind=KIND_GENERATED)]
    assert gen[0]["payload"]["engine"] == "fallback_deterministic"
    assert "算不出分身" in gen[0]["payload"]["degrade_reason"]
    assert store.verify()["ok"] is True


def test_generate_no_fallback_still_raises(store: TwinStore, monkeypatch) -> None:
    """🔴 負控制：量測模式（`--no-fallback`）不可以被這張網偷偷補上一張。

    沒有這一條，上面那張網會把「模型其實沒回話」也補成一筆好看的資料。
    """
    store.append(KIND_SUBMITTED, "v1", {"card": {"need": "整理桌面"}}, source="t")

    def boom(*a, **k):  # noqa: ANN001, ANN002, ANN003
        raise ValueError("假裝算不出來")

    monkeypatch.setattr(twinlink, "generate_one", boom)
    with pytest.raises(ValueError):
        twinlink.generate(store, DEAD_ENDPOINT, "nope", timeout=1.0, allow_fallback=False)


def test_generate_does_not_swallow_store_failures(store: TwinStore, monkeypatch) -> None:
    store.append(KIND_SUBMITTED, "v1", {"card": {"need": "整理桌面"}}, source="t")
    real_append = store.append

    def boom(kind, *a, **k):  # noqa: ANN001, ANN002, ANN003
        if kind == KIND_GENERATED:
            raise sqlite3.OperationalError("database or disk is full")
        return real_append(kind, *a, **k)

    monkeypatch.setattr(store, "append", boom)
    with pytest.raises(sqlite3.OperationalError):
        twinlink.generate(store, DEAD_ENDPOINT, "nope", timeout=1.0)


# ---------------------------------------------------------------------------
# 4. _safe_text：記錯誤的那一列自己不可以炸
# ---------------------------------------------------------------------------

def test_safe_text_survives_lone_surrogate() -> None:
    s = twinlink._safe_text("壞的：" + LONE_SURROGATE + "還有後面")
    s.encode("utf-8")                       # 不炸＝可以進事件流
    assert "壞的" in s and "還有後面" in s   # 只換掉壞的那一個字元，不是整段吃掉


def test_safe_text_truncates() -> None:
    assert len(twinlink._safe_text("長" * 5000, limit=120)) == 120


# ---------------------------------------------------------------------------
# 5. 時鐘倒退：摺疊看 seq 不看 ts
# ---------------------------------------------------------------------------

def test_fold_survives_clock_going_backwards(store: TwinStore) -> None:
    """NTP 把時鐘往回校 ⇒ 後寫的事件 ts 比較小。摺疊不可以因此取錯。"""
    store.append(KIND_SUBMITTED, "v1", {"card": {"need": "x"}}, source="t",
                 ts_unix_ms=3_000_000)
    store.append(KIND_GENERATED, "v1", {"arrival": "舊", "engine": "e_old"},
                 source="t", ts_unix_ms=2_000_000)
    store.append(KIND_GENERATED, "v1", {"arrival": "新", "engine": "e_new"},
                 source="t", ts_unix_ms=1_000_000)
    assert (store.current("v1") or {})["twin"]["engine"] == "e_new"
    assert store.verify()["ok"] is True
    # 🔴 負控制：如果照 ts 排序會取到**另一個**答案 ⇒ 上面那一行不是廢話
    rows = list(store.conn.execute(
        "SELECT ts_unix_ms, payload_json FROM twin_event WHERE kind='generated'"))
    by_ts = json.loads(sorted(rows, key=lambda r: r["ts_unix_ms"])[-1]["payload_json"])
    assert by_ts["engine"] == "e_old"
