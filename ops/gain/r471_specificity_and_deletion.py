#!/usr/bin/env python3
"""R471 §五 P6（專一性）與 P8（X-F／X-G 刪掉對照）的量具。
判準 DECISION_20260904_R471_VERDICT_GATE_TEETH_PREREG.md（`5740fa7`，本檔之前 commit）。

P6：M1/M2/M7/M8 底下，D1 的**完整輸出**不得含 F 或 G 的 FAIL 行。
P8：把條 F（或條 G）整段刪掉之後，M5（或 M6）必須回到 MISSED——證明新條文是承重牆。
    r695 教訓：「整段刪掉會不會 FAIL」比 env 旗標突變體更硬。
"""
from __future__ import annotations
import argparse, hashlib, json, pathlib, subprocess, sys

REL = "ops/gain/replay/paired_ci.py"
D1 = ["python3", REL, "--selftest"]

MUT = {  # 沿用 mutation_test_r470 的逐字錨點
    "M1": ('if MUTANT == "M1":', 'if True:'),
    "M2": ('if MUTANT == "M2":', 'if True:'),
    "M5": ('    if lo_pp > 0:\n', '    if hi_pp > 0:\n'),
    "M6": ('    if n < MIN_PAIRED:\n', '    if n < 0:\n'),
    "M7": ('    b = sum(1 for t in common if ok(A[t]) and not ok(B[t]))\n'
           '    c = sum(1 for t in common if ok(B[t]) and not ok(A[t]))\n',
           '    b = sum(1 for t in common if ok(B[t]) and not ok(A[t]))\n'
           '    c = sum(1 for t in common if ok(A[t]) and not ok(B[t]))\n'),
    "M8": ('if os.environ.get("MUTANT") == "M_KEY":', 'if True:'),
}

# 條 F／條 G 在 selftest() 裡的整段（逐字，必須恰好出現 1 次）
F_START = "    # F: verdict() 的判決表（R471）"
F_END = '            fails.append(f"F: verdict({lo_pp:+.2f},{hi_pp:+.2f}) = {got}，應為 {want}")\n'
G_START = "    # G: main() 裡 `n < MIN_PAIRED` 那一行 BROKEN 擋門的**接線**（R471）"
G_END = '        fails.append("G: " + msg)\n'


def cut(src: str, start_marker: str, end_marker: str) -> str:
    i = src.index(start_marker)
    j = src.index(end_marker) + len(end_marker)
    assert src.count(start_marker) == 1 and src.count(end_marker) == 1
    return src[:i] + src[j:]


def d1(wt: pathlib.Path):
    p = subprocess.run(D1, cwd=str(wt), capture_output=True, text=True, timeout=600)
    out = p.stdout + p.stderr
    return {"rc": p.returncode, "red": p.returncode != 0, "out": out,
            "f_fail": "SELFTEST FAIL: F:" in out, "g_fail": "SELFTEST FAIL: G:" in out,
            "broken": "SyntaxError" in out or "Traceback (most recent call last)" in out}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--worktree", required=True)
    ap.add_argument("--json")
    a = ap.parse_args()
    wt = pathlib.Path(a.worktree).expanduser().resolve()
    tgt = wt / REL
    orig = tgt.read_text(encoding="utf-8")
    sha = hashlib.sha256(orig.encode()).hexdigest()
    print(f"== 目標 {tgt} sha256={sha[:16]}")

    res = {"target_sha256": sha, "p6": {}, "p8": {}}
    base = d1(wt)
    if base["red"]:
        print("ABORT：乾淨基線不綠"); return 2
    print("== P6 專一性：M1/M2/M7/M8 底下 D1 完整輸出不得含 F/G 的 FAIL 行 ==")
    for m in ("M1", "M2", "M7", "M8"):
        old, new = MUT[m]
        assert orig.count(old) == 1, m
        try:
            tgt.write_text(orig.replace(old, new), encoding="utf-8")
            st = d1(wt)
        finally:
            tgt.write_text(orig, encoding="utf-8")
        ok = not st["f_fail"] and not st["g_fail"]
        lines = [l for l in st["out"].splitlines() if "SELFTEST FAIL" in l]
        res["p6"][m] = {"rc": st["rc"], "f_fail": st["f_fail"], "g_fail": st["g_fail"],
                        "fail_lines": [l[:160] for l in lines], "p6_ok": ok}
        print(f"  {m}: rc={st['rc']} F行={st['f_fail']} G行={st['g_fail']} "
              f"{'✓專一' if ok else '★非專一'}  FAIL行={[l[:70] for l in lines]}")

    print("== P8 刪掉對照：拿掉條 F/G 之後目標突變體要回到 MISSED ==")
    for tag, (cut_args, mut) in {
        "X-F": (((F_START, F_END)), "M5"),
        "X-G": (((G_START, G_END)), "M6"),
    }.items():
        cut_src = cut(orig, *cut_args)
        old, new = MUT[mut]
        assert cut_src.count(old) == 1, tag
        try:
            tgt.write_text(cut_src, encoding="utf-8")
            st_clean = d1(wt)                     # 刪掉之後乾淨基線仍須綠
            tgt.write_text(cut_src.replace(old, new), encoding="utf-8")
            st_mut = d1(wt)
        finally:
            tgt.write_text(orig, encoding="utf-8")
        missed = not st_mut["red"]
        res["p8"][tag] = {"mutant": mut, "clean_rc": st_clean["rc"], "mut_rc": st_mut["rc"],
                          "back_to_missed": missed, "broken": st_mut["broken"],
                          "p8_ok": missed and st_clean["rc"] == 0 and not st_mut["broken"]}
        print(f"  {tag}（刪條{tag[-1]} + {mut}）: 刪後乾淨 rc={st_clean['rc']}  "
              f"{mut} rc={st_mut['rc']} ⇒ {'MISSED ✓承重' if missed else '仍紅 ★非承重'}")

    back = hashlib.sha256(tgt.read_text(encoding="utf-8").encode()).hexdigest()
    if back != sha:
        print(f"ABORT：還原失敗 {back[:16]}"); return 2
    print(f"== 還原驗證 sha256={back[:16]} 逐字元相同 ✓")
    res["p6_all_ok"] = all(v["p6_ok"] for v in res["p6"].values())
    res["p8_all_ok"] = all(v["p8_ok"] for v in res["p8"].values())
    print(f"\n== P6={'PASS' if res['p6_all_ok'] else 'FAIL'}  P8={'PASS' if res['p8_all_ok'] else 'FAIL'}")
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
