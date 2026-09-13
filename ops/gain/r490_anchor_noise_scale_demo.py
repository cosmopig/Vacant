#!/usr/bin/env python3
"""R490 synthetic reproduction: what anchor A must and must not be.

Committed BEFORE the R490 criterion, because relaxing anchor A points in the direction
that favours my own hypothesis. House rule: a self-serving correction may only be
justified by semantics or by a synthetic reproduction. This is the synthetic reproduction.

Three separate things are demonstrated, each non-circular:

D2a  R489's anchor A (median over replicates of |log ratio| <= 0.08) is NOT a function
     of the centre of the permutation distribution. Two constructed distributions:
       P1  centred at EXACTLY 0.000, wide  -> old rule says BROKEN
       P2  centred at EXACTLY +0.070, narrow -> old rule says FINE
     A perfectly valid placebo is rejected and a placebo that manufactures a genuine 7%
     association is accepted. The rule answers "is this narrow", not "is this centred".

D2b  The obvious repair -- a significance test on the centre, |mean|/se <= K -- is
     FORCED RED as the replicate count R grows. The permutation distribution of this
     ratio-of-means estimator carries an O(1/n) Jensen offset (measured below at three
     n), and se shrinks like 1/sqrt(R) while that offset does not. So |z| grows without
     bound on a population with ZERO causal effect by construction.

D2c  What survives both: an EQUIVALENCE test on the centre against the practical margin
     the repo already prereg'd (EQUIV_LO/EQUIV_HI = 0.90/1.15, from R487). It passes P1,
     is stable in R, and still fails a placebo that forgot to permute (E) and one that
     manufactures 25% (P3).

Honesty boundary stated up front: adopting the existing practical band means anchor A
tolerates a manufactured association of up to log(1.15) = 0.1398, which is 22% of the
real R488 point estimate (log 1.8652 = 0.6234). Anchor A therefore certifies "the
placebo is null to within the practical margin", NOT "the placebo is exactly null".
"""
import json, math, random, statistics, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import r489_permutation_placebo as R489  # noqa: E402
from r488_pointwise_concurrency import (  # noqa: E402
    EQUIV_HI, EQUIV_LO, N_BUCKETS, bucketise, interval, is_analysable, is_chat)

OLD_MAX_ABS_LOG = R489.ANCHOR_A_MAX_ABS_LOG          # 0.08, imported so it cannot drift
BAND = (math.log(EQUIV_LO), math.log(EQUIV_HI))      # (-0.10536, +0.13976)
K = 3.0
R_LADDER = (25, 50, 100, 200, 400)


def old_rule(logs):
    return statistics.median(abs(x) for x in logs) <= OLD_MAX_ABS_LOG


def centre_ci(logs, k=K):
    m = statistics.fmean(logs)
    sd = statistics.pstdev(logs) if len(logs) > 1 else 0.0
    se = sd / math.sqrt(len(logs))
    return m, sd, se, (m - k * se, m + k * se)


def z_rule(logs, k=K):
    m, _sd, se, _ci = centre_ci(logs, k)
    if se == 0.0:
        return abs(m) == 0.0
    return abs(m) / se <= k


def equiv_rule(logs, k=K):
    """The centre's CI must lie inside the practical margin band."""
    _m, _sd, _se, (lo, hi) = centre_ci(logs, k)
    return BAND[0] <= lo and hi <= BAND[1]


def recentre(logs, target):
    m = statistics.fmean(logs)
    return [x - m + target for x in logs]


def population(n, sigma, seed, effect=1.0):
    """Requests 5 s apart; background load open 100 s out of every 300 s (real period
    structure). ms/tok is lognormal and, at effect == 1.0, INDEPENDENT of exposure."""
    rnd = random.Random(seed)
    rows = []
    for i in range(n):
        t = 1000.0 + i * 5.0
        exposed = ((t - 1000.0) % 300.0) < 100.0
        if exposed:
            rows.append(R489._row(100000 + i, t - 0.05, 100.0, tok=50, fin="length"))
        tok = 100 + (i % 5) * 40
        mspt = 8.0 * math.exp(rnd.gauss(0.0, sigma)) * (effect if exposed else 1.0)
        rows.append(R489._row(i + 1, t, tok * mspt, tok=tok))
    return rows


def global_perm_logs(rows, reps, seed, identity=False):
    """Replicate log ratios under B = infinity. Mirrors R489.analyse()'s setup.
    identity=True hands each row its OWN instant back = a placebo that forgot to permute."""
    chat = [r for r in rows if is_chat(r)]
    subset = [r for r in chat if is_analysable(r)]
    src = [interval(r, "start") for r in chat]
    index = R489.ExposureIndex(src)
    idx_of = {id(r): i for i, r in enumerate(chat)}
    sub = R489.SubsetIndex(index, [idx_of[id(r)] for r in subset])
    starts = [interval(r, "start")[0] for r in subset]
    lo = min(s for s, _ in src)
    which, _ = bucketise([r["completion_tokens"] for r in subset], N_BUCKETS)
    logs = []
    for rep in range(reps):
        rnd = random.Random(seed * 1000003 + rep)
        donors = starts if identity else R489.permute_donors(starts, lo, None, rnd)
        est, _recs, _exps = R489.estimate_at(subset, sub, donors, which)
        if est["ratio"] and est["ratio"] > 0:
            logs.append(math.log(est["ratio"]))
    return logs, len(subset)


def describe(name, logs, true_centre=None):
    m, sd, se, ci = centre_ci(logs)
    return {"case": name, "replicates": len(logs),
            "true_centre_by_construction": true_centre,
            "mean_log": round(m, 5), "sd_log": round(sd, 5),
            "centre_ci": [round(ci[0], 5), round(ci[1], 5)],
            "median_abs_log": round(statistics.median(abs(x) for x in logs), 5),
            "old_rule_pass": old_rule(logs), "z_rule_pass": z_rule(logs),
            "equiv_rule_pass": equiv_rule(logs)}


def main():
    wide, n_wide = global_perm_logs(population(n=300, sigma=0.9, seed=11), 400, seed=101)
    mid, n_mid = global_perm_logs(population(n=1000, sigma=0.9, seed=13), 400, seed=104)
    narrow, n_nar = global_perm_logs(population(n=4000, sigma=0.9, seed=12), 400, seed=102)
    planted, n_pl = global_perm_logs(R489._planted_bursty(n=600), 50, seed=103, identity=True)

    # --- D2a: constructed distributions with the centre known EXACTLY -----------
    P1 = describe("P1_perfect_null_wide", recentre(wide, 0.0), 0.0)
    P2 = describe("P2_manufactured_7pct_narrow", recentre(narrow, 0.07), 0.07)
    P3 = describe("P3_manufactured_25pct_narrow", recentre(narrow, 0.25), 0.25)
    E = describe("E_placebo_forgot_to_permute", planted)
    d2a = (P1["old_rule_pass"] is False and P2["old_rule_pass"] is True)

    # --- D2b: |z| on a ZERO-causal-effect population grows without bound in R ----
    # Two views, because a single realised path is itself noisy: (i) the realised
    # prefix at each R, (ii) the DETERMINISTIC projection that holds the measured
    # centre and sd fixed and varies only R -- |z| = |m| * sqrt(R) / sd. (ii) is the
    # structural claim; (i) is there so the noise in (i) is visible rather than hidden.
    m_all, sd_all, _se, _ci = centre_ci(wide)
    zl = []
    for r in R_LADDER + (1000, 4000):
        sub = wide[:r] if r <= len(wide) else None
        row = {"R": r, "projected_abs_z": round(abs(m_all) * math.sqrt(r) / sd_all, 3),
               "projected_z_rule_pass": abs(m_all) * math.sqrt(r) / sd_all <= K}
        if sub:
            m, _s, se, _c = centre_ci(sub)
            row.update({"realised_abs_z": round(abs(m) / se, 3) if se else None,
                        "realised_z_rule_pass": z_rule(sub),
                        "realised_equiv_rule_pass": equiv_rule(sub)})
        zl.append(row)
    pz = [x["projected_abs_z"] for x in zl]
    d2b = (pz == sorted(pz) and pz[-1] > K and not zl[-1]["projected_z_rule_pass"]
           and BAND[0] <= m_all <= BAND[1])   # ...while the centre stays inside the band

    # --- Jensen offset shrinks with n (the mechanism behind D2b) ----------------
    jensen = [{"n_subset": n, "mean_log": round(statistics.fmean(g), 5)}
              for n, g in ((n_wide, wide), (n_mid, mid), (n_nar, narrow))]
    jensen_monotone = all(abs(jensen[i]["mean_log"]) > abs(jensen[i + 1]["mean_log"])
                          for i in range(len(jensen) - 1))

    # --- D2c: the equivalence rule keeps its teeth ------------------------------
    # teeth in the fail direction (P3, E) and a pass on a perfectly centred null (P1);
    # at small R it must REFUSE to certify (that is the rule working, not failing).
    d2c = (P1["equiv_rule_pass"] is True and P3["equiv_rule_pass"] is False
           and E["equiv_rule_pass"] is False
           and zl[0]["realised_equiv_rule_pass"] is False        # R=25 cannot certify
           and zl[3]["realised_equiv_rule_pass"] is True         # R=200 can
           and zl[4]["realised_equiv_rule_pass"] is True)        # R=400 can

    verdict = "REPRODUCED" if (d2a and d2b and d2c) else "NOT_REPRODUCED"
    res = {"verdict": verdict,
           "D2a_old_rule_ignores_the_centre": d2a,
           "D2b_z_rule_forced_red_as_R_grows": d2b,
           "D2c_equivalence_rule_still_has_teeth": d2c,
           "jensen_offset_shrinks_with_n": jensen_monotone,
           "centre_of_zero_effect_population": round(m_all, 5),
           "old_threshold": OLD_MAX_ABS_LOG, "band_log": [round(b, 5) for b in BAND],
           "K": K, "cases": [P1, P2, P3, E], "z_ladder": zl, "jensen": jensen}
    print(json.dumps(res, indent=2))
    return 0 if verdict == "REPRODUCED" else 1


if __name__ == "__main__":
    sys.exit(main())
