#!/usr/bin/env python3
"""R500：R496 兩道擋門的**承重牆刪除測試**。
判準先行：DECISION_20260905_R500_R496_WALL_DELETION_PREREG.md（commit 4d655e8）。

env 旗標突變體答不了「刪掉正式那兩行會不會紅」；本尺把整段**實體刪掉**再重跑
`r496_mutation_check.py`，在 git worktree 的獨立副本上動刀（不碰工作目錄）。

用法：
  python3 ops/gain/r500_wall_deletion.py --selftest
  python3 ops/gain/r500_wall_deletion.py --worktree /dev/shm/r500wt [--json <path>]
"""
from __future__ import annotations
import argparse, json, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
REL = "ops/gain/r496_equal_n_windows.py"
CHECK = "ops/gain/r496_mutation_check.py"

# 判準 §一：逐字錨點，各須恰好出現 1 次
WALLS = {
    "W1": ('    if out["n_windows"] != N_WINDOWS_EXPECTED:\n'
           '        out["blockers"].append("BROKEN_WINDOWS")\n'),
    "W2": ('    if out["calibration"]["C_POS"] != "NEITHER" or '
           'out["calibration"]["C_NEG"] != "N_MATTERS":\n'
           '        out["blockers"].append("BROKEN_CALIBRATION")\n'),
}
WALL_OF_MUT = {"M1_ONE_POSITION": "W1", "M2_FORCE_SAME": "W2"}


def cut(src: str, block: str) -> str:
    """判準 §一：錨點必須恰好 1 次，否則不准動刀。"""
    n = src.count(block)
    if n != 1:
        raise ValueError(f"anchor count = {n}, expected 1")
    i = src.index(block)
    return src[:i] + src[i + len(block):]


def run_check(wt: pathlib.Path) -> dict:
    p = subprocess.run([sys.executable, CHECK], cwd=str(wt), capture_output=True,
                       text=True, timeout=900)
    out = p.stdout + p.stderr
    # 判準 §二.5：crash 不算偵測到
    broken = ("Traceback (most recent call last)" in out) or ("SyntaxError" in out)
    det = {}
    try:
        body = json.loads(out[out.index("{"):out.rindex("}") + 1])
        det = {k: bool(v.get("detected")) for k, v in body.items()}
    except Exception:
        broken = True
    return {"rc": p.returncode, "broken": broken, "detected": det, "raw_tail": out[-400:]}


def analyse(baseline: dict, cuts: dict) -> dict:
    """純函式：夾具可獨立設定 baseline 與每一格的結果。"""
    res = {"walls": {}, "specificity": {}, "n_broken_cut": 0}
    muts = sorted(WALL_OF_MUT)
    if baseline.get("broken") or not all(baseline.get("detected", {}).get(m) for m in muts):
        res["verdict"] = "BASELINE_BROKEN"
        res["baseline_detected"] = baseline.get("detected")
        return res
    for wall in sorted(WALLS):
        r = cuts.get(wall, {})
        if r.get("broken"):
            res["walls"][wall] = "BROKEN_CUT"
            res["n_broken_cut"] += 1
            continue
        own = [m for m, w in WALL_OF_MUT.items() if w == wall][0]
        still = bool(r.get("detected", {}).get(own))
        res["walls"][wall] = "STILL_RED_ELSEWHERE" if still else "LOAD_BEARING"
        for m, w in WALL_OF_MUT.items():          # 判準 §二.4：專一性負對照
            if w != wall:
                res["specificity"][f"cut_{wall}_keeps_{m}"] = bool(r.get("detected", {}).get(m))
    res["baseline_detected"] = baseline.get("detected")
    if res["n_broken_cut"]:
        res["verdict"] = "BROKEN_CUT_PRESENT"
    elif all(v == "LOAD_BEARING" for v in res["walls"].values()) and all(res["specificity"].values()):
        res["verdict"] = "ALL_WALLS_LOAD_BEARING"
    else:
        res["verdict"] = "SOME_WALL_NOT_LOAD_BEARING"
    return res


def main_run(wt: pathlib.Path) -> dict:
    tgt = wt / REL
    clean = tgt.read_text(encoding="utf-8")
    baseline = run_check(wt)
    cuts = {}
    for wall, block in WALLS.items():
        try:
            tgt.write_text(cut(clean, block), encoding="utf-8")
            cuts[wall] = run_check(wt)
        except ValueError as e:
            cuts[wall] = {"broken": True, "detected": {}, "raw_tail": f"anchor: {e}"}
        finally:
            tgt.write_text(clean, encoding="utf-8")      # 一律還原
    out = analyse(baseline, cuts)
    out["baseline_raw_tail"] = baseline.get("raw_tail")
    out["cut_detail"] = {k: {"rc": v.get("rc"), "detected": v.get("detected")}
                         for k, v in cuts.items()}
    return out


def selftest() -> int:
    fails = []

    def chk(n, c):
        if not c:
            fails.append(n)

    # cut：錨點必須恰好 1 次
    src = "a\nXX\nb\n"
    chk("cut_ok", cut(src, "XX\n") == "a\nb\n")
    for bad in ("ZZ\n", ):
        try:
            cut(src, bad)
            fails.append("cut_missing_should_raise")
        except ValueError:
            pass
    try:
        cut("XX\nXX\n", "XX\n")
        fails.append("cut_dup_should_raise")
    except ValueError:
        pass
    # 真檔上的錨點各恰好 1 次（前置尺：錨點過期要 BROKEN 不是安靜跳過）
    real = (ROOT / REL).read_text(encoding="utf-8")
    for w, b in WALLS.items():
        chk(f"anchor_{w}", real.count(b) == 1)

    ok = {"broken": False, "detected": {"M1_ONE_POSITION": True, "M2_FORCE_SAME": True}}
    # 兩面牆都承重 + 專一性全過 ⇒ ALL_WALLS_LOAD_BEARING
    good = analyse(ok, {
        "W1": {"broken": False, "detected": {"M1_ONE_POSITION": False, "M2_FORCE_SAME": True}},
        "W2": {"broken": False, "detected": {"M1_ONE_POSITION": True, "M2_FORCE_SAME": False}}})
    chk("all_load_bearing", good["verdict"] == "ALL_WALLS_LOAD_BEARING")
    # 刪了還紅 ⇒ STILL_RED_ELSEWHERE
    still = analyse(ok, {
        "W1": {"broken": False, "detected": {"M1_ONE_POSITION": True, "M2_FORCE_SAME": True}},
        "W2": {"broken": False, "detected": {"M1_ONE_POSITION": True, "M2_FORCE_SAME": False}}})
    chk("still_red", still["walls"]["W1"] == "STILL_RED_ELSEWHERE"
        and still["verdict"] == "SOME_WALL_NOT_LOAD_BEARING")
    # crash ⇒ BROKEN_CUT，不是 MISSED 也不是 DETECTED
    br = analyse(ok, {
        "W1": {"broken": True, "detected": {}},
        "W2": {"broken": False, "detected": {"M1_ONE_POSITION": True, "M2_FORCE_SAME": False}}})
    chk("broken_cut", br["walls"]["W1"] == "BROKEN_CUT" and br["verdict"] == "BROKEN_CUT_PRESENT")
    # 專一性壞掉（刪 W1 連 M2 也不紅了）⇒ 不准判 ALL
    sp = analyse(ok, {
        "W1": {"broken": False, "detected": {"M1_ONE_POSITION": False, "M2_FORCE_SAME": False}},
        "W2": {"broken": False, "detected": {"M1_ONE_POSITION": True, "M2_FORCE_SAME": False}}})
    chk("specificity_fails", sp["verdict"] == "SOME_WALL_NOT_LOAD_BEARING")
    # 基線不是 2/2 ⇒ BASELINE_BROKEN，且不准往下判
    bb = analyse({"broken": False, "detected": {"M1_ONE_POSITION": False, "M2_FORCE_SAME": True}}, {})
    chk("baseline_broken", bb["verdict"] == "BASELINE_BROKEN" and bb["walls"] == {})
    bb2 = analyse({"broken": True, "detected": {}}, {})
    chk("baseline_crash", bb2["verdict"] == "BASELINE_BROKEN")

    n = 12
    print(f"selftest {n - len(fails)}/{n}" + (f"  FAILS={fails}" if fails else ""))
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--worktree")
    ap.add_argument("--json")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.worktree:
        print("need --worktree (不准在工作目錄上動刀)")
        return 2
    out = main_run(pathlib.Path(a.worktree).expanduser().resolve())
    if a.json:
        p = ROOT / a.json
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"verdict={out['verdict']}  walls={out.get('walls')}  "
          f"baseline={out.get('baseline_detected')}")
    print(f"specificity={out.get('specificity')}  n_broken_cut={out.get('n_broken_cut')}")
    print(f"cut_detail={json.dumps(out.get('cut_detail'), ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
