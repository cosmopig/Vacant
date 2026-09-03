#!/usr/bin/env python3
"""round670 自檢：`conform_settle.py` 新增的 deliv 差值區間。

驗 CRITERION_20260903_R670 §四 的 P-R670-A/B/C/D。零模型呼叫、零沙箱，
fixture 全建在 --work（預設 /dev/shm），**不碰 r444 目錄**（唯讀複製）。
"""
from __future__ import annotations
import argparse, json, math, pathlib, shutil, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import conform_settle as CS          # noqa: E402
import paired_ci as PCI              # noqa: E402

OK, BAD = [], []


def check(name: str, cond: bool, detail: str = "") -> None:
    (OK if cond else BAD).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{('  — ' + detail) if detail else ''}")


def settle(run: pathlib.Path, rows: pathlib.Path) -> dict:
    return CS.settle(run, rows, "CONFORM", "OFF5", "OFF")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="真 run 目錄（只讀）")
    ap.add_argument("--work", default="/dev/shm/r670/selftest")
    a = ap.parse_args()
    src, work = pathlib.Path(a.run), pathlib.Path(a.work)
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    base = work / "base"
    base.mkdir()
    for f in ("rows.jsonl", "summary.json", "notes.jsonl"):
        shutil.copy2(src / f, base / f)
    rows = [json.loads(l) for l in (base / "rows.jsonl").read_text().splitlines() if l.strip()]

    print("== P-R670-B：deliv 區間與 paired_ci.py 在未竄改資料上必須逐位相同 ==")
    out = settle(base, base / "rows.jsonl")
    d = out["paired_test_vs_baseline"]["by"]["deliv"]
    A = {r["task_id"]: r for r in rows if r["arm"] == "CONFORM"}
    B = {r["task_id"]: r for r in rows if r["arm"] == "OFF5"}
    common = sorted(set(A) & set(B))
    pb = sum(1 for t in common if A[t]["meets_demand"] and not B[t]["meets_demand"])
    pc = sum(1 for t in common if B[t]["meets_demand"] and not A[t]["meets_demand"])
    ref = PCI.diff_ci(pb, pc, len(common))
    check("B deliv.lo 與 paired_ci 逐位相同", d["ci_lo_pp"] == 100.0 * ref["lo"],
          f"{d['ci_lo_pp']!r} vs {100.0*ref['lo']!r}")
    check("B deliv.hi 與 paired_ci 逐位相同", d["ci_hi_pp"] == 100.0 * ref["hi"])

    print("== P-R670-A：拒交格的候選其實是對的 ⇒ 兩指標分家 ==")
    # 找一個被拒交（accepted=false）的 CONFORM 格，把它翻成 meets_demand=true
    tgt = next(r["task_id"] for r in rows
               if r["arm"] == "CONFORM" and not r["accepted"] and not r["meets_demand"])
    fx = work / "A"
    fx.mkdir()
    for f in ("summary.json", "notes.jsonl"):
        shutil.copy2(base / f, fx / f)
    mut = []
    for r in rows:
        if r["arm"] == "CONFORM" and r["task_id"] == tgt:
            r = dict(r, meets_demand=True)
        mut.append(r)
    (fx / "rows.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in mut))
    o2 = settle(fx, fx / "rows.jsonl")
    d2, m2 = o2["paired_test_vs_baseline"]["by"]["deliv"], o2["paired_test_vs_baseline"]["by"]["meets_demand"]
    check("A md&!acc 由 0 變 1", o2["arms"]["CONFORM"]["meets_demand_and_not_accepted"] == 1)
    check("A meets_demand 的 b +1", m2["b"] == d["b"] + 1, f"{d['b']} -> {m2['b']}")
    check("A deliv 的 b/c 完全不動", (d2["b"], d2["c"]) == (d["b"], d["c"]))
    check("A 兩支給出**不同**區間（巧合斷掉）",
          (d2["ci_lo_pp"], d2["ci_hi_pp"]) != (m2["ci_lo_pp"], m2["ci_hi_pp"]),
          f"deliv[{d2['ci_lo_pp']:+.2f},{d2['ci_hi_pp']:+.2f}] "
          f"vs md[{m2['ci_lo_pp']:+.2f},{m2['ci_hi_pp']:+.2f}]")

    print("== P-R670-C：區間排除 0 <=> 精確 p<0.05（(b,c) 全格掃）==")
    bad = []
    for n in (60, 143, 179):
        for b in range(0, 21):
            for c in range(0, 21):
                if b + c > n:
                    continue
                r = PCI.diff_ci(b, c, n)
                lo, hi = 100 * r["lo"], 100 * r["hi"]
                if ((lo > 0) or (hi < 0)) != (CS.exact_mcnemar_p(b, c) < 0.05):
                    bad.append((n, b, c))
    check("C 全格一致", not bad, f"不一致 {len(bad)} 格" if bad else "掃過 1323 格")

    print("== P-R670-D：植入缺陷（M1 常態近似／M2 漏乘 n_d/n）必須被擋 ==")
    for m, why in (("M1", "常態近似"), ("M2", "漏乘 n_d/n")):
        PCI.MUTANT = m
        PCI._CP_CACHE.clear()
        caught_grid, caught_e2e = [], ""
        for n in (60, 143, 179):
            for b in range(0, 21):
                for c in range(0, 21):
                    if b + c > n:
                        continue
                    r = PCI.diff_ci(b, c, n)
                    lo, hi = 100 * r["lo"], 100 * r["hi"]
                    cap = 100.0 * (b + c) / n
                    if (((lo > 0) or (hi < 0)) != (CS.exact_mcnemar_p(b, c) < 0.05)
                            or lo < -cap - 1e-9 or hi > cap + 1e-9):
                        caught_grid.append((n, b, c))
        try:
            settle(base, base / "rows.jsonl")
        except CS.Broken as e:
            caught_e2e = str(e)[:70]
        check(f"D {m}（{why}）被三條界至少一條擋下",
              bool(caught_grid),
              f"grid 擋下 {len(caught_grid)} 格"
              + (f"；真資料端到端也擋下：{caught_e2e}" if caught_e2e else "；真資料端到端未觸發"))
        PCI.MUTANT = ""
        PCI._CP_CACHE.clear()

    print("== 反向：修好之後真資料仍 rc=0（不誤報）==")
    try:
        settle(base, base / "rows.jsonl")
        check("反向 乾淨資料不誤報", True)
    except CS.Broken as e:
        check("反向 乾淨資料不誤報", False, str(e))

    print(f"\n{len(OK)}/{len(OK)+len(BAD)} PASS")
    return 0 if not BAD else 2


if __name__ == "__main__":
    sys.exit(main())
