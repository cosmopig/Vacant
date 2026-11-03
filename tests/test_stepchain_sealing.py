"""步鏈分卷封印與校驗語義測試（DECISION_20261103_STEPCHAIN_SEALING.md Phase A：C1, C2, C6）。

G1–G4 補口（round 891 審查 DECISION_20261103_ROUND891_ARGON_PHASEA_REVIEW §3）：
- G1＝C1 的 30k-step 規模測試（本檔 chain30k fixture＋G1 測試）。
- G3＝C6 基準（30k-step verify ≤5s 實測；append P99 增量實測＋xfail 記錄未達）。
- G4＝負控制族別斷言（BROKEN 族 vs UNKNOWN 族）。
- G2＝真鏈驗收入庫（tests/test_stepchain_c2_realchain.py＋ops/stepchain/）。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time

import pytest

from vacant_network.intake import keys
from vacant_network.trace import recorder as R


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    keys.init_local()
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "data.csv").write_text("col\nval\n")
    return ws, R.Recorder(ws)


MAIN = R.Actor("pi", "s1")


def test_volume_seal_event_type_registered():
    assert "volume_seal" in R.EVENT_TYPES


def test_stepchain_sealing_c1_volume_split_and_verify(env):
    ws, rec = env
    # 設定較小的封印門檻便於快速測試
    rec.volume_max_entries = 5
    rec.compact_on_seal = False    # Phase A 語義：封印卷維持明文（.gz 路徑由 test_stepchain_phaseb 覆蓋）

    # 寫入 12 個 step 事件
    for i in range(12):
        rec.pre(f"t{i}", MAIN, "Write", {"file_path": f"f{i}.txt"})
        (ws / f"f{i}.txt").write_text(f"content {i}\n")
        rec.post(f"t{i}", MAIN, "Write", {"file_path": f"f{i}.txt"}, "ok")

    pdir = rec.dir
    sealed = sorted(pdir.glob("chain-*.ndjson"))
    # 預期至少有 2 個 sealed 卷，以及活動卷 chain.ndjson
    assert len(sealed) >= 2, f"Expected sealed volumes, got {sealed}"
    active_chain = pdir / "chain.ndjson"
    assert active_chain.is_file(), "Active chain.ndjson must exist"

    # 檢查每個 sealed 卷的尾筆皆為 volume_seal
    for s_path in sealed:
        lines = [json.loads(line) for line in s_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert lines, f"{s_path} is empty"
        last_entry = lines[-1]
        assert last_entry["type"] == "volume_seal"
        payload = last_entry["payload"]
        assert payload["sealed_file"] == s_path.name
        assert payload["entry_count"] == len(lines)
        assert "sha256_prefix" in payload

    # 驗章整條鏈全通
    ok, why = rec.verify()
    assert ok, f"verify failed: {why}"

    # 測試 verify_since 跨卷
    mark = None
    ok, why, mark = rec.verify_since(mark)
    assert ok, f"verify_since failed: {why}"
    assert mark is not None

    # 再追加一個 step，verify_since 應只驗新步並成功
    rec.pre("t_extra", MAIN, "Write", {"file_path": "extra.txt"})
    (ws / "extra.txt").write_text("extra\n")
    rec.post("t_extra", MAIN, "Write", {"file_path": "extra.txt"}, "ok")

    ok2, why2, mark2 = rec.verify_since(mark)
    assert ok2, f"verify_since extra failed: {why2}"
    assert mark2["seq"] > mark["seq"]


def test_stepchain_sealing_negative_controls(env):
    ws, rec = env
    rec.volume_max_entries = 4
    rec.compact_on_seal = False    # Phase A 語義：封印卷維持明文（.gz 路徑由 test_stepchain_phaseb 覆蓋）

    for i in range(8):
        rec.pre(f"t{i}", MAIN, "Write", {"file_path": f"f{i}.txt"})
        (ws / f"f{i}.txt").write_text(f"content {i}\n")
        rec.post(f"t{i}", MAIN, "Write", {"file_path": f"f{i}.txt"}, "ok")

    pdir = rec.dir
    sealed = sorted(pdir.glob("chain-*.ndjson"))
    assert sealed, "Need at least one sealed volume for negative controls"
    first_vol = sealed[0]

    # 負控制 1: 篡改 sealed 卷中某一筆內容 -> BROKEN
    original_bytes = first_vol.read_bytes()
    lines = original_bytes.splitlines()
    tampered_row = json.loads(lines[1])
    tampered_row["payload"]["tampered"] = True
    lines[1] = json.dumps(tampered_row).encode("utf-8")
    first_vol.write_bytes(b"\n".join(lines) + b"\n")

    ok, why = rec.verify()
    assert not ok, "Tampered sealed volume must fail verify"
    assert "does not verify" in why or "breaks" in why or "mismatch" in why

    # 復原
    first_vol.write_bytes(original_bytes)
    ok, why = rec.verify()
    assert ok, "Restored volume must verify"

    # 負控制 2: 刪除 sealed 卷的尾筆 volume_seal -> BROKEN
    lines_no_seal = lines[:-1]
    first_vol.write_bytes(b"\n".join(lines_no_seal) + b"\n")
    ok, why = rec.verify()
    assert not ok, "Missing volume_seal entry must fail verify"

    # 復原
    first_vol.write_bytes(original_bytes)

    # 負控制 3: 整卷遺失 -> 回 UNKNOWN / missing（不 crash、絕不返回 True）
    first_vol.unlink()
    ok, why = rec.verify()
    assert not ok, "Missing volume must fail verify"
    assert "UNKNOWN" in why or "missing" in why, f"Expected UNKNOWN/missing in why, got: {why}"


def test_stepchain_c2_backward_compatibility(env):
    ws, rec = env
    rec.compact_on_seal = False    # Phase A 語義：封印卷維持明文（.gz 路徑由 test_stepchain_phaseb 覆蓋）
    # 建立舊版無封印的單一 chain.ndjson
    for i in range(3):
        rec.pre(f"t{i}", MAIN, "Write", {"file_path": f"f{i}.txt"})
        (ws / f"f{i}.txt").write_text(f"content {i}\n")
        rec.post(f"t{i}", MAIN, "Write", {"file_path": f"f{i}.txt"}, "ok")

    # 確保目前沒有任何 chain-*.ndjson
    pdir = rec.dir
    assert not list(pdir.glob("chain-*.ndjson"))
    ok, why = rec.verify()
    assert ok, f"Initial legacy chain verify failed: {why}"

    # 升級：設置極小上限，在下一次 append 時應自動封印舊活動卷為 chain-000001.ndjson
    rec.volume_max_entries = 2
    rec.pre("t_next", MAIN, "Write", {"file_path": "next.txt"})
    (ws / "next.txt").write_text("next\n")
    rec.post("t_next", MAIN, "Write", {"file_path": "next.txt"}, "ok")

    sealed = sorted(pdir.glob("chain-*.ndjson"))
    assert len(sealed) >= 1, "Legacy chain should be sealed into chain-000001.ndjson"
    assert (pdir / "chain-000001.ndjson").is_file()

    ok, why = rec.verify()
    assert ok, f"Verify after sealing legacy chain failed: {why}"

def test_stepchain_sealing_gc_preserves_blobs_in_sealed_volumes(tmp_path, monkeypatch):
    vh = tmp_path / "vh"
    monkeypatch.setenv("VACANT_HOME", str(vh))
    keys.init_local(vh)
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "data.csv").write_text("col\nval\n")

    rec = R.Recorder(ws)
    rec.volume_max_entries = 4
    rec.compact_on_seal = False    # Phase A 語義：封印卷維持明文（.gz 路徑由 test_stepchain_phaseb 覆蓋）

    # 在第一卷產生一個較大的 output blob（觸發 _fit 存進 objects/）
    large_output = "LARGE_OUTPUT_IN_VOL_1_" + ("X" * 10000)
    rec.pre("t0", MAIN, "Write", {"file_path": "f0.txt"})
    (ws / "f0.txt").write_text("content 0\n")
    rec.post("t0", MAIN, "Write", {"file_path": "f0.txt"}, large_output)

    # 寫入後續步驟，把第一卷封印，產生新卷
    for i in range(1, 10):
        rec.pre(f"t{i}", MAIN, "Write", {"file_path": f"f{i}.txt"})
        (ws / f"f{i}.txt").write_text(f"content {i}\n")
        rec.post(f"t{i}", MAIN, "Write", {"file_path": f"f{i}.txt"}, "ok")

    pdir = rec.dir
    vols = sorted(pdir.glob("chain-*.ndjson"))
    assert len(vols) >= 2

    # 檢查第一卷是否包含 output_blob
    vol1_lines = (pdir / "chain-000001.ndjson").read_text(encoding="utf-8").splitlines()
    vol1_blobs = []
    for l in vol1_lines:
        row = json.loads(l)
        pl = row.get("payload") or {}
        if "output_blob" in pl:
            vol1_blobs.append(pl["output_blob"])
    assert vol1_blobs, "Vol 1 must contain output_blob"
    target_blob = vol1_blobs[0]
    target_blob_file = vh / "trace" / "objects" / target_blob[:2] / target_blob
    assert target_blob_file.is_file(), "Target blob must exist before GC"

    from vacant_network.retention import compact_trace, usage_report
    # 執行 compact_trace，不應誤刪第一卷的 output_blob
    compact_trace(vh)
    assert target_blob_file.is_file(), "Target blob in sealed volume must NOT be deleted by GC"

    # 檢查 usage_report 是否正確統計了多卷的總事件數
    rep = usage_report(root=vh)
    projects = rep.get("projects") or []
    assert len(projects) == 1
    # 總事件數應大於等於 12 步事件＋genesis＋seals
    assert projects[0].get("chain_events", 0) >= 12, f"chain_events underreported: {projects[0]}"


def test_stepchain_b1_volume_number_gap_must_not_overwrite(env):
    """B1（round 891 審查，DECISION_20261103_ROUND891_ARGON_PHASEA_REVIEW §7 門 3）：
    新封印卷號必須＝max(既有卷號)+1。若以 len(既有卷)+1，卷號出現缺口（Phase C 預算回收
    或整卷遺失後必然發生）時 len+1 會等於某既有卷號，os.replace 直接覆蓋已封印卷＝資料毀損。
    本測試：移除最小卷號（回收/遺失語義，與本檔負控制 3 同形）後續寫觸發新封印；
    既有最大卷號必須逐位元組不動，新封印必須落入 max+1（碰撞會同名覆蓋最大卷，故以最大卷為哨兵）。"""
    ws, rec = env
    rec.volume_max_entries = 4
    rec.compact_on_seal = False    # Phase A 語義：封印卷維持明文（.gz 路徑由 test_stepchain_phaseb 覆蓋）
    
    for i in range(12):
        rec.pre(f"t{i}", MAIN, "Write", {"file_path": f"f{i}.txt"})
        (ws / f"f{i}.txt").write_text(f"content {i}\n")
        rec.post(f"t{i}", MAIN, "Write", {"file_path": f"f{i}.txt"}, "ok")

    pdir = rec.dir
    sealed = sorted(pdir.glob("chain-*.ndjson"), key=lambda p: p.name)
    assert len(sealed) >= 2, f"need >=2 sealed volumes, got {len(sealed)}"
    top = sealed[-1]  # 既有最大卷號
    top_bytes = top.read_bytes()
    top_num = int(top.name.removeprefix("chain-").removesuffix(".ndjson"))

    # 移除最小卷號⇒卷號出現缺口（len 少 1，len+1 將等於某既有卷號）
    sealed[0].unlink()

    for i in range(12, 24):
        rec.pre(f"t{i}", MAIN, "Write", {"file_path": f"f{i}.txt"})
        (ws / f"f{i}.txt").write_text(f"content {i}\n")
        rec.post(f"t{i}", MAIN, "Write", {"file_path": f"f{i}.txt"}, "ok")

    sealed_now = sorted(p.name for p in pdir.glob("chain-*.ndjson"))
    assert top.read_bytes() == top_bytes, (
        f"B1: existing sealed volume {top.name} was OVERWRITTEN "
        f"(next_vol_num=len+1 collides with an existing volume number when a gap exists); "
        f"sealed={sealed_now}")
    expected_new = f"chain-{top_num + 1:06d}.ndjson"
    assert (pdir / expected_new).is_file(), (
        f"B1: new seal must go to {expected_new} (max existing + 1); got sealed={sealed_now}")
    tail = [json.loads(x) for x in (pdir / expected_new).read_text(encoding="utf-8").splitlines() if x.strip()]
    assert tail[-1]["type"] == "volume_seal", "new volume must end with its volume_seal"


def test_stepchain_sealing_set_aside_multivolume(env):
    """set_aside 必須一併處理所有封印卷（chain-*.ndjson / chain-*.ndjson.gz）。

    若只搬移活動卷 chain.ndjson，舊損壞封印卷仍留存於專案目錄中，
    下一次寫入建立新創世鏈後 verify 仍會載入舊封印卷導致永久 BROKEN，
    違反 set_aside '不能讓一條壞掉的鏈讓專案從此每一次都查不了' 之契約。"""
    ws, rec = env
    rec.volume_max_entries = 4
    rec.compact_on_seal = False

    for i in range(10):
        rec.pre(f"t{i}", MAIN, "Write", {"file_path": f"f{i}.txt"})
        (ws / f"f{i}.txt").write_text(f"content {i}\n")
        rec.post(f"t{i}", MAIN, "Write", {"file_path": f"f{i}.txt"}, "ok")

    pdir = rec.dir
    vols = list(pdir.glob("chain-*.ndjson"))
    assert len(vols) >= 2, f"need >= 2 sealed volumes, got {len(vols)}"

    # 竄改第一卷內容
    vols[0].write_bytes(b"tampered\n")
    ok, why = rec.verify()
    assert not ok, "verify must fail after tampering sealed volume"

    # 呼叫 set_aside 救回專案
    res = rec.set_aside(why)
    assert res, "set_aside must return a non-empty name"

    # 目錄下不應再殘存任何活動封印卷
    remaining_sealed = list(pdir.glob("chain-*.ndjson"))
    assert not remaining_sealed, f"sealed volumes must be set aside, got: {remaining_sealed}"
    assert not (pdir / "chain.ndjson").exists(), "active chain must be set aside"

    # 新寫入一筆事件，應成功建立全新創世並通過 verify
    rec.pre("t_after", MAIN, "Write", {"file_path": "after.txt"})
    (ws / "after.txt").write_text("after\n")
    rec.post("t_after", MAIN, "Write", {"file_path": "after.txt"}, "ok")

    ok2, why2 = rec.verify()
    assert ok2, f"verify must pass after set_aside and fresh start, but failed: {why2}"


def test_stepchain_sealing_set_aside_moves_gz_twins(env):
    """set_aside 必須一併搬走與明文同號的 `.gz` 卷（compact 半殘態：明文＋.gz 共存）。

    `compact_sealed_volume`（recorder.py:248-281）在 os.replace 後、刪原檔前失敗/中斷會留下
    `chain-NNNNNN.ndjson`＋`chain-NNNNNN.ndjson.gz` 共存——`_sealed_volume_paths` 的 docstring
    （recorder.py:305-323）明文承認此態存在且取明文。set_aside 若只依該去重 helper 搬明文，
    殘留 `.gz` 會使新創世鏈的 verify 永久 BROKEN，違反 set_aside「不能讓一條壞掉的鏈讓專案
    從此每一次都查不了」之契約。"""
    import gzip as _gz

    ws, rec = env
    rec.volume_max_entries = 4
    rec.compact_on_seal = False

    for i in range(6):
        rec.pre(f"t{i}", MAIN, "Write", {"file_path": f"f{i}.txt"})
        (ws / f"f{i}.txt").write_text(f"content {i}\n")
        rec.post(f"t{i}", MAIN, "Write", {"file_path": f"f{i}.txt"}, "ok")

    pdir = rec.dir
    vols = sorted(pdir.glob("chain-*.ndjson"))
    assert vols, f"need at least one sealed volume, got {sorted(pdir.iterdir())}"

    # 構造 compact 半殘態：第一卷的同號 .gz 在位（內容＝該卷明文之 gzip）
    v0 = vols[0]
    (v0.with_name(v0.name + ".gz")).write_bytes(_gz.compress(v0.read_bytes()))
    assert (v0.with_name(v0.name + ".gz")).is_file(), "precondition: .gz twin exists"

    res = rec.set_aside("test: gz twin must be set aside")
    assert res, "set_aside must return a non-empty name"

    remaining = [p.name for p in pdir.iterdir()
                 if p.name.startswith("chain-") and
                 (p.name.endswith(".ndjson") or p.name.endswith(".ndjson.gz"))]
    assert not remaining, f"all sealed volumes (incl. .gz twins) must be set aside, got: {remaining}"

    # 新創世鏈必須能正常 verify
    rec.pre("t_after", MAIN, "Write", {"file_path": "after.txt"})
    (ws / "after.txt").write_text("after\n")
    rec.post("t_after", MAIN, "Write", {"file_path": "after.txt"}, "ok")
    ok2, why2 = rec.verify()
    assert ok2, f"verify must pass after set_aside and fresh start, but failed: {why2}"



# ── G4 負控制（C1–C6 預註冊）：BROKEN 族與 UNKNOWN 族必須可區分、皆非 True ─────────
# Phase A 的 test_stepchain_sealing_negative_controls 已斷言「verify 失敗」；
# 本組補上預註冊要求的**族別**斷言：篡改/刪 seal 行＝BROKEN 族（非 UNKNOWN），
# 卷缺失＝UNKNOWN 族。損 .gz⇒BROKEN 非 UNKNOWN 見 test_stepchain_phaseb.py B-T2。
def test_g4_tamper_is_broken_family_not_unknown(env):
    """改封印卷一筆 ⇒ BROKEN 族（非 UNKNOWN、非 True）——C1–C6 預註冊負控制。"""
    ws, rec = env
    rec.volume_max_entries = 4
    rec.compact_on_seal = False
    for i in range(8):
        rec.pre(f"t{i}", MAIN, "Write", {"file_path": f"f{i}.txt"})
        (ws / f"f{i}.txt").write_text(f"content {i}\n")
        rec.post(f"t{i}", MAIN, "Write", {"file_path": f"f{i}.txt"}, "ok")
    first_vol = sorted(rec.dir.glob("chain-*.ndjson"))[0]
    assert rec.verify()[0]
    lines = first_vol.read_text().splitlines()
    row = dict(json.loads(lines[1]))
    row["payload"]["tampered"] = True
    lines[1] = json.dumps(row)
    first_vol.write_text("\n".join(lines) + "\n")
    ok, why = rec.verify()
    assert not ok, "tampered sealed volume must not verify True"
    assert "UNKNOWN" not in why.upper(), f"tamper is BROKEN-family, not missing: {why}"


def test_g4_delete_seal_line_is_broken_family_not_unknown(env):
    """刪封印卷的 seal 行 ⇒ BROKEN 族（非 UNKNOWN、非 True）——C1–C6 預註冊負控制。"""
    ws, rec = env
    rec.volume_max_entries = 4
    rec.compact_on_seal = False
    for i in range(8):
        rec.pre(f"t{i}", MAIN, "Write", {"file_path": f"f{i}.txt"})
        (ws / f"f{i}.txt").write_text(f"content {i}\n")
        rec.post(f"t{i}", MAIN, "Write", {"file_path": f"f{i}.txt"}, "ok")
    first_vol = sorted(rec.dir.glob("chain-*.ndjson"))[0]
    assert rec.verify()[0]
    lines = first_vol.read_text().splitlines()
    assert json.loads(lines[-1])["type"] == "volume_seal"
    first_vol.write_text("\n".join(lines[:-1]) + "\n")   # 刪 seal 行
    ok, why = rec.verify()
    assert not ok, "seal line deleted must not verify True"
    assert "UNKNOWN" not in why.upper(), f"seal deletion is BROKEN-family: {why}"


def test_g4_missing_volume_is_unknown_family(env):
    """封印卷缺失 ⇒ UNKNOWN 族（非 True）——C1–C6 預註冊負控制（L3 回收後即此形）。"""
    ws, rec = env
    rec.volume_max_entries = 4
    rec.compact_on_seal = False
    for i in range(8):
        rec.pre(f"t{i}", MAIN, "Write", {"file_path": f"f{i}.txt"})
        (ws / f"f{i}.txt").write_text(f"content {i}\n")
        rec.post(f"t{i}", MAIN, "Write", {"file_path": f"f{i}.txt"}, "ok")
    vols = sorted(rec.dir.glob("chain-*.ndjson"))
    assert len(vols) >= 2, f"need >=2 sealed volumes, got {vols}"
    assert rec.verify()[0]
    vols[0].unlink()                                        # 最舊封印卷缺失（模擬 L3 回收）
    ok, why = rec.verify()
    assert not ok, "missing volume must not verify True"
    assert "UNKNOWN" in why.upper(), f"missing volume must be UNKNOWN-family: {why}"


# ── G1（C1 規模）＋G3（C6 基準）────────────────────────────────────────────────
# C1 預註冊：合成 30k 步專案、無單檔 > VOLUME_MAX_BYTES、verify OK、verify_since 跨卷 OK、
# 篡改中段卷 ⇒ BROKEN、刪 seal 行 ⇒ BROKEN（非 UNKNOWN）。
# C6 預註冊：append P99 延遲增量 ≤10%（前後對照）；30k 步鏈 verify ≤5 s。
# 誠實邊界：30k 步 build 在本機約 4 分鐘（每筆 append fsync 為設計使然）——這是
# 預註冊規模的驗收成本，不另設跳過/縮小開關（縮小＝驗收打折）。

STEPS_30K = 30_000


@pytest.fixture(scope="module")
def chain30k(tmp_path_factory):
    """30k-step 合成專案（C1 規模），build 一次、G1/G3 共用。回傳度量 dict。"""
    vh = tmp_path_factory.mktemp("chain30k")
    ws = vh / "ws"
    ws.mkdir()
    old = os.environ.get("VACANT_HOME")
    os.environ["VACANT_HOME"] = str(vh)
    try:
        keys.init_local()
        rec = R.Recorder(ws)
        m30 = R.Actor("g1", "s1")
        rec.pre("w", m30, "Write", {"file_path": "f.txt"})
        rec.post("w", m30, "Write", {"file_path": "f.txt"}, "ok")
        t0 = time.perf_counter()
        step_ms = []
        for i in range(STEPS_30K):
            ta = time.perf_counter()
            rec.pre(f"t{i}", m30, "Write", {"file_path": f"f{i % 7}.txt"})
            rec.post(f"t{i}", m30, "Write", {"file_path": f"f{i % 7}.txt"}, "ok")
            step_ms.append((time.perf_counter() - ta) * 1000)
        build_s = time.perf_counter() - t0
        ok, why = rec.verify()
        t_v = time.perf_counter()
        ok_v, why_v = rec.verify()
        verify_s = time.perf_counter() - t_v
        ok_vs, why_vs, _mark = rec.verify_since(None)
        # 每個 .ndjson 檔的最大單行（＝單筆最大尺寸；封印最遲可超上限一筆）
        per_file = {}
        for p in rec.dir.iterdir():
            if p.name.endswith(".ndjson"):
                maxline = 0
                with open(p, "rb") as f:
                    for line in f:
                        if len(line) > maxline:
                            maxline = len(line)
                per_file[p.name] = {"bytes": p.stat().st_size, "max_line": maxline}
        step_ms.sort()
        yield {
            "rec": rec, "ws": ws, "home": vh,
            "build_s": build_s,
            "step_ms_p50": step_ms[len(step_ms) // 2],
            "step_ms_p99": step_ms[int(len(step_ms) * 0.99)],
            "verify_ok": ok, "verify_why": why,
            "verify_s": verify_s,
            "verify_since_ok": ok_vs, "verify_since_why": why_vs,
            "per_file": per_file,
        }
    finally:
        if old is not None:
            os.environ["VACANT_HOME"] = old
        else:
            os.environ.pop("VACANT_HOME", None)


def _fresh_home_copy(chain30k, tmp_path, label):
    """把 30k 鏈專案目錄複製到新 home（負控制用；不動共享鏈）。回傳 (rec, name)。"""
    name = chain30k["rec"].dir.name
    new_home = tmp_path / label
    (new_home / "trace" / "projects").mkdir(parents=True)
    shutil.copytree(chain30k["rec"].dir, new_home / "trace" / "projects" / name)
    old = os.environ.get("VACANT_HOME")
    os.environ["VACANT_HOME"] = str(new_home)
    return R.Recorder(chain30k["ws"]), name, old


def _restore_home(old):
    if old is not None:
        os.environ["VACANT_HOME"] = old
    else:
        os.environ.pop("VACANT_HOME", None)


def test_g1_c1_no_single_file_over_volume_max(chain30k):
    """C1：無單檔 > VOLUME_MAX_BYTES。封印檢查＝`sz >= 上限` 或 `行數 >= 上限`，
    故單檔至多超上限**一筆**（跨過門檻的那筆）；以該檔最大單行為界。"""
    per_file = chain30k["per_file"]
    sealed = {n: v for n, v in per_file.items() if n.startswith("chain-")}
    assert len(sealed) >= 10, f"30k steps should seal many volumes, got {len(sealed)}"
    for name, v in per_file.items():
        bound = R.DEFAULT_VOLUME_MAX_BYTES + v["max_line"]
        assert v["bytes"] <= bound, (
            f"{name} = {v['bytes']} B exceeds VOLUME_MAX_BYTES + one entry ({bound} B)")


def test_g1_c1_verify_and_verify_since_ok(chain30k):
    """C1：`vacant trace verify` OK＋verify_since 跨卷 OK（30k 步、多卷）。"""
    assert chain30k["verify_ok"], f"verify failed on 30k-step chain: {chain30k['verify_why']}"
    assert chain30k["verify_since_ok"], chain30k["verify_since_why"]
    # CLI 路徑（C1 點名 `vacant trace verify`）：cwd＝專案 ws、VACANT_HOME＝該 home
    r = subprocess.run(
        [sys.executable, "-m", "vacant_network.cli", "trace", "verify"],
        cwd=str(chain30k["ws"]),
        env={**os.environ, "VACANT_HOME": str(chain30k["home"])},
        capture_output=True, text=True, timeout=120,
    )
    assert r.returncode == 0, f"vacant trace verify CLI: rc={r.returncode}\n{r.stdout[-400:]}\n{r.stderr[-400:]}"


def test_g1_c1_tamper_middle_volume_is_broken_family(chain30k, tmp_path):
    """C1 負控制：篡改**中段卷**一筆 ⇒ BROKEN 族（非 UNKNOWN、非 True）。"""
    rec, _name, old = _fresh_home_copy(chain30k, tmp_path, "tamper_home")
    try:
        vols = sorted(rec.dir.glob("chain-*.ndjson"))
        assert len(vols) >= 3, f"need >=3 sealed volumes for a middle one, got {len(vols)}"
        assert rec.verify()[0], "precondition: chain verifies before tamper"
        mid = vols[len(vols) // 2]
        lines = mid.read_text(encoding="utf-8").splitlines()
        idx = len(lines) // 2
        row = dict(json.loads(lines[idx]))
        row["payload"]["tampered_by_test"] = True
        lines[idx] = json.dumps(row)
        mid.write_text("\n".join(lines) + "\n", encoding="utf-8")
        ok, why = rec.verify()
        assert not ok, "tampered middle volume must not verify True"
        assert "UNKNOWN" not in why.upper(), f"tamper is BROKEN-family, not missing: {why}"
    finally:
        _restore_home(old)


def test_g1_c1_delete_middle_seal_line_is_broken_family(chain30k, tmp_path):
    """C1 負控制：刪**中段卷**的 seal 行 ⇒ BROKEN 族（非 UNKNOWN、非 True）。"""
    rec, _name, old = _fresh_home_copy(chain30k, tmp_path, "noseal_home")
    try:
        vols = sorted(rec.dir.glob("chain-*.ndjson"))
        assert len(vols) >= 3, f"need >=3 sealed volumes for a middle one, got {len(vols)}"
        assert rec.verify()[0], "precondition: chain verifies before seal deletion"
        mid = vols[len(vols) // 2]
        lines = mid.read_text(encoding="utf-8").splitlines()
        assert json.loads(lines[-1])["type"] == "volume_seal"
        mid.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")   # 刪 seal 行
        ok, why = rec.verify()
        assert not ok, "middle volume seal line deleted must not verify True"
        assert "UNKNOWN" not in why.upper(), f"seal deletion is BROKEN-family: {why}"
    finally:
        _restore_home(old)


def test_g3_c6_verify_30k_under_5s(chain30k):
    """C6：30k 步鏈 verify ≤5 s（round 895 實測 ≈2.9 s）。"""
    assert chain30k["verify_ok"], chain30k["verify_why"]
    assert chain30k["verify_s"] <= 5.0, (
        f"30k-step verify took {chain30k['verify_s']:.2f}s > 5s (C6)")


# C6 append P99 增量：round 895 實測（本機、3000 步 A/B）＝base p99 5.81 ms vs
# after p99 8.71 ms ⇒ 增量 49.7% ＞ 10% 門檻——**未達**。成因（同輪 cProfile）：
# 封印事件本體（~55 ms/次、每 ~2000 筆一次）＋接近門檻時每次 append 的 O(檔大小)
# 行數掃描（6–9 ms 尾）。按 round 891 審查 §3 G3 的選項（「實測數據或明列未收口」），
# 此處以實測＋xfail 記錄；**Phase A 不因本項宣告完成**（誠實邊界，見該審查 §8）。
# 縮小尺度說明：P99 尾由封印門檻附近的局部行為決定，3000 步 A/B 與 30k 步同形；
# 30k 步的 after 分布另見 chain30k fixture 的 step_ms_p99。
@pytest.mark.xfail(
    strict=False,
    reason=("C6 append-P99 delta <=10% NOT MET on round-895 measurement "
            "(3000-step A/B: base p99 5.81ms vs after p99 8.71ms = +49.7%; "
            "seal event ~55ms + O(file-size) per-append scan near threshold). "
            "Recorded per round-891 review G3 alternative; Phase A not declared complete on C6."),
)
def test_g3_c6_append_p99_delta_le_10pct(tmp_path):
    """C6：append P99 延遲增量 ≤10%（前後對照）。before＝封印關閉（inf/None），
    after＝預設封印。同機、同荷、3000 步（尾局部性，見上方註）。"""

    def _p99_ms(n_steps, sealing):
        vh = tmp_path / ("ab_after" if sealing else "ab_base")
        ws = vh / "ws"
        ws.mkdir(parents=True)
        old = os.environ.get("VACANT_HOME")
        os.environ["VACANT_HOME"] = str(vh)
        try:
            keys.init_local()
            rec = R.Recorder(ws)
            if not sealing:
                rec.volume_max_bytes = float("inf")
                rec.volume_max_entries = None
            m = R.Actor("g3", "s1")
            for i in range(5):
                rec.pre(f"w{i}", m, "Write", {"file_path": "f.txt"})
                rec.post(f"w{i}", m, "Write", {"file_path": "f.txt"}, "ok")
            times = []
            for i in range(n_steps):
                t0 = time.perf_counter()
                rec.pre(f"t{i}", m, "Write", {"file_path": f"f{i % 5}.txt"})
                rec.post(f"t{i}", m, "Write", {"file_path": f"f{i % 5}.txt"}, "ok")
                times.append((time.perf_counter() - t0) * 1000)
        finally:
            _restore_home(old)
        times.sort()
        return times[int(len(times) * 0.99)]

    base = _p99_ms(3000, sealing=False)
    after = _p99_ms(3000, sealing=True)
    delta = (after - base) / base
    assert delta <= 0.10, (
        f"C6 P99 delta {delta * 100:.1f}% > 10% (base {base:.2f}ms, after {after:.2f}ms)")
