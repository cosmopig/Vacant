#!/usr/bin/env python3
"""R490 mutation check: every gate in r490_leveled_placebo has a fixture that sees it.

Rules this file obeys (all of them learned the hard way in this repo):
  * the mutation takes effect INSIDE the function under test (r490's _mut() reads the
    environment at call time); a module-level snapshot would make every mutant a silent
    no-op that looks exactly like a detector with no teeth;
  * each mutant declares WHICH VERDICT STRING it is expected to produce -- "the run
    crashed" is BROKEN, not a detection;
  * a NO-OP control must leave every verdict untouched, so that "the harness reacts to
    anything" cannot be mistaken for "the detector has teeth";
  * fixtures set each input independently rather than deriving one from another.
"""
import math, os, sys, traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import r490_leveled_placebo as M            # noqa: E402
import r489_permutation_placebo as R489     # noqa: E402


def _ladder(pc_frac=0.8, pc_agree=0.9, pc_p=0.5, primary_p=0.001, primary_frac=0.0,
            primary_agree=0.1, primary_maxlog=0.1, gate_p=0.001, gate_frac=0.0,
            glob_frac=0.0, glob_logs=None):
    """A ladder built field by field. glob_logs drives anchor A, pc_agree drives anchor B,
    and every gate quantity is separate from every other one."""
    return [
        M._fix_rung(60.0, p=pc_p, agreement=pc_agree, reproduction_frac=pc_frac),
        M._fix_rung(300.0, p=gate_p, agreement=0.1, reproduction_frac=gate_frac),
        M._fix_rung(M.PRIMARY_BLOCK, p=primary_p, agreement=primary_agree,
                    reproduction_frac=primary_frac, abs_log_max=primary_maxlog),
        dict(M._fix_rung(None, p=0.001, agreement=0.0, reproduction_frac=glob_frac),
             logs=(glob_logs if glob_logs is not None
                   else [0.001 * ((-1) ** i) for i in range(400)])),
    ]


def verdict_from(rungs, real=None):
    """decide() fed by the REAL anchor and role code, so a mutant in either is visible."""
    real = real or M._fix_real()
    rungs = M.assign_roles([dict(r) for r in rungs])
    return M.decide(real, rungs, M.anchors_v2(rungs))


def v_period(reps=40):
    return M.analyse(M._planted_period(), "start", reps=reps)["verdict"]


def v_rows_missing_field():
    """finish_reason removed: prereq_rows must refuse. The estimator reads it with .get,
    so the mutant path degrades instead of crashing -- the two answers stay comparable."""
    rows = [{k: v for k, v in r.items() if k != "finish_reason"}
            for r in M._planted_period(n=200)]
    return M.run_rows(rows)


def v_p_gate():
    """p computed by the real perm_p: 1 exceedance in 20 replicates.
    clean (1+1)/21 = 0.0952 > ALPHA -> the gate fires; without the +1, 1/20 = 0.05 does
    not clear the strict '>' and the gate goes quiet."""
    p = M.perm_p([2.0] + [0.0] * 19, 1.0)
    return verdict_from(_ladder(primary_p=p))


CASES = [
    # (mutant, description, callable, clean verdict, expected mutated verdict)
    ("M1_ANCHOR_A_ALWAYS_OK", "anchor A forced to pass",
     lambda: verdict_from(_ladder(glob_logs=[0.30] * 400)),
     "PLACEBO_LADDER_BROKEN", "CONCURRENCY_TAXES"),
    # pc_frac drops to 0 alongside pc_agree: at agreement 0.2 the B=60 rung is a GATE,
    # and a gate that reproduces 0.8 of the association fires R490-B's half, so the first
    # version of this fixture landed on SCALE_DEPENDENT_TAX and told me nothing about
    # anchor B. pc_p drops too: a positive control's p is irrelevant after A2, but this
    # rung STOPS being a positive control here, and then its p is read again. The gauge
    # was right both times; the fixture was not isolating the mutant.
    ("M2_ANCHOR_B_ALWAYS_OK", "anchor B forced to pass",
     lambda: verdict_from(_ladder(pc_agree=0.2, pc_frac=0.0, pc_p=0.001)),
     "PLACEBO_LADDER_BROKEN", "CONCURRENCY_TAXES"),
    ("M3_P_DROP_PLUS_ONE", "permutation p loses its +1",
     v_p_gate, "PERIOD_CONFOUNDED", "CONCURRENCY_TAXES"),
    ("M4_ROLE_ALL_GATES", "every rung forced to be a gate",
     lambda: verdict_from(_ladder()),
     "CONCURRENCY_TAXES", "SCALE_DEPENDENT_TAX"),
    # every rung reproduces here, so that turning them all into positive controls does
    # NOT trip step 7 first. With the default ladder the mutant stopped at
    # PLACEBO_LADDER_BROKEN (correct ordering, useless witness).
    ("M5_ROLE_ALL_POSITIVE", "every rung forced to be a positive control",
     lambda: verdict_from(_ladder(primary_frac=0.8, gate_frac=0.8, glob_frac=0.8)),
     "PERIOD_CONFOUNDED", "PRIMARY_IS_POSITIVE_CONTROL"),
    ("M6_SKIP_POSITIVE_CONTROL_CHECK", "positive control no longer has to reproduce",
     lambda: verdict_from(_ladder(pc_frac=0.2)),
     "PLACEBO_LADDER_BROKEN", "CONCURRENCY_TAXES"),
    ("M7_USE_OLD_MAX_GATE", "R489's max rule back in place of the leveled gate",
     lambda: verdict_from(_ladder(primary_maxlog=0.9)),
     "CONCURRENCY_TAXES", "PERIOD_CONFOUNDED"),
    ("M8_PRIMARY_PC_CHECK_OFF", "primary allowed to be judged as its own positive control",
     lambda: verdict_from(_ladder(primary_agree=0.9, primary_frac=0.8)),
     "PRIMARY_IS_POSITIVE_CONTROL", "PERIOD_CONFOUNDED"),
    ("M9_SCALE_DEPENDENCE_OFF", "other gate rungs stop being consulted",
     lambda: verdict_from(_ladder(gate_p=0.9)),
     "SCALE_DEPENDENT_TAX", "CONCURRENCY_TAXES"),
    ("M10_PREREQ_SILENT", "missing row fields pass silently",
     v_rows_missing_field, "LADDER_UNSCANNED", "UNSCANNED"),
    ("M11_GATE_REPRO_OFF", "R490-B's reproduction half switched off",
     v_period, "PERIOD_CONFOUNDED", "CONCURRENCY_TAXES"),
    ("M12_GATE_P_OFF", "D1's p half switched off",
     lambda: verdict_from(_ladder(primary_p=0.9)),
     "PERIOD_CONFOUNDED", "CONCURRENCY_TAXES"),
]


def run_case(mutant, fn):
    old = os.environ.get("R490_MUTANT")
    os.environ["R490_MUTANT"] = mutant
    try:
        return fn(), None
    except Exception:
        return None, traceback.format_exc(limit=3)
    finally:
        if old is None:
            os.environ.pop("R490_MUTANT", None)
        else:
            os.environ["R490_MUTANT"] = old


def main():
    results = []
    print(f"{'mutant':<32} {'clean':<28} {'mutated':<28} outcome")
    print("-" * 104)
    for mutant, desc, fn, want_clean, want_mut in CASES:
        clean, err_c = run_case("", fn)
        mutated, err_m = run_case(mutant, fn)
        if err_c or err_m:
            outcome = "BROKEN(crash)"
        elif clean != want_clean:
            outcome = f"BASELINE_BROKEN(want {want_clean})"
        elif mutated == clean:
            outcome = "MISSED"
        elif mutated != want_mut:
            outcome = f"DETECTED_OTHER(want {want_mut})"
        else:
            outcome = "detected"
        results.append((mutant, outcome))
        print(f"{mutant:<32} {str(clean):<28} {str(mutated):<28} {outcome}")

    # --- second witness for M10: the rung-level half of the same flag ---------------
    bad_rung = {"reps_requested": 4, "replicates": [{"ratio": 1.0, "agreement": 0.5,
                "coverage": 1.0, "n_hi": 1, "n_lo": 1}]}
    c, _ = run_case("", lambda: M.prereq_rung(bad_rung))
    m, _ = run_case("M10_PREREQ_SILENT", lambda: M.prereq_rung(bad_rung))
    ok10b = (c is False and m is True)
    results.append(("M10_PREREQ_SILENT(rung half)", "detected" if ok10b else "MISSED"))
    print(f"{'M10_PREREQ_SILENT(rung half)':<32} {str(c):<28} {str(m):<28} "
          f"{'detected' if ok10b else 'MISSED'}")

    # --- no-op control: an unknown mutant name must change nothing ------------------
    noop_ok = True
    for _mutant, _desc, fn, want_clean, _wm in CASES:
        a, _ = run_case("", fn)
        b, _ = run_case("M0_NOOP_CONTROL", fn)
        if a != b:
            noop_ok = False
    results.append(("M0_NOOP_CONTROL", "detected" if noop_ok else "MISSED"))
    print(f"{'M0_NOOP_CONTROL':<32} {'(all cases)':<28} {'(unchanged)':<28} "
          f"{'ok' if noop_ok else 'FAIL: the harness reacts to an unknown name'}")

    bad = [m for m, o in results if o not in ("detected",)]
    print()
    print(f"{len(results) - len(bad)}/{len(results)} behaved as prereg'd")
    for m, o in results:
        if o != "detected":
            print(f"  {m}: {o}")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
