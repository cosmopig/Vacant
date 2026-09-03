#!/usr/bin/env python3
"""如果把免費閘當成**升級觸發器**而不是拒絕器呢？

政策：先叫 1 次。跑可見測資（0 模型呼叫）。過了就交件；沒過才再叫一次，
最多用完手上的 5 個候選；全部沒過就拒絕。
預算是**變動的**：好題只花 1 次，難題才花到 5 次。

重放用的候選就是 OFF5 已經產生的那 5 份（呼叫順序不變），所以這不是新實驗，
是同一批呼叫的另一種花法。選擇只讀 visible，hidden 只算分。

用法：ops/gain/replay/escalate_on_visible_fail.py [run]（需先跑 replay_candidates.py）
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
            pool[r["task_id"]].append((int(idx), r["visible"], r["hidden"]))
    for t in pool:
        pool[t].sort()
    by = {}
    for l in (ROOT / "runs" / run / "rows.jsonl").read_text().splitlines():
        if not l.strip():
            continue
        r = json.loads(l)
        by.setdefault(r["arm"], {})[r["task_id"]] = r
    common = [t for t in sorted(set(by["ON"]) & set(by["OFF5"]) & set(pool))
              if len(pool[t]) == 5 and all(c[1] is not None for c in pool[t])]
    n = len(common)
    print(f"=== {run} === n={n} paired tasks (ON row present, full 5-candidate replay)")

    for kmax in (1, 2, 3, 4, 5):
        calls = ship = good = 0
        for t in common:
            pick = None
            used = 0
            for i, vis, hid in pool[t][:kmax]:
                used += 1
                if vis:
                    pick = (vis, hid)
                    break
            calls += used
            if pick:
                ship += 1
                good += int(bool(pick[1]))
        print(f"  escalate-until-visible-pass, cap {kmax} calls: mean calls/task={calls/n:.2f} "
              f"ship={ship:3d} cov={ship/n:.3f} good={good:3d} leak={ship-good:3d} "
              f"selacc={good/ship if ship else float('nan'):.4f} good/n={good/n:.4f}")

    for lab, arm, pred, bud in [("OFF   + visible gate", "OFF", lambda r: r["visible_ok"], 1.0),
                                ("OFF5  + visible gate", "OFF5", lambda r: r["visible_ok"], 5.0),
                                ("ON    minus oracle audit", "ON", lambda r: r["visible_ok"], 5.0),
                                ("ON    AS RUN [ORACLE audit]", "ON", lambda r: r["accepted"], 5.0)]:
        rs = [by[arm][t] for t in common]
        sh = [r for r in rs if pred(r)]
        g = sum(1 for r in sh if r["meets_demand"])
        print(f"  {lab:41s} mean calls/task={bud:.2f} ship={len(sh):3d} cov={len(sh)/n:.3f} "
              f"good={g:3d} leak={len(sh)-g:3d} selacc={g/len(sh):.4f} good/n={g/n:.4f}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "g_r441_gemma_only_mbpp_b")
