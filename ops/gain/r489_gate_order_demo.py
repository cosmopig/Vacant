#!/usr/bin/env python3
"""R489 synthetic reproduction: the R488 gate ORDER makes NO_TAX nearly unreachable.

round759 item 6 recorded the defect as a visible fact but did not repair it, because a
criterion may only be changed for a semantic reason or a synthetic reproduction -- never
because the numbers came out badly. This file is that reproduction, and it is committed
BEFORE the R489 criterion so the criterion cannot be tuned to it after the fact.

The construction: a population whose TRUE causal effect is exactly zero, measured by an
estimator with ordinary sampling noise, alongside a placebo that is also ~null. Both
|log ratio|s hover near 0, so which one is larger is a coin flip -- and R488's decide()
consults the placebo BEFORE it is allowed to say NO_TAX. A true null is therefore reported
as PERIOD_CONFOUNDED about half the time, and the more perfectly null the data are, the
worse it gets.

Run: python3 ops/gain/r489_gate_order_demo.py
"""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from r488_pointwise_concurrency import decide as decide_r488  # noqa: E402

TRIALS = 2000
SEED = 4890


def trial(rnd, real_sd, plac_sd):
    """One draw of a TRUE NULL: real and placebo log ratios are both mean-zero noise."""
    real_lr = rnd.gauss(0.0, real_sd)
    plac_lr = rnd.gauss(0.0, plac_sd)
    real = {"n_hi": 300, "n_lo": 300, "coverage": 0.99,
            "ratio": math.exp(real_lr),
            # a CI that is comfortably inside the practical-equivalence band: by
            # construction this population deserves NO_TAX.
            "ci_lo": 0.97, "ci_hi": 1.03}
    plac = {"coverage": 0.99, "ratio": math.exp(plac_lr)}
    return decide_r488(real, [plac])


def main():
    rnd = random.Random(SEED)
    print(f"R488 decide() on {TRIALS} draws from a TRUE NULL whose CI is inside the")
    print("practical-equivalence band [0.90, 1.15] -- the correct verdict is NO_TAX.\n")
    print(f"  {'real noise sd':>13s}  {'placebo noise sd':>16s}  {'NO_TAX':>7s}  {'PERIOD_CONFOUNDED':>18s}")
    worst = 1.0
    for real_sd, plac_sd in ((0.02, 0.02), (0.01, 0.02), (0.005, 0.02), (0.001, 0.02)):
        got = {}
        for _ in range(TRIALS):
            v = trial(rnd, real_sd, plac_sd)
            got[v] = got.get(v, 0) + 1
        frac_ok = got.get("NO_TAX", 0) / TRIALS
        worst = min(worst, frac_ok)
        print(f"  {real_sd:13.3f}  {plac_sd:16.3f}  {frac_ok:7.3f}  "
              f"{got.get('PERIOD_CONFOUNDED', 0) / TRIALS:18.3f}")
    print()
    print("Reading: the true effect is zero in every row of that table. The share of runs")
    print("that reach the correct NO_TAX verdict FALLS as the real estimate gets cleaner,")
    print("because a cleaner null has a SMALLER |log ratio| for the placebo to beat.")
    print("An unconditional placebo gate placed above NO_TAX is a mirror of a forced-green")
    print("gate: it is a forced-UNRESOLVED gate, and it points the wrong way -- the better")
    print("the evidence for the null, the less likely the null is reported.")
    print()
    print(f"worst NO_TAX share: {worst:.3f}")
    # This is the claim the R489 criterion change rests on; assert it so the file fails
    # loudly if a later edit to r488's decide() makes the reproduction stop reproducing.
    assert worst < 0.30, f"reproduction did not reproduce: worst NO_TAX share {worst}"
    print("REPRODUCED: R488's gate order suppresses NO_TAX on data that deserve it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
