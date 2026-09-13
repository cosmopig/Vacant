"""列層級（每題一個聚類單位）的關鍵表：避免把 3 份審查當成 3 個獨立觀測。"""
from __future__ import annotations
import json, math, pathlib, random, sys
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "ops/gain/replay"))
from reviewer_signal import fisher_exact_2x2, wilson, per_review_records  # noqa
from reviewer_stratified import task_difficulty, mh  # noqa
RUNS = ROOT / "runs"


def rows_of(runs):
    diff = task_difficulty(runs)
    out = []
    for run in runs:
        on, recs = per_review_records(run)
        by = defaultdict(list)
        for r in recs:
            by[r["task_id"]].append(r)
        for r in on:
            g = by[r["task_id"]]
            if not g:
                continue
            out.append({
                "run": run, "task_id": r["task_id"],
                "k": len(g),
                "nfail": sum(1 for x in g if not x["raw_pass"]),
                "nconf": sum(1 for x in g if x["confirmed"]),
                "passed_review": r["passed_review"],
                "visible_ok": r["initial_visible_ok"],
                "hidden_ok": r["initial_meets_demand"],
                "selected": r.get("selected_version"),
                "final_hidden_ok": r.get("meets_demand"),
                "diff": diff.get(r["task_id"], (None, 0))[0],
            })
    return out


def tab(rows, gate, ev):
    a = sum(1 for r in rows if gate(r) and ev(r))
    b = sum(1 for r in rows if gate(r) and not ev(r))
    c = sum(1 for r in rows if not gate(r) and ev(r))
    d = sum(1 for r in rows if not gate(r) and not ev(r))
    return a, b, c, d


def show(name, t):
    a, b, c, d = t
    pe = a / (a + c) if (a + c) else float("nan")
    pn = b / (b + d) if (b + d) else float("nan")
    print(f"   {name:46s} n={a+b+c+d:4d} [g&e={a:3d} g&~e={b:3d} ~g&e={c:3d} ~g&~e={d:3d}] "
          f"P(gate|ev)={pe:.3f} P(gate|~ev)={pn:.3f} lift={100*(pe-pn):+6.2f}pp "
          f"fisher_p={fisher_exact_2x2(a,b,c,d):.5f}")


def main(runs):
    rows = rows_of(runs)
    print("ON rows with reviews:", len(rows), " runs:", dict(Counter(r["run"] for r in rows)))
    vok = [r for r in rows if r["visible_ok"] is True]
    print("rows whose reviewed initial passes the VISIBLE suite:", len(vok),
          " of which hidden-fail:", sum(1 for r in vok if r["hidden_ok"] is False))

    print("\n== ROW LEVEL, visible-PASS subset: does reviewer FAIL predict HIDDEN failure? ==")
    show(">=1 raw FAIL vs hidden-fail", tab(vok, lambda r: r["nfail"] >= 1,
                                            lambda r: r["hidden_ok"] is False))
    show(">=2 raw FAIL vs hidden-fail", tab(vok, lambda r: r["nfail"] >= 2,
                                            lambda r: r["hidden_ok"] is False))
    show(">=1 confirmed CE vs hidden-fail", tab(vok, lambda r: r["nconf"] >= 1,
                                                lambda r: r["hidden_ok"] is False))
    show("gate REJECT (passed_review=False) vs hidden-fail",
         tab(vok, lambda r: not r["passed_review"], lambda r: r["hidden_ok"] is False))

    print("\n== ROW LEVEL, stratified by task difficulty (independent OFF/OFF5 samples) ==")
    def band(r):
        p = r["diff"]
        if p is None:
            return "unknown"
        if p >= 0.999:
            return "easy(indep. pass=1.0)"
        if p >= 0.6:
            return "mid(0.6-1.0)"
        return "hard(<0.6)"
    strata = []
    for name in ["easy(indep. pass=1.0)", "mid(0.6-1.0)", "hard(<0.6)"]:
        g = [r for r in vok if band(r) == name]
        t = tab(g, lambda r: r["nfail"] >= 1, lambda r: r["hidden_ok"] is False)
        strata.append(t)
        show(name + " : >=1 raw FAIL vs hidden-fail", t)
    orr, rd = mh(strata)
    print(f"   Mantel-Haenszel OR={orr:.3f}  weighted risk-difference={100*rd:+.2f}pp")

    # cluster bootstrap over rows for the pooled lift
    rng = random.Random(20260903)
    def lift(sample):
        a, b, c, d = tab(sample, lambda r: r["nfail"] >= 1, lambda r: r["hidden_ok"] is False)
        if not (a + c) or not (b + d):
            return None
        return 100 * (a / (a + c) - b / (b + d))
    boots = []
    for _ in range(4000):
        s = [vok[rng.randrange(len(vok))] for _ in range(len(vok))]
        v = lift(s)
        if v is not None:
            boots.append(v)
    boots.sort()
    print(f"   pooled row-level lift = {lift(vok):+.2f}pp, "
          f"bootstrap 95% CI [{boots[int(.025*len(boots))]:+.2f}, {boots[int(.975*len(boots))]:+.2f}] "
          f"(4000 resamples over rows)")

    # what would a reviewer-triggered refusal buy?
    print("\n== if the gate REFUSED every row flagged by >=1 raw FAIL (visible-PASS rows) ==")
    for thr, fld in ((1, "nfail"), (2, "nfail"), (3, "nfail"), (1, "nconf"), (2, "nconf")):
        flagged = [r for r in vok if r[fld] >= thr]
        tp = sum(1 for r in flagged if r["hidden_ok"] is False)
        fp = len(flagged) - tp
        print(f"   >={thr} {fld}: refuse {len(flagged)}/{len(vok)} rows; "
              f"correctly withhold {tp} wrong answers, wrongly withhold {fp} correct ones "
              f"(net shipped-correct change = {-fp:+d}, ship rate {1-len(flagged)/len(vok):.3f})")

    # claim truth x candidate state
    ct = [json.loads(l) for l in (ROOT / "ops/gain/replay/claim_truth.jsonl").open(encoding="utf-8")
          if l.strip()]
    conf = [r for r in ct if r["confirmed"] and r["claim_verdict"] in ("correct", "wrong")]
    print(f"\n== confirmed counterexamples with computable GT: n={len(conf)} ==")
    cc = Counter((r["claim_verdict"], r["cand_visible_ok"], r["cand_hidden_ok"]) for r in conf)
    for k in sorted(cc, key=str):
        print(f"   EXPECTED {k[0]:8s} candidate visible_ok={str(k[1]):5s} hidden_ok={str(k[2]):5s}: {cc[k]}")
    right = [r for r in conf if r["claim_verdict"] == "correct"]
    wrong = [r for r in conf if r["claim_verdict"] == "wrong"]
    for nm, g in (("EXPECTED correct", right), ("EXPECTED wrong", wrong)):
        bad = sum(1 for r in g if r["cand_hidden_ok"] is False)
        lo, hi = wilson(bad, len(g)) if g else (float('nan'),) * 2
        print(f"   {nm}: candidate really defective {bad}/{len(g)} = "
              f"{bad/len(g) if g else float('nan'):.3f} (95% CI {lo:.3f}-{hi:.3f})")


if __name__ == "__main__":
    main(sys.argv[1:])
