"""Reviewer 角色的離線解剖：它吐什麼、丟掉什麼、以及「FAIL 到底對應什麼」。

零 API 呼叫、零 sandbox 呼叫：全部欄位都已經在 runs/<run>/rows.jsonl 的
ON 列（`initial_visible_ok`／`initial_meets_demand`／`review_evidence`／
`reviewer_models`）與 calls.jsonl 的 review 回應文字裡。

V/GT 分離：`initial_meets_demand`（隱藏測資結果）**只做為被解釋的變數**，
沒有任何選擇規則讀它。
"""
from __future__ import annotations

import json
import math
import pathlib
import sys
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[3]
RUNS = ROOT / "runs"


def fisher_exact_2x2(a, b, c, d):
    """雙尾 Fisher exact p（table [[a,b],[c,d]]）。"""
    n = a + b + c + d
    r1, r2, c1 = a + b, c + d, a + c

    def prob(x):
        return (math.comb(r1, x) * math.comb(r2, c1 - x)) / math.comb(n, c1)

    lo = max(0, c1 - r2)
    hi = min(r1, c1)
    p0 = prob(a)
    return min(1.0, sum(prob(x) for x in range(lo, hi + 1) if prob(x) <= p0 * (1 + 1e-9)))


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    ctr = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, ctr - half), min(1.0, ctr + half))


def verdict_class(text: str) -> str:
    s = (text or "").strip()
    if not s:
        return "empty"
    first = s.splitlines()[0].strip().upper()
    if first == "VERDICT: PASS":
        return "PASS"
    if first == "VERDICT: FAIL":
        return "FAIL"
    return "malformed"


def load_run(run: str):
    rows = [json.loads(l) for l in (RUNS / run / "rows.jsonl").open(encoding="utf-8") if l.strip()]
    on = [r for r in rows if r["arm"] == "ON"]
    texts = {}          # (task_id, agent_id) -> last ok review response
    agent_model = {}
    for line in (RUNS / run / "calls.jsonl").open(encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        c = json.loads(line)
        m = c.get("meta") or {}
        if c.get("role") == "gen":
            agent_model.setdefault(c.get("agent_id"), c.get("model"))
        if c.get("role") == "review" and c.get("ok") and m.get("arm") == "ON":
            texts[(m.get("task_id"), c.get("agent_id"))] = c.get("response") or ""
    return on, texts, agent_model


def per_review_records(run):
    on, texts, agent_model = load_run(run)
    recs = []
    for r in on:
        models = r.get("reviewer_models") or []
        for i, ev in enumerate(r.get("review_evidence") or []):
            txt = texts.get((r["task_id"], ev["agent_id"]))
            recs.append({
                "run": run,
                "task_id": r["task_id"],
                "reviewer": ev["agent_id"],
                "reviewer_model": models[i] if i < len(models) else None,
                "worker": r["worker"],
                "worker_model": agent_model.get(r["worker"]),
                "raw_pass": ev["raw_pass"],
                "grounded_pass": ev["grounded_pass"],
                "confirmed": ev["counterexample_confirmed"],
                "status": ev["status"],
                "vclass": verdict_class(txt) if txt is not None else "text_missing",
                "text": txt,
                "cand_visible_ok": r["initial_visible_ok"],
                "cand_hidden_ok": r["initial_meets_demand"],
            })
    return on, recs


def norm_family(model: str | None) -> str:
    if not model:
        return "?"
    m = model.lower()
    if "gemma" in m:
        return "gemma"
    if "qwen" in m:
        return "qwen"
    return m


def table(recs, key_pred, label, out):
    """2x2：raw FAIL(是/否) × key_pred(是/否)."""
    a = sum(1 for r in recs if not r["raw_pass"] and key_pred(r))       # FAIL & event
    b = sum(1 for r in recs if not r["raw_pass"] and not key_pred(r))   # FAIL & no event
    c = sum(1 for r in recs if r["raw_pass"] and key_pred(r))           # PASS & event
    d = sum(1 for r in recs if r["raw_pass"] and not key_pred(r))       # PASS & no event
    n = a + b + c + d
    p_fail_given_event = a / (a + c) if (a + c) else float("nan")
    p_fail_given_not = b / (b + d) if (b + d) else float("nan")
    p = fisher_exact_2x2(a, b, c, d) if n else float("nan")
    out.append({
        "label": label, "n": n,
        "fail_event": a, "fail_noevent": b, "pass_event": c, "pass_noevent": d,
        "P(FAIL|event)": round(p_fail_given_event, 4),
        "P(FAIL|no event)": round(p_fail_given_not, 4),
        "lift_pp": round(100 * (p_fail_given_event - p_fail_given_not), 2),
        "fisher_p": round(p, 5),
    })
    return out[-1]


def main(runs):
    allrecs = []
    allrows = []
    for run in runs:
        on, recs = per_review_records(run)
        allrecs += recs
        allrows += [dict(r, _run=run) for r in on]
        print(f"\n===== {run}: ON rows={len(on)}  review records={len(recs)}")
        print("  verdict class:", dict(Counter(r["vclass"] for r in recs)))
        print("  evidence status:", dict(Counter(r["status"] for r in recs)))
        print("  raw PASS rate: %d/%d = %.4f" % (
            sum(r["raw_pass"] for r in recs), len(recs),
            sum(r["raw_pass"] for r in recs) / max(1, len(recs))))
        print("  grounded PASS rate: %d/%d = %.4f" % (
            sum(r["grounded_pass"] for r in recs), len(recs),
            sum(r["grounded_pass"] for r in recs) / max(1, len(recs))))

    print("\n\n########## POOLED (%d review records over %d runs) ##########" % (
        len(allrecs), len(runs)))
    print("verdict class:", dict(Counter(r["vclass"] for r in allrecs)))
    print("evidence status:", dict(Counter(r["status"] for r in allrecs)))

    # ---- Q1 claim pipeline ------------------------------------------------
    fails = [r for r in allrecs if not r["raw_pass"]]
    print("\n-- Q1 claim pipeline over %d raw-FAIL votes --" % len(fails))
    pipe = Counter(r["status"] for r in fails)
    print("  ", dict(pipe))
    parsed = [r for r in fails if r["status"] in
              ("counterexample_confirmed", "candidate_passed_claim")]
    unpar = [r for r in fails if r["status"] == "unparseable_claim"]
    oob = [r for r in fails if r["status"] == "outside_input_contract"]
    print("  parses AND in-contract: %d/%d = %.4f" % (
        len(parsed), len(fails), len(parsed) / max(1, len(fails))))
    print("  unparseable/no claim  : %d/%d = %.4f" % (
        len(unpar), len(fails), len(unpar) / max(1, len(fails))))
    print("  parsed but out-of-domain: %d/%d = %.4f" % (
        len(oob), len(fails), len(oob) / max(1, len(fails))))
    conf = [r for r in fails if r["confirmed"]]
    print("  machine-confirmed counterexample: %d/%d = %.4f  (of parsed in-contract: %.4f)" % (
        len(conf), len(fails), len(conf) / max(1, len(fails)),
        len(conf) / max(1, len(parsed))))

    # ---- Q3 THE KEY TABLES ------------------------------------------------
    out = []
    print("\n-- Q3a  raw FAIL x candidate VISIBLE failure (all review records) --")
    t = table(allrecs, lambda r: r["cand_visible_ok"] is False, "raw FAIL vs visible-fail", out)
    print("   ", json.dumps(t))
    vis_ok = [r for r in allrecs if r["cand_visible_ok"] is True]
    print("\n-- Q3b  raw FAIL x HIDDEN-ONLY failure (restricted to visible-PASS candidates) --")
    t = table(vis_ok, lambda r: r["cand_hidden_ok"] is False, "raw FAIL vs hidden-only-fail", out)
    print("    n(visible-ok records) =", len(vis_ok))
    print("   ", json.dumps(t))

    print("\n-- Q3c  same two tables using GROUNDED FAIL (confirmed counterexample) --")
    def gtable(recs, pred, label):
        a = sum(1 for r in recs if r["confirmed"] and pred(r))
        b = sum(1 for r in recs if r["confirmed"] and not pred(r))
        c = sum(1 for r in recs if not r["confirmed"] and pred(r))
        d = sum(1 for r in recs if not r["confirmed"] and not pred(r))
        pe = a / (a + c) if (a + c) else float("nan")
        pn = b / (b + d) if (b + d) else float("nan")
        r = {"label": label, "n": a + b + c + d, "conf_event": a, "conf_noevent": b,
             "noconf_event": c, "noconf_noevent": d,
             "P(confirmed|event)": round(pe, 4), "P(confirmed|no event)": round(pn, 4),
             "lift_pp": round(100 * (pe - pn), 2),
             "fisher_p": round(fisher_exact_2x2(a, b, c, d), 5)}
        print("   ", json.dumps(r))
        return r
    gtable(allrecs, lambda r: r["cand_visible_ok"] is False, "confirmed vs visible-fail")
    gtable(vis_ok, lambda r: r["cand_hidden_ok"] is False, "confirmed vs hidden-only-fail")

    # ---- three-way conditional rates --------------------------------------
    print("\n-- Q3d  P(raw FAIL) / P(confirmed) by true candidate state --")
    groups = {
        "visible FAIL (free exec already knows)":
            [r for r in allrecs if r["cand_visible_ok"] is False],
        "visible PASS but hidden FAIL (only place review can add value)":
            [r for r in allrecs if r["cand_visible_ok"] is True and r["cand_hidden_ok"] is False],
        "visible PASS and hidden PASS (correct)":
            [r for r in allrecs if r["cand_visible_ok"] is True and r["cand_hidden_ok"] is True],
    }
    for name, g in groups.items():
        nf = sum(1 for r in g if not r["raw_pass"])
        nc = sum(1 for r in g if r["confirmed"])
        lo, hi = wilson(nf, len(g))
        lo2, hi2 = wilson(nc, len(g))
        print(f"    {name}: n={len(g)}  rawFAIL={nf} ({nf/max(1,len(g)):.4f}, 95% CI {lo:.3f}-{hi:.3f})"
              f"  confirmed={nc} ({nc/max(1,len(g)):.4f}, CI {lo2:.3f}-{hi2:.3f})")

    # ---- row-level (majority) ---------------------------------------------
    print("\n-- Q3e  ROW level: majority raw-FAIL vs candidate state --")
    rrows = []
    for run in runs:
        on, recs = per_review_records(run)
        byrow = defaultdict(list)
        for r in recs:
            byrow[r["task_id"]].append(r)
        for r in on:
            g = byrow[r["task_id"]]
            if not g:
                continue
            rrows.append({
                "run": run, "task_id": r["task_id"],
                "maj_fail": sum(1 for x in g if not x["raw_pass"]) > len(g) / 2,
                "any_fail": any(not x["raw_pass"] for x in g),
                "any_conf": any(x["confirmed"] for x in g),
                "passed_review": r["passed_review"],
                "visible_ok": r["initial_visible_ok"],
                "hidden_ok": r["initial_meets_demand"],
            })
    def rtab(pred_gate, gate_name, subset, ev, ev_name):
        a = sum(1 for r in subset if pred_gate(r) and ev(r))
        b = sum(1 for r in subset if pred_gate(r) and not ev(r))
        c = sum(1 for r in subset if not pred_gate(r) and ev(r))
        d = sum(1 for r in subset if not pred_gate(r) and not ev(r))
        pe = a / (a + c) if (a + c) else float("nan")
        pn = b / (b + d) if (b + d) else float("nan")
        print(f"    {gate_name} x {ev_name}: n={a+b+c+d} "
              f"[gate&ev={a} gate&~ev={b} ~gate&ev={c} ~gate&~ev={d}] "
              f"P(gate|ev)={pe:.4f} P(gate|~ev)={pn:.4f} lift={100*(pe-pn):+.2f}pp "
              f"fisher_p={fisher_exact_2x2(a,b,c,d):.5f}")
    rtab(lambda r: r["any_fail"], "any raw FAIL", rrows,
         lambda r: r["visible_ok"] is False, "visible-fail")
    vok = [r for r in rrows if r["visible_ok"] is True]
    rtab(lambda r: r["any_fail"], "any raw FAIL", vok,
         lambda r: r["hidden_ok"] is False, "hidden-only-fail")
    rtab(lambda r: r["any_conf"], "any confirmed CE", rrows,
         lambda r: r["visible_ok"] is False, "visible-fail")
    rtab(lambda r: r["any_conf"], "any confirmed CE", vok,
         lambda r: r["hidden_ok"] is False, "hidden-only-fail")
    rtab(lambda r: not r["passed_review"], "gate says REJECT", rrows,
         lambda r: r["visible_ok"] is False, "visible-fail")
    rtab(lambda r: not r["passed_review"], "gate says REJECT", vok,
         lambda r: r["hidden_ok"] is False, "hidden-only-fail")
    print("    n rows total =", len(rrows), " n visible-ok rows =", len(vok))

    # ---- Q4 cross family ---------------------------------------------------
    print("\n-- Q4 cross-family vs same-family (per review record) --")
    for run in runs:
        _, recs = per_review_records(run)
        fams = Counter((norm_family(r["reviewer_model"]), norm_family(r["worker_model"]))
                       for r in recs)
        if len({f for f, _ in fams} | {w for _, w in fams}) < 2:
            print(f"    {run}: single family only ({dict(fams)}) -- no contrast")
            continue
        print(f"    {run}: pairs {dict(fams)}")
        for cross in (False, True):
            g = [r for r in recs
                 if (norm_family(r["reviewer_model"]) != norm_family(r["worker_model"])) == cross]
            if not g:
                continue
            nf = sum(1 for r in g if not r["raw_pass"])
            nc = sum(1 for r in g if r["confirmed"])
            gv = [r for r in g if r["cand_visible_ok"] is True]
            hid = [r for r in gv if r["cand_hidden_ok"] is False]
            hidok = [r for r in gv if r["cand_hidden_ok"] is True]
            print(f"      {'CROSS' if cross else 'SAME '}-family n={len(g)}: "
                  f"rawFAIL={nf} ({nf/len(g):.3f}) confirmed={nc} ({nc/len(g):.3f}) | "
                  f"among visible-PASS: P(FAIL|hidden-fail)={ (sum(1 for r in hid if not r['raw_pass'])/len(hid)) if hid else float('nan'):.3f} (n={len(hid)}) "
                  f"P(FAIL|hidden-ok)={ (sum(1 for r in hidok if not r['raw_pass'])/len(hidok)) if hidok else float('nan'):.3f} (n={len(hidok)})")

    # dump per-record file for downstream steps
    dump = ROOT / "ops/gain/replay/reviewer_records.jsonl"
    with dump.open("w", encoding="utf-8") as f:
        for r in allrecs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("\nwrote", dump)


if __name__ == "__main__":
    main(sys.argv[1:])
