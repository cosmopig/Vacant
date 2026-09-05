#!/usr/bin/env python3
"""R489 POST-HOC diagnostic (NOT part of the prereg'd decision, NOT in the prediction ledger).

Anchor A failed at 0.0911 against a locked threshold of 0.08. Two very different things
look identical from one number: 20 replicates being too few, or the global permutation
carrying a real bias. This separates them, and tests the one mechanism that could bias it
-- the self-skip. A long-lived request contains a randomly drawn instant more often, so
`skip=i` removes one unit of exposure more often for exactly the rows with the largest
ms/tok, which is a dependence between the placebo exposure and the outcome.

Run: python3 ops/gain/r489_anchor_a_diagnostic.py
"""
import json, math, random, statistics, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from r489_permutation_placebo import (  # noqa: E402
    DEFAULT_SNAPSHOT, ExposureIndex, SubsetIndex, N_BUCKETS, ANCHOR_A_MAX_ABS_LOG,
    bucketise, estimate_at, interval, is_analysable, is_chat, permute_donors)

REPS = 200


def main():
    rows = json.loads(Path(DEFAULT_SNAPSHOT).read_text())["rows"]
    chat = [r for r in rows if is_chat(r)]
    subset = [r for r in chat if is_analysable(r)]
    src = [interval(r, "start") for r in chat]
    idx_of = {id(r): i for i, r in enumerate(chat)}
    base = ExposureIndex(src)
    sub = SubsetIndex(base, [idx_of[id(r)] for r in subset])
    starts = [interval(r, "start")[0] for r in subset]
    lo = min(s for s, _ in src)
    which, _ = bucketise([r["completion_tokens"] for r in subset], N_BUCKETS)

    class NoSkip:
        def __init__(self, b):
            self.b = b

        def at(self, t, skip=None):
            return self.b.at(t)

    # Does the self-skip ever fire here? If it never does, the two rows below are equal
    # for a structural reason and the guard is inert on this population.
    own = [idx_of[id(r)] for r in subset]
    fires = tot = 0
    for rep in range(REPS):
        for i, t in enumerate(permute_donors(starts, lo, None, random.Random(90000 + rep))):
            if t is None:
                continue
            tot += 1
            s, e = src[own[i]]
            if s < t < e:
                fires += 1
    print(f"self-skip fires {fires}/{tot} donor draws under global permutation")
    print("  (zero means no analysable request STARTS inside another one's lifetime: the")
    print("   client is strictly sequential among successes, so the concurrency a request")
    print("   sees comes from the failed post-let-go pile-up R486 identified, not from")
    print("   its own siblings. The guard is correct but INERT on this population.)")
    print()

    pool = []
    for label, index in (("with self-skip (as measured)", sub), ("without self-skip", NoSkip(base))):
        logs = []
        for rep in range(REPS):
            d = permute_donors(starts, lo, None, random.Random(90000 + rep))
            est, _r, _e = estimate_at(subset, index, d, which)
            if est["ratio"]:
                logs.append(math.log(est["ratio"]))
        m, sd = statistics.fmean(logs), statistics.stdev(logs)
        se = sd / math.sqrt(len(logs))
        print(f"{label:30s} n={len(logs)}  mean log={m:+.5f}  sd={sd:.5f}  "
              f"se(mean)={se:.5f}  mean/se={m / se:+.2f}  median|log|={statistics.median(abs(x) for x in logs):.5f}")

        if label.startswith("with"):
            pool = logs

    # How often could anchor A have passed AT ALL? Its statistic is the median |log| of
    # 20 replicates; resample that statistic from the 200 draws above.
    rnd = random.Random(4891)
    hits = 0
    TRIALS = 20000
    for _ in range(TRIALS):
        med = statistics.median(abs(pool[rnd.randrange(len(pool))]) for _ in range(20))
        if med <= ANCHOR_A_MAX_ABS_LOG:
            hits += 1
    print()
    print(f"P(anchor A passes | the placebo is EXACTLY as valid as it actually is) = "
          f"{hits / TRIALS:.4f}  ({hits}/{TRIALS} resamples of the median of 20)")

    print()
    print(f"prereg'd anchor A threshold on the median |log| of 20 replicates: {ANCHOR_A_MAX_ABS_LOG}")
    print("The threshold was derived from the bootstrap CI WIDTH of the real estimate")
    print("(log width 0.2231 -> single-replicate SE ~0.0569). If the sd printed above is")
    print("materially larger than 0.0569, the threshold was simply set too tight for this")
    print("estimator's permutation variance, and anchor A failed for a reason that has")
    print("nothing to do with whether the placebo is valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
