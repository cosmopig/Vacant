# -*- coding: utf-8 -*-
"""verify_effects_summary（r1333, vq-el4.53）：effects_20261105_summary.json 核數機械化。

背景：自 r1266 起「開啟 effects summary 並核數」的 redo 已重複 8 次以上
（r1268/r1272/r1274/r1275/r1279/r1280/r1281/r1283/r1330 redo），每次都靠人工
程式載入＋口頭記錄——漏核一項無人可偵測（H-0 同構：漏掉一項得到的綠燈就是
漏洞成因；I-4：未測量不是通過）。ops/reqloop/verify_effects_summary.py 把核數
收斂為單一指令、一個裁決行：
  identity / discipline / policy30_internal / once20_internal / totals / reference / scope_note

本測試即驗收＋負控制：
- 正控：live 檔 rc=0、VERDICT: EFFECTS_SUMMARY_OK、七項全 OK（狀態欄位判定，
  非子串——"OK" ⊂ "BROKEN"，r1271 測試自身假綠燈教訓）、sha 身份釘住、
  數字與人類任務參考值一致；
- 負控：總和漂移／分臂漂移／成本漂移／零格空集／成本字串／缺檔／scope_note
  弱化——全部必須 BROKEN 且 rc=1（任何一種削弱不得照綠）。

對 live 檔全唯讀（負控制只操作 tmp 副本，絕不碰原檔）；0 model calls；
subprocess 只用 [sys.executable, script]（無 python -c 片段，不觸及
test_reqloop_ci_contract.py 的安裝合約掃描範圍）。
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "ops" / "reqloop" / "verify_effects_summary.py"
LIVE = REPO / "ops" / "audits" / "effects_20261105_summary.json"

# 身份釘住：本檔是 2026-11-05 審計產物（r1266–r1330 每輪 redo 皆重算一致）。
# 任何改動應為人類決策＋新參考值，不是靜默漂移（同 frozen-anchors 身份守衛思路）。
EXPECTED_SHA256 = "a710f7e44cb7dcc79afbf90a445a9776e091850aa7aa10228e1c2844cdd3fda5"

MANDATED = (
    "identity",
    "discipline",
    "policy30_internal",
    "once20_internal",
    "totals",
    "reference",
    "scope_note",
)

# 人類參考值（2026-11-05 任務：policy30＝15 草稿×兩臂、once20＝10 錯誤草稿×兩臂各一輪；
# 2026-11-06 任務第 6 條：policy30 generic7/10、localized6/10；once20 generic7/10、
# localized4/10；皆為開發選樣單 rep，不宣稱 localized 較好）。
REFERENCE = {
    "policy30": {
        "cells": 30,
        "wrong_to_right": 13,
        "right_to_wrong": 0,
        "preserved_good": 10,
        "still_wrong": 7,
        "arm_w2r": {"generic": 7, "localized": 6},
        "repair_sessions_total": 35,
        "api_model_calls_true_total": 915,
        "tokens_true_total": 33670510,
        "local_matches": 27,
        "current_code_matches": 30,
    },
    "feedback_once20": {
        "cells": 20,
        "wrong_to_right": 11,
        "right_to_wrong": 0,
        "preserved_good": 0,
        "still_wrong": 9,
        "arm_w2r": {"generic": 7, "localized": 4},
        "repair_sessions_total": 20,
        "api_model_calls_true_total": 457,
        "tokens_true_total": 19503953,
        "local_matches": 18,
        "current_code_matches": 20,
    },
}


def _run(path: str | Path | None = None) -> subprocess.CompletedProcess[str]:
    cmd = [sys.executable, str(SCRIPT)]
    if path is not None:
        cmd.append(str(path))
    return subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=120)


def _load_module():
    assert SCRIPT.is_file(), f"缺少 {SCRIPT}（vq-el4.53 未落地）"
    spec = importlib.util.spec_from_file_location("verify_effects_summary_mod", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _status_lines(stdout: str) -> dict[str, str]:
    return {
        l.split()[0]: l
        for l in stdout.splitlines()
        if l.strip() and not l.startswith("VERDICT")
    }


def test_script_exists() -> None:
    assert SCRIPT.is_file(), f"缺少 {SCRIPT}（vq-el4.53 未落地）"


@pytest.fixture(scope="module")
def live_run() -> subprocess.CompletedProcess[str]:
    r = _run()
    assert r.returncode == 0, f"rc={r.returncode}\n{r.stdout}\n{r.stderr}"
    return r


def test_live_verdict_ok(live_run: subprocess.CompletedProcess[str]) -> None:
    assert "VERDICT: EFFECTS_SUMMARY_OK" in live_run.stdout, live_run.stdout


def test_live_covers_all_mandated(live_run: subprocess.CompletedProcess[str]) -> None:
    lines = _status_lines(live_run.stdout)
    missing = [k for k in MANDATED if k not in lines]
    assert not missing, f"缺少檢查項 {missing}\n{live_run.stdout}"
    # 必須比對狀態欄位（第 2 欄）而非子串——"OK" ⊂ "BROKEN"（r1271 教訓）。
    broken = [k for k in MANDATED if lines[k].split()[1] != "OK"]
    assert not broken, f"有檢查項非 OK: {broken}\n{live_run.stdout}"


def test_live_file_sha_pinned() -> None:
    sha = hashlib.sha256(LIVE.read_bytes()).hexdigest()
    assert sha == EXPECTED_SHA256, (
        f"effects summary 已改變：{sha[:16]}…（期望 {EXPECTED_SHA256[:16]}…）——"
        "改動應為人類決策＋新參考值，不是靜默漂移"
    )


def test_live_reference_numbers() -> None:
    """核數本身：live 檔逐項數字＝人類任務參考值（11-05 設計＋11-06 第 6 條）。"""
    d = json.loads(LIVE.read_text(encoding="utf-8"))
    for ph, ref in REFERENCE.items():
        p = d["phases"][ph]
        for key in ("cells", "wrong_to_right", "right_to_wrong", "preserved_good",
                    "still_wrong", "repair_sessions_total",
                    "api_model_calls_true_total", "tokens_true_total",
                    "local_matches", "current_code_matches"):
            assert p[key] == ref[key], f"{ph}.{key}: {p[key]} != {ref[key]}"
        for arm, w2r in ref["arm_w2r"].items():
            assert p["per_arm"][arm]["wrong_to_right"] == w2r, (
                f"{ph}.per_arm.{arm}.wrong_to_right: "
                f"{p['per_arm'][arm]['wrong_to_right']} != {w2r}"
            )
    assert d["total_cells"] == 50, d["total_cells"]
    assert d["local_matches_total"] == 45, d["local_matches_total"]
    assert d["current_code_matches_total"] == 50, d["current_code_matches_total"]


def test_live_verify_api_reports_all_ok() -> None:
    mod = _load_module()
    checks = mod.verify(LIVE)
    by_name = {name: (ok, detail) for name, ok, detail in checks}
    missing = [k for k in MANDATED if k not in by_name]
    assert not missing, f"verify() 缺少檢查項 {missing}"
    broken = [k for k in MANDATED if not by_name[k][0]]
    assert not broken, f"verify() 有項非 OK: {[(k, by_name[k][1]) for k in broken]}"


def _tampered(tmp_path: Path, mutate) -> Path:
    d = json.loads(LIVE.read_text(encoding="utf-8"))
    mutate(d)
    p = tmp_path / "tampered_effects_summary.json"
    p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return p


def _mutate_arm_drift(d: dict) -> None:
    """總和保持 13、只改分臂（localized w2r 一格→generic，generic still_wrong 一格→localized）：
    舊式「只對總和」核數照綠，per-arm 內部一致＋reference 必須抓出。"""
    cds = d["phases"]["policy30"]["cells_detail"]
    loc_w2r = next(c for c in cds
                   if c["arm"] == "localized"
                   and not c["before_pass_independent"] and c["after_independent"])
    gen_sw = next(c for c in cds
                  if c["arm"] == "generic"
                  and not c["before_pass_independent"] and not c["after_independent"])
    loc_w2r["arm"] = "generic"
    gen_sw["arm"] = "localized"


@pytest.mark.parametrize(
    ("label", "mutate", "expected_broken"),
    [
        # 相對於 cells 重算的總和漂移（13→14）
        ("summary_drift",
         lambda d: d["phases"]["policy30"].__setitem__("wrong_to_right", 14),
         "policy30_internal"),
        # 分臂漂移（總和不變）——守「計數守住但身份/分佈未守」（r1296 同型）
        ("arm_drift", _mutate_arm_drift, "policy30_internal"),
        # 成本總和漂移（915→916）
        ("cost_drift",
         lambda d: d["phases"]["policy30"].__setitem__("api_model_calls_true_total", 916),
         "policy30_internal"),
        # 零格空集：空 cells_detail 不得判 OK（I-4：未測量不是通過；r1272 同型）
        ("vacuous",
         lambda d: [d["phases"][ph].__setitem__("cells_detail", []) for ph in d["phases"]],
         "policy30_internal"),
        # 成本欄位變字串：缺值＝None 不填 0、更不得是字串（repair.py 不變量同口徑）
        ("cost_string",
         lambda d: d["phases"]["policy30"]["cells_detail"][0].__setitem__("repair_sessions", "1"),
         "discipline"),
        # scope_note 弱化（無硬 token 上限→有上限）：聲明被改寫必須照紅
        ("scope_weakened",
         lambda d: d.__setitem__("scope_note", d["scope_note"].replace("無硬 token 上限", "有 token 上限")),
         "scope_note"),
    ],
)
def test_negative_controls(tmp_path: Path, label: str, mutate, expected_broken: str) -> None:
    p = _tampered(tmp_path, mutate)
    r = _run(p)
    assert r.returncode == 1, f"{label}: rc=0 假綠燈\n{r.stdout}\n{r.stderr}"
    assert "VERDICT: EFFECTS_SUMMARY_BROKEN" in r.stdout, r.stdout
    lines = _status_lines(r.stdout)
    assert expected_broken in lines, f"{label}: 輸出缺 {expected_broken}\n{r.stdout}"
    assert lines[expected_broken].split()[1] == "BROKEN", (
        f"{label}: {expected_broken} 未判 BROKEN: {lines[expected_broken]}"
    )


def test_missing_file_broken(tmp_path: Path) -> None:
    r = _run(tmp_path / "nonexistent_effects_summary.json")
    assert r.returncode == 1, f"缺檔仍 rc=0 假綠燈\n{r.stdout}"
    assert "VERDICT: EFFECTS_SUMMARY_BROKEN" in r.stdout, r.stdout
