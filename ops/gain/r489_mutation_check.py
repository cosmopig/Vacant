#!/usr/bin/env python3
"""R489 mutation check for r489_permutation_placebo.py.

Every mutant is aimed at a fixture that actually EXECUTES the mutated function -- round759
lost a mutant to a fixture that fed pooled_log_ratio ready-made cells and so never walked
the code under test. Includes a no-op control: if that is ever reported as caught, every
other row in the table is meaningless.
"""
import json, os, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MOD = HERE / "r489_permutation_placebo.py"

PRELUDE = f"""
import sys, json, math, random
sys.path.insert(0, {str(HERE)!r})
from r489_permutation_placebo import (ExposureIndex, permute_donors, block_of, anchors,
                                      decide, placebo_gate_input, analyse,
                                      _planted, _planted_bursty, _rung, _real, _plac)

def fixed_points():
    starts = [1000.0 + i * 5.0 for i in range(80)]
    d = permute_donors(starts, 1000.0, 300.0, random.Random(5))
    return sum(1 for i, s in enumerate(starts) if d[i] == s)

def own_duration():
    base = [(0.0, 1000.0), (500.0, 501.0)]
    a = ExposureIndex(base + [(600.0, 600.5)]).at(700.0, skip=2)
    b = ExposureIndex(base + [(600.0, 9000.0)]).at(700.0, skip=2)
    return [a, b]

_B = None
def bursty():
    global _B
    if _B is None:
        _B = analyse(_planted_bursty(), "start")
    return _B

out = {{}}
"""

FIXTURES = {
    # walks permute_donors
    "derangement":      "fixed_points()",
    # walks block_of via the full ladder on a population WITH local period structure
    "local_agreement":  "round(bursty()['anchors']['anchor_b_local_agreement_median'], 3)",
    "bursty_verdict":   "bursty()['verdict']",
    # walks the anchor gate end to end on a population whose ladder cannot be calibrated
    "sparse_verdict":   "analyse(_planted(), 'start')['verdict']",
    # walks ExposureIndex.at's self-skip
    "own_duration":     "own_duration()",
    # pure decision points, every input set independently
    "dec_clean_null":   "decide(_real(ratio=1.001, lo=0.97, hi=1.03), _plac(abs_log_max=0.02), True)",
    "dec_small_sig":    "decide(_real(ratio=1.06, lo=1.02, hi=1.10), _plac(), True)",
    "dec_max_vs_med":   "decide(_real(ratio=1.2), _plac(abs_log_max=0.5, abs_log_median=0.01), True)",
    "dec_plac_degen":   "decide(_real(), _plac(n_hi=3), True)",
    "dec_plac_cov":     "decide(_real(), _plac(coverage=0.1), True)",
    "dec_taxes":        "decide(_real(), _plac(), True)",
    "dec_ladder":       "decide(_real(), _plac(), False)",
    "anchor_a":         "anchors([_rung(60.0, ratio=1.9, agreement=0.8), _rung(None, ratio=1.5)])['anchor_a_ok']",
    "gate_input_max":   "round(placebo_gate_input(_rung(1800.0, ratio=1.5))['abs_log_max'], 6)",
}

MUTANTS = {
    "P1_NO_DERANGEMENT":        "derangement",
    "P2_GLOBAL_BLOCKS":         "local_agreement",
    "P3_ANCHOR_ALWAYS_OK":      "sparse_verdict",
    "P4_PLACEBO_INCLUDE_SELF":  "own_duration",
    "P5_USE_MEDIAN_NOT_MAX":    "dec_max_vs_med",
    "P6_NO_TAX_SWALLOWS_SMALL": "dec_small_sig",
    "P7_DROP_PLACEBO_DEGENERATE": "dec_plac_degen",
    "P8_RESTORE_R488_ORDER":    "dec_clean_null",
    "P9_DROP_PLACEBO_COVERAGE": "dec_plac_cov",
    "P10_NOOP_CONTROL":         None,
}


def verdicts(mutant):
    body = PRELUDE
    for name, expr in FIXTURES.items():
        body += (f"\ntry:\n    out[{name!r}] = {expr}\n"
                 f"except Exception as e:\n    out[{name!r}] = 'EXC:' + type(e).__name__\n")
    body += "\nprint(json.dumps(out))\n"
    env = dict(os.environ)
    env.pop("R488P2_MUTANT", None)
    if mutant:
        env["R489_MUTANT"] = mutant
    else:
        env.pop("R489_MUTANT", None)
    r = subprocess.run([sys.executable, "-c", body], capture_output=True, text=True, env=env)
    if r.returncode != 0:
        return {"__error__": r.stderr.strip()[-400:]}
    return json.loads(r.stdout)


def main():
    src = MOD.read_text()
    missing = [m for m in MUTANTS if m != "P10_NOOP_CONTROL" and m not in src]
    if missing:
        print("BASELINE_BROKEN: mutant names absent from module:", missing)
        return 2
    if "P10_NOOP_CONTROL" in src:
        print("BASELINE_BROKEN: the no-op control name appears in the module")
        return 2
    base = verdicts(None)
    if "__error__" in base:
        print("BASELINE_BROKEN:", base["__error__"])
        return 2
    bad = 0
    for mut, target in MUTANTS.items():
        v = verdicts(mut)
        if "__error__" in v:
            print(f"  {mut:28s} BROKEN  {v['__error__']}")
            bad += 1
            continue
        changed = sorted(k for k in FIXTURES if v.get(k) != base.get(k))
        if target is None:
            ok = not changed
            note = "no-op control: nothing changed" if ok else f"NO-OP CHANGED {changed}"
        else:
            ok = target in changed
            note = (f"seen by {target} ({base.get(target)} -> {v.get(target)})"
                    if ok else f"MISSED by {target}; changed={changed}")
        label = ("as-prereg" if target is None else "caught") if ok else "MISSED"
        if not ok:
            bad += 1
        print(f"  {mut:28s} {label:9s} {note}")
    print(f"{len(MUTANTS) - bad}/{len(MUTANTS)} mutants behaved as prereg'd (1 no-op control)")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
