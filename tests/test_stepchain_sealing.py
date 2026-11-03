"""步鏈分卷封印與校驗語義測試（DECISION_20261103_STEPCHAIN_SEALING.md Phase A：C1, C2）。"""
from __future__ import annotations

import json
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
