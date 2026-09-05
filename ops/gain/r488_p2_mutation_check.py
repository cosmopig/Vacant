#!/usr/bin/env python3
"""R488 P-2 mutation check for r488_pointwise_concurrency.py.

Fixtures are synthetic populations with a PLANTED effect plus direct calls into the pure
decide()/combine_hypotheses(). Includes a no-op control: if that is reported as caught,
every other row here is meaningless.
"""
import json, os, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MOD = HERE / "r488_pointwise_concurrency.py"

PRELUDE = f"""
import sys, json, math
sys.path.insert(0, {str(HERE)!r})
from r488_pointwise_concurrency import (exposure_at, exposures, estimate, bucketise,
                                        decide, combine_hypotheses, pooled_log_ratio,
                                        build_cells, N_BUCKETS)

def _row(rid, ts, lat_ms, tok=100):
    return {{"id": rid, "ts": ts, "latency_ms": lat_ms, "completion_tokens": tok,
             "status_code": 200, "finish_reason": "stop",
             "method": "POST", "path": "[gw] /v1/chat/completions"}}

def planted():
    rows = []
    for i in range(1, 241):
        if i <= 120:
            s, mspt = 1000.0 + i * 0.5, 20.0
        else:
            s, mspt = 100000.0 + (i - 120) * 500.0, 10.0
        tok = 100 + (i % 5) * 40
        rows.append(_row(i, s, tok * mspt, tok=tok))
    return rows

def planted_ratio():
    rows = planted()
    which, _ = bucketise([r["completion_tokens"] for r in rows], N_BUCKETS)
    e, _ = estimate(rows, rows, "start", which, 0.0)
    return e

def long_self():
    # one request made 100x longer; its OWN point exposure must not move
    src = [_row(1, 0.0, 1000.0), _row(2, 50.0, 1000.0)]
    a = exposures([_row(3, 100.0, 10.0)], src + [_row(3, 100.0, 10.0)], "start")[0][0]
    b = exposures([_row(3, 100.0, 100000.0)], src + [_row(3, 100.0, 100000.0)], "start")[0][0]
    return [a, b]

def simpson():
    # Within each token stratum the hi/lo ratio is EXACTLY 1.0, but the arms are
    # imbalanced across strata, so pooling without stratifying manufactures an effect.
    # This is what the stratification is for, so this is the fixture that can see it.
    recs = []
    recs += [(100, 1, 10.0)] * 30 + [(100, 0, 10.0)] * 60
    recs += [(500, 1, 30.0)] * 60 + [(500, 0, 30.0)] * 30
    which = lambda tok: 0 if tok == 100 else 1
    lr, _ = pooled_log_ratio(build_cells(recs, which))
    return round(math.exp(lr), 4) if lr is not None else None

out = {{}}
"""

FIXTURES = {
    "planted_ratio":  "round(planted_ratio()['ratio'], 4)",
    "planted_arms":   "[planted_ratio()['n_hi'], planted_ratio()['n_lo']]",
    "planted_cov":    "planted_ratio()['coverage']",
    "own_duration":   "long_self()",
    "point_gap":      "exposure_at(15.0, [(0.0,10.0),(20.0,30.0)])",
    "self_skipped":   "exposure_at(5.0, [(0.0,10.0)], skip=0)",
    "dec_degenerate": "decide({'n_hi':3,'n_lo':200,'coverage':0.9,'ratio':1.5,"
                      "'ci_lo':1.3,'ci_hi':1.7}, [{'coverage':0.9,'ratio':1.01}])",
    "dec_lowcov":     "decide({'n_hi':200,'n_lo':200,'coverage':0.1,'ratio':1.5,"
                      "'ci_lo':1.3,'ci_hi':1.7}, [{'coverage':0.9,'ratio':1.01}])",
    "dec_plac_uns":   "decide({'n_hi':200,'n_lo':200,'coverage':0.9,'ratio':1.5,"
                      "'ci_lo':1.3,'ci_hi':1.7}, [{'coverage':0.1,'ratio':1.01}])",
    "dec_confound":   "decide({'n_hi':200,'n_lo':200,'coverage':0.9,'ratio':1.5,"
                      "'ci_lo':1.3,'ci_hi':1.7}, [{'coverage':0.9,'ratio':1.9}])",
    "dec_taxes":      "decide({'n_hi':200,'n_lo':200,'coverage':0.9,'ratio':1.5,"
                      "'ci_lo':1.3,'ci_hi':1.7}, [{'coverage':0.9,'ratio':1.01}])",
    "comb_sens":      "combine_hypotheses({'verdict':'CONCURRENCY_TAXES'},"
                      "{'verdict':'NO_TAX'},'TS_UNRESOLVED_BY_ID')['verdict']",
    "comb_resolved":  "combine_hypotheses({'verdict':'CONCURRENCY_TAXES'},"
                      "{'verdict':'NO_TAX'},'TS_IS_START')['verdict']",
    "thin_cell":      "pooled_log_ratio({0:{'hi':[2.0]*5,'lo':[1.0]*30}})[0]",
    "strat_cancel":   "round(pooled_log_ratio({0:{'hi':[2.0]*30,'lo':[1.0]*30},"
                      "1:{'hi':[1.0]*30,'lo':[2.0]*30}})[0], 9)",
    "simpson":        "simpson()",
}

MUTANTS = {
    "N1_LIFETIME_OVERLAP":     "own_duration",
    "N3_DROP_COVERAGE_GATE":   "dec_lowcov",
    "N2_DROP_PLACEBO_GATE":    "dec_confound",
    "N4_INCLUDE_SELF":         "self_skipped",
    "N5_DROP_CELL_MINIMUM":    "thin_cell",
    "N6_DROP_STRATIFICATION":  "simpson",
    "N7_DROP_DEGENERATE_GATE": "dec_degenerate",
    "N8_IGNORE_TS_RESOLUTION": "comb_resolved",
    "N9_NOOP_CONTROL":         None,
}


def verdicts(mutant):
    body = PRELUDE
    for name, expr in FIXTURES.items():
        body += (f"\ntry:\n    out[{name!r}] = {expr}\n"
                 f"except Exception as e:\n    out[{name!r}] = 'EXC:' + type(e).__name__\n")
    body += "\nprint(json.dumps(out))\n"
    env = dict(os.environ)
    if mutant:
        env["R488P2_MUTANT"] = mutant
    else:
        env.pop("R488P2_MUTANT", None)
    r = subprocess.run([sys.executable, "-c", body], capture_output=True, text=True, env=env)
    if r.returncode != 0:
        return {"__error__": r.stderr.strip()[-300:]}
    return json.loads(r.stdout)


def main():
    src = MOD.read_text()
    missing = [m for m in MUTANTS if m != "N9_NOOP_CONTROL" and m not in src]
    if missing:
        print("BASELINE_BROKEN: mutant names absent from module:", missing)
        return 2
    if "N9_NOOP_CONTROL" in src:
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
            print(f"  {mut:26s} BROKEN  {v['__error__']}")
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
        print(f"  {mut:26s} {label:9s} {note}")
    print(f"{len(MUTANTS) - bad}/{len(MUTANTS)} mutants behaved as prereg'd")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
