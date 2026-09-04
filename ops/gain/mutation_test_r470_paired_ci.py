#!/usr/bin/env python3
"""R470：`paired_ci.py` 的植入缺陷測試。判準 `DECISION_20260904_R470_PAIRED_CI_TEETH_PREREG.md`
（`069f2d9`，本檔之前 commit）。突變體清單、偵測器集合、判決規則、事前預測都在那裡。

⚠ 源碼級突變，不是 env 旗標：`paired_ci.py` 的 `MUTANT` 只在 `__main__` 才從 env 讀
（模組層 `MUTANT = ""`）⇒ 被 import 時 env 旗標永遠不生效。

用法：python3 ops/gain/mutation_test_r470_paired_ci.py --worktree ~/vacant/wt_r470 [--json out]
"""
from __future__ import annotations
import argparse, hashlib, json, pathlib, subprocess, sys

REL = "ops/gain/replay/paired_ci.py"

# --- D5 的期望值：出自 R461 附錄 C.4 原文（判準 §二），不是本輪產生的基線 ---------
D5_EXPECT = {
    ("CONFORM", "OFF"): dict(n_paired=120, b_discordant_a_only=31, c_discordant_b_only=8,
                             delta_pp=19.17, ci95_lo_pp=8.80, ci95_hi_pp=26.46,
                             p_mcnemar_exact=0.0003, verdict="ON_WINS"),
    ("OFF5", "OFF"):    dict(n_paired=120, b_discordant_a_only=22, c_discordant_b_only=7,
                             delta_pp=12.50, ci95_lo_pp=3.12, ci95_hi_pp=19.19,
                             p_mcnemar_exact=0.0081, verdict="ON_WINS"),
}
D5_RUN = "runs/g_r447_conform_lcb2"

# --- 突變體：(名字, 逐字舊字串, 新字串)。每個都必須在檔裡恰好出現 1 次，否則 ABORT ---
V_OLD = '    if lo_pp > 0:\n        return "ON_WINS"\n    if hi_pp <= PRACTICAL_PP:\n        return "RULED_OUT"\n'
V_NEW = '    if lo_pp > 0:\n        return "RULED_OUT"\n    if hi_pp <= PRACTICAL_PP:\n        return "ON_WINS"\n'
BC_OLD = ('    b = sum(1 for t in common if ok(A[t]) and not ok(B[t]))\n'
          '    c = sum(1 for t in common if ok(B[t]) and not ok(A[t]))\n')
BC_SWAP = ('    b = sum(1 for t in common if ok(B[t]) and not ok(A[t]))\n'
           '    c = sum(1 for t in common if ok(A[t]) and not ok(B[t]))\n')
N1_OLD = '    b = sum(1 for t in common if ok(A[t]) and not ok(B[t]))\n'
N1_NEW = '    b = len([t for t in common if ok(A[t]) and not ok(B[t])])\n'
B1_OLD = '    """回傳 delta 的點估計與 95% 精確條件區間（單位：比例，非 pp）。"""\n'
B1_NEW = B1_OLD + '    this line is not python at all\n'

MUTANTS = [
    ("M1", 'if MUTANT == "M1":', 'if True:'),
    ("M2", 'if MUTANT == "M2":', 'if True:'),
    ("M3", V_OLD, V_NEW),
    ("M4", '    if lo_pp > 0:\n', '    if lo_pp >= 0:\n'),
    ("M5", '    if lo_pp > 0:\n', '    if hi_pp > 0:\n'),
    ("M6", '    if n < MIN_PAIRED:\n', '    if n < 0:\n'),
    ("M7", BC_OLD, BC_SWAP),
    ("M8", 'if os.environ.get("MUTANT") == "M_KEY":', 'if True:'),
    ("M9", '    for m in range(n, MAX_N_SEARCH + 1):\n', '    for m in range(1, MAX_N_SEARCH + 1):\n'),
    ("N1", N1_OLD, N1_NEW),
    ("B1", B1_OLD, B1_NEW),
]

# --- 偵測器（判準 §二，集合封閉） ------------------------------------------------
DETECTORS = [
    ("D1", ["python3", "ops/gain/replay/paired_ci.py", "--selftest"]),
    ("D2", ["python3", "ops/gain/replay/r463_key_teeth_test.py"]),
    ("D3", ["python3", "ops/gain/replay/pooled_paired_ci.py", "--selftest"]),
    ("D4", ["python3", "ops/gain/r462_r461_census.py", "--selftest"]),
    ("D6", ["python3", "ops/gain/replay/conform_settle_ci_selftest.py",
            "--run", "runs/g_r444_conform_mbpp", "--work", "/dev/shm/r470/d6"]),
]
BROKEN_MARKS = ("SyntaxError", "Traceback (most recent call last)", "ImportError", "IndentationError")


def run_cmd(cmd, cwd, timeout=600):
    p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout + p.stderr)


def detector_state(name, cmd, wt):
    rc, out = run_cmd(cmd, wt)
    broken = any(m in out for m in BROKEN_MARKS)
    return {"rc": rc, "red": rc != 0, "broken": broken,
            "tail": out.strip().splitlines()[-1][:160] if out.strip() else ""}


def d5_state(wt):
    """真資料回歸見證：逐欄比對 C.4 釘死的八個數字。"""
    fields = []
    broken = False
    for (a, b), exp in D5_EXPECT.items():
        jp = pathlib.Path("/dev/shm/r470") / f"d5_{a}_{b}.json"
        jp.parent.mkdir(parents=True, exist_ok=True)
        if jp.exists():
            jp.unlink()
        rc, out = run_cmd(["python3", "ops/gain/replay/paired_ci.py", "--run", D5_RUN,
                           "--a-arm", a, "--b-arm", b, "--key", "deliv",
                           "--json", str(jp)], wt)
        if rc != 0 or not jp.exists():
            broken = broken or any(m in out for m in BROKEN_MARKS)
            fields.append(f"{a}v{b}:rc={rc}")
            continue
        got = json.loads(jp.read_text(encoding="utf-8"))
        for k, want in exp.items():
            g = got.get(k)
            if isinstance(want, float):
                nd = 4 if k == "p_mcnemar_exact" else 2
                bad = g is None or round(float(g), nd) != round(want, nd)
            else:
                bad = g != want
            if bad:
                fields.append(f"{a}v{b}.{k}={g}(want {want})")
    return {"rc": 1 if fields else 0, "red": bool(fields), "broken": broken,
            "tail": "; ".join(fields)[:400] if fields else "逐欄相同"}


def all_detectors(wt):
    st = {n: detector_state(n, c, wt) for n, c in DETECTORS}
    st["D5"] = d5_state(wt)
    return st


def classify(st):
    red = [n for n, s in st.items() if s["red"]]
    if not red:
        return "MISSED", []
    clean_red = [n for n in red if not st[n]["broken"]]
    if not clean_red:
        return "BROKEN", red
    return "DETECTED", sorted(clean_red)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--worktree", required=True)
    ap.add_argument("--json")
    a = ap.parse_args()
    wt = pathlib.Path(a.worktree).expanduser().resolve()
    tgt = wt / REL
    orig = tgt.read_text(encoding="utf-8")
    orig_sha = hashlib.sha256(orig.encode()).hexdigest()

    print(f"== 目標 {tgt}  sha256={orig_sha[:16]}")
    print("== 前置條件 §五-1／§五-3：乾淨基線 ==")
    base = all_detectors(wt)
    for n in sorted(base):
        print(f"  {n}: rc={base[n]['rc']} red={base[n]['red']} | {base[n]['tail']}")
    if any(s["red"] for s in base.values()):
        print("ABORT §五：乾淨基線不是全綠，不准往下量")
        return 2

    results = {}
    for name, old, new in MUTANTS:
        if orig.count(old) != 1:
            print(f"ABORT：{name} 的錨點在檔裡出現 {orig.count(old)} 次（必須恰好 1）")
            return 2
        try:
            tgt.write_text(orig.replace(old, new), encoding="utf-8")
            st = all_detectors(wt)
            verdict, red = classify(st)
            results[name] = {"verdict": verdict, "red": red,
                             "detail": {n: st[n]["tail"] for n in red}}
            print(f"  {name}: {verdict:9s} 紅的是 {red}")
            for n in red:
                print(f"        {n}: {st[n]['tail']}")
        finally:
            tgt.write_text(orig, encoding="utf-8")
            back = hashlib.sha256(tgt.read_text(encoding='utf-8').encode()).hexdigest()
            if back != orig_sha:
                print(f"ABORT §五-2：{name} 還原失敗 sha={back[:16]}")
                return 2

    # 總判決（判準 §四，先寫死）
    ms = [n for n in results if n.startswith("M")]
    missed = [n for n in ms if results[n]["verdict"] == "MISSED"]
    if results["N1"]["verdict"] == "DETECTED" or results["B1"]["verdict"] == "DETECTED":
        overall = "BROKEN_CALIBRATION"
    elif len(missed) >= 5:
        overall = "NO_TEETH"
    elif missed:
        overall = "PARTIAL_TEETH"
    else:
        overall = "HAS_TEETH"
    print(f"\n== 總判決 {overall}   MISSED={missed}")
    out = {"target_sha256": orig_sha, "baseline": base, "mutants": results,
           "missed": missed, "overall": overall}
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
