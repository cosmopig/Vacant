#!/usr/bin/env python3
"""R467 自檢：`verify_lcb_bank.py` 的 probe 接線＋R466 普查的來源釘。

判準見 `DECISION_20260904_R467_VERIFY_LCB_BANK_PROBE_PATH_FIX.md` §五。
每個突變體的判準都寫「**偵測器該看到的那個量**」，不是 `rc != 0`
（memory：突變體放錯目錄害 import 失敗也是 rc≠0＝infra 壞掉被誤判成有牙齒）。

突變體一律透過環境變數在**被測函式內部**生效（memory：寫在模組層的突變體
永遠不生效，輸出長得跟「偵測條沒牙齒」一模一樣），且以 subprocess 跑**同一支**
正式腳本 —— 不是複製一份 —— 所以 import 環境與正式跑完全相同。

用法：python3 ops/gain/r467_selftest.py
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
VERIFY = ROOT / "ops/gain/verify_lcb_bank.py"
CENSUS = ROOT / "ops/gain/r466_r461_sec2_sec6_census.py"

FAILS: list[str] = []
N = 0


def ck(name: str, ok: bool, got: object = "") -> None:
    global N
    N += 1
    print(f"  [{'ok' if ok else 'FAIL'}] {name}" + (f"  → {got}" if not ok else ""))
    if not ok:
        FAILS.append(name)


def run_verify(version: str, mutant: str = "") -> tuple[int, dict, str]:
    env = dict(os.environ)
    env.pop("R467_MUTANT", None)
    if mutant:
        env["R467_MUTANT"] = mutant
    r = subprocess.run([sys.executable, str(VERIFY), "--version", version],
                       capture_output=True, text=True, cwd=ROOT, env=env)
    try:
        out = json.loads(r.stdout)
    except json.JSONDecodeError:
        out = {}
    return r.returncode, out, r.stderr


def run_census(mutant: str = "") -> tuple[int, dict]:
    env = dict(os.environ)
    env.pop("R466_MUTANT", None)
    if mutant:
        env["R466_MUTANT"] = mutant
    r = subprocess.run([sys.executable, str(CENSUS)],
                       capture_output=True, text=True, cwd=ROOT, env=env)
    try:
        return r.returncode, json.loads(r.stdout)
    except json.JSONDecodeError:
        return r.returncode, {}


def main() -> int:
    print("R467 selftest")

    # ── A 乾淨跑：三個 version 各自讀對檔 ──────────────────────────
    clean = {}
    for v, want_cov, want_bank, want_file in (
            ("v1", "12/91", "lcb", "lcb_probe_solutions.json"),
            ("v2", "12/120", "lcb2", "lcb_probe_solutions.json"),
            ("v3", "12/189", "lcb3", "lcb_v3_probe_solutions.json")):
        rc, o, _ = run_verify(v)
        clean[v] = (rc, o)
        ck(f"A {v} rc==0", rc == 0, rc)
        ck(f"A {v} probe_coverage=={want_cov}", o.get("probe_coverage") == want_cov,
           o.get("probe_coverage"))
        ck(f"A {v} probe_bank_name=={want_bank}", o.get("probe_bank_name") == want_bank,
           o.get("probe_bank_name"))
        ck(f"A {v} 讀的是 {want_file}",
           str(o.get("probe_solutions_path", "")).endswith(want_file),
           o.get("probe_solutions_path"))
        ck(f"A {v} 接線一致", o.get("probe_wiring_consistent") is True,
           o.get("probe_wiring_error"))

    # ── B 沒有突變體時不准有殘留（防「乾淨跑其實也在突變」）──────────
    ck("B 乾淨跑 v3 的 probe_wiring_error 是 None",
       clean["v3"][1].get("probe_wiring_error") is None)

    # ── M1 hardcode_v1v2：偵測器該看到的量＝v3 覆蓋率退回 0/189 ────────
    rc1, o1, _ = run_verify("v3", "hardcode_v1v2")
    ck("M1 v3 probe_coverage 退回 '0/189'（＝修復前的病徵）",
       o1.get("probe_coverage") == "0/189", o1.get("probe_coverage"))
    ck("M1 一致性擋門同時吐 PROBE_PATH_REPORT_MISMATCH",
       str(o1.get("probe_wiring_error", "")).startswith("PROBE_PATH_REPORT_MISMATCH"),
       o1.get("probe_wiring_error"))
    # 判準 §五「額外一條」：突變之下 rc **不變**（hard_fail 組成本輪刻意沒動）
    # ⇒ 就把「rc 不變」本身釘成判準，而不是沿用「rc 必須改判」。
    ck("M1 rc 仍為 0（hard_fail 組成沒動，這是刻意的，見 §五 額外一條）", rc1 == 0, rc1)

    # ── M2 always_v3：偵測器該看到的量＝v2 覆蓋率變 0/120 ─────────────
    rc2, o2, _ = run_verify("v2", "always_v3")
    ck("M2 v2 probe_coverage 變成 '0/120'", o2.get("probe_coverage") == "0/120",
       o2.get("probe_coverage"))
    ck("M2 v1 覆蓋率也一起壞（0/91）",
       run_verify("v1", "always_v3")[1].get("probe_coverage") == "0/91")

    # ── M3 report_mismatch：只翻「回報側」，不動「實際讀取側」 ──────────
    #    兩邊本來就不同源（ast 取出的路徑 vs 直接呼叫 gain_run._canonical_solutions），
    #    所以這條擋門看得見；若同源則它結構上不可能被任何夾具看見（memory r695）。
    rc3, o3, _ = run_verify("v3", "report_mismatch")
    ck("M3 吐 PROBE_PATH_REPORT_MISMATCH",
       str(o3.get("probe_wiring_error", "")).startswith("PROBE_PATH_REPORT_MISMATCH"),
       o3.get("probe_wiring_error"))
    ck("M3 probe_wiring_consistent 變 False", o3.get("probe_wiring_consistent") is False)
    ck("M3 覆蓋率仍是實際讀到的 12/189（＝證明翻的只有回報側）",
       o3.get("probe_coverage") == "12/189", o3.get("probe_coverage"))

    # ── M4 bad_inverse：要**吵**，不准安靜 fallback ────────────────────
    rc4, o4, _ = run_verify("v3", "bad_inverse")
    ck("M4 吐 PROBE_BANK_MAP_BROKEN",
       str(o4.get("probe_wiring_error", "")).startswith("PROBE_BANK_MAP_BROKEN"),
       o4.get("probe_wiring_error"))
    ck("M4 probe_coverage 是 null 而**不是** '0/189'"
       "（『沒量到』與『量到 0』必須分得開）",
       o4.get("probe_coverage") is None, o4.get("probe_coverage"))
    ck("M4 probe_task_ids 也是 null", o4.get("probe_task_ids") is None)

    # ── M5（在 r466 裡叫 M7_drop_source_pin）：拿掉來源釘就會 SOURCE_DRIFT ──
    rc5, c5 = run_census("M7_drop_source_pin")
    drift = c5.get("facts", {}).get("pins", {}).get("drift", [])
    # ⚠ 判準 §五 M5 原文寫的是「drift 含 `source:probe_path_hardcoded`」——**實測 MISS**。
    #   真正漂移的是 main() 裡那兩條，`probe_path_hardcoded` **沒有**漂移，
    #   因為 `PROBE_PATH = ...` 那一行本輪**刻意保留**（tests/test_lcb_bank_v2.py:20 匯入它）。
    #   ⇒ 原判準記 MISS（見 DECISION 附錄 A），這裡改釘語意上正確的量，
    #     並且把「為什麼那條沒漂移」也變成可測的，而不是用文字帶過。
    ck("M5 拿掉來源釘 ⇒ drift 恰為 main() 裡那兩條",
       sorted(drift) == ["source:coverage_expr", "source:coverage_uses_probe_path"], drift)
    _lit = 'PROBE_PATH = pathlib.Path(__file__).resolve().parent / "data" / "lcb_probe_solutions.json"'
    ck("M5 註腳：`PROBE_PATH = ...` 那行今天仍在 worktree（＝它沒漂移是刻意的，不是沒偵測到）",
       _lit in (ROOT / "ops/gain/verify_lcb_bank.py").read_text(encoding="utf-8"))
    ck("M5 拿掉來源釘 ⇒ verdict 變 SOURCE_DRIFT",
       c5.get("verdict") == "SOURCE_DRIFT", c5.get("verdict"))
    ck("M5 之下 source_pin_commit 記成 None（看得出釘被拿掉）",
       c5.get("facts", {}).get("pins", {}).get("source_pin_commit") is None)

    # ── M5 的反向：有釘的時候普查照樣 OK（＝釘不是把眼睛遮起來）────────
    rc6, c6 = run_census()
    ck("M5' 有釘時 verdict==OK 且 drift 為空",
       c6.get("verdict") == "OK" and not c6.get("facts", {}).get("pins", {}).get("drift"),
       (c6.get("verdict"), c6.get("facts", {}).get("pins", {}).get("drift")))
    ck("M5' 有釘時四條 source_pins 全對得上",
       all(c6.get("facts", {}).get("pins", {}).get("source_pins", {"x": False}).values()))

    print(f"\n收集數 {N} 條，失敗 {len(FAILS)} 條")
    if FAILS:
        for f in FAILS:
            print("  FAIL:", f)
        print("SELFTEST_FAIL")
        return 1
    print("SELFTEST_PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
