"""Reviewer FAIL 是「這份候選碼有問題」還是只是「這題很難」？

作法：用**同題其他臂**（OFF／OFF5，獨立樣本，不是被審的那份碼）算每題難度，
再看在同一難度層裡 reviewer FAIL 是否仍能分辨 hidden-fail。
若條件化難度後 lift 歸零 ⇒ reviewer 只是難度偵測器，不能拿來選答案。

零 API、零 sandbox：全部欄位已落盤。
"""
from __future__ import annotations
import json, math, pathlib, sys
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[3]
RUNS = ROOT / "runs"
sys.path.insert(0, str(ROOT / "ops/gain/replay"))
from reviewer_signal import fisher_exact_2x2, wilson, per_review_records, norm_family  # noqa


def task_difficulty(runs):
    """每題難度 = 所有 run 的 OFF/OFF5 列 meets_demand 平均（獨立於被審候選）。"""
    agg = defaultdict(lambda: [0, 0])
    for run in runs:
        for line in (RUNS / run / "rows.jsonl").open(encoding="utf-8"):
            if not line.strip():
                continue
            r = json.loads(line)
            if r["arm"] in ("OFF", "OFF5") and r.get("meets_demand") is not None:
                a = agg[r["task_id"]]
                a[0] += 1 if r["meets_demand"] else 0
                a[1] += 1
    return {k: (v[0] / v[1], v[1]) for k, v in agg.items()}


def mh(strata):
    """Mantel-Haenszel 合併 odds ratio + 每層 risk difference 的加權平均。"""
    num = den = 0.0
    wsum = wnum = 0.0
    for (a, b, c, d) in strata:
        n = a + b + c + d
        if n == 0:
            continue
        num += a * d / n
        den += b * c / n
        if (a + c) and (b + d):
            rd = a / (a + c) - b / (b + d)
            w = (a + c) * (b + d) / n
            wnum += w * rd
            wsum += w
    orr = num / den if den else float("nan")
    return orr, (wnum / wsum if wsum else float("nan"))


def main(runs):
    diff = task_difficulty(runs)
    recs = []
    for run in runs:
        _, rr = per_review_records(run)
        recs += rr
    recs = [r for r in recs if r["task_id"] in diff and r["cand_visible_ok"] is not None]
    print("review records with difficulty:", len(recs))
    d0 = [diff[r["task_id"]][0] for r in recs]
    print("difficulty (OFF/OFF5 hidden pass rate) quantiles:",
          [round(sorted(d0)[int(q * (len(d0) - 1))], 3) for q in (0, .25, .5, .75, 1)])

    # 只看被審候選「通過可見測資」的子集：那是 reviewer 唯一可能加值的地方
    sub = [r for r in recs if r["cand_visible_ok"] is True]
    print("\nrestricted to visible-PASS candidates: n =", len(sub))

    def bins(r):
        p = diff[r["task_id"]][0]
        if p >= 0.999:
            return "easy (all indep. samples pass)"
        if p >= 0.6:
            return "mid (0.6-1.0)"
        return "hard (<0.6)"

    strata = []
    print("\n-- stratified by task difficulty: raw FAIL x hidden-fail (visible-PASS only) --")
    for name in ["easy (all indep. samples pass)", "mid (0.6-1.0)", "hard (<0.6)"]:
        g = [r for r in sub if bins(r) == name]
        a = sum(1 for r in g if not r["raw_pass"] and r["cand_hidden_ok"] is False)
        b = sum(1 for r in g if not r["raw_pass"] and r["cand_hidden_ok"] is True)
        c = sum(1 for r in g if r["raw_pass"] and r["cand_hidden_ok"] is False)
        d = sum(1 for r in g if r["raw_pass"] and r["cand_hidden_ok"] is True)
        strata.append((a, b, c, d))
        pe = a / (a + c) if (a + c) else float("nan")
        pn = b / (b + d) if (b + d) else float("nan")
        print(f"   {name:34s} n={a+b+c+d:5d}  hidden-fail n={a+c:4d}  "
              f"P(FAIL|hidden-fail)={pe:.3f}  P(FAIL|hidden-ok)={pn:.3f}  "
              f"lift={100*(pe-pn):+6.2f}pp  fisher_p={fisher_exact_2x2(a,b,c,d):.4f}")
    orr, rd = mh(strata)
    print(f"   Mantel-Haenszel pooled OR = {orr:.3f}   weighted risk-difference = {100*rd:+.2f}pp")

    # 同樣做 confirmed counterexample
    strata2 = []
    print("\n-- stratified: confirmed counterexample x hidden-fail (visible-PASS only) --")
    for name in ["easy (all indep. samples pass)", "mid (0.6-1.0)", "hard (<0.6)"]:
        g = [r for r in sub if bins(r) == name]
        a = sum(1 for r in g if r["confirmed"] and r["cand_hidden_ok"] is False)
        b = sum(1 for r in g if r["confirmed"] and r["cand_hidden_ok"] is True)
        c = sum(1 for r in g if not r["confirmed"] and r["cand_hidden_ok"] is False)
        d = sum(1 for r in g if not r["confirmed"] and r["cand_hidden_ok"] is True)
        strata2.append((a, b, c, d))
        pe = a / (a + c) if (a + c) else float("nan")
        pn = b / (b + d) if (b + d) else float("nan")
        print(f"   {name:34s} n={a+b+c+d:5d}  P(conf|hidden-fail)={pe:.3f}  "
              f"P(conf|hidden-ok)={pn:.3f}  lift={100*(pe-pn):+6.2f}pp  "
              f"fisher_p={fisher_exact_2x2(a,b,c,d):.4f}")
    orr2, rd2 = mh(strata2)
    print(f"   Mantel-Haenszel pooled OR = {orr2:.3f}   weighted risk-difference = {100*rd2:+.2f}pp")

    # ---- reviewer-model main effect vs target-model effect ----------------
    print("\n-- reviewer model main effect (FAIL rate), pooled over runs with both families --")
    two = [r for r in recs if r["run"] in ("g_r356_3arm_20260830", "g_het3_r278_20260829")]
    cell = defaultdict(lambda: [0, 0])
    for r in two:
        k = (norm_family(r["reviewer_model"]), norm_family(r["worker_model"]))
        cell[k][0] += 0 if r["raw_pass"] else 1
        cell[k][1] += 1
    for k in sorted(cell):
        f, n = cell[k]
        lo, hi = wilson(f, n)
        print(f"   reviewer={k[0]:5s} target={k[1]:5s}  FAIL {f:4d}/{n:4d} = {f/n:.3f} "
              f"(95% CI {lo:.3f}-{hi:.3f})")
    for fam in ("gemma", "qwen"):
        f = sum(cell[k][0] for k in cell if k[0] == fam)
        n = sum(cell[k][1] for k in cell if k[0] == fam)
        print(f"   reviewer={fam} (any target): FAIL {f}/{n} = {f/n:.3f}")
        f = sum(cell[k][0] for k in cell if k[1] == fam)
        n = sum(cell[k][1] for k in cell if k[1] == fam)
        print(f"   target  ={fam} (any reviewer): FAIL {f}/{n} = {f/n:.3f}")

    # ---- per-lens ---------------------------------------------------------
    print("\n-- per lens (agent_id) FAIL rate / confirmed rate, pooled all runs --")
    per = defaultdict(lambda: [0, 0, 0])
    for r in recs:
        p = per[r["reviewer"]]
        p[0] += 0 if r["raw_pass"] else 1
        p[1] += 1 if r["confirmed"] else 0
        p[2] += 1
    for k in sorted(per):
        f, c, n = per[k]
        print(f"   {k:10s} FAIL {f:4d}/{n:4d}={f/n:.3f}  confirmed {c:3d}/{n:4d}={c/n:.3f}")

    # ---- detector operating points (row level, visible-PASS rows only) ----
    print("\n-- detector operating points on rows whose initial passes visible tests --")
    rows = []
    for run in runs:
        on, rr = per_review_records(run)
        byrow = defaultdict(list)
        for r in rr:
            byrow[r["task_id"]].append(r)
        for r in on:
            g = byrow[r["task_id"]]
            if not g or r["initial_visible_ok"] is not True:
                continue
            rows.append({"nfail": sum(1 for x in g if not x["raw_pass"]),
                         "nconf": sum(1 for x in g if x["confirmed"]),
                         "k": len(g),
                         "bad": r["initial_meets_demand"] is False})
    nbad = sum(1 for r in rows if r["bad"])
    print(f"   rows={len(rows)}  hidden-fail rows={nbad} ({nbad/len(rows):.3f})")
    for thr in (1, 2, 3):
        for field, nm in (("nfail", "raw FAIL"), ("nconf", "confirmed CE")):
            tp = sum(1 for r in rows if r[field] >= thr and r["bad"])
            fp = sum(1 for r in rows if r[field] >= thr and not r["bad"])
            fn = nbad - tp
            prec = tp / (tp + fp) if tp + fp else float("nan")
            rec = tp / nbad if nbad else float("nan")
            lo, hi = wilson(tp, tp + fp) if tp + fp else (float('nan'),) * 2
            print(f"   >={thr} {nm:12s}: flagged={tp+fp:4d} TP={tp:3d} FP={fp:3d} "
                  f"precision={prec:.3f} (CI {lo:.3f}-{hi:.3f}) recall={rec:.3f}")


if __name__ == "__main__":
    main(sys.argv[1:])
