#!/usr/bin/env python3
"""R490: the R489 permutation placebo, re-decided with a LEVELED gate.

Criteria: DECISION_20260905_R490_LEVELED_PLACEBO_PREREG.md (committed first, aeb9871).
Synthetic reproduction justifying the anchor A change: r490_anchor_noise_scale_demo.py
(2dcca08, committed BEFORE the criterion because the change favours my own hypothesis).

Three repairs, all argued in the prereg:
  D1  max-over-R replicates == a permutation test at level 1/(R+1). R is not a free
      parameter of a test; ALPHA is. Gate becomes p <= ALPHA with ALPHA = 0.05, which is
      R489's own effective level at its R=20, held fixed while R rises to 400.
  D2  anchor A becomes an EQUIVALENCE test on the CENTRE of the global-permutation
      distribution against the band the repo already prereg'd, [0.90, 1.15].
  D3  a rung's ROLE follows from its own agreement against the existing constant
      ANCHOR_B_MIN_AGREEMENT = 0.50: positive control (must reproduce) vs gate.

The estimator (interval, exposure, stratification, pooling, bootstrap) is IMPORTED from
R488 through R489 and is not re-implemented here, so the rounds cannot drift apart.
New tunables introduced by this file: ALPHA (0.05) and R_REPLICATES (400). Both are
declared in the prereg; the band and the agreement threshold are inherited constants.
"""
import argparse, hashlib, json, math, os, random, statistics, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))

import r489_permutation_placebo as R489  # noqa: E402
from r489_permutation_placebo import (  # noqa: E402
    ANCHOR_B_MIN_AGREEMENT, BLOCK_LADDER, PRIMARY_BLOCK, SNAPSHOT_SHA,
    ExposureIndex, SubsetIndex, estimate_at, permute_donors)
from r488_pointwise_concurrency import (  # noqa: E402
    EQUIV_HI, EQUIV_LO, MIN_COVERAGE, MIN_PER_ARM, N_BUCKETS,
    bootstrap_ci, bucketise, interval, is_analysable, is_chat)

DEFAULT_SNAPSHOT = ROOT / "ops/gain/data/r486_gateway_snapshot_v2.json"

# --- prereg'd constants (DECISION_20260905_R490_LEVELED_PLACEBO_PREREG.md) ---
ALPHA = 0.05
R_REPLICATES = 400
R_OLD = 20                      # R489's R, kept so the old rule stays computable
ANCHOR_A_K = 3.0
BAND_LO, BAND_HI = math.log(EQUIV_LO), math.log(EQUIV_HI)
PERM_SEED = 4900
OLD_MAX_ABS_LOG = R489.ANCHOR_A_MAX_ABS_LOG   # 0.08, imported so it cannot drift

ROW_FIELDS = ("ts", "latency_ms", "completion_tokens", "status_code",
              "finish_reason", "method", "path")
REP_FIELDS = ("ratio", "agreement", "coverage", "n_hi", "n_lo")

VERDICTS = ("EXPOSURE_DEGENERATE", "UNSCANNED", "UNRESOLVED", "NO_TAX",
            "LADDER_UNSCANNED", "PLACEBO_LADDER_BROKEN", "PLACEBO_UNSCANNED",
            "PLACEBO_DEGENERATE", "PRIMARY_IS_POSITIVE_CONTROL", "PERIOD_CONFOUNDED",
            "SCALE_DEPENDENT_TAX", "TAXES_BELOW_MARGIN", "CONCURRENCY_TAXES",
            "SPEEDUP_ANOMALY")


def _mut(name):
    """Read at CALL time. A module-level snapshot would make every mutant a no-op that
    looks exactly like a detector with no teeth (this repo has shipped that bug)."""
    return os.environ.get("R490_MUTANT", "") == name


def contamination_check():
    for var in ("R488P2_MUTANT", "R489_MUTANT"):
        if os.environ.get(var, ""):
            raise SystemExit(f"REFUSING: {var}={os.environ[var]!r} would mutate an imported estimator")


# ------------------------------------------------------------------ prerequisite gauge

def prereq_rows(rows):
    """Type-2 'silently unmeasurable' guard: the fields the estimator reads must exist.
    Reports what is missing rather than letting a rename become a quiet pass."""
    if _mut("M10_PREREQ_SILENT"):
        return {"ok": True, "n_rows": len(rows), "missing": {}}
    missing = {}
    for f in ROW_FIELDS:
        n = sum(1 for r in rows if f not in r)
        if n:
            missing[f] = n
    return {"ok": not missing, "n_rows": len(rows), "missing": missing}


def prereq_rung(rung):
    """A rung is measurable only if EVERY replicate produced a ratio and an agreement.
    A drop in the number measured must be BROKEN, never a pass."""
    if _mut("M10_PREREQ_SILENT"):
        return True
    reps = rung.get("replicates") or []
    if len(reps) < rung.get("reps_requested", 0):
        return False
    for r in reps:
        for f in REP_FIELDS:
            if f not in r:
                return False
        if r["ratio"] is None or r["ratio"] <= 0 or r["agreement"] is None:
            return False
    return True


# ------------------------------------------------------------------ the leveled gate

def perm_p(abs_logs, real_abs_log):
    """p = (1 + #{placebo |log| >= real |log|}) / (R + 1).

    Domain is [1/(R+1), 1] and it is non-decreasing in the exceedance count; both are
    asserted exhaustively in selftest(). The +1 is what stops p from ever being 0, i.e.
    what stops the gate from claiming more resolution than R replicates can carry."""
    if not abs_logs or real_abs_log is None:
        return None
    k = sum(1 for x in abs_logs if x >= real_abs_log)
    if _mut("M3_P_DROP_PLUS_ONE"):
        return k / len(abs_logs)
    return (1 + k) / (len(abs_logs) + 1)


def centre_ci(logs, k=ANCHOR_A_K):
    m = statistics.fmean(logs)
    sd = statistics.pstdev(logs) if len(logs) > 1 else 0.0
    se = sd / math.sqrt(len(logs))
    return m, sd, se, (m - k * se, m + k * se)


def kappa(a, a_chance):
    """Agreement in EXCESS of chance (R490-A / A1). a_chance is MEASURED, not assumed:
    it is the global permutation's own agreement, i.e. what random donors score by
    luck alone. Without it the role rule cannot classify its own negative control as a
    gate -- on an unbalanced exposure, chance agreement already exceeds 0.50."""
    if a is None or a_chance is None or a_chance >= 1.0:
        return None
    return (a - a_chance) / (1.0 - a_chance)


def role_of(rung, a_chance=0.0):
    """THE role rule, and the only place the role threshold is compared. assign_roles()
    delegates here rather than repeating the comparison: a condition tested in two places
    makes the first one dead code, and a mutant on it then looks exactly like a detector
    with no teeth. a_chance defaults to 0 so a fixture can drive the raw agreement."""
    k = kappa(rung.get("agreement_median"), a_chance)
    if k is None:
        return None
    return "positive_control" if k >= ANCHOR_B_MIN_AGREEMENT else "gate"


def assign_roles(ladder):
    """D3 + A1: chance-corrected agreement decides gate vs positive control.
    The global rung has kappa == 0 by construction and is therefore always a gate --
    asserted in selftest, not reported as a finding."""
    glob = next((r for r in ladder if r["block_s"] is None), None)
    a_chance = glob.get("agreement_median") if glob else None
    for r in ladder:
        r["agreement_chance"] = a_chance
        r["kappa"] = kappa(r.get("agreement_median"), a_chance)
        if _mut("M4_ROLE_ALL_GATES"):
            r["role"] = "gate"
        elif _mut("M5_ROLE_ALL_POSITIVE"):
            r["role"] = "positive_control"
        else:
            r["role"] = role_of(r, a_chance)
    return ladder


def anchors_v2(rungs):
    """Anchor A: the CENTRE of the global permutation, inside the practical band.
    Anchor B: unchanged from R489. Set independently so a fixture can drive each side."""
    glob = next((r for r in rungs if r["block_s"] is None), None)
    local = next((r for r in rungs if r["block_s"] == 60.0), None)
    a = {"measured": False}
    if glob and glob.get("logs"):
        m, sd, se, (lo, hi) = centre_ci(glob["logs"])
        a = {"measured": True, "mean_log": m, "sd_log": sd, "se": se,
             "centre_ci_lo": lo, "centre_ci_hi": hi,
             "band_lo": BAND_LO, "band_hi": BAND_HI,
             # computed from the SAME logs the new rule sees, so the two rules can
             # never be fed different inputs and then compared
             "old_median_abs_log": statistics.median(abs(x) for x in glob["logs"]),
             "old_rule_pass": statistics.median(abs(x) for x in glob["logs"]) <= OLD_MAX_ABS_LOG}
    a_ok = bool(a["measured"] and BAND_LO <= a["centre_ci_lo"] and a["centre_ci_hi"] <= BAND_HI)
    b_val = local.get("agreement_median") if local else None
    b_ok = b_val is not None and b_val >= ANCHOR_B_MIN_AGREEMENT
    if _mut("M1_ANCHOR_A_ALWAYS_OK"):
        a_ok = True
    if _mut("M2_ANCHOR_B_ALWAYS_OK"):
        b_ok = True
    return {"anchor_a": a, "anchor_a_ok": a_ok,
            "anchor_b_agreement_median": b_val, "anchor_b_ok": b_ok,
            "ladder_ok": bool(a_ok and b_ok)}


# ------------------------------------------------------------------ the decision

def decide(real, ladder, anchors, primary_block=PRIMARY_BLOCK):
    """Single decision point. Every input is set independently by the caller.

    `ladder` is a list of dicts with block_s / role / p / coverage_min / n_hi_min /
    n_lo_min / measurable. `anchors` carries anchor_a_ok and anchor_b_ok."""
    if real.get("n_hi", 0) < MIN_PER_ARM or real.get("n_lo", 0) < MIN_PER_ARM:
        return "EXPOSURE_DEGENERATE"
    if real.get("coverage", 0.0) < MIN_COVERAGE:
        return "UNSCANNED"
    if real.get("ratio") is None or real.get("ci_lo") is None or real.get("ci_hi") is None:
        return "UNRESOLVED"
    lo, hi = real["ci_lo"], real["ci_hi"]
    if lo <= 1.0 <= hi:                       # R489's gate-order repair, unchanged
        return "NO_TAX" if (EQUIV_LO <= lo and hi <= EQUIV_HI) else "UNRESOLVED"
    if not ladder or any((not r.get("measurable")) or r.get("p") is None
                         or r.get("role") is None for r in ladder):
        return "LADDER_UNSCANNED"
    if not (anchors.get("anchor_a_ok") and anchors.get("anchor_b_ok")):
        return "PLACEBO_LADDER_BROKEN"
    if not _mut("M6_SKIP_POSITIVE_CONTROL_CHECK"):
        # R490-A / A2: a placebo attenuates toward 1, so an exceedance test can never
        # certify reproduction. Ask what FRACTION of the real log association it kept.
        if any(r["role"] == "positive_control"
               and (r.get("reproduction_frac") is None
                    or r["reproduction_frac"] < ANCHOR_B_MIN_AGREEMENT) for r in ladder):
            return "PLACEBO_LADDER_BROKEN"
    primary = next((r for r in ladder if r["block_s"] == primary_block), None)
    if primary is None:
        return "LADDER_UNSCANNED"
    if primary.get("coverage_min", 0.0) < MIN_COVERAGE:
        return "PLACEBO_UNSCANNED"
    if primary.get("n_hi_min", 0) < MIN_PER_ARM or primary.get("n_lo_min", 0) < MIN_PER_ARM:
        return "PLACEBO_DEGENERATE"
    if not _mut("M8_PRIMARY_PC_CHECK_OFF"):
        if primary["role"] == "positive_control":
            return "PRIMARY_IS_POSITIVE_CONTROL"
    gate_fires = (primary["abs_log_max"] is not None
                  and primary["abs_log_max"] >= real["abs_log"]) \
        if _mut("M7_USE_OLD_MAX_GATE") else (primary["p"] > ALPHA)
    if gate_fires:
        return "PERIOD_CONFOUNDED"
    if lo > 1.0:
        if not _mut("M9_SCALE_DEPENDENCE_OFF"):
            if any(r["role"] == "gate" and r["p"] > ALPHA for r in ladder):
                return "SCALE_DEPENDENT_TAX"
        return "TAXES_BELOW_MARGIN" if hi <= EQUIV_HI else "CONCURRENCY_TAXES"
    if hi < 1.0:
        return "SPEEDUP_ANOMALY"
    return "UNRESOLVED"


# ------------------------------------------------------------------ driver

def rung(subset, index, starts, lo, which, real_exposures, real_abs_log, block_s, reps):
    recs = []
    for rep in range(reps):
        rnd = random.Random(PERM_SEED * 1000003 + int(block_s or -1) * 101 + rep)
        donors = permute_donors(starts, lo, block_s, rnd)
        est, _r, _e = estimate_at(subset, index, donors, which, real_exposures)
        est.pop("buckets", None)
        est["replicate"] = rep
        recs.append(est)
    out = {"block_s": block_s, "reps_requested": reps, "replicates": recs}
    if not prereq_rung(out):
        out.update({"measurable": False, "p": None, "role": None,
                    "agreement_median": None, "reproduction_frac": None,
                    "abs_log_max": None, "coverage_min": 0.0, "n_hi_min": 0, "n_lo_min": 0})
        out.pop("replicates")
        return out
    logs = [math.log(r["ratio"]) for r in recs]
    abs_logs = [abs(x) for x in logs]
    out.update({
        "measurable": True, "logs": logs, "n_measured": len(logs),
        "agreement_median": statistics.median(r["agreement"] for r in recs),
        "coverage_min": min(r["coverage"] for r in recs),
        "n_hi_min": min(r["n_hi"] for r in recs), "n_lo_min": min(r["n_lo"] for r in recs),
        "ratio_median": statistics.median(r["ratio"] for r in recs),
        "abs_log_median": statistics.median(abs_logs),
        "abs_log_max": max(abs_logs),
        "abs_log_max_at_R20": max(abs_logs[:R_OLD]),
        "p": perm_p(abs_logs, real_abs_log),
        "p_at_R20": perm_p(abs_logs[:R_OLD], real_abs_log)})
    out["reproduction_frac"] = (out["abs_log_median"] / real_abs_log
                                if real_abs_log else None)
    out.pop("replicates")
    return out     # role is assigned later by assign_roles(), which needs the whole ladder


def analyse(rows, hyp, reps=R_REPLICATES):
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
    real["abs_log"] = abs(math.log(real["ratio"])) if real.get("ratio") else None
    real.pop("buckets", None)

    ladder = assign_roles([rung(subset, sub_index, starts, lo, which, real_exp,
                                real["abs_log"], b, reps) for b in BLOCK_LADDER])
    anc = anchors_v2(ladder)
    lean = [{k: v for k, v in r.items() if k != "logs"} for r in ladder]
    verdict = decide(real, ladder, anc)
    return {"verdict": verdict, "hyp": hyp, "n_chat": len(chat), "n_subset": len(subset),
            "token_edges": edges, "real": real, "anchors": anc, "ladder": lean,
            "old_rule": old_rule_report(real, ladder, anc)}


def old_rule_report(real, ladder, anc):
    """R489's rules, computed and reported but NOT binding (prereg section 2)."""
    primary = next((r for r in ladder if r["block_s"] == PRIMARY_BLOCK), None)
    a = anc.get("anchor_a", {})
    return {"anchor_a_median_abs_log": a.get("old_median_abs_log"),
            "anchor_a_threshold": OLD_MAX_ABS_LOG,
            "anchor_a_pass_old_rule": a.get("old_rule_pass"),
            "real_abs_log": real.get("abs_log"),
            "primary_abs_log_max_at_R20": primary and primary.get("abs_log_max_at_R20"),
            "primary_abs_log_max_at_R": primary and primary.get("abs_log_max"),
            "max_gate_fires_at_R20": bool(primary and primary.get("abs_log_max_at_R20") is not None
                                          and real.get("abs_log") is not None
                                          and primary["abs_log_max_at_R20"] >= real["abs_log"]),
            "max_gate_fires_at_R": bool(primary and primary.get("abs_log_max") is not None
                                        and real.get("abs_log") is not None
                                        and primary["abs_log_max"] >= real["abs_log"]),
            "implied_level_at_R20": 1.0 / (R_OLD + 1),
            "implied_level_at_R": 1.0 / (R_REPLICATES + 1)}


def run(path, ts_verdict, reps=R_REPLICATES):
    contamination_check()
    rows = json.loads(Path(path).read_text())["rows"]
    pre = prereq_rows(rows)
    if not pre["ok"]:
        return {"verdict": "LADDER_UNSCANNED", "prereq_rows": pre}
    start, end = analyse(rows, "start", reps), analyse(rows, "end", reps)
    out = R489.R488.combine_hypotheses(start, end, ts_verdict)
    out["prereq_rows"] = pre
    return out


# ------------------------------------------------------------------------ selftest

def _row(rid, ts, lat_ms, tok=100, fin="stop"):
    """Rows are built HERE rather than imported from R489: a fixture that borrowed the
    row constructor of the module it depends on would drift silently along with it, and
    ROW_FIELDS (what prereq_rows demands) would never be tested against anything."""
    return {"id": rid, "ts": ts, "latency_ms": lat_ms, "completion_tokens": tok,
            "status_code": 200, "finish_reason": fin,
            "method": "POST", "path": "[gw] /v1/chat/completions"}


def _planted_period(n=720, seed=11):
    """P-10's other direction: an association that is PURE period confounding.

    ms/tok depends ONLY on which half of the window the request is in (20 vs 10); being
    exposed causes exactly nothing. Exposure is a coin flip whose RATE tracks the same
    halves (0.8 then 0.2), so the exposed group is over-represented in the slow half and
    the pooled estimate sees an association that is entirely between-period.

    A within-block permutation at B=1800 keeps each donor inside its own half, so it
    reproduces that association -> the gate must fire (PERIOD_CONFOUNDED). This is the
    population that _planted_bursty is NOT: there the effect is pointwise, so scrambling
    who was exposed destroys it. Step 11 only has teeth if both fixtures exist."""
    rnd = random.Random(seed)
    rows = []
    for i in range(n):
        t = 1000.0 + i * 5.0
        first_half = i < n // 2
        if rnd.random() < (0.8 if first_half else 0.2):
            rows.append(_row(100000 + i, t - 1.0, 2000.0, tok=50, fin="length"))
        tok = 100 + (i % 5) * 40
        mspt = 20.0 if first_half else 10.0      # <- exposure is NOT in this line
        rows.append(_row(i + 1, t, tok * mspt, tok=tok))
    return rows


def _fix_rung(block_s, p=0.001, agreement=0.0, coverage=1.0, n=200, abs_log_max=0.1,
              measurable=True, role=None, reproduction_frac=1.0):
    """A ladder rung built FIELD BY FIELD, deliberately NOT via rung(). Sharing the
    module's own constructor would hide a schema rename from every fixture.

    p and reproduction_frac are set INDEPENDENTLY: after R490-A/A2 a positive control is
    judged on the fraction of the real association it kept, not on its p, and a fixture
    that derived one from the other could not tell those two rules apart."""
    r = {"block_s": block_s, "p": p, "agreement_median": agreement,
         "coverage_min": coverage, "n_hi_min": n, "n_lo_min": n,
         "abs_log_max": abs_log_max, "abs_log_max_at_R20": abs_log_max,
         "reproduction_frac": reproduction_frac,
         "measurable": measurable, "logs": [0.0] * 10, "abs_log_median": 0.0}
    r["role"] = role if role is not None else role_of(r)
    return r


def _fix_real(ratio=1.5, lo=1.3, hi=1.7, n=200, coverage=0.99):
    return {"ratio": ratio, "ci_lo": lo, "ci_hi": hi, "n_hi": n, "n_lo": n,
            "coverage": coverage, "abs_log": abs(math.log(ratio))}


def _fix_anc(a=True, b=True):
    return {"anchor_a_ok": a, "anchor_b_ok": b}


def _fix_ladder(primary_p=0.001, other_gate_p=0.001, pc_p=0.001, pc_frac=0.8):
    """Default ladder: one positive control (B=60) that reproduces 80% of the real
    association, two gates that do not, and the global rung. pc_p stays at the value a
    good positive control really gets (small -- it attenuates, so it never exceeds the
    real value), which is exactly why A2 stopped judging it on p."""
    return [_fix_rung(60.0, p=pc_p, agreement=0.9, reproduction_frac=pc_frac),
            _fix_rung(300.0, p=other_gate_p, agreement=0.1),
            _fix_rung(PRIMARY_BLOCK, p=primary_p, agreement=0.1),
            _fix_rung(None, p=0.001, agreement=0.0)]


def _decide_reads():
    """Every string key decide() reads, taken from its SOURCE with ast -- not from a
    hand-kept list that would silently go stale."""
    import ast, inspect
    tree = ast.parse(inspect.getsource(decide))
    keys = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "get" and node.args \
                and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            keys.add(node.args[0].value)
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant) \
                and isinstance(node.slice.value, str):
            keys.add(node.slice.value)
    return keys


def selftest():
    fails = []

    def chk(name, cond):
        if not cond:
            fails.append(name)

    # === A. perm_p: domain and monotonicity, exhaustively ==========================
    for R in (1, 2, 5, 20, 400):
        prev = None
        for k in range(R + 1):
            logs = [2.0] * k + [0.0] * (R - k)
            v = perm_p(logs, 1.0)
            chk(f"perm_p in domain R={R} k={k}", 1.0 / (R + 1) - 1e-12 <= v <= 1.0 + 1e-12)
            chk(f"perm_p non-decreasing R={R} k={k}", prev is None or v >= prev - 1e-12)
            prev = v
    chk("perm_p can never be 0 (that is what the +1 buys)",
        min(perm_p([0.0] * R, 1.0) for R in (1, 20, 400)) > 0.0)
    chk("perm_p is None when unmeasurable",
        perm_p([], 1.0) is None and perm_p([0.1], None) is None)
    chk("perm_p counts ties as exceedances (>=, not >)", perm_p([1.0, 1.0], 1.0) == 1.0)

    # === B. anchor A v2: both directions, driven independently ====================
    def glob(logs):
        return [_fix_rung(60.0, agreement=0.9), dict(_fix_rung(None), logs=logs)]
    tight_null = [0.001 * ((-1) ** i) for i in range(400)]
    chk("anchor A passes a centred, tight null", anchors_v2(glob(tight_null))["anchor_a_ok"])
    chk("anchor A fails a centre outside the band",
        not anchors_v2(glob([0.30] * 400))["anchor_a_ok"])
    chk("anchor A refuses to certify when the CI is too wide to fit the band",
        not anchors_v2(glob([0.5 * ((-1) ** i) for i in range(9)]))["anchor_a_ok"])
    chk("anchor A is a threshold, not a formality",
        anchors_v2(glob([BAND_HI - 1e-9] * 400))["anchor_a_ok"]
        and not anchors_v2(glob([BAND_HI + 1e-6] * 400))["anchor_a_ok"])
    chk("anchor A unmeasured is a FAILED anchor, not a passed one",
        not anchors_v2([_fix_rung(60.0, agreement=0.9)])["anchor_a_ok"])
    chk("anchor B fails when tight blocks lose the local structure",
        not anchors_v2([_fix_rung(60.0, agreement=0.2), dict(_fix_rung(None), logs=tight_null)])
        ["anchor_b_ok"])
    chk("anchor B exactly at the threshold passes",
        anchors_v2([_fix_rung(60.0, agreement=ANCHOR_B_MIN_AGREEMENT),
                    dict(_fix_rung(None), logs=tight_null)])["anchor_b_ok"])
    chk("anchor B just under the threshold fails",
        not anchors_v2([_fix_rung(60.0, agreement=ANCHOR_B_MIN_AGREEMENT - 1e-9),
                        dict(_fix_rung(None), logs=tight_null)])["anchor_b_ok"])
    chk("the OLD anchor A rule is still computed and reported",
        anchors_v2(glob([0.2] * 400))["anchor_a"]["old_rule_pass"] is False
        and anchors_v2(glob([0.01] * 400))["anchor_a"]["old_rule_pass"] is True)

    # === C. rung roles (D3), both sides of the inherited constant =================
    chk("role: agreement at the threshold is a positive control",
        role_of({"agreement_median": ANCHOR_B_MIN_AGREEMENT}) == "positive_control")
    chk("role: just under the threshold is a gate",
        role_of({"agreement_median": ANCHOR_B_MIN_AGREEMENT - 1e-9}) == "gate")
    chk("role: unmeasured agreement has no role", role_of({"agreement_median": None}) is None)

    # === D. every verdict is reachable ============================================
    got = {}
    got["EXPOSURE_DEGENERATE"] = decide(_fix_real(n=1), _fix_ladder(), _fix_anc())
    got["UNSCANNED"] = decide(_fix_real(coverage=0.1), _fix_ladder(), _fix_anc())
    got["UNRESOLVED"] = decide(dict(_fix_real(), ci_lo=None), _fix_ladder(), _fix_anc())
    got["NO_TAX"] = decide(_fix_real(ratio=1.0, lo=0.95, hi=1.05), _fix_ladder(), _fix_anc())
    got["LADDER_UNSCANNED"] = decide(_fix_real(), [_fix_rung(60.0, measurable=False)], _fix_anc())
    got["PLACEBO_LADDER_BROKEN"] = decide(_fix_real(), _fix_ladder(), _fix_anc(a=False))
    got["PLACEBO_UNSCANNED"] = decide(
        _fix_real(), [_fix_rung(60.0, p=0.5, agreement=0.9), _fix_rung(300.0), _fix_rung(None),
                     _fix_rung(PRIMARY_BLOCK, coverage=0.1)], _fix_anc())
    got["PLACEBO_DEGENERATE"] = decide(
        _fix_real(), [_fix_rung(60.0, p=0.5, agreement=0.9), _fix_rung(300.0), _fix_rung(None),
                      _fix_rung(PRIMARY_BLOCK, n=1)], _fix_anc())
    got["PRIMARY_IS_POSITIVE_CONTROL"] = decide(
        _fix_real(), [_fix_rung(60.0, p=0.5, agreement=0.9), _fix_rung(300.0), _fix_rung(None),
                      _fix_rung(PRIMARY_BLOCK, p=0.5, agreement=0.9)], _fix_anc())
    got["PERIOD_CONFOUNDED"] = decide(_fix_real(), _fix_ladder(primary_p=0.5), _fix_anc())
    got["SCALE_DEPENDENT_TAX"] = decide(_fix_real(), _fix_ladder(other_gate_p=0.9), _fix_anc())
    got["TAXES_BELOW_MARGIN"] = decide(_fix_real(ratio=1.05, lo=1.01, hi=1.10),
                                       _fix_ladder(), _fix_anc())
    got["CONCURRENCY_TAXES"] = decide(_fix_real(), _fix_ladder(), _fix_anc())
    got["SPEEDUP_ANOMALY"] = decide(_fix_real(ratio=0.8, lo=0.7, hi=0.9),
                                    _fix_ladder(), _fix_anc())
    for want, actual in got.items():
        chk(f"verdict reachable: {want}", actual == want)
    chk("no verdict is unreachable", set(got) == set(VERDICTS))
    chk("every returned verdict is declared", set(got.values()) <= set(VERDICTS))

    # === E. the positive-control check is bidirectional (R490-A / A2) =============
    chk("a positive control that FAILS to reproduce breaks the ladder",
        decide(_fix_real(), _fix_ladder(pc_frac=ANCHOR_B_MIN_AGREEMENT - 1e-9), _fix_anc())
        == "PLACEBO_LADDER_BROKEN")
    chk("a positive control that reproduces does not break the ladder",
        decide(_fix_real(), _fix_ladder(pc_frac=0.8), _fix_anc()) == "CONCURRENCY_TAXES")
    chk("reproduction exactly at the threshold passes",
        decide(_fix_real(), _fix_ladder(pc_frac=ANCHOR_B_MIN_AGREEMENT), _fix_anc())
        == "CONCURRENCY_TAXES")
    chk("an unmeasured reproduction fraction is a FAILURE, not a pass",
        decide(_fix_real(), _fix_ladder(pc_frac=None), _fix_anc()) == "PLACEBO_LADDER_BROKEN")
    # A2 itself: the OLD rule judged the positive control on p. A placebo attenuates, so a
    # perfect positive control gets a TINY p -- under the old rule that broke the ladder.
    # These two say the p of a positive control now changes nothing.
    chk("a positive control's p no longer decides anything (tiny p)",
        decide(_fix_real(), _fix_ladder(pc_p=1.0 / (R_REPLICATES + 1)), _fix_anc())
        == "CONCURRENCY_TAXES")
    chk("a positive control's p no longer decides anything (large p)",
        decide(_fix_real(), _fix_ladder(pc_p=0.9), _fix_anc()) == "CONCURRENCY_TAXES")
    # ... and a positive control is NOT read as a gate by step 12 either.
    chk("a positive control with a large p does not fire SCALE_DEPENDENT_TAX",
        decide(_fix_real(), _fix_ladder(pc_p=0.9), _fix_anc()) != "SCALE_DEPENDENT_TAX")

    # === F. schema contract: decide()'s keys must exist on REAL objects ===========
    rows = R489._planted_bursty(n=600)
    res = analyse(rows, "start", reps=8)
    keys = _decide_reads()
    available = set(res["real"]) | set(res["anchors"]) | set(res["ladder"][0])
    missing = sorted(k for k in keys if k not in available)
    chk(f"decide() reads only keys the real pipeline produces (missing={missing})", not missing)
    chk("a real rung is measurable and carries a role",
        res["ladder"][0]["measurable"] and res["ladder"][0]["role"] in ("gate", "positive_control"))
    chk("prereq_rung rejects a rung whose replicates went missing",
        not prereq_rung({"reps_requested": 4, "replicates": [
            {"ratio": 1.0, "agreement": 0.5, "coverage": 1.0, "n_hi": 1, "n_lo": 1}]}))
    chk("prereq_rung rejects a replicate missing a field",
        not prereq_rung({"reps_requested": 1, "replicates": [{"ratio": 1.0}]}))
    chk("prereq_rows names what is missing",
        prereq_rows([{k: 1 for k in ROW_FIELDS if k != "ts"}])["missing"] == {"ts": 1})
    chk("prereq_rows passes a complete row",
        prereq_rows([{k: 1 for k in ROW_FIELDS}])["ok"] is True)

    # === G. planted population with a TRUE effect walks the whole path ============
    chk("planted: real estimate finds the planted effect",
        res["real"]["ratio"] is not None and res["real"]["ratio"] > 1.2)
    chk("planted: B=60 is a positive control (donors are near-identical)",
        next(r for r in res["ladder"] if r["block_s"] == 60.0)["role"] == "positive_control")
    chk("planted: the global rung is a gate (permutation destroys agreement)",
        next(r for r in res["ladder"] if r["block_s"] is None)["role"] == "gate")

    print(f"selftest {len(fails)} failed" if fails else "selftest all passed")
    for f in fails:
        print("  FAIL:", f)
    return 1 if fails else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--snapshot", default=str(DEFAULT_SNAPSHOT))
    ap.add_argument("--ts-verdict", default="TS_IS_START")
    ap.add_argument("--reps", type=int, default=R_REPLICATES)
    ap.add_argument("--json")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    contamination_check()
    raw = Path(a.snapshot).read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if sha != SNAPSHOT_SHA:
        print(f"ABORT: snapshot sha {sha} != prereg'd {SNAPSHOT_SHA}")
        return 2
    out = run(a.snapshot, a.ts_verdict, reps=a.reps)
    out["snapshot_sha256"] = sha
    out["reps"] = a.reps
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=2, sort_keys=True, default=str))
    print(json.dumps({"verdict": out["verdict"], "ts_verdict": out.get("ts_verdict"),
                      "sensitivity_agrees": out.get("sensitivity_agrees"),
                      "start_verdict": out.get("start", {}).get("verdict"),
                      "end_verdict": out.get("end", {}).get("verdict")}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
