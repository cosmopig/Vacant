#!/usr/bin/env python3
"""R487-B mutation check: prove the ts-semantics selftest has teeth.

Mutants take effect INSIDE the functions under test. M0 is a no-op negative control.
A crash does not count as a catch -- a named check must fail.
"""
import os, re, subprocess, sys
from pathlib import Path

GAUGE = Path(__file__).resolve().parent / "r487_ts_semantics.py"
MUTANTS = [
    ("M0_NOOP", "N", "negative control"),
    ("M2_INV_COUNTS_TIES", "Y", "count equal values as inversions"),
    ("M3_DROP_MARGIN", "Y", "adopt the smallest key even without a decisive margin"),
    ("M4_DROP_ABS_THRESHOLD", "Y", "adopt a key whose own inversion rate is high"),
    ("M5_DROP_PAIR_GUARD", "Y", "decide on fewer than 100 pairs (type-3 silent-nothing)"),
    ("M6_DROP_POPULATION_AGREEMENT", "Y", "adopt even when all-rows and chat-only disagree"),
]


def run_selftest(m):
    env = dict(os.environ)
    env.pop("R487B_MUTANT", None)
    if m != "M0_NOOP":
        env["R487B_MUTANT"] = m
    p = subprocess.run([sys.executable, str(GAUGE), "--selftest"],
                       capture_output=True, text=True, env=env)
    out = p.stdout + p.stderr
    crash = 1 if "Traceback" in out else 0
    mm = re.search(r"FAILED=\[(.*)\]", out)
    names = [x.strip().strip("'\"") for x in mm.group(1).split(",")] if (mm and mm.group(1)) else []
    return p.returncode, crash, names


def main():
    rc, crash, names = run_selftest("M0_NOOP")
    if rc != 0 or crash or names:
        print(f"BASELINE_BROKEN rc={rc} crash={crash} failed={names}")
        return 2
    print("baseline: rc=0 crash=0 failed=[] -> CLEAN")
    bad = 0
    for name, expect, _d in MUTANTS:
        rc, crash, names = run_selftest(name)
        caught = "Y" if names else "N"
        ok = (caught == expect) and not (caught == "Y" and crash)
        bad += 0 if ok else 1
        print(f"{name:32s} expect_catch={expect} caught={caught} crash={crash} "
              f"{'OK ' if ok else 'BAD'}  by={names[:4]}")
    print(f"{len(MUTANTS)-bad}/{len(MUTANTS)} mutants behaved as prereg'd")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
