#!/usr/bin/env python3
"""OFF5 的 5 個候選都在硬碟上——如果用可見測資去「挑」而不只是「擋」呢？

零額外模型呼叫（5 次 gen 已經花掉了），沙箱執行不算預算。
V/GT 紀律：選擇只讀 replay 快取的 `visible`，`hidden` 只用來算分。

用法：ops/gain/replay/off5_visible_select.py [run]
需要先跑 ops/gain/replay/replay_candidates.py <run>
"""
from __future__ import annotations
import json, os, sys, collections
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CACHE = Path(os.environ.get("REPLAY_OUT", "/private/tmp/claude-501/"
             "-Users-cosmopig-Documents-GitHub-Vacant/ab1fa694-341b-43a5-8fb3-2ff0b03bcdff/scratchpad"))


def main(run):
    data = json.loads((CACHE / f"replay_{run}.json").read_text())
    pool = collections.defaultdict(list)
    for r in data["results"]:
        arm, role, idx = r["key"].split(":")
        if (arm, role) == ("OFF5", "gen"):
            pool[r["task_id"]].append((int(idx), r["visible"], r["hidden"], r["code_sha"]))
    for t in pool:
        pool[t].sort()

    by = {}
    for l in (ROOT / "runs" / run / "rows.jsonl").read_text().splitlines():
        if not l.strip():
            continue
        r = json.loads(l)
        by.setdefault(r["arm"], {})[r["task_id"]] = r
    common = sorted(set(by["ON"]) & set(by["OFF5"]) & set(pool))
    common = [t for t in common if len(pool[t]) == 5 and all(c[1] is not None for c in pool[t])]
    n = len(common)
    print(f"=== {run} === tasks with a complete 5-candidate replay AND an ON row: n={n}")

    def report(lab, sel, budget=5):
        ship = good = 0
        for t in common:
            pick = sel(pool[t], by["OFF5"][t])
            if pick is None:
                continue
            ship += 1
            good += int(bool(pick[2]))
        print(f"  {lab:52s} calls={budget} ship={ship:3d} cov={ship/n:.3f} "
              f"good={good:3d} leak={ship-good:3d} selacc={good/ship if ship else float('nan'):.4f} "
              f"good/n={good/n:.4f}")

    # baselines re-expressed on this task set, straight from rows.jsonl
    for lab, arm, pred in [("OFF5  as run (majority winner, ship-all)", "OFF5", lambda r: True),
                           ("OFF5  as run + visible gate", "OFF5", lambda r: r["visible_ok"]),
                           ("ON    minus oracle audit", "ON", lambda r: r["visible_ok"]),
                           ("ON    AS RUN (visible + hidden audit) [ORACLE]", "ON", lambda r: r["accepted"])]:
        rs = [by[arm][t] for t in common]
        sh = [r for r in rs if pred(r)]
        g = sum(1 for r in sh if r["meets_demand"])
        print(f"  {lab:52s} calls={1 if arm=='OFF' else 5} ship={len(sh):3d} cov={len(sh)/n:.3f} "
              f"good={g:3d} leak={len(sh)-g:3d} selacc={g/len(sh) if sh else float('nan'):.4f} good/n={g/n:.4f}")

    print("  --- zero extra model calls, selection by visible tests only ---")
    def first_pass(c, row):
        for x in c:
            if x[1]:
                return x
        return None
    def literal_majority_pass(c, row):
        ok = [x for x in c if x[1]]
        if not ok:
            return None
        cnt = collections.Counter(x[3] for x in ok)
        best = max(cnt.values())
        for x in ok:
            if cnt[x[3]] == best:
                return x
        return None
    def need2(c, row):
        ok = [x for x in c if x[1]]
        if len(ok) < 2:
            return None
        return literal_majority_pass(c, row)
    def need3(c, row):
        ok = [x for x in c if x[1]]
        if len(ok) < 3:
            return None
        return literal_majority_pass(c, row)
    report("OFF5V-SELECT: first candidate passing visible", first_pass)
    report("OFF5V-SELECT: literal-majority among visible-passers", literal_majority_pass)
    report("OFF5V-SELECT + require >=2 visible-passers", need2)
    report("OFF5V-SELECT + require >=3 visible-passers", need3)

    # how many visible-passers per task
    d = collections.Counter(sum(1 for x in pool[t] if x[1]) for t in common)
    print("  visible-passers per task histogram:", dict(sorted(d.items())))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "g_r441_gemma_only_mbpp_b")
