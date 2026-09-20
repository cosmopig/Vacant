"""twinstore／twinlink 的判準。

這一批測試守的是 2026-09-20 人類指示裡的兩句硬話：
**「資料不要刪除」** 與 **「數位分身要好要能用」**。

紀律：每一組「應該擋得住」都配一個**負控制**（故意弄壞，證明檢查會紅）。
只證明乾淨的輸入會綠，等於沒測。
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
    KIND_ERROR, KIND_GENERATED, KIND_INGEST_GAP, KIND_NOTE, KIND_PUBLISHED,
    KIND_SUBMITTED, TwinStore, canonical_json,
)


@pytest.fixture()
def store(tmp_path: pathlib.Path) -> TwinStore:
    s = TwinStore(tmp_path / "t.sqlite3")
    yield s
    s.close()


# ---------------------------------------------------------------------------
# 「資料不要刪除」＝可執行的，不是慣例
# ---------------------------------------------------------------------------

def test_update_and_delete_are_blocked(store: TwinStore) -> None:
    """🔴 核心判準。UPDATE／DELETE 必須 ABORT，不是「我們約定不要這樣寫」。"""
    store.append(KIND_NOTE, "a", {"v": 1}, source="t")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        store.conn.execute("UPDATE twin_event SET source='x' WHERE seq=1")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        store.conn.execute("DELETE FROM twin_event WHERE seq=1")
    # 擋下來之後庫還能繼續寫（第一版踩過：被擋的那一句把交易留在開著的狀態，
    # 下一次 append 會炸 "cannot start a transaction within a transaction"）
    store.append(KIND_NOTE, "a", {"v": 2}, source="t")
    assert store.count() == 2


def test_reopening_restores_the_triggers(tmp_path: pathlib.Path) -> None:
    """有人用生連線把 trigger 拔掉之後，重開 store 要把守衛補回去。"""
    db = tmp_path / "t.sqlite3"
    s = TwinStore(db); s.append(KIND_NOTE, "a", {"v": 1}, source="t"); s.close()

    raw = sqlite3.connect(str(db)); raw.isolation_level = None
    raw.execute("PRAGMA writable_schema=ON")
    raw.execute("DELETE FROM sqlite_master WHERE type='trigger'")
    raw.execute("PRAGMA writable_schema=OFF")
    raw.close()

    s2 = TwinStore(db)
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        s2.conn.execute("DELETE FROM twin_event WHERE seq=1")
    s2.close()


def test_state_change_appends_never_overwrites(store: TwinStore) -> None:
    """狀態變化＝追加一列。舊列一列都不准少——這是「不要刪除」的另一半。"""
    store.append(KIND_SUBMITTED, "v", {"card": {"need": "x"}}, source="t")
    store.append(KIND_GENERATED, "v", {"arrival": "嗨"}, source="t")
    store.append(KIND_PUBLISHED, "v", {"http": 200}, source="t")
    assert store.current("v")["status"] == "published"
    assert len(list(store.events(sub_id="v"))) == 3
    # 第一列的內容原封不動
    first = list(store.events(sub_id="v"))[0]
    assert first["payload"]["card"]["need"] == "x"


# ---------------------------------------------------------------------------
# 雜湊鏈：正控制綠，負控制紅
# ---------------------------------------------------------------------------

def test_clean_chain_verifies(store: TwinStore) -> None:
    for i in range(5):
        store.append(KIND_NOTE, f"s{i}", {"i": i}, source="t")
    v = store.verify()
    assert v["ok"] is True
    assert v["checked"] == 5
    # 「沒壞」要寫 None 不是 0——0 是一個合法的位置
    assert v["broken_at"] is None


@pytest.mark.parametrize("column,value", [
    ("payload_json", "{\"tampered\":1}"),
    ("source", "someone-else"),
    ("kind", "note"),
    ("sub_id", "other"),
])
def test_tampering_any_column_turns_verify_red(
        tmp_path: pathlib.Path, column: str, value: str) -> None:
    """🔴 負控制：改哪一欄都要被抓到，不是只有 payload。"""
    db = tmp_path / "t.sqlite3"
    s = TwinStore(db)
    s.append(KIND_NOTE, "a", {"v": 1}, source="t")
    s.append(KIND_ERROR, "b", {"v": 2}, source="t")
    s.append(KIND_NOTE, "c", {"v": 3}, source="t")
    assert s.verify()["ok"] is True
    s.close()

    raw = sqlite3.connect(str(db)); raw.isolation_level = None
    raw.execute("PRAGMA writable_schema=ON")
    raw.execute("DELETE FROM sqlite_master WHERE type='trigger'")
    raw.execute("PRAGMA writable_schema=OFF")
    raw.close()
    raw = sqlite3.connect(str(db)); raw.isolation_level = None
    raw.execute(f"UPDATE twin_event SET {column}=? WHERE seq=2", (value,))
    raw.close()

    s2 = TwinStore(db)
    v = s2.verify()
    assert v["ok"] is False, f"改 {column} 竟然驗得過"
    assert v["broken_at"] == 2
    s2.close()


def test_read_only_mode_cannot_write(tmp_path: pathlib.Path) -> None:
    """🔴 給現場螢幕的唯讀端點，唯讀要由 SQLite 強制，不是靠自律。"""
    db = tmp_path / "t.sqlite3"
    w = TwinStore(db)
    w.append(KIND_NOTE, "a", {"v": 1}, source="t")
    w.close()

    ro = TwinStore(db, read_only=True)
    # 讀得到
    assert ro.count() == 1
    assert ro.verify()["ok"] is True
    # 寫不進去——連 INSERT 都要被 SQLite 擋，不是只有 UPDATE/DELETE
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        ro.append(KIND_NOTE, "b", {"v": 2}, source="t")
    ro.close()

    # 負控制：同一個檔用可寫模式開就寫得進去（證明剛剛擋下來的是 mode=ro，
    # 不是這個檔本身壞了或權限不對）
    w2 = TwinStore(db)
    w2.append(KIND_NOTE, "b", {"v": 2}, source="t")
    assert w2.count() == 2
    w2.close()


def test_two_stores_have_different_genesis(tmp_path: pathlib.Path) -> None:
    """兩個庫的創世串不可以一樣，否則「把別台的鏈接過來」會驗得過。"""
    a = TwinStore(tmp_path / "a.sqlite3")
    b = TwinStore(tmp_path / "b.sqlite3")
    assert a.genesis() != b.genesis()
    a.close(); b.close()


def test_canonical_json_is_deterministic() -> None:
    """鏈上算的是這個字串的 sha256，所以鍵序不可以影響結果。"""
    assert canonical_json({"b": 1, "a": 2}) == canonical_json({"a": 2, "b": 1})


def test_newline_in_source_is_rejected(store: TwinStore) -> None:
    """雜湊用換行當分隔，所以欄位裡不能有換行——要明確炸，不是安靜地撞雜湊。"""
    with pytest.raises(ValueError, match="換行"):
        store.append(KIND_NOTE, "a", {}, source="two\nlines")


# ---------------------------------------------------------------------------
# 「沒量到」不准寫 0
# ---------------------------------------------------------------------------

def test_offline_ingest_reports_null_not_zero(store: TwinStore) -> None:
    """🔴 雲端連不上 ≠ 雲端沒東西。pulled 必須是 None。"""
    r = twinlink.ingest(store, "http://127.0.0.1:1", "tok", timeout=2.0)
    assert r["pulled"] is None
    assert r["seen"] is None
    assert r["ok"] is False
    assert store.count(KIND_INGEST_GAP) == 1


def test_successful_empty_ingest_reports_zero(store: TwinStore, monkeypatch) -> None:
    """對照組：真的連上了而且真的是空的，那才可以寫 0。"""
    monkeypatch.setattr(twinlink, "_http_json", lambda *a, **k: (200, {"items": []}))
    r = twinlink.ingest(store, "http://x", "tok")
    assert r["pulled"] == 0
    assert r["ok"] is True
    assert store.count(KIND_INGEST_GAP) == 0


def test_ingest_is_idempotent(store: TwinStore, monkeypatch) -> None:
    items = {"items": [{"id": "abc", "ts": 1, "card": {"need": "x"}}]}
    monkeypatch.setattr(twinlink, "_http_json", lambda *a, **k: (200, items))
    assert twinlink.ingest(store, "http://x", "t")["pulled"] == 1
    assert twinlink.ingest(store, "http://x", "t")["pulled"] == 0
    assert store.count(KIND_SUBMITTED) == 1


# ---------------------------------------------------------------------------
# 離線退路：可以退化，不可以冒充
# ---------------------------------------------------------------------------

def test_fallback_is_labelled_not_disguised() -> None:
    """🔴 鐵律 5 的展場版本：退化查表不可以長得像真模型。"""
    out = twinlink.generate_one(
        {"need": "整理桌面", "shape": "圓潤", "color": "暖土"}, None,
        endpoint="http://127.0.0.1:1/v1", model="nope", timeout=2.0)
    assert out["engine"] == "fallback_deterministic"
    assert not str(out["engine"]).startswith("lmstudio:")
    assert out["degraded_from"] == "lmstudio:nope"
    assert out["degrade_reason"]
    assert all(out[k] for k in ("arrival", "working", "handover"))


def test_no_fallback_raises_instead_of_lying() -> None:
    """量測模式：連不上就炸，不准偷偷給一個看起來成功的結果。"""
    with pytest.raises(Exception):
        twinlink.generate_one({}, None, endpoint="http://127.0.0.1:1/v1",
                              model="nope", timeout=2.0, allow_fallback=False)


# ---------------------------------------------------------------------------
# thinking 模式：答案被思考擠掉 ⇒ 升額重試一次
# ---------------------------------------------------------------------------

def test_squeezed_out_needs_both_conditions() -> None:
    """🔴 只看 content 空會誤判。必須「空 **且** reasoning 幾乎用完額度」。"""
    # 空 ＋ reasoning 吃光 ⇒ 是被擠掉
    assert twinlink._squeezed_out(
        {"text": "", "reasoning_tokens": 1597, "budget": 1600}) is True
    # 空 但 reasoning 沒吃多少 ⇒ 不是被擠掉（模型真的沒話說，升額也沒用）
    assert twinlink._squeezed_out(
        {"text": "", "reasoning_tokens": 12, "budget": 1600}) is False
    # 有內容 ⇒ 不管 reasoning 多長都不是
    assert twinlink._squeezed_out(
        {"text": "{...}", "reasoning_tokens": 1599, "budget": 1600}) is False
    # 量不到 reasoning_tokens ⇒ 不准猜（沒量到 ≠ 成立）
    assert twinlink._squeezed_out(
        {"text": "", "reasoning_tokens": None, "budget": 1600}) is False


def test_escalates_budget_once_then_succeeds(monkeypatch) -> None:
    """第一發被擠掉 → 升額重試 → 成功，而且 `budget_escalated` 留痕。"""
    calls = []

    def fake(prompt, endpoint, model, budget, timeout):
        calls.append(budget)
        if len(calls) == 1:   # 第一發：空的，reasoning 吃光
            return {"parsed": None, "text": "", "budget": budget,
                    "latency_ms": 10, "reasoning_tokens": budget - 3,
                    "completion_tokens": budget, "reasoning_chars": 4000}
        return {"parsed": {"arrival": "a", "working": "b", "handover": "c"},
                "text": '{"arrival":"a","working":"b","handover":"c"}',
                "budget": budget, "latency_ms": 20, "reasoning_tokens": 900,
                "completion_tokens": 950, "reasoning_chars": 2000}

    monkeypatch.setattr(twinlink, "_call_model", fake)
    out = twinlink.generate_one({"need": "x"}, None, "http://e/v1", "m")
    assert out["engine"] == "lmstudio:m"
    assert out["budget_escalated"] is True
    assert calls == [twinlink.MAX_TOKENS,
                     twinlink.MAX_TOKENS * twinlink.ESCALATE_FACTOR]


def test_escalates_at_most_once_then_falls_back(monkeypatch) -> None:
    """🔴 重試只准一次。無限重試會讓展場在模型壞掉時卡死。"""
    calls = []

    def always_squeezed(prompt, endpoint, model, budget, timeout):
        calls.append(budget)
        return {"parsed": None, "text": "", "budget": budget, "latency_ms": 10,
                "reasoning_tokens": budget - 1, "completion_tokens": budget,
                "reasoning_chars": 9000}

    monkeypatch.setattr(twinlink, "_call_model", always_squeezed)
    out = twinlink.generate_one({"need": "x"}, None, "http://e/v1", "m")
    assert len(calls) == 2, f"重試了 {len(calls)-1} 次，應該只有 1 次"
    assert out["engine"] == "fallback_deterministic"
    assert out["budget_escalated"] is True


def test_no_escalation_when_model_merely_misformats(monkeypatch) -> None:
    """模型有回話但格式不對 ⇒ **不該**升額重試（升額解決不了格式問題）。"""
    calls = []

    def misformatted(prompt, endpoint, model, budget, timeout):
        calls.append(budget)
        return {"parsed": None, "text": "我覺得這個人很有趣。", "budget": budget,
                "latency_ms": 10, "reasoning_tokens": 50,
                "completion_tokens": 80, "reasoning_chars": 100}

    monkeypatch.setattr(twinlink, "_call_model", misformatted)
    out = twinlink.generate_one({"need": "x"}, None, "http://e/v1", "m")
    assert len(calls) == 1, "不該重試"
    assert out["engine"] == "fallback_deterministic"
    assert "解析不出" in out["degrade_reason"]


def test_view_surfaces_engine_to_the_screen(store: TwinStore) -> None:
    """engine 必須出到畫面層，否則現場分不出真跑跟退化。"""
    store.append(KIND_SUBMITTED, "v", {"card": {"need": "x"}}, source="t")
    store.append(KIND_GENERATED, "v", {"arrival": "a", "working": "b",
                                       "handover": "c",
                                       "engine": "fallback_deterministic"},
                 source="t")
    view = twinlink.build_view(store)
    assert view["people"][0]["engine"] == "fallback_deterministic"
    assert "fallback_deterministic" in view["honesty"]


# ---------------------------------------------------------------------------
# KS-1（鐵律 1）
# ---------------------------------------------------------------------------

def test_ks1_blocks_forbidden_wording() -> None:
    with pytest.raises(ValueError, match="KS-1"):
        twinlink.assert_ks1_clean("你有責任把這件事做完")
    with pytest.raises(ValueError, match="KS-1"):
        twinlink.assert_ks1_clean("做不好會被懲罰")


def test_ks1_passes_the_real_prompt() -> None:
    """正控制：真正在用的 prompt 要過得了自己的防呆。"""
    twinlink.assert_ks1_clean(twinlink.SYSTEM_PROMPT)
    twinlink.assert_ks1_clean(twinlink.build_prompt(
        {"need": "整理桌面", "vibe": "慢"}, None))


# ---------------------------------------------------------------------------
# 模型回應解析：不硬湊
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad", [
    "", "沒有大括號", '{"arrival":"只有一個鍵"}', "{壞 json}",
    '{"arrival":"a","working":"b"}', '{"arrival":"","working":"b","handover":"c"}',
    "[1,2,3]",
])
def test_parser_returns_none_for_garbage(bad: str) -> None:
    assert twinlink._parse_model_json(bad) is None


@pytest.mark.parametrize("good", [
    '{"arrival":"a","working":"b","handover":"c"}',
    '```json\n{"arrival":"a","working":"b","handover":"c"}\n```',
    '廢話在前面 {"arrival":"a","working":"b","handover":"c"} 廢話在後面',
])
def test_parser_accepts_real_model_shapes(good: str) -> None:
    """正控制：模型真的會這樣包（圍欄、前後贅字），這些都要吃得下。"""
    assert twinlink._parse_model_json(good) == {
        "arrival": "a", "working": "b", "handover": "c"}


# ---------------------------------------------------------------------------
# export：原子換檔
# ---------------------------------------------------------------------------

def test_export_writes_valid_json_and_leaves_no_tmp(
        store: TwinStore, tmp_path: pathlib.Path) -> None:
    store.append(KIND_SUBMITTED, "v", {"card": {"need": "x"}}, source="t")
    out = tmp_path / "live" / "visitors.json"
    twinlink.export(store, out)
    assert json.loads(out.read_text(encoding="utf-8"))["counts"]["visitors"] == 1
    assert not list(out.parent.glob("*.tmp")), "留了暫存檔，螢幕可能讀到半份"
