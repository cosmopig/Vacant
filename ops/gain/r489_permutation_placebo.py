#!/usr/bin/env python3
"""R489: point-in-time concurrency exposure with a WITHIN-BLOCK PERMUTATION placebo.

Criteria: DECISION_20260905_R489_PERMUTATION_PLACEBO_PREREG.md (committed first, 742a06a).
Synthetic reproduction justifying the gate-order repair: r489_gate_order_demo.py (8d6575f).

R488's placebo sampled the exposure function at s_i +/- 30/60 min. The client is
sequential, so a real start instant is mechanically "the moment a seat just freed up",
while a shifted instant is a structurally different kind of moment: the low-exposure arm
collapsed from 728 rows to 2-10 and the placebo could not be scanned at all.

This placebo instead hands row i the start instant OF ANOTHER ROW, drawn by permuting
start instants inside time blocks of width B. The multiset of instants inside a block is
unchanged, so the marginal exposure distribution is preserved by construction (the arms
cannot collapse); the donor's instant cannot be caused by row i's own throughput; and
period structure coarser than B survives, which is the confound the placebo exists to
absorb.

The estimator itself (interval, exposure, stratified pooled ratio, bootstrap) is IMPORTED
from r488_pointwise_concurrency rather than copied, so the two rounds cannot drift apart.
"""
import argparse, bisect, json, math, os, random, statistics, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))

import r488_pointwise_concurrency as R488  # noqa: E402
from r488_pointwise_concurrency import (  # noqa: E402
    MIN_COVERAGE, MIN_PER_ARM, N_BUCKETS, EQUIV_LO, EQUIV_HI,
    bootstrap_ci, bucketise, build_cells, exposure_at, interval,
    is_analysable, is_chat, pooled_log_ratio,
)

DEFAULT_SNAPSHOT = ROOT / "ops/gain/data/r486_gateway_snapshot_v2.json"
SNAPSHOT_SHA = "060efe0ce91975269b73de61de65c4e3c7fb447bb83b3273d96a73af950ce59c"

# --- prereg'd constants (DECISION_20260905_R489_..._PREREG.md) ---------------
BLOCK_LADDER = (60.0, 300.0, 900.0, 1800.0, 3600.0, None)   # None = whole window
PRIMARY_BLOCK = 1800.0
N_REPLICATES = 20
PERM_SEED = 4890
ANCHOR_A_MAX_ABS_LOG = 0.08      # global permutation must be ~null
ANCHOR_B_MIN_AGREEMENT = 0.50    # B=60s must reproduce the real exposure often

VERDICTS = ("EXPOSURE_DEGENERATE", "UNSCANNED", "UNRESOLVED", "NO_TAX",
            "PLACEBO_LADDER_BROKEN", "PLACEBO_UNSCANNED", "PLACEBO_DEGENERATE",
            "PERIOD_CONFOUNDED", "TAXES_BELOW_MARGIN", "CONCURRENCY_TAXES",
            "SPEEDUP_ANOMALY")


def _mut(name):
    return os.environ.get("R489_MUTANT", "") == name


def contamination_check():
    """r488's own mutant hook must be off, or every number here is from mutated code."""
    leaked = os.environ.get("R488P2_MUTANT", "")
    if leaked:
        raise SystemExit(f"REFUSING: R488P2_MUTANT={leaked!r} would mutate the imported estimator")


# ------------------------------------------------------------------ exposure (fast path)

class ExposureIndex:
    """count of intervals with s < t < e, in O(log n). Proven equivalent to r488's
    exposure_at() by exhaustive random comparison in selftest()."""

    def __init__(self, ivals):
        self.ivals = list(ivals)
        self.starts = sorted(s for s, _ in self.ivals)
        self.ends = sorted(e for _, e in self.ivals)

    def at(self, t, skip=None):
        n = bisect.bisect_left(self.starts, t) - bisect.bisect_right(self.ends, t)
        if skip is not None and not _mut("P4_PLACEBO_INCLUDE_SELF"):
            s, e = self.ivals[skip]
            if s < t < e:
                n -= 1
        return n


# ------------------------------------------------------------------ the permutation

def block_of(s, lo, block_s):
    if block_s is None or _mut("P2_GLOBAL_BLOCKS"):
        return 0
    return int((s - lo) // block_s)


def permute_donors(starts, lo, block_s, rnd):
    """-> list of donor start instants (None where the block has fewer than 2 members).

    Inside a block the members are shuffled and then rotated by one, i.e. mapped onto a
    single cycle. A cycle of length >= 2 has no fixed point, so no row can be handed back
    its own instant -- that is what makes this a placebo rather than the real estimate.
    """
    blocks = {}
    for i, s in enumerate(starts):
        blocks.setdefault(block_of(s, lo, block_s), []).append(i)
    donors = [None] * len(starts)
    for members in blocks.values():
        if len(members) < 2:
            continue
        order = list(members)
        rnd.shuffle(order)
        for k, idx in enumerate(order):
            j = order[(k + 1) % len(order)]
            if _mut("P1_NO_DERANGEMENT"):
                j = idx
            donors[idx] = starts[j]
    return donors


# ------------------------------------------------------------------ estimation

def estimate_at(subset, index, instants, which, real_exposures=None):
    """instants[i] is where to sample row i (None = not measurable for this row)."""
    recs, exps, agree = [], [], []
    for i, (r, t) in enumerate(zip(subset, instants)):
        if t is None:
            exps.append(None)
            continue
        c = index.at(t, skip=i)
        exps.append(c)
        recs.append(((r.get("completion_tokens") or 0), c,
                     r["latency_ms"] / r["completion_tokens"]))
        if real_exposures is not None and real_exposures[i] is not None:
            agree.append(1.0 if c == real_exposures[i] else 0.0)
    lr, detail = pooled_log_ratio(build_cells(recs, which))
    n_hi = sum(1 for _t, c, _y in recs if c >= 1)
    out = {"coverage": (len(recs) / len(subset)) if subset else 0.0,
           "n": len(recs), "n_hi": n_hi, "n_lo": len(recs) - n_hi,
           "log_ratio": lr, "ratio": (math.exp(lr) if lr is not None else None),
           "buckets": detail,
           "agreement": (statistics.fmean(agree) if agree else None)}
    return out, recs, exps


def _summ(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return {"n": len(vals), "min": min(vals), "median": statistics.median(vals),
            "max": max(vals), "mean": statistics.fmean(vals)}


def ladder_rung(subset, index, starts, lo, which, real_exposures, block_s):
    """R replicates of the permutation placebo at one block width."""
    reps = []
    for rep in range(N_REPLICATES):
        # deterministic without relying on tuple hashing
        rnd = random.Random(PERM_SEED * 1000003 + int(block_s or -1) * 101 + rep)
        donors = permute_donors(starts, lo, block_s, rnd)
        est, _recs, _exps = estimate_at(subset, index, donors, which, real_exposures)
        est["replicate"] = rep
        est.pop("buckets")
        reps.append(est)
    ratios = [r["ratio"] for r in reps]
    abslogs = [abs(math.log(x)) for x in ratios if x is not None and x > 0]
    return {"block_s": block_s, "replicates": reps,
            "ratio": _summ(ratios), "abs_log_ratio": _summ(abslogs),
            "coverage": _summ([r["coverage"] for r in reps]),
            "agreement": _summ([r["agreement"] for r in reps]),
            "n_hi": _summ([r["n_hi"] for r in reps]),
            "n_lo": _summ([r["n_lo"] for r in reps])}


def anchors(rungs):
    """Two-directional calibration, set independently so a fixture can drive each side."""
    glob = next((r for r in rungs if r["block_s"] is None), None)
    local = next((r for r in rungs if r["block_s"] == 60.0), None)
    a_val = glob["abs_log_ratio"]["median"] if glob and glob["abs_log_ratio"] else None
    b_val = local["agreement"]["median"] if local and local["agreement"] else None
    a_ok = a_val is not None and a_val <= ANCHOR_A_MAX_ABS_LOG
    b_ok = b_val is not None and b_val >= ANCHOR_B_MIN_AGREEMENT
    if _mut("P3_ANCHOR_ALWAYS_OK"):
        a_ok = b_ok = True
    return {"anchor_a_global_abs_log_median": a_val, "anchor_a_ok": a_ok,
            "anchor_b_local_agreement_median": b_val, "anchor_b_ok": b_ok,
            "ladder_ok": bool(a_ok and b_ok)}


# ------------------------------------------------------------------ the decision

def decide(real, placebo, ladder_ok):
    """Single decision point. real/placebo/ladder_ok are set INDEPENDENTLY by the caller.

    Order is prereg'd: the placebo guards only claims whose CI EXCLUDES 1.0. A period
    confound can manufacture an association; it cannot manufacture the absence of one.
    """
    if real.get("n_hi", 0) < MIN_PER_ARM or real.get("n_lo", 0) < MIN_PER_ARM:
        return "EXPOSURE_DEGENERATE"
    if real.get("coverage", 0.0) < MIN_COVERAGE:
        return "UNSCANNED"
    if real.get("ratio") is None or real.get("ci_lo") is None or real.get("ci_hi") is None:
        return "UNRESOLVED"
    lo, hi = real["ci_lo"], real["ci_hi"]
    ci_contains_one = (lo <= 1.0 <= hi)
    if _mut("P6_NO_TAX_SWALLOWS_SMALL"):
        ci_contains_one = True
    if ci_contains_one and not _mut("P8_RESTORE_R488_ORDER"):
        return "NO_TAX" if (EQUIV_LO <= lo and hi <= EQUIV_HI) else "UNRESOLVED"
    if not ladder_ok:
        return "PLACEBO_LADDER_BROKEN"
    if not _mut("P9_DROP_PLACEBO_COVERAGE"):
        if placebo.get("coverage", 0.0) < MIN_COVERAGE or placebo.get("abs_log_max") is None:
            return "PLACEBO_UNSCANNED"
    if not _mut("P7_DROP_PLACEBO_DEGENERATE"):
        if placebo.get("n_hi", 0) < MIN_PER_ARM or placebo.get("n_lo", 0) < MIN_PER_ARM:
            return "PLACEBO_DEGENERATE"
    gate_val = placebo.get("abs_log_median") if _mut("P5_USE_MEDIAN_NOT_MAX") \
        else placebo.get("abs_log_max")
    if gate_val is not None and gate_val >= abs(math.log(real["ratio"])):
        return "PERIOD_CONFOUNDED"
    if _mut("P8_RESTORE_R488_ORDER") and ci_contains_one:
        return "NO_TAX" if (EQUIV_LO <= lo and hi <= EQUIV_HI) else "UNRESOLVED"
    if lo > 1.0:
        return "TAXES_BELOW_MARGIN" if hi <= EQUIV_HI else "CONCURRENCY_TAXES"
    if hi < 1.0:
        return "SPEEDUP_ANOMALY"
    return "UNRESOLVED"


def placebo_gate_input(rung):
    """Collapse a ladder rung into the four numbers decide() is allowed to see."""
    al = rung["abs_log_ratio"]
    return {"block_s": rung["block_s"],
            "coverage": (rung["coverage"] or {}).get("min", 0.0),
            "n_hi": (rung["n_hi"] or {}).get("min", 0),
            "n_lo": (rung["n_lo"] or {}).get("min", 0),
            "abs_log_max": (al or {}).get("max"),
            "abs_log_median": (al or {}).get("median")}


# ------------------------------------------------------------------ driver

class SubsetIndex:
    """Exposure index over the full chat population, with `skip` addressed by SUBSET
    position. Kept separate from ExposureIndex so a fixture can drive either alone."""

    def __init__(self, base, own):
        self.base, self.own = base, own

    def at(self, t, skip=None):
        return self.base.at(t, skip=(self.own[skip] if skip is not None else None))


def analyse(rows, hyp):
    chat = [r for r in rows if is_chat(r)]
    subset = [r for r in chat if is_analysable(r)]
    if len(subset) < 2 * MIN_PER_ARM:
        return {"verdict": "UNSCANNED", "reason": f"subset={len(subset)}"}
    src = [interval(r, hyp) for r in chat]
    index = ExposureIndex(src)
    idx_of = {id(r): i for i, r in enumerate(chat)}
    sub_index = SubsetIndex(index, [idx_of[id(r)] for r in subset])

    starts = [interval(r, hyp)[0] for r in subset]
    lo = min(s for s, _ in src)
    which, edges = bucketise([r["completion_tokens"] for r in subset], N_BUCKETS)

    real, recs, real_exp = estimate_at(subset, sub_index, starts, which)
    real["ci_lo"], real["ci_hi"] = bootstrap_ci(recs, which)

    rungs = [ladder_rung(subset, sub_index, starts, lo, which, real_exp, b)
             for b in BLOCK_LADDER]
    anc = anchors(rungs)
    primary = next(r for r in rungs if r["block_s"] == PRIMARY_BLOCK)
    pin = placebo_gate_input(primary)
    verdict = decide(real, pin, anc["ladder_ok"])
    return {"verdict": verdict, "hyp": hyp, "n_chat": len(chat), "n_subset": len(subset),
            "token_edges": edges,
            "real": {k: v for k, v in real.items() if k != "buckets"},
            "real_buckets": real["buckets"],
            "anchors": anc, "primary_placebo": pin,
            "ladder": [{k: v for k, v in r.items() if k != "replicates"} for r in rungs],
            "ladder_replicates": {str(r["block_s"]): r["replicates"] for r in rungs}}


def run(path, ts_verdict):
    contamination_check()
    rows = json.loads(Path(path).read_text())["rows"]
    start, end = analyse(rows, "start"), analyse(rows, "end")
    return R488.combine_hypotheses(start, end, ts_verdict)

# ------------------------------------------------------------------------ selftest

def _row(rid, ts, lat_ms, tok=100, fin="stop"):
    return {"id": rid, "ts": ts, "latency_ms": lat_ms, "completion_tokens": tok,
            "status_code": 200, "finish_reason": fin,
            "method": "POST", "path": "[gw] /v1/chat/completions"}


def _planted(n=400, seed=7):
    """True causal effect: a request that STARTS while a background request is open runs
    at 20 ms/tok instead of 10. The backgrounds are placed i.i.d. across the window, so
    exposure carries no period signal -- a permutation placebo must therefore land at 1.0
    while the real estimate lands at 2.0."""
    rnd = random.Random(seed)
    rows = []
    for i in range(n):
        t = 1000.0 + i * 100.0
        exposed = rnd.random() < 0.5
        if exposed:
            # background request, in `chat` but not analysable, open across t
            rows.append(_row(100000 + i, t - 1.0, 2000.0, tok=50, fin="length"))
        tok = 100 + (i % 5) * 40
        mspt = 20.0 if exposed else 10.0
        rows.append(_row(i + 1, t, tok * mspt, tok=tok))
    return rows


def _planted_bursty(n=600, seed=9):
    """Same planted causal effect, but on a population shaped like the real client:
    requests 5 s apart, and the background load arrives in BURSTS (100 s open out of every
    300 s) so the data carry genuine local period structure. _planted() above is 100 s
    apart with i.i.d. backgrounds, which is why its B=60 s rung has no donors at all."""
    rows = []
    for i in range(n):
        t = 1000.0 + i * 5.0
        exposed = ((t - 1000.0) % 300.0) < 100.0
        if exposed:
            rows.append(_row(100000 + i, t - 0.05, 100.0, tok=50, fin="length"))
        tok = 100 + (i % 5) * 40
        mspt = 10.0 if exposed else 5.0
        rows.append(_row(i + 1, t, tok * mspt, tok=tok))
    return rows


def _rung(block_s, ratio=None, agreement=None, coverage=1.0, n=200):
    """A synthetic ladder rung, every field set independently by the caller."""
    al = abs(math.log(ratio)) if ratio else None
    return {"block_s": block_s, "replicates": [],
            "ratio": ({"n": 1, "min": ratio, "median": ratio, "max": ratio, "mean": ratio}
                      if ratio else None),
            "abs_log_ratio": ({"n": 1, "min": al, "median": al, "max": al, "mean": al}
                              if al is not None else None),
            "coverage": {"n": 1, "min": coverage, "median": coverage, "max": coverage,
                         "mean": coverage},
            "agreement": ({"n": 1, "min": agreement, "median": agreement,
                           "max": agreement, "mean": agreement}
                          if agreement is not None else None),
            "n_hi": {"n": 1, "min": n, "median": n, "max": n, "mean": n},
            "n_lo": {"n": 1, "min": n, "median": n, "max": n, "mean": n}}


def _real(ratio=1.5, lo=1.3, hi=1.7, n_hi=200, n_lo=200, coverage=0.99):
    return {"ratio": ratio, "ci_lo": lo, "ci_hi": hi, "n_hi": n_hi, "n_lo": n_lo,
            "coverage": coverage}


def _plac(abs_log_max=0.01, abs_log_median=None, coverage=0.99, n_hi=200, n_lo=200):
    return {"abs_log_max": abs_log_max,
            "abs_log_median": abs_log_max if abs_log_median is None else abs_log_median,
            "coverage": coverage, "n_hi": n_hi, "n_lo": n_lo}


def selftest():
    ok, fail = 0, []

    def chk(name, cond):
        nonlocal ok
        if cond:
            ok += 1
        else:
            fail.append(name)

    # === A. the fast exposure index must be the SAME FUNCTION as r488's slow one ======
    rnd = random.Random(11)
    mismatch = 0
    for _ in range(300):
        ivals = []
        for _ in range(rnd.randrange(2, 12)):
            s = rnd.uniform(0, 50)
            ivals.append((s, s + rnd.uniform(0.001, 20)))
        idx = ExposureIndex(ivals)
        for _ in range(6):
            t = rnd.uniform(-5, 75)
            if idx.at(t) != exposure_at(t, ivals):
                mismatch += 1
            k = rnd.randrange(len(ivals))
            if idx.at(t, skip=k) != exposure_at(t, ivals, skip=k):
                mismatch += 1
        # and on the interval endpoints themselves, where strictness matters
        for s, e in ivals:
            if idx.at(s) != exposure_at(s, ivals) or idx.at(e) != exposure_at(e, ivals):
                mismatch += 1
    chk("fast index == r488 exposure_at (1800+ random probes incl. endpoints)", mismatch == 0)

    # a request's own start never counts itself even without skip (strict inequality)
    chk("own start is not self-concurrent", ExposureIndex([(0.0, 5.0)]).at(0.0) == 0)

    # === B. the permutation is a derangement AND preserves the within-block marginal ===
    rnd = random.Random(12)
    bad_fixed, bad_multiset, bad_singleton = 0, 0, 0
    for trial in range(200):
        starts = sorted(rnd.uniform(0, 3000) for _ in range(rnd.randrange(3, 40)))
        block_s = rnd.choice([60.0, 300.0, 1800.0, None])
        donors = permute_donors(starts, min(starts), block_s, random.Random(trial))
        blocks = {}
        for i, s in enumerate(starts):
            blocks.setdefault(block_of(s, min(starts), block_s), []).append(i)
        for members in blocks.values():
            got = [donors[i] for i in members]
            if len(members) < 2:
                if got != [None]:
                    bad_singleton += 1
                continue
            if any(donors[i] == starts[i] for i in members):
                bad_fixed += 1
            if sorted(got) != sorted(starts[i] for i in members):
                bad_multiset += 1
    chk("no row is handed its own instant (derangement)", bad_fixed == 0)
    chk("within-block instant multiset is preserved exactly", bad_multiset == 0)
    chk("blocks of size 1 are unmeasurable, not silently self-assigned", bad_singleton == 0)

    # marginal preservation is what makes arm collapse impossible: under a GLOBAL
    # permutation the multiset of sampled instants is exactly the real one, so the
    # exposure multiset -- and hence n_hi/n_lo before the self-skip -- is identical.
    starts = [1000.0 + i * 7.0 for i in range(60)]
    d = permute_donors(starts, 1000.0, None, random.Random(3))
    chk("global permutation samples exactly the real instant multiset",
        sorted(d) == sorted(starts))

    # === C. the placebo cannot be moved by the row's OWN duration ====================
    base = [(0.0, 1000.0), (500.0, 501.0)]          # row 0 long, row 1 short
    short = ExposureIndex(base + [(600.0, 600.5)])
    longr = ExposureIndex(base + [(600.0, 9000.0)])
    chk("placebo exposure ignores the row's own lifetime",
        short.at(700.0, skip=2) == longr.at(700.0, skip=2) == 1)

    # === D. every verdict is reachable (mirror of the forced-green census) ============
    reach = {
        "EXPOSURE_DEGENERATE": decide(_real(n_hi=3), _plac(), True),
        "UNSCANNED": decide(_real(coverage=0.1), _plac(), True),
        "UNRESOLVED": decide(_real(ratio=None), _plac(), True),
        "NO_TAX": decide(_real(ratio=1.0, lo=0.97, hi=1.03), _plac(abs_log_max=9.0), True),
        "PLACEBO_LADDER_BROKEN": decide(_real(), _plac(), False),
        "PLACEBO_UNSCANNED": decide(_real(), _plac(coverage=0.1), True),
        "PLACEBO_DEGENERATE": decide(_real(), _plac(n_hi=3), True),
        "PERIOD_CONFOUNDED": decide(_real(), _plac(abs_log_max=0.9), True),
        "TAXES_BELOW_MARGIN": decide(_real(ratio=1.06, lo=1.02, hi=1.10), _plac(), True),
        "CONCURRENCY_TAXES": decide(_real(), _plac(), True),
        "SPEEDUP_ANOMALY": decide(_real(ratio=0.5, lo=0.4, hi=0.6), _plac(), True),
    }
    for want, got in reach.items():
        chk(f"reachable: {want}", got == want)
    chk("no verdict outside the declared vocabulary",
        set(reach.values()) <= set(VERDICTS) and set(reach) == set(VERDICTS))

    # === E. the gate-order repair is REAL, not cosmetic ==============================
    # the exact shape from r489_gate_order_demo.py: a true null whose CI sits inside the
    # practical band, with a placebo that is noisier than the (very clean) real estimate.
    null_real = _real(ratio=1.001, lo=0.97, hi=1.03)
    noisy_plac = _plac(abs_log_max=0.02)
    chk("R489 calls a clean null NO_TAX", decide(null_real, noisy_plac, True) == "NO_TAX")
    chk("R488 called that same input PERIOD_CONFOUNDED",
        R488.decide({**null_real, "coverage": 0.99},
                    [{"coverage": 0.99, "ratio": math.exp(0.02)}]) == "PERIOD_CONFOUNDED")
    # ... and the repair must NOT have handed a free pass to positive claims
    chk("a positive claim still faces the placebo",
        decide(_real(), _plac(abs_log_max=0.9), True) == "PERIOD_CONFOUNDED")
    chk("a small-but-significant claim is NOT swallowed by NO_TAX",
        decide(_real(ratio=1.06, lo=1.02, hi=1.10), _plac(), True) == "TAXES_BELOW_MARGIN")
    chk("a small-but-significant claim still faces the placebo",
        decide(_real(ratio=1.06, lo=1.02, hi=1.10), _plac(abs_log_max=0.9), True)
        == "PERIOD_CONFOUNDED")
    # a CI containing 1.0 but WIDER than the band is UNRESOLVED, not NO_TAX
    chk("wide CI around 1.0 is UNRESOLVED not NO_TAX",
        decide(_real(ratio=1.0, lo=0.5, hi=2.0), _plac(), True) == "UNRESOLVED")

    # === F. the gate quantity is the MAX over replicates, as prereg'd ================
    chk("gate uses max, not median",
        decide(_real(ratio=1.2), _plac(abs_log_max=0.5, abs_log_median=0.01), True)
        == "PERIOD_CONFOUNDED")
    chk("placebo_gate_input takes the worst replicate",
        placebo_gate_input(_rung(1800.0, ratio=1.5))["abs_log_max"]
        == abs(math.log(1.5)))

    # === G. anchors, both directions, driven independently ===========================
    good = [_rung(60.0, ratio=1.9, agreement=0.8), _rung(1800.0, ratio=1.05),
            _rung(None, ratio=1.02)]
    chk("anchors pass when both hold", anchors(good)["ladder_ok"] is True)
    chk("anchor A fails when the global permutation is not null",
        anchors([_rung(60.0, ratio=1.9, agreement=0.8), _rung(None, ratio=1.5)])
        ["anchor_a_ok"] is False)
    chk("anchor B fails when tight blocks lose the local structure",
        anchors([_rung(60.0, ratio=1.9, agreement=0.2), _rung(None, ratio=1.02)])
        ["anchor_b_ok"] is False)
    chk("anchor A is a threshold, not a formality",
        anchors([_rung(60.0, ratio=1.9, agreement=0.8),
                 _rung(None, ratio=math.exp(ANCHOR_A_MAX_ABS_LOG + 1e-6))])["anchor_a_ok"]
        is False
        and anchors([_rung(60.0, ratio=1.9, agreement=0.8),
                     _rung(None, ratio=math.exp(ANCHOR_A_MAX_ABS_LOG - 1e-6))])
        ["anchor_a_ok"] is True)
    chk("anchor B is a threshold, not a formality",
        anchors([_rung(60.0, ratio=1.9, agreement=ANCHOR_B_MIN_AGREEMENT),
                 _rung(None, ratio=1.0)])["anchor_b_ok"] is True
        and anchors([_rung(60.0, ratio=1.9, agreement=ANCHOR_B_MIN_AGREEMENT - 1e-9),
                     _rung(None, ratio=1.0)])["anchor_b_ok"] is False)
    chk("a missing rung is a failed anchor, not a passed one",
        anchors([_rung(1800.0, ratio=1.05)])["ladder_ok"] is False)

    # === H. end to end on a population with a PLANTED causal effect ==================
    # H1: dense + bursty background, i.e. shaped like the real client (5 s apart, local
    # period structure). This is the fixture the whole path has to get right.
    res = analyse(_planted_bursty(), "start")
    chk("planted: arms are populated",
        res["real"]["n_hi"] >= MIN_PER_ARM and res["real"]["n_lo"] >= MIN_PER_ARM)
    chk("planted: real ratio recovers the 2.0 that was planted",
        res["real"]["ratio"] is not None and 1.8 <= res["real"]["ratio"] <= 2.2)
    chk("planted: permutation placebo does NOT collapse (this is what R488 could not do)",
        res["primary_placebo"]["coverage"] >= 0.95
        and res["primary_placebo"]["n_hi"] >= MIN_PER_ARM
        and res["primary_placebo"]["n_lo"] >= MIN_PER_ARM)
    chk("planted: placebo at the primary block lands near null",
        res["primary_placebo"]["abs_log_max"] < 0.3)
    chk("planted: both anchors hold on a population that has period structure",
        res["anchors"]["anchor_a_ok"] is True and res["anchors"]["anchor_b_ok"] is True)
    chk("planted: verdict is CONCURRENCY_TAXES", res["verdict"] == "CONCURRENCY_TAXES")

    # H2: the SAME planted effect on a population whose requests are 100 s apart. The
    # B=60 s rung then has one member per block, so anchor B is not measurable and the
    # ladder cannot be calibrated -- the gate must bite even though the effect is real
    # and the real estimate is perfect. A ladder that passed here would be a formality.
    sparse = analyse(_planted(), "start")
    chk("sparse: the real estimate is still perfect",
        sparse["real"]["ratio"] is not None and 1.8 <= sparse["real"]["ratio"] <= 2.2)
    chk("sparse: B=60 s has no donors at all",
        next(r for r in sparse["ladder"] if r["block_s"] == 60.0)["agreement"] is None)
    chk("sparse: an uncalibratable ladder blocks the positive claim",
        sparse["verdict"] == "PLACEBO_LADDER_BROKEN")

    # === I. contamination gate ========================================================
    saved = os.environ.get("R488P2_MUTANT")
    os.environ["R488P2_MUTANT"] = "N1_LIFETIME_OVERLAP"
    try:
        contamination_check()
        chk("refuses to run with r488's mutant hook set", False)
    except SystemExit:
        chk("refuses to run with r488's mutant hook set", True)
    finally:
        if saved is None:
            os.environ.pop("R488P2_MUTANT", None)
        else:
            os.environ["R488P2_MUTANT"] = saved

    print(f"selftest {ok}/{ok + len(fail)} passed")
    for f in fail:
        print("  FAIL:", f)
    return 0 if not fail else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--snapshot", default=str(DEFAULT_SNAPSHOT))
    ap.add_argument("--ts-verdict", default="TS_IS_START")
    ap.add_argument("--json")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    contamination_check()
    import hashlib
    raw = Path(a.snapshot).read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if sha != SNAPSHOT_SHA:
        print(f"ABORT: snapshot sha {sha} != prereg'd {SNAPSHOT_SHA}")
        return 2
    out = run(a.snapshot, a.ts_verdict)
    out["snapshot_sha256"] = sha
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=2, sort_keys=True))
    print(json.dumps({"verdict": out["verdict"], "ts_verdict": out["ts_verdict"],
                      "ts_resolved": out.get("ts_resolved"),
                      "sensitivity_agrees": out.get("sensitivity_agrees"),
                      "start_verdict": out["start"]["verdict"],
                      "end_verdict": out["end"]["verdict"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
