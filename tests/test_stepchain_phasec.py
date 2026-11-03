"""步鏈預算回收（L3）測試（DECISION_20261103_STEPCHAIN_SEALING.md Phase C：C4、C5）。

預註冊驗收（§6 Phase C：實作輪先寫失敗測試——TDD）：
- C4（回收）：明確預算下只回收超出 recency 窗的封印卷（活動卷／卷 1（創世）／
  最近 3 卷不動）；回收後 `verify` ⇒ UNKNOWN（非 True、非例外）；其後事件仍逐筆
  可驗；`volume_reclaimed` 事件在鏈上且有簽章。
- C5（零設定／fail-open）：全新狀態目錄預設路徑全通；無預算 ⇒ 零刪除。

L2 冷壓縮與 L3 回收正交：本檔 pin `compact_on_seal=False`（.gz 的負控制由
Phase B 的 test_stepchain_phaseb.py 獨立覆蓋，含「損 .gz⇒BROKEN」）。
"""
from __future__ import annotations

import contextlib
import os
import pathlib

import pytest

from vacant_network import retention
from vacant_network.intake import keys
from vacant_network.logbook import _signed_bytes
from vacant_network.trace import recorder as R


@pytest.fixture
def multi_volume(tmp_path, monkeypatch):
    """多封印卷專案（≥8 卷）。回傳 home/ws/rec/卷清單。"""
    vh = tmp_path / "vh"
    ws = vh / "ws"
    ws.mkdir(parents=True)
    monkeypatch.setenv("VACANT_HOME", str(vh))
    keys.init_local()
    rec = R.Recorder(ws)
    rec.compact_on_seal = False
    rec.volume_max_entries = 6          # 每 6 行封印一卷 ⇒ 60 步≈20 卷
    m = R.Actor("pc", "s1")
    for i in range(60):
        rel = f"f{i % 5}.txt"
        rec.pre(f"t{i}", m, "Write", {"file_path": rel})
        (ws / rel).write_text(f"content {i}\n")
        rec.post(f"t{i}", m, "Write", {"file_path": rel}, "ok")
    vols = sorted(rec.dir.glob("chain-*.ndjson"))
    assert len(vols) >= 8, f"need >=8 sealed volumes, got {len(vols)}"
    return {"home": vh, "ws": ws, "rec": rec, "vols": vols}


def _dir_bytes(p: pathlib.Path) -> int:
    total = 0
    if p.is_dir():
        for dirpath, _d, files in os.walk(p):
            for f in files:
                fp = pathlib.Path(dirpath) / f
                with contextlib.suppress(OSError):
                    total += fp.stat().st_size
    return total


def _protected_names(mv: dict) -> set[str]:
    """絕不動的卷：活動卷、卷 1（創世）、最近 3 卷（DEFAULT_KEEP_SET_ASIDE 鏡）。"""
    vols = mv["vols"]
    return {"chain.ndjson", vols[0].name, vols[-1].name, vols[-2].name, vols[-3].name}


def _target_bytes(mv: dict) -> int:
    """預算＝objects＋保護集（活動＋卷 1＋最近 3 卷）：超出部分必被回收。"""
    home, rec, vols = mv["home"], mv["rec"], mv["vols"]
    base = _dir_bytes(home / "trace" / "objects")
    base += rec.chain_path.stat().st_size
    for v in (vols[0], vols[-1], vols[-2], vols[-3]):
        base += v.stat().st_size
    return base


def _vol_num(name: str) -> int:
    return int(name.removeprefix("chain-").removesuffix(".ndjson"))


def _entry_signed_ok(e, who) -> bool:
    """逐筆簽章驗證（與鏈連續性無關）：其後事件仍逐筆可驗的判據。"""
    return who.verify(
        _signed_bytes(e.stream_id, e.branch_id, e.seq, e.prev_hash, e.ts_ms, e.type, e.payload),
        bytes.fromhex(e.sig),
    )


def _verifier_identity() -> "object":
    from vacant_network.identity import Identity, PublicIdentity
    me = keys.load_or_create("verifier")
    return PublicIdentity(vacant_id=me.vacant_id, pub=me.pub)


def _active_entries(rec: R.Recorder) -> list:
    from vacant_network.logbook import Logbook
    return Logbook.load(rec.chain_path).entries


def test_c4_event_type_registered():
    assert "volume_reclaimed" in R.EVENT_TYPES


def test_c4_reclaim_only_oldest_sealed_volumes(multi_volume):
    """C4：明確預算下只回收超出 recency 窗的封印卷；活動／卷 1／最近 3 卷不動。

    性質斷言（可偽反）：(a) 保護集全數存活；(b) ≥1 卷被回收；(c) 所有被回收卷的
    卷號 < 所有存活非保護卷的卷號——即「最舊優先、不跳級」。"""
    mv = multi_volume
    target = _target_bytes(mv)
    res = retention.compact_trace(dry_run=False, target_bytes=target)
    d = mv["rec"].dir
    prot = _protected_names(mv)
    for n in prot:
        assert (d / n).is_file(), f"protected volume must survive reclamation: {n}"
    before = {v.name for v in mv["vols"]}
    after = {p.name for p in d.glob("chain-*.ndjson")}
    reclaimed = before - after
    assert reclaimed, "tree over explicit budget must reclaim >=1 oldest sealed volume"
    assert res["volumes_reclaimed"] == len(reclaimed), res
    max_reclaimed = max(_vol_num(n) for n in reclaimed)
    for n in after - prot:
        assert _vol_num(n) > max_reclaimed, (
            f"reclaimed {sorted(reclaimed)} but newer non-protected volume {n} survived "
            f"(oldest-first violated)")


def test_c4_verify_unknown_after_reclaim_not_true_no_exception(multi_volume):
    """C4：回收後 `verify` ⇒ UNKNOWN（非 True、非例外）——缺卷是缺口，不是綠燈。"""
    mv = multi_volume
    res = retention.compact_trace(dry_run=False, target_bytes=_target_bytes(mv))
    assert res["volumes_reclaimed"] >= 1
    ok, why = mv["rec"].verify()
    assert not ok, "chain with reclaimed volumes must not verify True"
    assert "UNKNOWN" in why.upper(), f"missing (reclaimed) volume is UNKNOWN family: {why}"


def test_c4_volume_reclaimed_events_on_chain_and_signed(multi_volume):
    """C4：每筆回收在活動鏈上有 `volume_reclaimed`（卷名、first_seq–last_seq、預算），
    且逐筆簽章可驗——回收動作本身入鏈記責。"""
    mv = multi_volume
    target = _target_bytes(mv)
    res = retention.compact_trace(dry_run=False, target_bytes=target)
    n = res["volumes_reclaimed"]
    assert n >= 1
    who = _verifier_identity()
    entries = _active_entries(mv["rec"])
    recl = [e for e in entries if e.type == "volume_reclaimed"]
    assert len(recl) == n, f"expected {n} volume_reclaimed events, got {len(recl)}"
    before = {v.name for v in mv["vols"]}
    after = {p.name for p in mv["rec"].dir.glob("chain-*.ndjson")}
    reclaimed = before - after
    for e in recl:
        pl = e.payload or {}
        assert pl.get("volume") in reclaimed, f"event names an un-reclaimed volume: {pl}"
        assert isinstance(pl.get("first_seq"), int) and pl["first_seq"] >= 1
        assert isinstance(pl.get("last_seq"), int) and pl["last_seq"] >= pl["first_seq"]
        assert pl.get("target_bytes") == target
        assert _entry_signed_ok(e, who), f"volume_reclaimed event not validly signed: {pl}"
    # 其後事件仍逐筆可驗（回收後再追加一步；新事件簽章獨立可驗）
    m = R.Actor("pc", "s2")
    (mv["ws"] / "after.txt").write_text("after reclaim\n")
    mv["rec"].pre("a1", m, "Write", {"file_path": "after.txt"})
    mv["rec"].post("a1", m, "Write", {"file_path": "after.txt"}, "ok")
    tail = _active_entries(mv["rec"])
    assert tail[-1].type == "step"
    for e in tail:
        assert _entry_signed_ok(e, who), f"entry {e.seq} ({e.type}) failed per-entry signature check"


def test_c4_dry_run_reclaims_nothing_and_signs_nothing(multi_volume):
    mv = multi_volume
    res = retention.compact_trace(dry_run=True, target_bytes=_target_bytes(mv))
    d = mv["rec"].dir
    for v in mv["vols"]:
        assert v.is_file(), f"dry_run must not delete {v.name}"
    assert (d / "chain.ndjson").is_file()
    assert not [e for e in _active_entries(mv["rec"]) if e.type == "volume_reclaimed"], (
        "dry_run must not sign volume_reclaimed events")
    assert res.get("volumes_reclaimed", 0) == 0


def test_c5_no_budget_zero_deletion(multi_volume):
    """C5：無預算 ⇒ 零刪除（預設行為不改變；封印卷是記責記錄，GC 向來不碰）。"""
    mv = multi_volume
    res = retention.compact_trace(dry_run=False)          # target_bytes=None
    before = {v.name for v in mv["vols"]}
    after = {p.name for p in mv["rec"].dir.glob("chain-*.ndjson")}
    assert after == before, f"no budget ⇒ zero deletion; lost: {before - after}"
    assert res.get("volumes_reclaimed", 0) == 0
    assert mv["rec"].verify()[0], "no-budget gc must leave the chain fully verifiable"


def test_c5_fresh_state_dir_gc_runs_clean(tmp_path, monkeypatch):
    """C5：全新狀態目錄（無 trace/）預設路徑全通——報表同形、不例外。"""
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    rep = retention.gc_all(target_bytes=1)
    assert isinstance(rep, dict) and rep is not None
    assert "bytes_freed" in rep and "files_removed" in rep
