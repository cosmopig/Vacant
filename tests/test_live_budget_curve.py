"""活行重抽預算曲線的守衛（round 121，方向 B）。

鏡像 `ops/realrun/live_budget_curve.json` 由同一把尺（live_budget_curve.py）對
v4/v6/v7 三個已註冊批次的 progress.jsonl 產生：B_resample3 臂（可見測試失敗驅動、
乾淨重抽、max-attempts=3）按 n_attempts 分解的接受率（cap 1/2/3）。本測試：
  1. 輸入 pin（每個 progress.jsonl 的 sha256 對得上盤上檔案）；
  2. 鏡像 == 工具對同一輸入的即時重算（caps 逐項相等）；
  3. 描述性口徑釘死：descriptive_only=true、decision_state=null、scorer_used=false；
  4. 關鍵數字 pin（v7: A=45/170，B 各 cap 40/52/59；v6 與 v4 同形）；
  5. selftest（合成資料）須過。

這是描述性分解，不是新的 decision state：註冊的 A-vs-B 結論仍以各批次
analyze_v*.json 為準；三個批次不同模型/抽取，不得 pooling。
"""

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TOOL = REPO / "ops" / "realrun" / "live_budget_curve.py"
MIRROR = REPO / "ops" / "realrun" / "live_budget_curve.json"

import pytest


def _missing_inputs() -> list[str]:
    """鏡像 pin 的 progress.jsonl 哪些不在這台機器上（空＝齊全）。"""
    out: list[str] = []
    for b in json.loads(MIRROR.read_text(encoding="utf-8"))["batches"]:
        for p in b.get("input", []):
            f = Path(p["root"]) / "progress.jsonl"
            if not f.exists():
                out.append(str(f))
    return out


# 證據在 1003 dev VM 的磁碟上、這台機器沒有 ⇒ **沒量到（不是不合格）**，
# 照本庫慣例跳過（同 `test_citation_archive.py` 的 skipif；UNKNOWN，不是 PASS/FAIL）。
_MISSING_INPUTS = _missing_inputs()


def _tool():
    spec = importlib.util.spec_from_file_location("live_budget_curve", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _mirror() -> dict:
    return json.loads(MIRROR.read_text(encoding="utf-8"))


def _by_batch(m: dict) -> dict:
    return {b["batch"]: b for b in m["batches"]}


def test_selftest():
    r = subprocess.run(
        [sys.executable, str(TOOL), "--selftest"],
        capture_output=True, text=True, timeout=120,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "SELFTEST PASS" in r.stdout


@pytest.mark.skipif(
    bool(_MISSING_INPUTS),
    reason="輸入不在這台機器 ⇒ 沒量到（不是不合格）：" + "；".join(_MISSING_INPUTS[:3])
           + ("…（共 %d 個）" % len(_MISSING_INPUTS) if len(_MISSING_INPUTS) > 3 else ""),
)
def test_inputs_pinned():
    m = _mirror()
    assert m["schema"] == "vacant.realrun.live_budget_curve/1"
    for b in m["batches"]:
        assert b["input"], f"{b['batch']}: no input pins"
        for pin in b["input"]:
            p = Path(pin["root"]) / "progress.jsonl"
            assert p.exists(), f"missing {p}"
            assert hashlib.sha256(p.read_bytes()).hexdigest() == pin["progress_sha256"], \
                f"{b['batch']}: {p} changed after the mirror was written"


@pytest.mark.skipif(
    bool(_MISSING_INPUTS),
    reason="輸入不在這台機器 ⇒ 沒量到（不是不合格）：" + "；".join(_MISSING_INPUTS[:3])
           + ("…（共 %d 個）" % len(_MISSING_INPUTS) if len(_MISSING_INPUTS) > 3 else ""),
)
def test_mirror_matches_tool_rederivation():
    mod = _tool()
    m = _mirror()
    for b in m["batches"]:
        live = mod.curve(b["batch"], mod.load_cells(b["roots"]), b["meta"])
        assert b["caps"] == live["caps"], f"{b['batch']}: caps drifted"
        assert b["arm_a"] == live["arm_a"], f"{b['batch']}: arm_a drifted"
        assert b["arm_b"] == live["arm_b"], f"{b['batch']}: arm_b drifted"
        assert b["margins_pp"] == live["margins_pp"], f"{b['batch']}: margins drifted"


def test_honest_citable_shape():
    m = _mirror()
    assert m["descriptive_only"] is True
    assert "no decision state" in m["note"]
    for b in m["batches"]:
        assert b["descriptive_only"] is True
        assert b["decision_state"] is None
        assert b["scorer_used"] is False
        assert b["n_voids_excluded"] == 0  # v4/v6/v7 全部零 void；非零須先改本斷言並說明


def test_caps_monotone_and_counts_add_up():
    m = _mirror()
    for b in m["batches"]:
        caps = [b["caps"][k]["accepted"] for k in ("1", "2", "3")]
        assert caps == sorted(caps), f"{b['batch']}: caps not monotone"
        acc = b["arm_b"]["accepted_by_attempt"]
        assert sum(acc.values()) == b["arm_b"]["accepted"], f"{b['batch']}: accepted split"
        assert b["caps"]["1"]["accepted"] == acc.get("1", 0)
        assert b["caps"]["3"]["accepted"] == b["arm_b"]["accepted"]
        assert all(b["caps"][k]["n_cells"] == b["arm_b"]["n"] for k in ("1", "2", "3"))


def test_v7_key_numbers_pinned():
    b = _by_batch(_mirror())["v7"]
    assert b["n_reps"] == 5
    assert b["arm_a"]["n"] == 170 and b["arm_a"]["accepted"] == 45
    assert b["arm_b"]["n"] == 170 and b["arm_b"]["accepted"] == 59
    assert b["arm_b"]["accepted_by_attempt"] == {"1": 40, "2": 12, "3": 7}
    assert b["arm_b"]["rejected_by_attempt"] == {"3": 111}
    assert b["caps"]["1"]["pct"] == 23.53
    assert b["caps"]["2"]["pct"] == 30.59
    assert b["caps"]["3"]["pct"] == 34.71
    assert b["margins_pp"] == {"cap2_minus_cap1": 7.06, "cap3_minus_cap2": 4.12}
    assert b["meta"]["model"] == "gemma-4-12b-it-qat"
    assert b["meta"]["prereg_id"] == "v7_live_resample_crossmodel_34tasks_20261027"


def test_v6_key_numbers_pinned():
    b = _by_batch(_mirror())["v6"]
    assert b["n_reps"] == 5
    assert b["arm_a"]["n"] == 170 and b["arm_a"]["accepted"] == 87
    assert b["arm_b"]["accepted"] == 104
    assert b["arm_b"]["accepted_by_attempt"] == {"1": 88, "2": 12, "3": 4}
    assert b["caps"] == {
        "1": {"accepted": 88, "n_cells": 170, "pct": 51.76},
        "2": {"accepted": 100, "n_cells": 170, "pct": 58.82},
        "3": {"accepted": 104, "n_cells": 170, "pct": 61.18},
    }
    assert b["margins_pp"] == {"cap2_minus_cap1": 7.06, "cap3_minus_cap2": 2.35}
    assert b["meta"]["model"].startswith("qwen")


def test_v4_key_numbers_pinned():
    b = _by_batch(_mirror())["v4"]
    assert b["n_reps"] == 3
    assert b["arm_a"]["n"] == 102 and b["arm_a"]["accepted"] == 56
    assert b["arm_b"]["accepted"] == 66
    assert b["arm_b"]["accepted_by_attempt"] == {"1": 50, "2": 9, "3": 7}
    assert b["caps"] == {
        "1": {"accepted": 50, "n_cells": 102, "pct": 49.02},
        "2": {"accepted": 59, "n_cells": 102, "pct": 57.84},
        "3": {"accepted": 66, "n_cells": 102, "pct": 64.71},
    }
    assert b["margins_pp"] == {"cap2_minus_cap1": 8.82, "cap3_minus_cap2": 6.86}
