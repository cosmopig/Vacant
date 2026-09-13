"""三個補充統計，全部離線、零模型呼叫。

A. 審查在「執行看不見的區域」有沒有訊號：只看 ON 臂 initial_visible_ok=True
   的題目（可見測試已經無法分辨），問 reviewer 的 FAIL 旗標準不準。
   只讀 rows.jsonl。
B. 出貨那份的條件正確率 vs 五個候選裡有幾個通過可見測試。
C. 用執行落地的信心分數排序後的 coverage / 條件正確率曲線，對照 ON 自己的
   accept 閘。

B、C 需要 exec_select.py 產出的 cache。
"""
from __future__ import annotations

import collections
import json
import math
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
import analyze_select as A  # noqa: E402

RUNS = ["g_r441_gemma_only_mbpp_b", "g_r356_3arm_20260830"]


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def part_a(runs):
    print("A. reviewer signal where execution is blind (ON, initial_visible_ok=True)")
    for run in runs:
        rows = [json.loads(x) for x in
                (REPO / "runs" / run / "rows.jsonl").open(encoding="utf-8")]
        sub = [r for r in rows if r["arm"] == "ON" and r.get("initial_visible_ok")
               and r.get("initial_meets_demand") is not None]
        t = collections.Counter(
            (bool(r["passed_review"]), bool(r["initial_meets_demand"])) for r in sub)
        catch, false_alarm = t[(False, False)], t[(False, True)]
        miss, clean = t[(True, False)], t[(True, True)]
        n = catch + false_alarm + miss + clean
        base = (catch + miss) / n
        lo, hi = wilson(catch, catch + false_alarm)
        print(f"  {run}: n={n}  FAIL-flag fired {catch+false_alarm} times "
              f"(precision {catch}/{catch+false_alarm} = "
              f"{catch/max(1,catch+false_alarm):.3f}, Wilson [{lo:.3f},{hi:.3f}]) "
              f"vs base error rate {base:.3f}; recall {catch}/{catch+miss}")


def part_b(runs):
    tot = collections.defaultdict(lambda: [0, 0])
    for run in runs:
        facts, rows = A.load(run)
        for t in A.usable_tasks(facts, rows)[0]:
            cs = facts[t]
            k = sum(1 for c in cs if c["visible_ok"])
            if k == 0:
                continue
            tot[k][0] += 1
            tot[k][1] += bool(A.p_visfilter_vote_short(cs)["hidden_ok"])
    print("\nB. conditional accuracy of the shipped pick vs #candidates passing "
          "the 3 visible asserts (pooled)")
    for k in sorted(tot):
        n, ok = tot[k]
        print(f"  {k}/5 pass visible: n={n:3d}  correct {ok:3d} = {100*ok/n:6.2f}%")


def part_c(runs):
    print("\nC. execution-grounded confidence ranking vs ON's own accept gate")
    for run in runs:
        facts, rows = A.load(run)
        tasks = A.usable_tasks(facts, rows)[0]
        n = len(tasks)
        pick = {t: A.p_visfilter_vote_short(facts[t]) for t in tasks}

        def conf(t):
            vp = [c for c in facts[t] if c["visible_ok"]]
            if not vp:
                return (-1, 0, 0)
            b = collections.Counter(c["sig"] for c in vp)
            return (len(vp), max(b.values()), -len(b))
        order = sorted(tasks, key=conf, reverse=True)
        print(f"  {run} (n={n})")
        for frac in (1.0, 0.9, 0.81, 0.6):
            k = int(round(frac * n))
            ok = sum(1 for t in order[:k] if pick[t]["hidden_ok"])
            print(f"    coverage {100*k/n:5.1f}% ({k:3d})  cond. pass "
                  f"{ok:3d}/{k} = {100*ok/k:6.2f}%")
        on = [t for t in tasks if ("ON", t) in rows]
        acc = [t for t in on if rows[("ON", t)].get("accepted") is not False]
        if acc:
            okp = sum(1 for t in acc if rows[("ON", t)]["meets_demand"])
            print(f"    ON accept gate  coverage {100*len(acc)/len(on):5.1f}% "
                  f"({len(acc):3d})  cond. pass {okp:3d}/{len(acc)} = "
                  f"{100*okp/len(acc):6.2f}%")


if __name__ == "__main__":
    runs = sys.argv[1:] or RUNS
    part_a(runs)
    part_b(runs)
    part_c(runs)
