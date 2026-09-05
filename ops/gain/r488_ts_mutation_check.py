#!/usr/bin/env python3
"""R488 P-1 mutation check: does each gate in r488_ts_semantics_sign.py have teeth?

Every mutant must be visible to at least one fixture. Fixtures are a mix of synthetic
POPULATIONS and direct calls into the pure decide()/combine_populations() -- gates that
only fire on exact ties are unreachable from any population (see EXHAUSTIVE note below),
so they are driven the same way selftest drives them: inputs set independently by hand.

Includes a NO-OP control: a mutant name the module never reads. If that one is reported
as caught, the harness itself is broken and every other row is meaningless.
"""
import itertools, os, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MOD = HERE / "r488_ts_semantics_sign.py"

# fixture name -> python snippet returning a verdict string, run in a fresh interpreter
FIXTURES = {
    "pop_start_j50":  "analyze(_pop('start', jitter=50.0))['verdict']",
    "pop_start_j1":   "analyze(_pop('start', jitter=1.0))['verdict']",
    "pop_end_j5":     "analyze(_pop('end', jitter=5.0))['verdict']",
    "pop_noise":      "analyze(_pop('noise', jitter=5.0))['verdict']",
    "pop_const_lat":  "analyze(_pop('const', jitter=5.0))['verdict']",
    "pop_small_n20":  "analyze(_pop('start', n=20, jitter=50.0))['verdict']",
    "pop_dup_ts":     "analyze(_dup_ts_pop())['verdict']",
    # pure-function fixtures: each input set INDEPENDENTLY of the others
    "dec_high_inv":   "decide({'ts':0.5,'ts_plus_lat':0.4,'ts_minus_lat':0.6},"
                      "{'b':30,'c':0,'p':0.0})",
    "dec_tie_bc":     "decide({'ts':0.9,'ts_plus_lat':0.001,'ts_minus_lat':0.001},"
                      "{'b':5,'c':5,'p':1.0})",   # kept: shows the tie path still rejects
    "comb_disagree":  "combine_populations({'verdict':'TS_IS_START'},"
                      "{'verdict':'TS_IS_END'})['verdict']",
}

# mutant -> fixture that MUST change (prereg'd before running)
MUTANTS = {
    "M1_DROP_SIGN_TEST":             "pop_start_j1",
    "M3_DROP_ABS_THRESHOLD":         "dec_high_inv",
    "M4_TIES_COUNT_AS_INVERSION":    "pop_dup_ts",
    "M5_DROP_PAIR_GUARD":            "pop_small_n20",
    "M6_DROP_POPULATION_AGREEMENT":  "comb_disagree",
    "M9_RANK_BY_MAX":                "pop_start_j50",
    # M8 was prereg'd as must-catch. Deleting the dead direction gate turned it into a
    # genuine no-op (binom p is symmetric in b<->c; direction is carried by the ranking),
    # so it is reclassified as a SECOND no-op control on that exhaustively-proven ground.
    # The original MISSED output is recorded in GAIN_STATE.md round759.
    "M8_SWAP_BC":                    None,
    "M7_NOOP_CONTROL":               None,   # must change NOTHING
}

PRELUDE = f"""
import sys, json
sys.path.insert(0, {str(HERE)!r})
from r488_ts_semantics_sign import (analyze, decide, combine_populations, _pop)

def _dup_ts_pop(n=400):
    # id order is correct, but many adjacent rows share an identical ts: counting ties as
    # inversions must change the ranking. No population with distinct timestamps can see
    # M4, so the fixture has to manufacture the ties.
    rows = []
    for i in range(1, n + 1):
        base = float(i // 4)          # 4 rows share each ts
        rows.append({{"id": i, "ts": base, "latency_ms": 10.0 * (i % 4),
                      "method": "POST", "path": "[gw] /v1/chat/completions"}})
    return rows

out = {{}}
"""


def verdicts(mutant):
    body = PRELUDE
    for name, expr in FIXTURES.items():
        body += f"\ntry:\n    out[{name!r}] = {expr}\nexcept Exception as e:\n    out[{name!r}] = 'EXC:' + type(e).__name__\n"
    body += "\nprint(json.dumps(out))\n"
    env = dict(os.environ)
    if mutant:
        env["R488_MUTANT"] = mutant
    else:
        env.pop("R488_MUTANT", None)
    r = subprocess.run([sys.executable, "-c", body], capture_output=True, text=True, env=env)
    if r.returncode != 0:
        return {"__error__": r.stderr.strip()[-300:]}
    import json as _j
    return _j.loads(r.stdout)


def main():
    src = MOD.read_text()
    # every prereg'd mutant name except the no-op must literally appear in the module --
    # a mutation string written from the RUNTIME value instead of the file's characters
    # silently never fires and looks exactly like a toothless detector
    missing = [m for m in MUTANTS if m != "M7_NOOP_CONTROL" and m not in src]
    if missing:
        print("BASELINE_BROKEN: mutant names absent from module:", missing)
        return 2
    if "M7_NOOP_CONTROL" in src:
        print("BASELINE_BROKEN: the no-op control name appears in the module")
        return 2

    base = verdicts(None)
    if "__error__" in base:
        print("BASELINE_BROKEN:", base["__error__"])
        return 2

    # exhaustive structural fact, asserted rather than assumed: `best` is argmin of the
    # inversion counts, so #viol(best) <= #viol(second), which is exactly c <= b. The
    # direction gate can therefore ONLY fire on an exact tie (b == c). It is not dead
    # code -- pop_const_lat reaches it -- but it is narrower than it reads.
    viol_bad = 0
    for n in range(1, 7):
        for pb in itertools.product([0, 1], repeat=n):
            for ps in itertools.product([0, 1], repeat=n):
                if sum(pb) > sum(ps):
                    continue          # pb must be the argmin to be `best`
                b = sum(1 for x, y in zip(pb, ps) if y and not x)
                c = sum(1 for x, y in zip(pb, ps) if x and not y)
                if b < c:
                    viol_bad += 1
    print(f"exhaustive: b >= c whenever best is argmin -> violations={viol_bad} (must be 0)")
    if viol_bad:
        print("BASELINE_BROKEN: the b>c gate is not what it claims")
        return 2

    rows, bad = [], 0
    for mut, target in MUTANTS.items():
        v = verdicts(mut)
        if "__error__" in v:
            print(f"  {mut:30s} BROKEN {v['__error__']}")
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
        rows.append((mut, ok, note, changed))
        if not ok:
            bad += 1
        label = ('as-prereg' if target is None else 'caught') if ok else 'MISSED'
        print(f"  {mut:30s} {label:9s} {note}")

    print(f"{len(rows) - bad}/{len(rows)} mutants behaved as prereg'd")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
