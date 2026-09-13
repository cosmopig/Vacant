"""Reviewer 角色的收支表：投訴漏斗、審查改變了什麼、修訂的修復率、可放鬆的過濾器。

零 API 呼叫。sandbox 只用 arg_probe.py / sibling_oracle.py 已經落盤的快取
（_arg_probe_cache.json / _sibling_cache.json），本支不再開新的 sandbox。
hidden_check 結果（initial_meets_demand / meets_demand）只當被解釋的變數。
"""
from __future__ import annotations
import ast, json, pathlib, sys
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "ops/gain"))
sys.path.insert(0, str(ROOT / "ops/gain/replay"))
import gain_run as G  # noqa
from claim_truth import eq  # noqa
from reviewer_signal import fisher_exact_2x2, wilson  # noqa

RUNS_DIR = ROOT / "runs"
RUNS = ["g_r441_gemma_only_mbpp_b", "g_r356_3arm_20260830",
        "g_onoff5_371_r123_20260825", "g_het3_r278_20260829"]


def on_rows():
    out = []
    for run in RUNS:
        for l in (RUNS_DIR / run / "rows.jsonl").open(encoding="utf-8"):
            if not l.strip():
                continue
            r = json.loads(l)
            if r["arm"] == "ON" and r.get("review_evidence"):
                r["_run"] = run
                out.append(r)
    return out


def select(passed_review, ivo, rvo, rfc):
    if passed_review and ivo:
        return "initial"
    if rvo and rfc:
        return "revised"
    if ivo:
        return "initial_fallback"
    if rvo:
        return "revised_unconfirmed_fallback"
    return "revised_both_visible_fail"


def main():
    rows = on_rows()
    recs = [json.loads(l) for l in
            (ROOT / "ops/gain/replay/reviewer_records.jsonl").open(encoding="utf-8") if l.strip()]
    by = defaultdict(list)
    for r in recs:
        by[(r["run"], r["task_id"])].append(r)
    print("### 1. selection rebuild sanity check (must be 0 mismatches)")
    mism = sum(1 for r in rows if select(r["passed_review"], r["initial_visible_ok"],
                                         r["revised_visible_ok"],
                                         r.get("revised_fixes_counterexamples", True))
               != r["selected_version"])
    print(f"   ON rows={len(rows)}  mismatches={mism}")

    print("\n### 2. did the 3 review calls change the shipped answer?")
    div, gain, loss, unk = 0, 0, 0, 0
    for r in rows:
        rfc = r.get("revised_fixes_counterexamples", True)
        actual = select(r["passed_review"], r["initial_visible_ok"], r["revised_visible_ok"], rfc)
        cf = select(True, r["initial_visible_ok"], r["revised_visible_ok"], True)
        if actual == cf:
            continue
        div += 1
        cf_hidden = r["initial_meets_demand"] if cf.startswith("initial") else None
        if cf_hidden is None:
            unk += 1
        elif r["meets_demand"] is True and cf_hidden is False:
            gain += 1
        elif r["meets_demand"] is False and cf_hidden is True:
            loss += 1
    print(f"   rows where the review verdicts changed which code shipped: {div}/{len(rows)} "
          f"({div/len(rows):.4f})   fixed={gain} broke={loss} unknown={unk}")

    print("\n### 3. complaint funnel by the truth about the reviewed initial")
    def funnel(sel, name):
        g = [r for r in rows if sel(r)]
        n = len(g)
        af = sum(1 for r in g if any(not x["raw_pass"] for x in by[(r["_run"], r["task_id"])]))
        ac = sum(1 for r in g if any((not x["raw_pass"]) and G.parse_review_claim(x["text"] or "")
                                     for x in by[(r["_run"], r["task_id"])]))
        cc = sum(1 for r in g if any(x["confirmed"] for x in by[(r["_run"], r["task_id"])]))
        gt = sum(1 for r in g if not r["passed_review"])
        print(f"   {name:42s} n={n:4d}  >=1 FAIL {af:4d}({af/n:.3f})  "
              f">=1 parsed claim {ac:4d}({ac/n:.3f})  >=1 confirmed CE {cc:4d}({cc/n:.3f})  "
              f"gate rejected {gt:3d}({gt/n:.3f})")
    funnel(lambda r: r["initial_meets_demand"] is False, "initial WRONG (hidden)")
    funnel(lambda r: r["initial_meets_demand"] is True, "initial CORRECT (hidden)")
    funnel(lambda r: r["initial_visible_ok"] is True and r["initial_meets_demand"] is False,
           "  visible-PASS but hidden-WRONG")
    funnel(lambda r: r["initial_visible_ok"] is False, "  visible-FAIL (free exec finds it)")

    print("\n### 4. repair yield: does a confirmed counterexample make the revision work?")
    wrong = [r for r in rows if r["initial_meets_demand"] is False]
    trig = [r for r in wrong if any(e["counterexample_confirmed"] for e in r["review_evidence"])]
    no = [r for r in wrong if not any(e["counterexample_confirmed"] for e in r["review_evidence"])]
    i1 = sum(1 for r in trig if r.get("revision_transition") == "improved")
    i0 = sum(1 for r in no if r.get("revision_transition") == "improved")
    print(f"   initial-wrong rows n={len(wrong)}")
    print(f"     with >=1 confirmed CE: improved {i1}/{len(trig)}={i1/len(trig):.3f} "
          f"(95% CI {wilson(i1,len(trig))[0]:.3f}-{wilson(i1,len(trig))[1]:.3f})")
    print(f"     with  0 confirmed CE: improved {i0}/{len(no)}={i0/len(no):.3f} "
          f"(95% CI {wilson(i0,len(no))[0]:.3f}-{wilson(i0,len(no))[1]:.3f})")
    print(f"     fisher_p={fisher_exact_2x2(i1,len(trig)-i1,i0,len(no)-i0):.3g}   "
          f"harmed anywhere = {sum(1 for r in rows if r.get('revision_transition')=='harmed')}")
    print("   pooled revision transitions:",
          dict(Counter(r.get("revision_transition") for r in rows)))

    print("\n### 5. relaxing the input-contract pre-filter (zero extra model calls)")
    cand = {tuple(json.loads(k)): v for k, v in json.loads(
        (ROOT / "ops/gain/replay/_arg_probe_cache.json").read_text(encoding="utf-8")).items()}
    claims = defaultdict(list)
    for r in recs:
        if r["raw_pass"]:
            continue
        c = G.parse_review_claim(r["text"] or "")
        if c is None:
            continue
        claims[(r["run"], r["task_id"])].append((r, list(c[0]), c[1]))

    def v(e):
        if e is None or e[0] != "ok":
            return (False, None)
        try:
            return (True, ast.literal_eval(e[1]))
        except Exception:
            return (False, None)
    out = []
    for key, items in claims.items():
        cres = cand.get(key)
        if cres is None:
            continue
        r0 = items[0][0]
        A = any(x[0]["confirmed"] for x in items)
        B = C = False
        for j, (r, args, exp) in enumerate(items):
            if j >= len(cres):
                continue
            cok, cv = v(cres[j])
            if (not cok) or (not eq(cv, exp)):
                B = True
                if cok:
                    C = True
        out.append({"vis": r0["cand_visible_ok"], "hid": r0["cand_hidden_ok"],
                    "A": A, "B": B, "C": C})
    for scope, sel in (("visible-PASS rows", lambda r: r["vis"] is True),
                       ("all rows with a parsed claim", lambda r: True)):
        g = [r for r in out if sel(r)]
        nb = sum(1 for r in g if r["hid"] is False)
        print(f"   -- {scope}: n={len(g)} hidden-fail={nb}")
        for k, nm in (("A", "current (contract-filtered confirmed CE)"),
                      ("B", "relaxed: no contract pre-filter"),
                      ("C", "relaxed but excluding candidate-crash claims")):
            tp = sum(1 for r in g if r[k] and r["hid"] is False)
            fp = sum(1 for r in g if r[k] and r["hid"] is True)
            lo, hi = wilson(tp, tp + fp) if tp + fp else (float("nan"),) * 2
            print(f"      {nm:44s} flagged={tp+fp:3d} TP={tp:3d} FP={fp:3d} "
                  f"precision={tp/(tp+fp) if tp+fp else float('nan'):.3f} (CI {lo:.3f}-{hi:.3f}) "
                  f"recall={tp/nb:.3f} fisher_p={fisher_exact_2x2(tp,fp,nb-tp,len(g)-nb-fp):.4g}")
    print("\n   headroom arithmetic (ESTIMATE, not a measurement):")
    a_tp = sum(1 for r in out if r["A"] and r["hid"] is False)
    b_tp = sum(1 for r in out if r["B"] and r["hid"] is False)
    y = i1 / len(trig)
    ylo, yhi = wilson(i1, len(trig))
    print(f"      extra truly-wrong rows given a grounded complaint: {b_tp-a_tp}")
    print(f"      x measured repair yield {y:.3f} (CI {ylo:.3f}-{yhi:.3f}) "
          f"=> {(b_tp-a_tp)*y:.1f} extra fixes over {len(rows)} ON rows "
          f"= {100*(b_tp-a_tp)*y/len(rows):+.2f}pp "
          f"(range {100*(b_tp-a_tp)*ylo/len(rows):+.2f} to {100*(b_tp-a_tp)*yhi/len(rows):+.2f}pp)")
    ceiling = len(wrong) * y
    print(f"      ceiling if EVERY wrong row got a grounded complaint: {ceiling:.0f} fixes "
          f"= {100*(ceiling-13)/len(rows):+.2f}pp over the 13 actually observed")


if __name__ == "__main__":
    main()
