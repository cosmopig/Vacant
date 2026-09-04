#!/usr/bin/env python3
"""`analyze_r447.py` 的植入缺陷測試——每個突變體都要有**指名的**那一條看得見它。

判準（記憶鐵律：不准只寫 rc≠0）：
  每個突變體必須讓 selftest 失敗，**而且**失敗的標籤裡要出現這裡指名的那一條。
  只要「有東西紅了」不算抓到——那會把 infra 壞掉誤判成偵測器有牙齒。
  crash 收場也不算抓到（rc≠0 但沒有標籤 ⇒ 記 CRASH，不記 caught）。

突變體一律在被測函式**內部**生效（模組全域 `MUTANT`，函式呼叫當下才讀）：
  寫在模組層的突變體永遠不生效，而那個症狀跟「偵測條沒牙齒」長得一模一樣。
"""
from __future__ import annotations
import io, contextlib, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from ops.gain import analyze_r447 as A  # noqa: E402
from ops.gain import r447_reject_reconstruct as R  # noqa: E402
from ops.gain import r447_eq5_offline as Q  # noqa: E402

# 突變體 → 一定要紅的那一條的標籤前綴
EXPECT = {
    "M1_deliv_ignores_accepted":    "G accepted=False 不算交付",
    "M2_union_denominator":         "H n_common 排除單臂題",
    "M3_ignore_missing_fields":     "B 缺欄位 ⇒ BROKEN",
    "M4_ignore_row_accounting":     "C rows+void!=processed ⇒ BROKEN",
    "M5_ignore_terminal":           "D run_terminal=False ⇒ BROKEN",
    "M6_pz2_holds_ignores_direction": "I3 c>=b/2",
    "M7_pz6_only_conform":          "F4 P-Z6 掃全部臂不只 CONFORM",
    "M8_pz5b_pass":                 "K P-Z5b",
    "M9_drop_overturn":             "F2 P-Z6 反例 ⇒ 觸發推翻條件",
    "M10_widen_windows":            "J3 P-Z4 2.21 是 MISS",
    "M11_power_off5_uses_off_pair": "P2 OFF5 那格的 MDE 餵的是 OFF5 自己的配對",
}

# `r447_reject_reconstruct.py` 的突變體 → 一定要紅的那一條
EXPECT_RECON = {
    "M1_skip_calibration":     "R7 校準對不上 ⇒ BROKEN",
    "M3_count_all_candidates": "R5 被丟掉的候選數＝可見沒過的候選數",
}


# `r447_eq5_offline.py`（R452）的突變體 → 一定要紅的那一條
EXPECT_EQ5OFF = {
    "X1_gate_takes_last":            "E7 規則 A 取第一個可見通過的",
    "X2_gate_reject_counts_as_deliv": "E8 五份全不過 ⇒ 拒交",
    "X3_skip_order_check":           "E3 候選順序與 involved 不符 ⇒ BROKEN",
    "X4_skip_calibration":           "E4 校準對不上 ⇒ BROKEN",
    "X5_skip_min_calib":             "E5 UNCALIBRATED",
    "X6_emit_delta_when_broken":     "E11 UNCALIBRATED 時不吐 Δ",
    "X7_skip_candidate_count":       "E2 候選數不是 5 ⇒ BROKEN",
    "X8_deliv_ignores_accepted":     "E9 規則 B 讀 rows 的 accepted",
    "X9_include_failed_calls":       "E2b 失敗的請求不算候選",
    "X10_ignore_missing_fields":     "E1 缺欄位 ⇒ BROKEN",
}


def run(mutant: str, mod=A) -> tuple[int, list[str]]:
    mod.MUTANT = mutant
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = mod.selftest()
    except Exception as e:                      # noqa: BLE001
        mod.MUTANT = ""
        return 2, [f"CRASH:{type(e).__name__}:{e}"]
    fails = list(mod.LAST_FAILS)
    mod.MUTANT = ""
    return rc, fails


def main() -> int:
    bad = []
    marks = []
    for mod, table, label in ((A, EXPECT, "analyze_r447"),
                              (R, EXPECT_RECON, "reject_reconstruct"),
                              (Q, EXPECT_EQ5OFF, "eq5_offline")):
        rc0, f0 = run("", mod)
        if rc0 != 0 or f0:
            print(f"BASELINE FAIL [{label}] rc={rc0} fails={f0}")
            return 1
        print(f"baseline [{label}] (MUTANT=none) SELFTEST PASS")
        _check(mod, table, marks, bad)
    print("MUTATION " + ("PASS" if not bad else "FAIL") + " caught=" + " ".join(marks))
    for b in bad:
        print("  " + b)
    return 0 if not bad else 1


def _check(mod, table, marks, bad) -> None:
    for m, want in table.items():
        rc, fails = run(m, mod)
        named = any(x.startswith(want) for x in fails)
        crashed = any(x.startswith("CRASH:") for x in fails)
        ok = (rc != 0) and named and not crashed
        marks.append(f"{m}:{'Y' if ok else 'N'}")
        if not ok:
            bad.append(f"{m} rc={rc} 指名條={want!r} 實際失敗={fails}")


if __name__ == "__main__":
    sys.exit(main())
