#!/usr/bin/env python3
"""R487 gauge: does the self-inflicted gateway concurrency tax NORMAL requests?

Criteria live in DECISION_20260905_R487_CONCURRENCY_TAX_PREREG.md, committed BEFORE
this file. Nothing here may loosen them.

Two things are measured:
  P-1  duration-matched (completion_tokens-stratified) ms/tok ratio, exposed vs unexposed
  P-3  duration-matched null for model reload events (repairs R486's forced-green P-2)
plus P-2, a guard that says whether the duration bias that motivates stratification is
actually present in this data.

Every verdict is computed under BOTH `ts` semantics (start / end) and only adopted when
they agree (R486 amendment A).

Mutation hooks: _mut() is read INSIDE the functions under test, never at module import.
"""
import argparse, json, math, os, random, statistics, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SNAPSHOT = ROOT / "ops/gain/data/r486_gateway_snapshot_v2.json"
BOOT_SEED = 487
BOOT_ITERS = 2000


def _mut(name):
    """Mutation flag, read at call time (never at import) so module-level patching
    of a constant cannot silently no-op the mutant."""
    return os.environ.get("R487_MUTANT", "") == name


# ---------------------------------------------------------------- selection

def is_chat(row):
    return row.get("method") == "POST" and "/v1/chat/completions" in (row.get("path") or "")


def chat_rows(rows):
    return [r for r in rows if is_chat(r)]


def is_ref(row):
    if not is_chat(row):
        return False
    if (row.get("completion_tokens") or 0) < 1:
        return False
    if (row.get("latency_ms") or 0) <= 0:
        return False
    if _mut("M4_REF_IGNORE_ERRORS"):
        return True
    if row.get("error") is not None:
        return False
    return row.get("status_code") == 200


def ref_rows(rows):
    return [r for r in rows if is_ref(r)]


def ms_per_tok(row):
    return row["latency_ms"] / row["completion_tokens"]


# ---------------------------------------------------------------- intervals

def interval(row, hyp):
    """Lifetime interval under a `ts` semantics hypothesis."""
    dur = (row.get("latency_ms") or 0) / 1000.0
    ts = row["ts"]
    if hyp == "start":
        return (ts, ts + dur)
    if hyp == "end":
        return (ts - dur, ts)
    raise ValueError(hyp)


def _ov(a, b):
    return max(0.0, min(a[1], b[1]) - max(a[0], b[0]))


# ---------------------------------------------------------------- exposure

def exposure(ref, allchat, hyp):
    """Returns {id: (exposed_bool_E1, overlap_frac_E2)} for each REF row, where the
    neighbours considered are ALL chat rows (not just REF) other than the row itself."""
    strict_pos = not _mut("M1_OVERLAP_ALLOW_TOUCH")
    riv = [(r["id"], interval(r, hyp), r) for r in ref]
    aiv = [(r["id"], interval(r, hyp)) for r in allchat]
    out = {}
    for rid, iv, row in riv:
        segs = []
        for oid, oiv in aiv:
            if oid == rid and not _mut("M2_OVERLAP_INCLUDES_SELF"):
                continue
            lo, hi = max(iv[0], oiv[0]), min(iv[1], oiv[1])
            # single decision point: a second `if hi > lo` here would make this guard
            # dead code and silently neuter the M1 mutant.
            if hi > lo or (hi == lo and not strict_pos):
                segs.append((lo, hi))
        dur = iv[1] - iv[0]
        merged = []
        for lo, hi in sorted(segs):
            if merged and lo <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], hi))
            else:
                merged.append((lo, hi))
        union = sum(hi - lo for lo, hi in merged)
        frac = (union / dur) if dur > 0 else 0.0
        out[rid] = (len(segs) > 0, min(frac, 1.0))
    return out


# ---------------------------------------------------------------- strata

def quantile_cuts(values, k):
    """k-quantile cut points (k-1 of them) over the whole population."""
    s = sorted(values)
    if not s:
        return []
    return [s[int(round(i * len(s) / k))] if int(round(i * len(s) / k)) < len(s) else s[-1]
            for i in range(1, k)]


def bucket(value, cuts):
    b = 0
    for c in cuts:
        if value >= c:
            b += 1
    return b


def cell_key(row, tok_cuts, prompt_cut_by_bucket, mode):
    if _mut("M7_MATCH_ON_LATENCY"):
        # forbidden by the prereg: latency IS the outcome, matching on it matches the
        # effect away. Kept only as a mutant.
        tb = bucket(row["latency_ms"], tok_cuts)
    else:
        tb = bucket(row["completion_tokens"], tok_cuts)
    if _mut("M3_STRATA_COLLAPSE"):
        tb = 0
    if mode == "tok":
        return (row.get("model"), tb)
    pc = prompt_cut_by_bucket.get(tb)
    pb = 0 if (pc is None or (row.get("prompt_tokens") or 0) < pc) else 1
    return (row.get("model"), tb, pb)


# ---------------------------------------------------------------- estimator

def pooled_log_ratio(cells):
    """cells: {key: (exposed_vals, unexposed_vals)} -> (L, ratio, usable_keys)."""
    num = den = 0.0
    usable = []
    for k, (ex, un) in sorted(cells.items(), key=lambda kv: str(kv[0])):
        if len(ex) < 10 or len(un) < 10:
            continue
        me, mu = statistics.median(ex), statistics.median(un)
        if me <= 0 or mu <= 0:
            continue
        w = len(ex) * len(un) / (len(ex) + len(un))
        if _mut("M5_UNWEIGHTED_POOL"):
            w = 1.0
        num += w * (math.log(me) - math.log(mu))
        den += w
        usable.append(k)
    if den == 0:
        return None, None, usable
    L = num / den
    return L, math.exp(L), usable


def bootstrap_ci(cells, iters=BOOT_ITERS, seed=BOOT_SEED):
    rnd = random.Random(seed)
    use = {k: v for k, v in cells.items() if len(v[0]) >= 10 and len(v[1]) >= 10}
    if not use:
        return None, None
    outs = []
    for _ in range(iters):
        res = {}
        for k, (ex, un) in use.items():
            res[k] = ([ex[rnd.randrange(len(ex))] for _ in ex],
                      [un[rnd.randrange(len(un))] for _ in un])
        _, r, _ = pooled_log_ratio(res)
        if r is not None:
            outs.append(r)
    if len(outs) < iters // 2:
        return None, None
    outs.sort()
    return outs[int(0.025 * len(outs))], outs[int(0.975 * len(outs)) - 1]


# ---------------------------------------------------------------- verdicts

def verdict_p1(ratio, lo, hi, n_usable_cells, n_exp, n_unexp):
    if n_usable_cells < 3 or n_exp < 30 or n_unexp < 30 or ratio is None or lo is None:
        return "UNSCANNED"
    if ratio >= 1.20 and lo > 1.00:
        return "CONCURRENCY_TAXES"
    if lo >= 0.90 and hi <= 1.15:
        return "NO_TAX"
    return "UNRESOLVED"


def verdict_p2(rate_top, rate_bot):
    if rate_top is None or rate_bot is None:
        return "UNSCANNED"
    return "DURATION_BIAS_PRESENT" if (rate_top - rate_bot) >= 0.10 else "DURATION_BIAS_ABSENT"


def verdict_p3(O, E, p, n_events):
    if n_events < 5:
        return "UNSCANNED"
    if E <= 0:
        return "UNSCANNED"
    r = O / E
    if r >= 1.5 and p < 0.05:
        return "RELOAD_EXCESS"
    if 0.67 <= r <= 1.5:
        return "RELOAD_AS_CHANCE"
    if r < 0.67 and p < 0.05:
        return "RELOAD_DEFICIT"
    return "UNRESOLVED"


# ---------------------------------------------------------------- P-3

def _phi(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def reload_duration_matched(allchat, events, hyp):
    """Duration-matched Poisson null for 'did a load/unload event land inside this
    request's lifetime'. Replaces R486's fixed-threshold P-2, which round757 proved
    was structurally forced green."""
    if not allchat:
        return dict(O=0, E=0.0, ratio=None, z=None, p=None, n_events=0, lam=None)
    ivs = [interval(r, hyp) for r in allchat]
    t0 = min(iv[0] for iv in ivs)
    t1 = max(iv[1] for iv in ivs)
    span = max(t1 - t0, 1e-9)
    ev = [e for e in events if t0 <= e["ts"] <= t1]
    lam = len(ev) / span
    if _mut("M6_RELOAD_FIXED_NULL"):
        lam = 0.0
    O = 0
    E = 0.0
    var = 0.0
    for iv in ivs:
        d = max(iv[1] - iv[0], 0.0)
        p_i = 1.0 - math.exp(-lam * d)
        E += p_i
        var += p_i * (1.0 - p_i)
        if any(iv[0] <= e["ts"] <= iv[1] for e in ev):
            O += 1
    if var > 0:
        z = (O - E) / math.sqrt(var)
        p = 2.0 * (1.0 - _phi(abs(z)))
    else:
        z = p = None
    return dict(O=O, E=E, ratio=(O / E if E > 0 else None), z=z, p=p,
                n_events=len(ev), lam=lam, span_s=span)


# ---------------------------------------------------------------- analysis

def analyze_one(rows, events, hyp, strat_mode):
    allchat = chat_rows(rows)
    ref = ref_rows(rows)
    exp = exposure(ref, allchat, hyp)
    tok_cuts = quantile_cuts([r["completion_tokens"] for r in ref], 5)

    prompt_cut = {}
    if strat_mode == "tok_prompt":
        by_b = {}
        for r in ref:
            by_b.setdefault(bucket(r["completion_tokens"], tok_cuts), []).append(
                r.get("prompt_tokens") or 0)
        prompt_cut = {b: statistics.median(v) for b, v in by_b.items()}

    cells = {}
    n_exp = n_unexp = 0
    rate_num = {}
    rate_den = {}
    for r in ref:
        e1, _frac = exp[r["id"]]
        k = cell_key(r, tok_cuts, prompt_cut, strat_mode)
        ex, un = cells.setdefault(k, ([], []))
        (ex if e1 else un).append(ms_per_tok(r))
        n_exp += 1 if e1 else 0
        n_unexp += 0 if e1 else 1
        tb = bucket(r["completion_tokens"], tok_cuts)
        rate_den[tb] = rate_den.get(tb, 0) + 1
        rate_num[tb] = rate_num.get(tb, 0) + (1 if e1 else 0)

    L, ratio, usable = pooled_log_ratio(cells)
    lo, hi = bootstrap_ci(cells)
    p1 = verdict_p1(ratio, lo, hi, len(usable), n_exp, n_unexp)

    tb_all = sorted(rate_den)
    rate_top = (rate_num[tb_all[-1]] / rate_den[tb_all[-1]]) if tb_all else None
    rate_bot = (rate_num[tb_all[0]] / rate_den[tb_all[0]]) if tb_all else None
    p2 = verdict_p2(rate_top, rate_bot)

    rl = reload_duration_matched(allchat, events, hyp)
    p3 = verdict_p3(rl["O"], rl["E"], rl["p"] if rl["p"] is not None else 1.0, rl["n_events"])

    # E2 secondary (declared in the prereg, reported unconditionally)
    cells2 = {}
    for r in ref:
        _e1, frac = exp[r["id"]]
        if 0.05 <= frac < 0.5:
            continue
        k = cell_key(r, tok_cuts, prompt_cut, strat_mode)
        ex, un = cells2.setdefault(k, ([], []))
        (ex if frac >= 0.5 else un).append(ms_per_tok(r))
    L2, ratio2, usable2 = pooled_log_ratio(cells2)
    lo2, hi2 = bootstrap_ci(cells2)
    n_exp2 = sum(len(v[0]) for v in cells2.values())
    n_unexp2 = sum(len(v[1]) for v in cells2.values())
    p1_e2 = verdict_p1(ratio2, lo2, hi2, len(usable2), n_exp2, n_unexp2)

    fr = {}
    for r in ref:
        fr[r.get("finish_reason")] = fr.get(r.get("finish_reason"), 0) + 1

    return dict(hyp=hyp, strat=strat_mode,
                n_chat=len(allchat), n_ref=len(ref),
                tok_cuts=tok_cuts, n_cells=len(cells), usable_cells=len(usable),
                n_exposed=n_exp, n_unexposed=n_unexp,
                ratio=ratio, ci_lo=lo, ci_hi=hi, p1=p1,
                exposure_rate_by_tok_bucket={str(b): rate_num[b] / rate_den[b] for b in tb_all},
                rate_top=rate_top, rate_bot=rate_bot, p2=p2,
                reload=rl, p3=p3,
                e2=dict(ratio=ratio2, ci_lo=lo2, ci_hi=hi2, usable_cells=len(usable2),
                        n_exposed=n_exp2, n_unexposed=n_unexp2, verdict=p1_e2),
                finish_reason=fr)


def combine(v):
    """Apply the two global gates from the prereg to the four per-configuration verdicts.

    `v` maps "<hyp>|<strat>" -> {"p1":..,"p2":..,"p3":..}. Kept separate from analyze_one
    so that a fixture can set the four inputs INDEPENDENTLY -- if the gate's inputs were
    derived from one another no fixture could ever see the gate fail.
    """
    a1, b1 = v["start|tok"]["p1"], v["end|tok"]["p1"]
    a2, b2 = v["start|tok"]["p2"], v["end|tok"]["p2"]
    a3, b3 = v["start|tok"]["p3"], v["end|tok"]["p3"]
    ts_ok_p1 = (a1 == b1) or _mut("M8_DROP_TS_AGREEMENT")
    ts_ok_p2 = (a2 == b2) or _mut("M8_DROP_TS_AGREEMENT")
    ts_ok_p3 = (a3 == b3) or _mut("M8_DROP_TS_AGREEMENT")
    strat_ok = (v["start|tok"]["p1"] == v["start|tok_prompt"]["p1"]
                and v["end|tok"]["p1"] == v["end|tok_prompt"]["p1"])
    if _mut("M9_DROP_STRAT_AGREEMENT"):
        strat_ok = True
    out = {}
    out["ts_sensitive"] = {"p1": not ts_ok_p1, "p2": not ts_ok_p2, "p3": not ts_ok_p3}
    out["strat_sensitive"] = not strat_ok
    out["p1"] = a1 if ts_ok_p1 else "TS_SENSITIVE"
    if out["p1"] not in ("UNSCANNED", "TS_SENSITIVE") and not strat_ok:
        out["p1"] = "UNRESOLVED"
    out["p2"] = a2 if ts_ok_p2 else "TS_SENSITIVE"
    out["p3"] = a3 if ts_ok_p3 else "TS_SENSITIVE"
    out["p1_raw"] = {"start_tok": a1, "end_tok": b1,
                     "start_tokprompt": v["start|tok_prompt"]["p1"],
                     "end_tokprompt": v["end|tok_prompt"]["p1"]}
    out["p2_raw"] = {"start": a2, "end": b2}
    out["p3_raw"] = {"start": a3, "end": b3}
    return out


def run(snapshot_path):
    d = json.loads(Path(snapshot_path).read_text())
    rows, events = d["rows"], d["events"]
    res = {}
    for hyp in ("start", "end"):
        for sm in ("tok", "tok_prompt"):
            res[f"{hyp}|{sm}"] = analyze_one(rows, events, hyp, sm)
    out = {"rows_scanned": len(rows), "events_scanned": len(events)}
    out.update(combine(res))
    out["detail"] = res
    return out


# ---------------------------------------------------------------- selftest

def _row(rid, ts, lat, ctok=10, ptok=100, model="m", status=200, err=None,
         method="POST", path="[gw] /v1/chat/completions", fr="stop"):
    return dict(id=rid, ts=ts, latency_ms=lat, completion_tokens=ctok, prompt_tokens=ptok,
                model=model, status_code=status, error=err, method=method, path=path,
                finish_reason=fr)


def selftest():
    ok = 0
    fail = []

    def chk(name, cond):
        nonlocal ok
        if cond:
            ok += 1
        else:
            fail.append(name)

    # --- selection
    chk("chat_post", is_chat(_row(1, 0, 100)))
    chk("chat_get_excluded", not is_chat(_row(1, 0, 100, method="GET")))
    chk("chat_path_excluded", not is_chat(_row(1, 0, 100, path="[gw] /api/events")))
    chk("ref_ok", is_ref(_row(1, 0, 100)))
    chk("ref_zero_tokens", not is_ref(_row(1, 0, 100, ctok=0)))
    chk("ref_null_tokens", not is_ref(dict(_row(1, 0, 100), completion_tokens=None)))
    chk("ref_zero_latency", not is_ref(_row(1, 0, 0)))
    chk("ref_error", not is_ref(_row(1, 0, 100, err="boom")))
    chk("ref_status500", not is_ref(_row(1, 0, 100, status=500)))
    chk("ref_needs_chat", not is_ref(_row(1, 0, 100, method="GET")))

    # --- intervals (hand computed, not via interval())
    chk("iv_start", interval(_row(1, 1000.0, 2500.0), "start") == (1000.0, 1002.5))
    chk("iv_end", interval(_row(1, 1000.0, 2500.0), "end") == (997.5, 1000.0))
    try:
        interval(_row(1, 0, 1), "middle")
        chk("iv_bad_hyp", False)
    except ValueError:
        chk("iv_bad_hyp", True)

    # --- overlap primitive
    chk("ov_disjoint", _ov((0, 1), (2, 3)) == 0)
    chk("ov_touch_zero", _ov((0, 1), (1, 2)) == 0)
    chk("ov_partial", abs(_ov((0, 10), (5, 20)) - 5) < 1e-9)
    chk("ov_contained", abs(_ov((0, 10), (2, 4)) - 2) < 1e-9)

    # --- exposure: hand-built scenario, expectations written out by hand
    #   A=[0,10) B=[5,20) C=[100,110) D touches A exactly at 10 -> must NOT expose
    A = _row(1, 0.0, 10000.0)
    B = _row(2, 5.0, 15000.0)
    C = _row(3, 100.0, 10000.0)
    D = _row(4, 110.0, 5000.0)      # [110,115]: touches C at exactly 110, nothing else
    ex = exposure([A, B, C, D], [A, B, C, D], "start")
    chk("exp_A", ex[1][0] is True)
    chk("exp_B", ex[2][0] is True)
    chk("exp_C_touch_only", ex[3][0] is False)   # C's only neighbour touches at a point
    chk("exp_D_touch_only", ex[4][0] is False)
    chk("frac_A", abs(ex[1][1] - 0.5) < 1e-9)          # A overlaps B on [5,10) of [0,10)
    chk("frac_C", ex[3][1] == 0.0)
    chk("frac_D", ex[4][1] == 0.0)
    #   union, not sum: two neighbours covering the same span must not exceed 1.0
    E1 = _row(5, 0.0, 10000.0)
    E2 = _row(6, 0.0, 10000.0)
    E3 = _row(7, 0.0, 10000.0)
    exu = exposure([E1], [E1, E2, E3], "start")
    chk("frac_union_capped", abs(exu[5][1] - 1.0) < 1e-9)
    #   neighbours may be non-REF chat rows
    NR = _row(8, 0.0, 10000.0, status=500, err="x")
    exn = exposure([A], [A, NR], "start")
    chk("exp_neighbour_can_be_nonref", exn[1][0] is True)
    #   self must never expose itself
    exs = exposure([C], [C], "start")
    chk("exp_no_self", exs[3][0] is False)

    # --- strata
    cuts = quantile_cuts([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 5)
    chk("cuts_len", len(cuts) == 4)
    chk("cuts_sorted", cuts == sorted(cuts))
    chk("bucket_low", bucket(0, [3, 5, 7, 9]) == 0)
    chk("bucket_high", bucket(100, [3, 5, 7, 9]) == 4)
    chk("bucket_edge_inclusive", bucket(3, [3, 5, 7, 9]) == 1)
    chk("cuts_empty", quantile_cuts([], 5) == [])

    # --- pooled estimator: hand computed
    #   cell X: exposed median 2.0, unexposed median 1.0 -> L=ln2, n 10/10 -> w=5
    #   cell Y: exposed median 1.0, unexposed median 1.0 -> L=0,    n 10/10 -> w=5
    cx = {("m", 0): ([2.0] * 10, [1.0] * 10), ("m", 1): ([1.0] * 10, [1.0] * 10)}
    L, ratio, usable = pooled_log_ratio(cx)
    chk("pool_L", abs(L - math.log(2) / 2) < 1e-9)
    chk("pool_ratio", abs(ratio - math.sqrt(2)) < 1e-9)
    chk("pool_usable", len(usable) == 2)
    #   weighting really is n_e*n_u/(n_e+n_u): make one cell much bigger
    cw = {("m", 0): ([2.0] * 100, [2.0 / math.e] * 100), ("m", 1): ([1.0] * 10, [1.0] * 10)}
    _, rw, _ = pooled_log_ratio(cw)
    chk("pool_weighted_toward_big_cell", rw > math.exp(0.5 * 1.0))
    #   thin cells are dropped
    ct = {("m", 0): ([2.0] * 9, [1.0] * 50), ("m", 1): ([1.0] * 10, [1.0] * 10)}
    _, _, ut = pooled_log_ratio(ct)
    chk("pool_drops_thin", ut == [("m", 1)])
    chk("pool_all_thin_none", pooled_log_ratio({("m", 0): ([1.0], [1.0])})[1] is None)

    # --- bootstrap
    same = {("m", 0): ([1.0, 1.1, 0.9] * 10, [1.0, 1.1, 0.9] * 10),
            ("m", 1): ([2.0, 2.2, 1.8] * 10, [2.0, 2.2, 1.8] * 10),
            ("m", 2): ([3.0, 3.3, 2.7] * 10, [3.0, 3.3, 2.7] * 10)}
    blo, bhi = bootstrap_ci(same, iters=200, seed=1)
    chk("boot_contains_one", blo <= 1.0 <= bhi)
    chk("boot_deterministic", bootstrap_ci(same, iters=200, seed=1) ==
         bootstrap_ci(same, iters=200, seed=1))
    chk("boot_no_usable", bootstrap_ci({("m", 0): ([1.0], [1.0])}) == (None, None))

    # --- P-1 verdict table
    chk("p1_taxes", verdict_p1(1.5, 1.2, 1.9, 5, 100, 100) == "CONCURRENCY_TAXES")
    chk("p1_ratio_but_ci", verdict_p1(1.5, 0.95, 2.0, 5, 100, 100) == "UNRESOLVED")
    # significant but below the practical margin -> NO_TAX by prereg design, not UNRESOLVED
    chk("p1_small_but_significant_is_no_tax",
        verdict_p1(1.05, 1.01, 1.10, 5, 100, 100) == "NO_TAX")
    chk("p1_ratio_ge_but_ci_low", verdict_p1(1.30, 0.99, 1.60, 5, 100, 100) == "UNRESOLVED")
    chk("p1_no_tax", verdict_p1(1.02, 0.95, 1.10, 5, 100, 100) == "NO_TAX")
    chk("p1_wide", verdict_p1(1.02, 0.5, 1.9, 5, 100, 100) == "UNRESOLVED")
    chk("p1_unscanned_cells", verdict_p1(1.5, 1.2, 1.9, 2, 100, 100) == "UNSCANNED")
    chk("p1_unscanned_exp", verdict_p1(1.5, 1.2, 1.9, 5, 29, 100) == "UNSCANNED")
    chk("p1_unscanned_unexp", verdict_p1(1.5, 1.2, 1.9, 5, 100, 29) == "UNSCANNED")
    chk("p1_unscanned_beats_unresolved", verdict_p1(1.0, 0.1, 9.9, 1, 5, 5) == "UNSCANNED")
    chk("p1_none_ratio", verdict_p1(None, None, None, 5, 100, 100) == "UNSCANNED")

    # --- P-2 verdict
    chk("p2_present", verdict_p2(0.9, 0.5) == "DURATION_BIAS_PRESENT")
    chk("p2_absent_ceiling", verdict_p2(1.0, 0.99) == "DURATION_BIAS_ABSENT")
    # NB: the >=0.10 boundary is float-exact (0.60-0.50 == 0.0999...); test off the edge
    chk("p2_just_over", verdict_p2(0.62, 0.50) == "DURATION_BIAS_PRESENT")
    chk("p2_just_under", verdict_p2(0.55, 0.50) == "DURATION_BIAS_ABSENT")
    chk("p2_unscanned", verdict_p2(None, 0.5) == "UNSCANNED")

    # --- P-3 verdict
    chk("p3_excess", verdict_p3(30, 10.0, 0.001, 16) == "RELOAD_EXCESS")
    chk("p3_chance", verdict_p3(10, 10.0, 0.9, 16) == "RELOAD_AS_CHANCE")
    chk("p3_deficit", verdict_p3(1, 10.0, 0.001, 16) == "RELOAD_DEFICIT")
    chk("p3_excess_needs_p", verdict_p3(30, 10.0, 0.9, 16) == "UNRESOLVED")
    chk("p3_unscanned_events", verdict_p3(30, 10.0, 0.001, 4) == "UNSCANNED")
    chk("p3_unscanned_zeroE", verdict_p3(0, 0.0, 1.0, 16) == "UNSCANNED")

    # --- P-3 mechanics on synthetic data with a hand-computable answer
    #   4 requests of 10s inside a 1000s span, 10 events -> lam=0.01, p_i=1-e^-0.1=0.0952
    syn = [_row(i, 100.0 * i, 10000.0) for i in range(1, 5)]
    evs = [dict(ts=100.0 * i + 5.0, event="loaded") for i in range(1, 11)]
    rl = reload_duration_matched(syn, evs, "start")
    chk("p3_lam_from_window", rl["n_events"] == 4)          # only 4 events land in span
    chk("p3_O_counts_inside", rl["O"] == 4)
    chk("p3_E_positive", rl["E"] > 0)
    chk("p3_no_events", reload_duration_matched(syn, [], "start")["n_events"] == 0)
    chk("p3_no_rows", reload_duration_matched([], evs, "start")["O"] == 0)
    #   an event outside every interval must not be counted as a hit
    syn2 = [_row(1, 0.0, 1000.0), _row(2, 500.0, 1000.0)]
    rl2 = reload_duration_matched(syn2, [dict(ts=300.0, event="loaded")], "start")
    chk("p3_event_outside", rl2["O"] == 0 and rl2["n_events"] == 1)

    # --- normal tail
    chk("phi_center", abs(_phi(0.0) - 0.5) < 1e-12)
    chk("phi_196", abs(_phi(1.96) - 0.975) < 1e-3)

    # --- end-to-end on a synthetic snapshot whose answer is known by construction:
    #   exposed rows are made 2x slower per token; expect ratio ~2 and TAXES
    rows = []
    rid = 0
    for b in range(5):
        ctok = 10 + 20 * b
        for i in range(15):                      # exposed cluster, all overlapping
            rid += 1
            rows.append(_row(rid, 10000.0 + b * 1000, ctok * 2.0 * 10, ctok=ctok))
        for i in range(15):                      # isolated, far apart
            rid += 1
            rows.append(_row(rid, 500000.0 + rid * 1000, ctok * 1.0 * 10, ctok=ctok))
    synres = analyze_one(rows, [], "start", "tok")
    chk("e2e_ratio_near_2", synres["ratio"] is not None and abs(synres["ratio"] - 2.0) < 0.05)
    chk("e2e_verdict", synres["p1"] == "CONCURRENCY_TAXES")
    chk("e2e_cells", synres["usable_cells"] == 5)
    chk("e2e_split", synres["n_exposed"] == 75 and synres["n_unexposed"] == 75)
    chk("e2e_p3_unscanned_no_events", synres["p3"] == "UNSCANNED")
    #   null version: same structure, no speed difference -> must not say TAXES
    rows0 = [dict(r) for r in rows]
    for r in rows0:
        r["latency_ms"] = r["completion_tokens"] * 10.0
    null = analyze_one(rows0, [], "start", "tok")
    chk("e2e_null_not_taxes", null["p1"] != "CONCURRENCY_TAXES")
    chk("e2e_null_no_tax", null["p1"] == "NO_TAX")

    # --- global gates (inputs set independently, never derived from one another)
    def V(a, b, c, d, e, f, g, h):
        return {"start|tok": {"p1": a, "p2": b, "p3": c},
                "end|tok": {"p1": d, "p2": e, "p3": f},
                "start|tok_prompt": {"p1": g, "p2": b, "p3": c},
                "end|tok_prompt": {"p1": h, "p2": e, "p3": f}}
    g_all = combine(V("NO_TAX", "DURATION_BIAS_PRESENT", "RELOAD_AS_CHANCE",
                      "NO_TAX", "DURATION_BIAS_PRESENT", "RELOAD_AS_CHANCE",
                      "NO_TAX", "NO_TAX"))
    chk("gate_agree_p1", g_all["p1"] == "NO_TAX")
    chk("gate_agree_p2", g_all["p2"] == "DURATION_BIAS_PRESENT")
    chk("gate_agree_p3", g_all["p3"] == "RELOAD_AS_CHANCE")
    chk("gate_clean_flags", g_all["strat_sensitive"] is False
        and g_all["ts_sensitive"] == {"p1": False, "p2": False, "p3": False})
    g_ts1 = combine(V("CONCURRENCY_TAXES", "DURATION_BIAS_PRESENT", "RELOAD_AS_CHANCE",
                      "NO_TAX", "DURATION_BIAS_PRESENT", "RELOAD_AS_CHANCE",
                      "CONCURRENCY_TAXES", "NO_TAX"))
    chk("gate_ts_p1_sensitive", g_ts1["p1"] == "TS_SENSITIVE" and g_ts1["ts_sensitive"]["p1"])
    chk("gate_ts_p1_only", g_ts1["p2"] == "DURATION_BIAS_PRESENT" and g_ts1["p3"] == "RELOAD_AS_CHANCE")
    g_ts3 = combine(V("NO_TAX", "DURATION_BIAS_PRESENT", "RELOAD_EXCESS",
                      "NO_TAX", "DURATION_BIAS_PRESENT", "RELOAD_AS_CHANCE",
                      "NO_TAX", "NO_TAX"))
    chk("gate_ts_p3_sensitive", g_ts3["p3"] == "TS_SENSITIVE")
    chk("gate_ts_p3_leaves_p1", g_ts3["p1"] == "NO_TAX")
    g_st = combine(V("CONCURRENCY_TAXES", "DURATION_BIAS_PRESENT", "RELOAD_AS_CHANCE",
                     "CONCURRENCY_TAXES", "DURATION_BIAS_PRESENT", "RELOAD_AS_CHANCE",
                     "NO_TAX", "CONCURRENCY_TAXES"))
    chk("gate_strat_downgrades", g_st["p1"] == "UNRESOLVED" and g_st["strat_sensitive"])
    g_un = combine(V("UNSCANNED", "UNSCANNED", "UNSCANNED",
                     "UNSCANNED", "UNSCANNED", "UNSCANNED",
                     "NO_TAX", "NO_TAX"))
    chk("gate_unscanned_survives_strat", g_un["p1"] == "UNSCANNED")

    print(f"selftest {ok}/{ok + len(fail)} passed" + (f"  FAILED={fail}" if fail else ""))
    return 0 if not fail else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", default=str(DEFAULT_SNAPSHOT))
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    out = run(a.snapshot)
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=2, sort_keys=True))
    d = out["detail"]["start|tok"]
    print(f"  P-1 {out['p1']}  (start|tok ratio={d['ratio']} CI=[{d['ci_lo']},{d['ci_hi']}] "
          f"cells={d['usable_cells']} exp/unexp={d['n_exposed']}/{d['n_unexposed']})")
    print(f"  P-2 {out['p2']}  rate_bot={d['rate_bot']} rate_top={d['rate_top']} "
          f"by_bucket={d['exposure_rate_by_tok_bucket']}")
    r = d["reload"]
    print(f"  P-3 {out['p3']}  O={r['O']} E={r['E']:.2f} ratio={r['ratio']} "
          f"z={r['z']} p={r['p']} events={r['n_events']}")
    print(f"  E2(secondary) {d['e2']['verdict']} ratio={d['e2']['ratio']} "
          f"CI=[{d['e2']['ci_lo']},{d['e2']['ci_hi']}] n={d['e2']['n_exposed']}/{d['e2']['n_unexposed']}")
    print(f"  gates ts_sensitive={out['ts_sensitive']} strat_sensitive={out['strat_sensitive']}")
    print(f"  raw p1={out['p1_raw']}  p2={out['p2_raw']}  p3={out['p3_raw']}")
    print(f"  n_chat={d['n_chat']} n_ref={d['n_ref']} finish_reason={d['finish_reason']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
