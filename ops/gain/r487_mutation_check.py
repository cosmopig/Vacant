#!/usr/bin/env python3
"""R487: does the selftest actually have teeth?

Each mutant is a semantic change made INSIDE the function under test (never a
module-level constant read at import, which would silently no-op and look exactly like a
toothless detector). For each we prereg whether the selftest must catch it, and we record
WHICH named check caught it -- a crash does not count as a catch.

M0 is a no-op negative control: if "catching" M0 too, the harness itself is broken.
"""
import os, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GAUGE = HERE / "r487_concurrency_tax.py"

MUTANTS = [
    ("M0_NOOP", "N", "negative control: no mutation is applied"),
    ("M1_OVERLAP_ALLOW_TOUCH", "Y", "zero-length touch counts as overlap"),
    ("M2_OVERLAP_INCLUDES_SELF", "Y", "a request overlaps itself => everything EXPOSED"),
    ("M3_STRATA_COLLAPSE", "Y", "drop the duration matching (one big stratum)"),
    ("M4_REF_IGNORE_ERRORS", "Y", "failed/500 requests enter the reference population"),
    ("M5_UNWEIGHTED_POOL", "Y", "pool cells unweighted instead of n_e*n_u/(n_e+n_u)"),
    ("M6_RELOAD_FIXED_NULL", "Y", "P-3 null lambda=0 => back to R486's forced-green form"),
    ("M7_MATCH_ON_LATENCY", "Y", "match on latency (the OUTCOME) instead of tokens"),
    ("M8_DROP_TS_AGREEMENT", "Y", "adopt a verdict even when the two ts semantics disagree"),
    ("M9_DROP_STRAT_AGREEMENT", "Y", "adopt P-1 even when the two stratifications disagree"),
]


def run_selftest(mutant):
    env = dict(os.environ)
    if mutant != "M0_NOOP":
        env["R487_MUTANT"] = mutant
    else:
        env.pop("R487_MUTANT", None)
    p = subprocess.run([sys.executable, str(GAUGE), "--selftest"],
                       capture_output=True, text=True, env=env)
    out = p.stdout + p.stderr
    crash = 1 if ("Traceback" in out) else 0
    m = re.search(r"FAILED=\[(.*)\]", out)
    names = [x.strip().strip("'\"") for x in m.group(1).split(",")] if (m and m.group(1)) else []
    return p.returncode, crash, names, out


def main():
    rc0, crash0, names0, out0 = run_selftest("M0_NOOP")
    if rc0 != 0 or crash0 or names0:
        print(f"BASELINE_BROKEN rc={rc0} crash={crash0} failed={names0}")
        print(out0)
        return 2
    print(f"baseline: rc=0 crash=0 failed=[] -> CLEAN")

    bad = 0
    for name, expect, desc in MUTANTS:
        rc, crash, names, out = run_selftest(name)
        caught = "Y" if names else "N"
        ok = (caught == expect) and not (caught == "Y" and not names)
        # a crash is not a catch: the mutant must be seen by a NAMED check
        if caught == "Y" and crash:
            ok = False
        if not ok:
            bad += 1
        print(f"{name:30s} expect_catch={expect} caught={caught} crash={crash} "
              f"{'OK ' if ok else 'BAD'}  by={names[:5]}")
    print(f"{len(MUTANTS) - bad}/{len(MUTANTS)} mutants behaved as prereg'd")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
