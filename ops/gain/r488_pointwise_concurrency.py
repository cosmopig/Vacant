#!/usr/bin/env python3
"""R488 P-2: does concurrency AT THE INSTANT A REQUEST STARTS tax its throughput?

Criteria: DECISION_20260905_R488_POINTWISE_CONCURRENCY_PREREG.md (committed first, 6ac4d2e).

Why not R487's exposure. R487 defined exposure as "did this request's LIFETIME overlap
anyone else's". Under fixed completion_tokens, latency = ms_per_tok * tokens, so a slow
request lives longer and therefore overlaps more BY CONSTRUCTION: token matching does not
close that path, and the exposure is a function of the outcome. Counting only the other
requests already open at the instant this one STARTS cannot be caused by this request's
own duration.

That still leaves confounding by period: R486 showed 99.9% of the overlap is the client's
own post-let-go requests, which pile up during slow stretches, so point-in-time
concurrency may be nothing but a marker for "it is a bad time right now". The PLACEBO is
the control for exactly that -- the same exposure function sampled at s_i +/- 30/60 min,
which shares the period but has no causal link to this request.
"""
import argparse, json, math, os, random, statistics, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SNAPSHOT = ROOT / "ops/gain/data/r486_gateway_snapshot_v2.json"

N_BUCKETS = 5
MIN_PER_CELL = 20        # per bucket per arm, to use that bucket
MIN_PER_ARM = 50         # overall, else EXPOSURE_DEGENERATE
MIN_COVERAGE = 0.50
EQUIV_LO, EQUIV_HI = 0.90, 1.15   # same practical-margin band as R487
PLACEBO_SHIFTS = (-3600.0, -1800.0, 1800.0, 3600.0)
BOOTSTRAP_N = 2000
BOOTSTRAP_SEED = 4880


def _mut(name):
    return os.environ.get("R488P2_MUTANT", "") == name


# ------------------------------------------------------------------ data shaping

def is_chat(row):
    return row.get("method") == "POST" and "/v1/chat/completions" in (row.get("path") or "")


def is_analysable(row):
    return (row.get("status_code") == 200 and row.get("finish_reason") == "stop"
            and (row.get("completion_tokens") or 0) > 0
            and (row.get("latency_ms") or 0) > 0)


def interval(row, hyp):
    """(start, end) under hyp in {'start','end'}: whether gateway ts is the start or end."""
    ts = row["ts"]
    lat = (row.get("latency_ms") or 0) / 1000.0
    return (ts, ts + lat) if hyp == "start" else (ts - lat, ts)


def exposure_at(t, ivals, skip=None):
    """How many intervals strictly contain the instant t. `skip` excludes the row itself."""
    n = 0
    for i, (s, e) in enumerate(ivals):
        if skip is not None and i == skip:
            if not _mut("N4_INCLUDE_SELF"):
                continue
        if _mut("N1_LIFETIME_OVERLAP"):
            # the R487 definition this round exists to replace
            ms, me = t
            if s < me and ms < e:
                n += 1
        elif s < t < e:
            n += 1
    return n


def exposures(subset, source, hyp, shift=0.0):
    """Point-in-time exposure for each row of `subset`, sampled at its start + shift.

    Returns (list of C or None, window). None = the sampled instant fell outside the
    observed window, so that row is not measurable for this shift.
    """
    src = [interval(r, hyp) for r in source]
    lo = min(s for s, _ in src)
    hi = max(e for _, e in src)
    idx = {id(r): i for i, r in enumerate(source)}
    out = []
    for r in subset:
        s, e = interval(r, hyp)
        t = s + shift
        if not (lo <= t <= hi):
            out.append(None)
            continue
        probe = (t, t + (e - s)) if _mut("N1_LIFETIME_OVERLAP") else t
        out.append(exposure_at(probe, src, skip=idx.get(id(r))))
    return out, (lo, hi)


def bucketise(vals, k):
    """k quantile edges over vals -> a function mapping a value to bucket index."""
    s = sorted(vals)
    edges = [s[int(len(s) * i / k)] for i in range(1, k)]

    def which(v):
        b = 0
        for ed in edges:
            if v >= ed:
                b += 1
        return b
    return which, edges


# ------------------------------------------------------------------ estimation

def pooled_log_ratio(cells):
    """cells: {bucket: {'hi': [y...], 'lo': [y...]}} -> (pooled log ratio, per-bucket rows).

    Harmonic-n weighted mean of within-bucket log(mean_hi / mean_lo). Stratifying on
    completion_tokens is what keeps this from being a comparison of long vs short answers.
    """
    num = den = 0.0
    detail = []
    for b in sorted(cells):
        hi, lo = cells[b]["hi"], cells[b]["lo"]
        if not _mut("N5_DROP_CELL_MINIMUM") and (len(hi) < MIN_PER_CELL or len(lo) < MIN_PER_CELL):
            continue
        if not hi or not lo:
            continue
        mh, ml = statistics.fmean(hi), statistics.fmean(lo)
        if mh <= 0 or ml <= 0:
            continue
        lr = math.log(mh / ml)
        w = 2.0 * len(hi) * len(lo) / (len(hi) + len(lo))
        num += w * lr
        den += w
        detail.append({"bucket": b, "n_hi": len(hi), "n_lo": len(lo),
                       "mean_hi": mh, "mean_lo": ml, "ratio": mh / ml, "w": w})
    if den == 0:
        return None, detail
    return num / den, detail


def build_cells(recs, which):
    """recs: list of (tokens, exposure, y). Unstratified under N6."""
    cells = {}
    for tok, c, y in recs:
        b = 0 if _mut("N6_DROP_STRATIFICATION") else which(tok)
        arm = "hi" if c >= 1 else "lo"
        cells.setdefault(b, {"hi": [], "lo": []})[arm].append(y)
    return cells


def bootstrap_ci(recs, which, seed=BOOTSTRAP_SEED, n=BOOTSTRAP_N):
    rnd = random.Random(seed)
    pool = list(recs)
    if not pool:
        return None, None
    reps = []
    for _ in range(n):
        samp = [pool[rnd.randrange(len(pool))] for _ in range(len(pool))]
        lr, _d = pooled_log_ratio(build_cells(samp, which))
        if lr is not None:
            reps.append(lr)
    if len(reps) < n * 0.9:
        return None, None
    reps.sort()
    return math.exp(reps[int(0.025 * len(reps))]), math.exp(reps[int(0.975 * len(reps))])


def estimate(subset, source, hyp, which, shift=0.0):
    exp, window = exposures(subset, source, hyp, shift)
    recs, keep = [], []
    for r, c in zip(subset, exp):
        if c is None:
            continue
        recs.append(((r.get("completion_tokens") or 0), c,
                     r["latency_ms"] / r["completion_tokens"]))
        keep.append(r)
    cov = len(recs) / len(subset) if subset else 0.0
    n_hi = sum(1 for _t, c, _y in recs if c >= 1)
    n_lo = len(recs) - n_hi
    lr, detail = pooled_log_ratio(build_cells(recs, which))
    out = {"shift": shift, "coverage": cov, "n": len(recs), "n_hi": n_hi, "n_lo": n_lo,
           "log_ratio": lr, "ratio": (math.exp(lr) if lr is not None else None),
           "buckets": detail, "window": window,
           "kept_ids": [r["id"] for r in keep]}
    return out, recs


def decide(real, placebos):
    """Single decision point. `real` and each placebo are dicts set INDEPENDENTLY by the
    caller, so a fixture can drive every branch without going near a file."""
    if not _mut("N7_DROP_DEGENERATE_GATE") and (
            real.get("n_hi", 0) < MIN_PER_ARM or real.get("n_lo", 0) < MIN_PER_ARM):
        return "EXPOSURE_DEGENERATE"
    if not _mut("N3_DROP_COVERAGE_GATE") and real.get("coverage", 0.0) < MIN_COVERAGE:
        return "UNSCANNED"
    if real.get("ratio") is None or real.get("ci_lo") is None:
        return "UNRESOLVED"
    if not _mut("N3_DROP_COVERAGE_GATE"):
        for p in placebos:
            if p.get("coverage", 0.0) < MIN_COVERAGE or p.get("ratio") is None:
                return "PLACEBO_UNSCANNED"
    if not _mut("N2_DROP_PLACEBO_GATE"):
        mag = abs(math.log(real["ratio"]))
        for p in placebos:
            if abs(math.log(p["ratio"])) >= mag:
                return "PERIOD_CONFOUNDED"
    lo, hi = real["ci_lo"], real["ci_hi"]
    if lo > 1.0:
        return "CONCURRENCY_TAXES"
    if EQUIV_LO <= lo and hi <= EQUIV_HI:
        return "NO_TAX"
    return "UNRESOLVED"


def analyse(rows, hyp):
    chat = [r for r in rows if is_chat(r)]
    subset = [r for r in chat if is_analysable(r)]
    if len(subset) < 2 * MIN_PER_ARM:
        return {"verdict": "UNSCANNED", "reason": f"subset={len(subset)}"}
    which, edges = bucketise([r["completion_tokens"] for r in subset], N_BUCKETS)
    real, recs = estimate(subset, chat, hyp, which, 0.0)
    real["ci_lo"], real["ci_hi"] = bootstrap_ci(recs, which)
    placebos = []
    for sh in PLACEBO_SHIFTS:
        p, _ = estimate(subset, chat, hyp, which, sh)
        placebos.append(p)
    verdict = decide(real, placebos)
    # prereg overturn clause: the placebo drops rows the real estimate keeps, so the two
    # |log ratio|s are not over the same population unless we force a common row set.
    common = set(real["kept_ids"])
    for p in placebos:
        common &= set(p["kept_ids"])
    csub = [r for r in subset if r["id"] in common]
    common_out = None
    if len(csub) >= 2 * MIN_PER_ARM:
        cw, _ = bucketise([r["completion_tokens"] for r in csub], N_BUCKETS)
        creal, crecs = estimate(csub, chat, hyp, cw, 0.0)
        creal["ci_lo"], creal["ci_hi"] = bootstrap_ci(crecs, cw)
        cplac = [estimate(csub, chat, hyp, cw, sh)[0] for sh in PLACEBO_SHIFTS]
        common_out = {"n": len(csub), "verdict": decide(creal, cplac),
                      "real": _slim(creal), "placebos": [_slim(p) for p in cplac]}
    return {"verdict": verdict, "hyp": hyp, "n_subset": len(subset), "n_chat": len(chat),
            "token_edges": edges, "real": _slim(real),
            "placebos": [_slim(p) for p in placebos],
            "common_rowset": common_out}


def _slim(d):
    return {k: v for k, v in d.items() if k != "kept_ids"}


def combine_hypotheses(start, end, ts_verdict):
    """P-1 resolved ts, so the resolved branch is primary and the other is sensitivity.
    Set INDEPENDENTLY by the caller so a fixture can see this gate (r758 M6)."""
    primary = {"TS_IS_START": start, "TS_IS_END": end}.get(ts_verdict)
    if _mut("N8_IGNORE_TS_RESOLUTION"):
        primary = None
    if primary is None:
        agree = start.get("verdict") == end.get("verdict")
        return {"verdict": start.get("verdict") if agree else "TS_SENSITIVE",
                "ts_verdict": ts_verdict, "ts_resolved": False,
                "start": start, "end": end}
    return {"verdict": primary.get("verdict"), "ts_verdict": ts_verdict,
            "ts_resolved": True, "start": start, "end": end,
            "sensitivity_agrees": start.get("verdict") == end.get("verdict")}


def run(path, ts_verdict):
    rows = json.loads(Path(path).read_text())["rows"]
    return combine_hypotheses(analyse(rows, "start"), analyse(rows, "end"), ts_verdict)


# ------------------------------------------------------------------------ selftest

def _row(rid, ts, lat_ms, tok=100, status=200, fin="stop"):
    return {"id": rid, "ts": ts, "latency_ms": lat_ms, "completion_tokens": tok,
            "status_code": status, "finish_reason": fin,
            "method": "POST", "path": "[gw] /v1/chat/completions"}


def selftest():
    ok, fail = 0, []

    def chk(name, cond):
        nonlocal ok
        if cond:
            ok += 1
        else:
            fail.append(name)

    # --- interval semantics: both hypotheses, set independently
    chk("interval start", interval(_row(1, 100.0, 2000.0), "start") == (100.0, 102.0))
    chk("interval end", interval(_row(1, 100.0, 2000.0), "end") == (98.0, 100.0))

    # --- exposure_at is a POINT query, not a lifetime overlap. A request that starts
    # after another has already finished must score 0 even though a lifetime-overlap
    # definition of a *longer* probe would also score 0 -- and, critically, a request
    # that starts before another opens must ALSO score 0 however long it lives.
    ivals = [(0.0, 10.0), (20.0, 30.0)]
    chk("point inside one", exposure_at(5.0, ivals) == 1)
    chk("point in the gap", exposure_at(15.0, ivals) == 0)
    chk("point at open edge is not inside", exposure_at(0.0, ivals) == 0)
    chk("point at close edge is not inside", exposure_at(10.0, ivals) == 0)
    chk("point inside second", exposure_at(25.0, ivals) == 1)
    chk("skip excludes self", exposure_at(5.0, [(0.0, 10.0)], skip=0) == 0)
    chk("skip keeps others", exposure_at(5.0, [(0.0, 10.0), (1.0, 9.0)], skip=0) == 1)

    # THE property this round is built on: lengthening a request cannot raise its own
    # point-in-time exposure, but it does raise its lifetime overlap.
    src = [_row(1, 0.0, 1000.0), _row(2, 50.0, 1000.0)]
    short = _row(3, 100.0, 10.0)
    long_ = _row(3, 100.0, 100000.0)
    es, _ = exposures([short], src + [short], "start")
    el, _ = exposures([long_], src + [long_], "start")
    chk("own duration cannot change own point exposure", es[0] == el[0] == 0)

    # --- bucketise
    which, edges = bucketise(list(range(100)), 5)
    chk("bucket count", len(edges) == 4)
    chk("bucket low", which(0) == 0)
    chk("bucket high", which(99) == 4)
    chk("bucket monotone", all(which(i) <= which(j) for i, j in zip(range(0, 99), range(1, 100))))

    # --- pooled_log_ratio: a known answer, not just "it ran"
    cells = {0: {"hi": [2.0] * 30, "lo": [1.0] * 30}}
    lr, det = pooled_log_ratio(cells)
    chk("pooled ratio 2.0", abs(math.exp(lr) - 2.0) < 1e-12)
    chk("pooled detail one bucket", len(det) == 1)
    chk("pooled harmonic weight", abs(det[0]["w"] - 30.0) < 1e-9)
    chk("thin cell dropped", pooled_log_ratio({0: {"hi": [2.0] * 5, "lo": [1.0] * 30}})[0] is None)
    two = {0: {"hi": [2.0] * 30, "lo": [1.0] * 30}, 1: {"hi": [1.0] * 30, "lo": [2.0] * 30}}
    chk("opposing buckets cancel", abs(pooled_log_ratio(two)[0]) < 1e-12)
    chk("no cells -> None", pooled_log_ratio({})[0] is None)

    # --- decide(): every branch driven by hand-set, independent inputs
    good = {"n_hi": 200, "n_lo": 200, "coverage": 0.9, "ratio": 1.5,
            "ci_lo": 1.3, "ci_hi": 1.7}
    quiet = [{"coverage": 0.9, "ratio": 1.01}]
    chk("decide taxes", decide(good, quiet) == "CONCURRENCY_TAXES")
    chk("decide degenerate",
        decide({**good, "n_hi": 3}, quiet) == "EXPOSURE_DEGENERATE")
    chk("decide degenerate other arm",
        decide({**good, "n_lo": 3}, quiet) == "EXPOSURE_DEGENERATE")
    chk("decide unscanned",
        decide({**good, "coverage": 0.1}, quiet) == "UNSCANNED")
    chk("decide placebo unscanned",
        decide(good, [{"coverage": 0.1, "ratio": 1.01}]) == "PLACEBO_UNSCANNED")
    chk("decide placebo missing ratio",
        decide(good, [{"coverage": 0.9, "ratio": None}]) == "PLACEBO_UNSCANNED")
    chk("decide period confounded",
        decide(good, [{"coverage": 0.9, "ratio": 1.9}]) == "PERIOD_CONFOUNDED")
    chk("decide period confounded by a DOWNWARD placebo",
        decide(good, [{"coverage": 0.9, "ratio": 0.4}]) == "PERIOD_CONFOUNDED")
    # NOTE these two use a real ratio further from 1 than the placebo. That is not
    # cosmetic: see "placebo gate outranks" below -- with real ~= 1.0 the placebo gate
    # fires first and NO_TAX/UNRESOLVED become unreachable.
    chk("decide no_tax",
        decide({**good, "ratio": 1.05, "ci_lo": 0.95, "ci_hi": 1.10}, quiet) == "NO_TAX")
    chk("decide unresolved wide",
        decide({**good, "ratio": 1.05, "ci_lo": 0.5, "ci_hi": 2.0}, quiet) == "UNRESOLVED")
    chk("decide unresolved when ratio missing",
        decide({**good, "ratio": None}, quiet) == "UNRESOLVED")
    chk("decide unresolved when ci missing",
        decide({**good, "ci_lo": None}, quiet) == "UNRESOLVED")
    # the equivalence band means "smaller than the practical margin", NOT "no effect"
    chk("NO_TAX can cover a CI that excludes 1 on the low side",
        decide({**good, "ratio": 0.95, "ci_lo": 0.91, "ci_hi": 0.99}, quiet) == "NO_TAX")

    # DEFECT OF FORM, recorded not repaired (the prereg is locked; r758 handled the
    # absolute-margin rule the same way). The placebo gate is unconditional and sits
    # ABOVE the NO_TAX branch, so the closer the real effect is to null, the easier it is
    # for a near-null placebo to outrank it. A genuinely null result is therefore reported
    # as PERIOD_CONFOUNDED rather than NO_TAX -- the mirror of a forced green light.
    chk("placebo gate outranks a null real effect",
        decide({**good, "ratio": 1.0, "ci_lo": 0.98, "ci_hi": 1.02},
               [{"coverage": 0.9, "ratio": 1.001}]) == "PERIOD_CONFOUNDED")
    chk("NO_TAX is reachable only when real is further from 1 than every placebo",
        decide({**good, "ratio": 1.06, "ci_lo": 0.95, "ci_hi": 1.12},
               [{"coverage": 0.9, "ratio": 1.001}]) == "NO_TAX")

    # --- combine_hypotheses with INDEPENDENTLY set branch verdicts
    A, B = {"verdict": "CONCURRENCY_TAXES"}, {"verdict": "NO_TAX"}
    chk("combine uses resolved start",
        combine_hypotheses(A, B, "TS_IS_START").get("verdict") == "CONCURRENCY_TAXES")
    chk("combine uses resolved end",
        combine_hypotheses(A, B, "TS_IS_END").get("verdict") == "NO_TAX")
    chk("combine flags disagreement in sensitivity",
        combine_hypotheses(A, B, "TS_IS_START").get("sensitivity_agrees") is False)
    chk("combine unresolved ts and branches disagree -> TS_SENSITIVE",
        combine_hypotheses(A, B, "TS_UNRESOLVED_BY_ID").get("verdict") == "TS_SENSITIVE")
    chk("combine unresolved ts but branches agree",
        combine_hypotheses(A, A, "TS_UNRESOLVED_BY_ID").get("verdict") == "CONCURRENCY_TAXES")
    chk("combine records ts_resolved",
        combine_hypotheses(A, B, "TS_IS_START").get("ts_resolved") is True)

    # --- filters
    chk("analysable ok", is_analysable(_row(1, 0.0, 100.0)))
    chk("reject non-200", not is_analysable(_row(1, 0.0, 100.0, status=500)))
    chk("reject length finish", not is_analysable(_row(1, 0.0, 100.0, fin="length")))
    chk("reject zero tokens", not is_analysable(_row(1, 0.0, 100.0, tok=0)))
    chk("reject null tokens", not is_analysable({**_row(1, 0.0, 100.0), "completion_tokens": None}))
    chk("chat filter", is_chat(_row(1, 0.0, 1.0)))
    chk("chat filter rejects GET",
        not is_chat({"method": "GET", "path": "[gw] /api/events"}))

    # --- end-to-end on a synthetic population with a KNOWN planted effect:
    # requests that start while others are open are genuinely 2x slower per token.
    src, sub = [], []
    for i in range(1, 241):
        # 120 in a busy block (overlapping), 120 isolated
        if i <= 120:
            s = 1000.0 + i * 0.5
            tok, mspt = 100 + (i % 5) * 40, 20.0
        else:
            s = 100000.0 + (i - 120) * 500.0
            tok, mspt = 100 + (i % 5) * 40, 10.0
        r = _row(i, s, tok * mspt, tok=tok)
        src.append(r)
        sub.append(r)
    which2, _ = bucketise([r["completion_tokens"] for r in sub], N_BUCKETS)
    est, recs2 = estimate(sub, src, "start", which2, 0.0)
    chk("planted effect recovered ~2x", est["ratio"] is not None and abs(est["ratio"] - 2.0) < 0.05)
    chk("planted effect has both arms", est["n_hi"] >= 50 and est["n_lo"] >= 50)
    chk("planted coverage full", est["coverage"] == 1.0)

    print(f"selftest {ok}/{ok + len(fail)} passed")
    for f in fail:
        print("  FAIL:", f)
    return 0 if not fail else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", default=str(DEFAULT_SNAPSHOT))
    ap.add_argument("--ts-verdict", default="TS_IS_START",
                    help="P-1's answer; drives which hypothesis is primary")
    ap.add_argument("--json")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    out = run(a.snapshot, a.ts_verdict)
    print(f"P-2 verdict {out['verdict']}   ts_verdict={out['ts_verdict']} "
          f"ts_resolved={out['ts_resolved']} sensitivity_agrees={out.get('sensitivity_agrees')}")
    for hyp in ("start", "end"):
        h = out[hyp]
        r = h.get("real", {})
        print(f"  H={hyp:5s} {h.get('verdict'):20s} n_subset={h.get('n_subset')} "
              f"n_hi/lo={r.get('n_hi')}/{r.get('n_lo')} cov={r.get('coverage')}")
        print(f"        real ratio={r.get('ratio')} CI=[{r.get('ci_lo')}, {r.get('ci_hi')}] "
              f"buckets_used={len(r.get('buckets') or [])}")
        for p in h.get("placebos", []):
            print(f"        placebo {p['shift']:+8.0f}s ratio={p.get('ratio')} "
                  f"cov={p.get('coverage'):.3f} n_hi/lo={p.get('n_hi')}/{p.get('n_lo')}")
        c = h.get("common_rowset")
        if c:
            cr = c["real"]
            print(f"        common-rowset n={c['n']} verdict={c['verdict']} "
                  f"ratio={cr.get('ratio')} CI=[{cr.get('ci_lo')}, {cr.get('ci_hi')}] "
                  f"placebo_ratios={[round(x.get('ratio'), 4) if x.get('ratio') else None for x in c['placebos']]}")
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
