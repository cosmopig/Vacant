#!/usr/bin/env python3
"""R495 承重牆檢查：四個突變體，判準見
DECISION_20260905_R495_R486_R490_EMPIRICAL_CENSUS_PREREG.md §七（commit 4f9f4c1）。

每個突變體的偵測條寫的是「哪一個具名的量必須變成什麼」，**不是 rc≠0**
（rc≠0 也可能只是 infra 壞掉）。突變一律在被測函式**內部**呼叫時才讀旗標。

M3_NO_GLIVE 走的是 selftest（它拆的是守門，不是判別量）。
"""
from __future__ import annotations
import json, os, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOL = "ops/gain/r495_empirical_census.py"
# 突變體一律跑**真快照**：G-REPRO 是排在 G-CAL 前面的擋門，換小快照會讓
# verdict 先被 BROKEN_NO_REPRO 佔掉，M2／M4 的偵測條（判準 §七 寫死 BROKEN_CALIBRATION）
# 就永遠測不到 ⇒ 那會是「乾淨 PASS、植入缺陷仍 PASS」的假測試。


def run(mut, extra=()):
    env = dict(os.environ)
    if mut:
        env["R495_MUTANT"] = mut
    else:
        env.pop("R495_MUTANT", None)
    p = subprocess.run([sys.executable, TOOL, *extra], cwd=ROOT, env=env,
                       capture_output=True, text=True)
    return p


def census_json(mut):
    out = ROOT / f"/tmp/r495_mut_{mut or 'clean'}.json"
    p = run(mut, ("--json", str(out)))
    try:
        return json.loads(out.read_text()), p
    except Exception:
        return None, p


def main() -> int:
    results = {}

    # M1：只跑全視窗 ⇒ G-N 必須攔下來
    d, p = census_json("M1_NO_SUBWINDOWS")
    results["M1_NO_SUBWINDOWS"] = {
        "detected": bool(d) and d.get("verdict") == "BROKEN_WINDOWS",
        "observed": (d or {}).get("verdict"), "n_windows": (d or {}).get("n_windows"),
        "expected": "verdict == BROKEN_WINDOWS"}

    # M2：子視窗判決一律覆寫成全視窗判決 ⇒ 負對照必須倒
    d, p = census_json("M2_FORCE_SAME")
    results["M2_FORCE_SAME"] = {
        "detected": bool(d) and d.get("verdict") == "BROKEN_CALIBRATION"
                    and (d.get("calibration") or {}).get("C_NEG") != "EMPIRICAL_MOVABLE",
        "observed": (d or {}).get("verdict"), "C_NEG": ((d or {}).get("calibration") or {}).get("C_NEG"),
        "n_movable": (d or {}).get("n_movable"),
        "expected": "verdict == BROKEN_CALIBRATION 且 C_NEG != EMPIRICAL_MOVABLE"}

    # M3：拿掉 G-LIVE ⇒ selftest 的 C1_glive 必須 FAIL
    p = run("M3_NO_GLIVE", ("--selftest",))
    results["M3_NO_GLIVE"] = {
        "detected": "FAIL C1_glive" in p.stdout and p.returncode != 0,
        "observed": [l for l in p.stdout.splitlines() if "C1_glive" in l],
        "expected": "selftest C1_glive FAIL"}

    # M4：不再吐 EMPIRICAL_DEGENERATE ⇒ 正對照必須倒
    d, p = census_json("M4_NO_DEGENERATE")
    results["M4_NO_DEGENERATE"] = {
        "detected": bool(d) and d.get("verdict") == "BROKEN_CALIBRATION"
                    and (d.get("calibration") or {}).get("C_POS") != "EMPIRICAL_DEGENERATE",
        "observed": (d or {}).get("verdict"), "C_POS": ((d or {}).get("calibration") or {}).get("C_POS"),
        "expected": "verdict == BROKEN_CALIBRATION 且 C_POS != EMPIRICAL_DEGENERATE"}

    n = sum(1 for v in results.values() if v["detected"])
    print(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"{n}/{len(results)} behaved as prereg'd")
    return 0 if n == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
