"""2026-09-24 code review 抓到、主線驗證成立的三個 twinlink 缺陷——回歸判準。

裁決：`decisions/DECISION_20260924_TWIN_AGENT_RUN.md` §七。
每一條都是**先寫成會紅**（在修之前的碼上跑過、確認紅），再修到綠。

| 缺陷 | 嚴重度 | 守的那句話 |
|---|---|---|
| 退役事件把 `farewell` 明文寫進 append-only 鏈 | 高 | 撤回之後鏈上／畫面上不可以還有他的話，抹除證明不准說謊 |
| 還沒生成就撤回的人永遠 `arriving` | 中 | 撤回的人不佔「必留」名額、不算「還在等」 |
| `shown = live[:k]` 切前綴 | 中 | 算進必留的 fresh 一定上得了畫面，不會沒演過就被退役 |

⚠ 每一條都配負控制：證明「那個量法量得到東西」，綠燈才有意義。
"""
from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.exhibit.twin import twinlink, twinvault  # noqa: E402
from ops.exhibit.twin.twinstore import (  # noqa: E402
    KIND_GENERATED, KIND_NOTE, KIND_SUBMITTED, TwinStore, canonical_json,
)

MIN = 60_000
DAY = 86_400_000
#: 分身交件時說的那句話。中文 ⇒ 一定進得了 secrets（非 ASCII）。
HANDOVER = "我把那封給阿嬤的信寫好了，放在桌上"


@pytest.fixture()
def store(tmp_path: pathlib.Path):
    s = TwinStore(tmp_path / "t.sqlite3")
    yield s
    s.close()


def _chain_blob(store: TwinStore) -> str:
    return "\n".join(canonical_json(e["payload"]) for e in store.events())


def _sealed_person(st: TwinStore, sid: str, *, sub_ms: int, gen_ms: int,
                   handover: str = HANDOVER) -> None:
    """走**產品路徑**的封印（原文鏈外），時間戳可控。"""
    payload, secs = st.vault.seal_card(sid, {"need": "寫信給阿嬤"}, None,
                                       ts=sub_ms, ts_ms=sub_ms)
    twinvault.assert_sealed_shape(payload, "card")
    st.append(KIND_SUBMITTED, sid, payload, source="test", ts_unix_ms=sub_ms)
    twin = {"arrival": "我到了", "working": "在寫", "handover": handover,
            "engine": "fallback_deterministic"}
    payload, secs = st.vault.seal_twin(sid, twin)
    twinvault.assert_sealed_shape(payload, "twin")
    st.append(KIND_GENERATED, sid, payload, source="test", ts_unix_ms=gen_ms)


def _legacy_person(st: TwinStore, sid: str, *, sub_ms: int,
                   gen_ms: int | None) -> None:
    """2026-09-21 之前的寫法（原文在 payload）。只用來造時間形狀。"""
    st.append(KIND_SUBMITTED, sid, {"card": {"need": f"事:{sid}"}, "ts": sub_ms},
              source="test", ts_unix_ms=sub_ms)
    if gen_ms is not None:
        st.append(KIND_GENERATED, sid,
                  {"arrival": f"{sid} 到了", "working": "做",
                   "handover": f"{sid} 交件", "engine": "fallback_deterministic"},
                  source="test", ts_unix_ms=gen_ms)


# ---------------------------------------------------------------------------
# 缺陷一（高）：退役事件把分身的話明文寫上鏈
# ---------------------------------------------------------------------------

def _retire_everyone_but_one(store: TwinStore, now: int) -> None:
    """造「他」＋一位更新的觀眾，視窗只留 1 位 ⇒ 他被退役。"""
    _sealed_person(store, "他", sub_ms=now - 2 * DAY, gen_ms=now - 2 * DAY + 5)
    _legacy_person(store, "新來的", sub_ms=now - DAY, gen_ms=now - DAY + 5)
    v = twinlink.build_view(store, recent=1, record_retire=True, now_ms=now)
    assert v["counts"]["retired"] == 1, "前提沒成立：他應該被退役"


def test_negative_control_the_handover_really_is_readable(store: TwinStore) -> None:
    """負控制：他的那句話**確實存在、讀得到**——不然下面「鏈上找不到」沒有意義。"""
    now = 1_900_000_000_000
    _sealed_person(store, "他", sub_ms=now - DAY, gen_ms=now - DAY + 5)
    assert store.current("他")["twin"]["handover"] == HANDOVER
    assert HANDOVER not in _chain_blob(store), "封印前提壞了：生成那一列就上鏈了"


def test_retire_note_does_not_carry_plaintext(store: TwinStore) -> None:
    now = 1_900_000_000_000
    _retire_everyone_but_one(store, now)
    assert HANDOVER not in _chain_blob(store), \
        "🔴 退役事件把分身的話寫進 append-only 鏈了——撤回刪不掉"
    note = next(e for e in store.events(kind=KIND_NOTE)
                if e["payload"].get("twinlink_event") == twinlink.RETIRE_MARK)
    assert "farewell" not in note["payload"]


def test_retiring_still_plays_the_farewell_before_withdrawal(store: TwinStore) -> None:
    """正控制：修掉明文之後，退場那句話**畫面照樣拿得到**（從檔案庫讀）。"""
    now = 1_900_000_000_000
    _retire_everyone_but_one(store, now)
    v = twinlink.build_view(store, recent=1, now_ms=now + 1000)
    got = {r["id"]: r["farewell"] for r in v["retirement"]["retiring"]}
    assert got.get("他") == HANDOVER


def test_withdrawn_person_is_not_played_while_retiring(store: TwinStore) -> None:
    now = 1_900_000_000_000
    _retire_everyone_but_one(store, now)
    out = twinlink.withdraw(store, "他")
    assert out["ok"] is True
    v = twinlink.build_view(store, recent=1, now_ms=now + 1000)
    assert all(r["id"] != "他" for r in v["retirement"]["retiring"]), \
        "🔴 撤回之後 retiring[] 還在播他"
    assert HANDOVER not in repr(v)
    assert out["fully_erased"] is True, str(out)


def test_legacy_farewell_notes_are_reported_as_residual(store: TwinStore) -> None:
    """已經帶了 farewell 的舊 note 拿不掉 ⇒ 抹除證明**必須**把它列進殘留。"""
    now = 1_900_000_000_000
    _sealed_person(store, "他", sub_ms=now - DAY, gen_ms=now - DAY + 5)
    # 2026-09-24 修之前的碼寫出來的那一列，逐字形狀
    old = store.append(KIND_NOTE, "他", {
        "twinlink_event": twinlink.RETIRE_MARK, "farewell": HANDOVER,
        "reason": "場次輪替", "recent": 1, "stage_ms": now - DAY,
        "at": "2026-09-23T00:00:00+00:00", "screen_confirmed": None,
    }, source="local:twinlink.retire", ts_unix_ms=now - 1000)
    assert old["seq"] in twinvault.legacy_plaintext_seqs(store, "他")
    out = twinlink.withdraw(store, "他")
    assert old["seq"] in out["residual_plaintext_seqs"]
    assert out["fully_erased"] is False, "🔴 鏈上還有他的話，卻說完全刪掉了"
    # 舊 note 的原文也不可以再從 retiring[] 播出來
    v = twinlink.build_view(store, recent=1, now_ms=now)
    assert HANDOVER not in repr(v["retirement"])


# ---------------------------------------------------------------------------
# 缺陷二（中）：還沒生成就撤回的人永遠 arriving
# ---------------------------------------------------------------------------

def test_withdrawn_before_generation_is_not_arriving_forever(store: TwinStore) -> None:
    now = 1_900_000_000_000
    _legacy_person(store, "早走的", sub_ms=now - 3 * DAY, gen_ms=None)
    for i in range(3):
        _legacy_person(store, f"a{i}", sub_ms=now - DAY + i * MIN,
                       gen_ms=now - DAY + i * MIN + 5)
    twinlink.withdraw(store, "早走的")

    v = twinlink.build_view(store, recent=2, now_ms=now)
    assert v["counts"]["waiting"] == 0, "🔴 撤回的人被算成「還在等」"
    assert v["counts"]["arriving"] == 0, "🔴 撤回的人被標成正在抵達"
    assert len(v["people"]) == 2, "撤回的人不可以把視窗撐大"


def test_negative_control_a_real_arriving_person_still_counts(store: TwinStore) -> None:
    """負控制：**沒撤回**的 arriving 照樣必留——修法不可以一刀把 arriving 都砍掉。"""
    now = 1_900_000_000_000
    _legacy_person(store, "還在生成", sub_ms=now - 3 * DAY, gen_ms=None)
    for i in range(3):
        _legacy_person(store, f"a{i}", sub_ms=now - DAY + i * MIN,
                       gen_ms=now - DAY + i * MIN + 5)
    v = twinlink.build_view(store, recent=2, now_ms=now)
    assert any(p["id"] == "還在生成" and p["tier"] == "arriving" for p in v["people"])


# ---------------------------------------------------------------------------
# 缺陷三（中）：必留的 fresh 排在較新的 ambient 後面就上不了畫面
# ---------------------------------------------------------------------------

def _late_fresh_scene(store: TwinStore, now: int) -> None:
    # 30 分鐘前投卡、卡在生成裡、剛剛才生出來 ⇒ fresh
    _legacy_person(store, "卡很久的", sub_ms=now - 30 * MIN, gen_ms=now - 10_000)
    # 20／22 分鐘前投卡、早就生完 ⇒ ambient，但送出時間比他新
    _legacy_person(store, "A1", sub_ms=now - 20 * MIN, gen_ms=now - 19 * MIN)
    _legacy_person(store, "A2", sub_ms=now - 22 * MIN, gen_ms=now - 21 * MIN)


def test_fresh_behind_newer_ambient_is_shown(store: TwinStore) -> None:
    now = 1_900_000_000_000
    _late_fresh_scene(store, now)
    v = twinlink.build_view(store, recent=2, now_ms=now)
    ids = [p["id"] for p in v["people"]]
    assert "卡很久的" in ids, f"🔴 必留的 fresh 沒上畫面：{ids}"
    assert len(ids) == 2
    # 順序仍然是送出時間新到舊（保證那一條不能因為修這個而壞掉）
    subs = {"卡很久的": 30, "A1": 20, "A2": 22}
    assert [subs[i] for i in ids] == sorted(subs[i] for i in ids)


def test_fresh_is_not_retired_without_ever_being_shown(store: TwinStore) -> None:
    now = 1_900_000_000_000
    _late_fresh_scene(store, now)
    first = twinlink.build_view(store, recent=2, record_retire=True, now_ms=now)
    later = now + 16 * MIN   # 他變 ambient 了
    twinlink.build_view(store, recent=2, record_retire=True, now_ms=later)
    retired = {e["sub_id"] for e in store.events(kind=KIND_NOTE)
               if e["payload"].get("twinlink_event") == twinlink.RETIRE_MARK}
    # 缺陷的形狀：**fresh 那一整段都不在畫面上**，一變 ambient 就被退役。
    # 被退役本身不是缺陷（演過之後退場是正常的）；沒演過就退役才是。
    if "卡很久的" in retired:
        assert "卡很久的" in [p["id"] for p in first["people"]], \
            "🔴 他從沒上過畫面就被退役了"


def test_negative_control_prefix_order_would_bury_him(store: TwinStore) -> None:
    """負控制：照**送出時間**排，他確實排在兩位 ambient 後面（場景真的有那個形狀）。"""
    now = 1_900_000_000_000
    _late_fresh_scene(store, now)
    v = twinlink.build_view(store, recent=0, now_ms=now)   # 關窗：全部依序
    assert [p["id"] for p in v["people"]] == ["A1", "A2", "卡很久的"]
