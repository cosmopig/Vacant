#!/usr/bin/env python3
"""R490-B synthetic reproduction: the LEVELED gate (R490 D1) cannot see period
confounding, for the same structural reason A2 found in the positive-control check.

Committed BEFORE the criterion it justifies, and before any real-data verdict of R490.

Claim reproduced here
---------------------
On a population whose association is 100% period confounding (exposure causes nothing;
both exposure rate and outcome track the same two halves of the window), the primary
placebo REPRODUCES 98% of the real log association -- and the R490/R490-A rule still
answers CONCURRENCY_TAXES, i.e. "a real concurrency tax, not a period artifact".

Mechanism (measured, not assumed)
---------------------------------
permute_donors() maps a block onto a single cycle, so the MULTISET of start instants in
a block is preserved exactly; exposure is a function of the instant, so the multiset of
exposures per block survives too (measured below: identical in most replicates, the rest
differing only through self-exclusion). If the outcome depends only on the block, the
pooled estimate is then nearly deterministic under permutation: the placebo spread
collapses to sd ~= 0.001 while the quantity being judged (how much of the association was
reproduced) lives at the 0.4 scale. Any systematic attenuation, however practically
irrelevant, is therefore many sd away and "significant".

This is the significance-vs-equivalence error the repo has already recorded twice
(D2b: a significance test as an anchor is forced-red; R487-B: two near-zero rates must
not be compared with an absolute difference). A p-value answers "is the placebo
DIFFERENT from real at all"; the gate needs "did the placebo REPRODUCE real".

Direction disclosure: the repair this justifies makes CONCURRENCY_TAXES HARDER to claim,
i.e. it works AGAINST the hypothesis this loop is trying to support.
"""
import math, random, statistics, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import r490_leveled_placebo as M            # noqa: E402
import r489_permutation_placebo as R489     # noqa: E402
from r488_pointwise_concurrency import (    # noqa: E402
    N_BUCKETS, bucketise, interval, is_analysable, is_chat)

ALPHA = M.ALPHA
REPRO_THRESHOLD = M.ANCHOR_B_MIN_AGREEMENT      # 0.50, the inherited constant
R = 200


def measure(rows, block_s=M.PRIMARY_BLOCK, reps=R, want_multiset=False):
    chat = [r for r in rows if is_chat(r)]
    subset = [r for r in chat if is_analysable(r)]
    src = [interval(r, "start") for r in chat]
    index = R489.ExposureIndex(src)
    idx = {id(r): i for i, r in enumerate(chat)}
    sub = R489.SubsetIndex(index, [idx[id(r)] for r in subset])
    starts = [interval(r, "start")[0] for r in subset]
    lo = min(s for s, _ in src)
    which, _ = bucketise([r["completion_tokens"] for r in subset], N_BUCKETS)
    real, _recs, rexp = R489.estimate_at(subset, sub, starts, which)
    real_log = math.log(real["ratio"])

    def multiset(exps):
        d = {}
        for i, s in enumerate(starts):
            b = R489.block_of(s, lo, block_s)
            d.setdefault(b, {})
            d[b][exps[i]] = d[b].get(exps[i], 0) + 1
        return d

    logs, agrees, same_multiset = [], [], 0
    rm = multiset(rexp)
    for rep in range(reps):
        rnd = random.Random(M.PERM_SEED * 1000003 + int(block_s or -1) * 101 + rep)
        donors = R489.permute_donors(starts, lo, block_s, rnd)
        est, _r, pexp = R489.estimate_at(subset, sub, donors, which, rexp)
        logs.append(math.log(est["ratio"]))
        agrees.append(est["agreement"])
        if want_multiset and multiset(pexp) == rm:
            same_multiset += 1
    abs_logs = [abs(x) for x in logs]
    return {"real_log": real_log, "real_ratio": real["ratio"],
            "mean": statistics.fmean(logs), "sd": statistics.pstdev(logs),
            "median_abs": statistics.median(abs_logs),
            "reproduction_frac": statistics.median(abs_logs) / abs(real_log),
            "agreement": statistics.median(agrees),
            "exceed": sum(1 for x in abs_logs if x >= abs(real_log)),
            "p": M.perm_p(abs_logs, abs(real_log)), "reps": reps,
            "same_multiset": same_multiset}


def main():
    checks, fails = [], []

    def chk(name, cond, detail=""):
        checks.append((name, bool(cond), detail))
        if not cond:
            fails.append(name)

    print("=" * 78)
    print("A. PERIOD-CONFOUNDED population (exposure causes nothing)")
    per = measure(M._planted_period(), want_multiset=True)
    print(f"   real ratio={per['real_ratio']:.4f}  |log real|={abs(per['real_log']):.6f}")
    print(f"   placebo mean={per['mean']:.6f}  sd={per['sd']:.6f}  agreement={per['agreement']:.4f}")
    print(f"   reproduction fraction = {per['reproduction_frac']:.4f}   "
          f"(the placebo kept {per['reproduction_frac']*100:.1f}% of the association)")
    print(f"   gap real-mean = {per['real_log']-per['mean']:.6f} "
          f"= {(per['real_log']-per['mean'])/per['sd']:.2f} sd")
    print(f"   exceedances = {per['exceed']}/{per['reps']}   p = {per['p']:.5f}")
    print(f"   per-block exposure multiset identical to real in "
          f"{per['same_multiset']}/{per['reps']} replicates  <- the mechanism")
    chk("A1 the placebo reproduces most of the association", per["reproduction_frac"] >= 0.9)
    chk("A2 the leveled gate nevertheless does NOT fire", per["p"] <= ALPHA)
    chk("A3 the permutation distribution is degenerate (sd << the gap it judges)",
        per["sd"] < 0.01 * abs(per["real_log"]))
    chk("A4 the mechanism is multiset preservation", per["same_multiset"] >= 0.5 * per["reps"])

    print()
    print("B. POINTWISE-EFFECT population (a real per-request tax)")
    bur = measure(R489._planted_bursty(n=600))
    print(f"   real ratio={bur['real_ratio']:.4f}  reproduction fraction = "
          f"{bur['reproduction_frac']:.4f}  exceedances={bur['exceed']}/{bur['reps']}  "
          f"p={bur['p']:.5f}")
    chk("B1 a genuine pointwise effect is NOT reproduced by the placebo",
        bur["reproduction_frac"] < REPRO_THRESHOLD)
    chk("B2 the leveled gate does not fire here either (correctly)", bur["p"] <= ALPHA)

    print()
    print("C. the p-value cannot separate A from B; the reproduction fraction can")
    print(f"   p:                    A={per['p']:.5f}   B={bur['p']:.5f}   -> same answer")
    print(f"   reproduction fraction: A={per['reproduction_frac']:.4f}  "
          f"B={bur['reproduction_frac']:.4f}  -> opposite sides of {REPRO_THRESHOLD}")
    chk("C1 p gives the SAME verdict on a confounded and an unconfounded population",
        (per["p"] > ALPHA) == (bur["p"] > ALPHA))
    chk("C2 the reproduction fraction gives OPPOSITE verdicts",
        (per["reproduction_frac"] >= REPRO_THRESHOLD)
        != (bur["reproduction_frac"] >= REPRO_THRESHOLD))

    print()
    print("D. not a knife-edge: sweep the confound strength (exposure-rate contrast)")
    print("   rate_hi/rate_lo   reproduction   p        gate fires?")
    swept = []
    for hi, lo_ in ((0.9, 0.1), (0.8, 0.2), (0.7, 0.3), (0.6, 0.4)):
        rows = _period_rows(hi, lo_)
        m = measure(rows, reps=100)
        swept.append(m)
        print(f"   {hi:.1f}/{lo_:.1f}            {m['reproduction_frac']:.4f}       "
              f"{m['p']:.5f}  {'yes' if m['p'] > ALPHA else 'NO'}")
    chk("D1 the gate fails to fire across the whole sweep",
        all(m["p"] <= ALPHA for m in swept))
    chk("D2 the reproduction fraction stays high across the whole sweep",
        all(m["reproduction_frac"] >= REPRO_THRESHOLD for m in swept))

    print()
    for name, ok, _d in checks:
        print(f"   [{'ok' if ok else 'FAIL'}] {name}")
    verdict = "REPRODUCED" if not fails else "NOT_REPRODUCED"
    print(f"\nverdict: {verdict}")
    return 0 if verdict == "REPRODUCED" else 1


def _period_rows(rate_hi, rate_lo, n=720, seed=11):
    """Same construction as M._planted_period but with the exposure-rate contrast open,
    written HERE so the sweep cannot be an artifact of one hard-coded pair of rates."""
    rnd = random.Random(seed)
    rows = []
    for i in range(n):
        t = 1000.0 + i * 5.0
        first = i < n // 2
        if rnd.random() < (rate_hi if first else rate_lo):
            rows.append(M._row(100000 + i, t - 1.0, 2000.0, tok=50, fin="length"))
        tok = 100 + (i % 5) * 40
        rows.append(M._row(i + 1, t, tok * (20.0 if first else 10.0), tok=tok))
    return rows


if __name__ == "__main__":
    sys.exit(main())
