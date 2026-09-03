#!/usr/bin/env python3
"""離線分析：把「接受閘」當成一個分類器來量（拒絕 = 正類）。

零模型呼叫、零 sandbox 執行——只讀已落盤的 rows.jsonl。

問的是：ON 的 5 次呼叫換到的那道拒絕閘，跟「跑一次可見測資就拒絕」
（0 次模型呼叫、純本機執行）比起來，多買到了什麼？

用法：ops/gain/replay/gate_2x2.py [run ...]
"""
from __future__ import annotations
import json, sys, math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUNS = ROOT / "runs"


def load(run, arm=None):
    rows = [json.loads(l) for l in (RUNS / run / "rows.jsonl").read_text().splitlines() if l.strip()]
    return [r for r in rows if arm is None or r["arm"] == arm]


def confirmed_ce(r):
    return sum(1 for e in (r.get("review_evidence") or []) if e.get("counterexample_confirmed"))


GATES = {
    # name: (predicate ship?, model calls the gate itself costs, uses hidden GT?)
    "no_gate (ship everything)":      (lambda r: True, 0, False),
    "visible-test gate (0 calls)":    (lambda r: bool(r.get("visible_ok")), 0, False),
    "peer-review gate (3 calls)":     (lambda r: bool(r.get("passed_review")), 3, False),
    "visible AND review (3 calls)":   (lambda r: bool(r.get("visible_ok")) and bool(r.get("passed_review")), 3, False),
    "visible AND no confirmed CE":    (lambda r: bool(r.get("visible_ok")) and confirmed_ce(r) == 0, 3, False),
    "ON actual = visible AND audit":  (lambda r: bool(r.get("accepted")), 0, True),
}


def two_by_two(rows, ship):
    tp = sum(1 for r in rows if not ship(r) and not r["meets_demand"])   # refused & would fail
    fp = sum(1 for r in rows if not ship(r) and r["meets_demand"])       # refused & would pass  (false refusal)
    fn = sum(1 for r in rows if ship(r) and not r["meets_demand"])       # shipped & fails  (LEAK)
    tn = sum(1 for r in rows if ship(r) and r["meets_demand"])           # shipped & passes (delivered good)
    n = len(rows)
    shipped = tn + fn
    return dict(
        n=n, refused=tp + fp, shipped=shipped,
        refuse_tp=tp, refuse_fp=fp, leaked=fn, delivered_good=tn,
        precision=(tp / (tp + fp)) if (tp + fp) else float("nan"),
        recall=(tp / (tp + fn)) if (tp + fn) else float("nan"),
        false_refusal_rate=(fp / (fp + tn)) if (fp + tn) else float("nan"),
        coverage=shipped / n if n else float("nan"),
        selective_acc=(tn / shipped) if shipped else float("nan"),
        leak_rate_of_all=fn / n if n else float("nan"),
    )


def fmt(name, d, calls, gt):
    return (f"  {name:34s} ship={d['shipped']:3d}/{d['n']:3d} cov={d['coverage']:.3f} "
            f"selacc={d['selective_acc']:.4f} leak={d['leaked']:3d} "
            f"good_thrown={d['refuse_fp']:3d} P={d['precision']:.3f} R={d['recall']:.3f} "
            f"| gate-calls={calls}{' [USES HIDDEN GT]' if gt else ''}")


def mcnemar_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    s = sum(math.comb(n, i) for i in range(0, k + 1))
    return min(1.0, 2 * s / (2 ** n))


def main(runs):
    for run in runs:
        print(f"\n=== {run} ===")
        on = load(run, "ON")
        if on:
            print(f"[ON] n={len(on)} rows")
            for name, (pred, calls, gt) in GATES.items():
                if name.startswith("peer") or name.startswith("visible AND"):
                    if not any("passed_review" in r for r in on):
                        continue
                print(fmt(name, two_by_two(on, pred), calls, gt))
            # paired: ON actual gate vs free visible gate, same rows same code
            act = GATES["ON actual = visible AND audit"][0]
            vis = GATES["visible-test gate (0 calls)"][0]
            diff = [(r["task_id"], act(r), vis(r)) for r in on if act(r) != vis(r)]
            print(f"  [paired] rows where ON's 5-call gate differs from the free 0-call gate: {len(diff)}")
            for t, a, v in diff:
                r = next(x for x in on if x["task_id"] == t)
                print(f"      {t}: ON_ship={a} free_ship={v} truth_pass={r['meets_demand']} "
                      f"audited={r.get('audited')} audit_ok={r.get('audit_ok')}")
            # leak comparison paired (b/c)
            b = sum(1 for r in on if (act(r) and not r["meets_demand"]) and not (vis(r) and not r["meets_demand"]))
            c = sum(1 for r in on if (vis(r) and not r["meets_demand"]) and not (act(r) and not r["meets_demand"]))
            print(f"  [paired leaks] ON-only-leak b={b} free-only-leak c={c} McNemar exact p={mcnemar_exact(b,c):.4f}")

        for arm in ("OFF", "OFF5"):
            rs = load(run, arm)
            if not rs or rs[0].get("visible_ok") is None:
                continue
            print(f"[{arm}] n={len(rs)} rows")
            print(fmt("no_gate (as run)", two_by_two(rs, lambda r: True), 0, False))
            print(fmt("visible-test gate (0 calls)", two_by_two(rs, lambda r: bool(r.get("visible_ok"))), 0, False))


if __name__ == "__main__":
    main(sys.argv[1:] or ["g_r441_gemma_only_mbpp_b", "g_r356_3arm_20260830", "g_onoff5_371_r123_20260825"])
