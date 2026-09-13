#!/usr/bin/env python3
"""R488 P-1: resolve whether the gateway `ts` is request START or END.

Criteria: DECISION_20260905_R488_POINTWISE_CONCURRENCY_PREREG.md (committed first, 6ac4d2e).

Same ranking as R487-B (inversion rate of three candidate keys under id order); the
MARGIN is what changed: absolute difference -> paired sign test over discordant adjacent
pairs. The only admissible justification for that change is the synthetic reproduction
already committed as ops/gain/r487b_margin_rule_demo.py; see the prereg's disclosure
section for why a TS_IS_START verdict here is NOT an independent confirmation.

R487-B's rule and its raw outputs are untouched -- later rounds arbitrate with those.
"""
import argparse, json, math, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SNAPSHOT = ROOT / "ops/gain/data/r486_gateway_snapshot_v2.json"

KEYS = ("ts", "ts_plus_lat", "ts_minus_lat")
VERDICT_OF_KEY = {"ts": "TS_UNRESOLVED_BY_ID",
                  "ts_plus_lat": "TS_IS_START",
                  "ts_minus_lat": "TS_IS_END"}
MIN_PAIRS = 100        # unchanged from R487-B
MAX_BEST_INV = 0.02    # unchanged from R487-B
MAX_SIGN_P = 0.01      # new: replaces MIN_MARGIN = 0.05


def _mut(name):
    """Mutant flag. Read INSIDE the function under test -- a module-level read would be
    evaluated at import time and look identical to a toothless detector (r695)."""
    return os.environ.get("R488_MUTANT", "") == name


def binom_two_sided(b, n):
    """Exact two-sided binomial p-value at p0=0.5. Self-checked against textbook values
    in selftest() -- a hand-rolled statistic that has never been checked against a known
    answer is how r678 shipped a CP interval with the bisection direction reversed."""
    if n <= 0:
        return 1.0
    k = min(b, n - b)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2.0 ** n)
    return min(1.0, 2.0 * tail)


def key_value(row, key):
    ts = row["ts"]
    lat = (row.get("latency_ms") or 0) / 1000.0
    if key == "ts":
        return ts
    if key == "ts_plus_lat":
        return ts + lat
    if key == "ts_minus_lat":
        return ts - lat
    raise ValueError(key)


def violations(rows, key):
    """Per adjacent id-ordered pair: True where `key` DECREASES (an inversion)."""
    s = sorted(rows, key=lambda r: r["id"])
    out = []
    for a, b in zip(s, s[1:]):
        va, vb = key_value(a, key), key_value(b, key)
        if _mut("M4_TIES_COUNT_AS_INVERSION"):
            out.append(vb <= va)
        else:
            out.append(vb < va)
    return out


def sign_test(viol_best, viol_second):
    """Discordant-pair counts between the best and runner-up key, and the exact p."""
    b = c = 0
    for vb, vs in zip(viol_best, viol_second):
        if vs and not vb:
            b += 1
        elif vb and not vs:
            c += 1
    if _mut("M8_SWAP_BC"):
        b, c = c, b
    return b, c, binom_two_sided(b, b + c)


def decide(inv, sign):
    """Single decision point. inv: {key: rate}; sign: {'b','c','p'}.

    Pure and independently settable so a fixture can drive every branch -- a gate buried
    in a file-reading run() is one no fixture can reach (r758 M6).

    NOTE (r759): a `b > c` direction gate used to sit between the two gates below. It was
    DEAD CODE and has been deleted rather than left as an empty green light:
      * `best` is the argmin of the inversion counts over the same pairs, so
        #viol(best) <= #viol(second), which is exactly c <= b -- b < c is unreachable;
      * the only remaining way for `b > c` to be false is b == c, and b == c forces
        binom_two_sided(b, 2b) == 1.0 > MAX_SIGN_P, so the p gate already rejects it.
    Both facts are asserted exhaustively in selftest() instead of assumed. Deleting it
    changed no verdict on the real snapshot or on any calibration population (r759).
    """
    order = sorted(inv.items(), key=lambda kv: kv[1],
                   reverse=_mut("M9_RANK_BY_MAX"))
    best_key, best_inv = order[0]
    if not _mut("M3_DROP_ABS_THRESHOLD") and best_inv > MAX_BEST_INV:
        return "TS_UNRESOLVED_BY_ID"
    if not _mut("M1_DROP_SIGN_TEST") and sign["p"] > MAX_SIGN_P:
        return "TS_UNRESOLVED_BY_ID"
    return VERDICT_OF_KEY[best_key]


def analyze(rows):
    ids = [r["id"] for r in rows]
    if len(set(ids)) != len(ids):
        return {"verdict": "BROKEN", "reason": "duplicate ids", "n": len(rows)}
    if len(rows) < 2:
        return {"verdict": "UNSCANNED", "reason": "fewer than 2 rows", "n": len(rows)}
    viol = {k: violations(rows, k) for k in KEYS}
    npairs = len(viol[KEYS[0]])
    inv = {k: sum(v) / npairs for k, v in viol.items()}
    if npairs < MIN_PAIRS and not _mut("M5_DROP_PAIR_GUARD"):
        return {"verdict": "UNSCANNED", "reason": f"n_pairs={npairs}<{MIN_PAIRS}",
                "inv": inv, "n_pairs": npairs, "n": len(rows)}
    order = sorted(inv.items(), key=lambda kv: kv[1])
    b, c, p = sign_test(viol[order[0][0]], viol[order[1][0]])
    sign = {"best": order[0][0], "second": order[1][0], "b": b, "c": c, "p": p}
    return {"verdict": decide(inv, sign), "inv": inv, "sign": sign,
            "n_pairs": npairs, "n": len(rows)}


def is_chat(row):
    return row.get("method") == "POST" and "/v1/chat/completions" in (row.get("path") or "")


def combine_populations(allr, chat):
    """Both populations must agree. Split out so a fixture can set the two verdicts
    INDEPENDENTLY; deriving one from the other makes this gate structurally invisible."""
    agree = allr.get("verdict") == chat.get("verdict")
    if _mut("M6_DROP_POPULATION_AGREEMENT"):
        agree = True
    return {"all": allr, "chat": chat,
            "population_sensitive": not agree,
            "verdict": allr.get("verdict") if agree else "TS_POPULATION_SENSITIVE"}


def run(path):
    d = json.loads(Path(path).read_text())
    rows = d["rows"]
    return combine_populations(analyze(rows), analyze([r for r in rows if is_chat(r)]))


# ------------------------------------------------------------- calibration corpus
# Generators live here rather than importing the R487-B demo's, so the calibration is not
# built out of the module under test's own helpers (r699).

def _pop(truth, n=800, jitter=5.0, seed=11, span=20000.0):
    """truth: 'start' (id assigned at completion), 'end' (id assigned at arrival),
    'noise' (ts independent of id), 'const' (id at completion but latency constant --
    ts and ts+lat then induce IDENTICAL orderings, i.e. genuinely ambiguous)."""
    import random
    rnd = random.Random(seed)
    rows = []
    if truth == "noise":
        for i in range(1, n + 1):
            rows.append({"id": i, "ts": rnd.uniform(0, span),
                         "latency_ms": rnd.uniform(0.1, jitter) * 1000.0})
    elif truth == "const":
        starts = sorted(rnd.uniform(0, span) for _ in range(n))
        for i, s in enumerate(starts, 1):
            rows.append({"id": i, "ts": s, "latency_ms": jitter * 1000.0})
    elif truth == "end":
        starts = sorted(rnd.uniform(0, span) for _ in range(n))
        for i, s in enumerate(starts, 1):
            lat = rnd.uniform(0.1, jitter)
            rows.append({"id": i, "ts": s + lat, "latency_ms": lat * 1000.0})
    elif truth == "start":
        ends = sorted(rnd.uniform(0, span) for _ in range(n))
        for i, e in enumerate(ends, 1):
            lat = rnd.uniform(0.1, jitter)
            rows.append({"id": i, "ts": e - lat, "latency_ms": lat * 1000.0})
    else:
        raise ValueError(truth)
    for r in rows:
        r["method"] = "POST"
        r["path"] = "[gw] /v1/chat/completions"
    return rows


CALIBRATION = (
    ("pos_start_j50",  "start", 50.0,  "TS_IS_START"),
    ("pos_start_j5",   "start",  5.0,  "TS_IS_START"),
    ("pos_start_j1",   "start",  1.0,  "TS_IS_START"),
    ("pos_start_j0.2", "start",  0.2,  "TS_IS_START"),
    ("neg_end_j5",     "end",    5.0,  "TS_IS_END"),
    ("neg_end_j0.2",   "end",    0.2,  "TS_IS_END"),
    ("neg_noise",      "noise",  5.0,  "TS_UNRESOLVED_BY_ID"),
    ("neg_const_lat",  "const",  5.0,  "TS_UNRESOLVED_BY_ID"),
)


DIRECTION_OF = {"TS_IS_START": "start", "TS_IS_END": "end", "TS_UNRESOLVED_BY_ID": None}


def calibrate(verbose=False):
    """Two-directional calibration, reported under BOTH readings of the prereg.

    The prereg says of the END negatives "must return TS_IS_END, must not say START" and
    then names the falsification clause as "wrong direction on any of them". Those two
    sentences disagree when a population comes back UNRESOLVED. I am not silently taking
    the reading that keeps my own rule alive, so both are computed and reported:

      wrong_direction  -- a directional population got the OPPOSITE direction, or an
                          ambiguous/noise population produced ANY direction. This is the
                          prereg's operative falsification clause and drives rule_broken.
      strict_mismatch  -- verdict != expected on ANY population, UNRESOLVED included.
                          Kept on the record so a later round can arbitrate the other way.

    Directional populations are scored by RECOVERY RATE over both truths together: an END
    population with narrow latency is the mirror image of the START population with narrow
    latency, and scoring one as "report the rate as-is" and the other as "rule invalidated"
    would apply two standards to one phenomenon.
    """
    recovered = directional = 0
    wrong_direction, strict_mismatch, detail = [], [], []
    for name, truth, jitter, expect in CALIBRATION:
        res = analyze(_pop(truth, jitter=jitter))
        got = res.get("verdict")
        ok = got == expect
        got_dir = DIRECTION_OF.get(got, "?")
        want_dir = DIRECTION_OF.get(expect, "?")
        if not ok:
            strict_mismatch.append({"name": name, "expect": expect, "got": got})
        if want_dir is None:
            # ambiguous/noise: producing ANY direction is a wrong answer
            bad = got_dir is not None
        else:
            directional += 1
            recovered += 1 if ok else 0
            bad = got_dir is not None and got_dir != want_dir
        if bad:
            wrong_direction.append({"name": name, "expect": expect, "got": got})
        detail.append({"name": name, "expect": expect, "got": got, "ok": ok,
                       "wrong_direction": bad,
                       "sign": res.get("sign"), "inv": res.get("inv")})
        if verbose:
            s = res.get("sign") or {}
            print(f"  {name:15s} expect={expect:20s} got={got:22s} "
                  f"{'ok  ' if ok else 'MISS'} b={s.get('b')} c={s.get('c')} p={s.get('p'):.4g}"
                  f"{'  <-- WRONG DIRECTION' if bad else ''}")
    return {"recovered": recovered, "directional": directional,
            "wrong_direction": wrong_direction,
            "strict_mismatch": strict_mismatch,
            "rule_broken": len(wrong_direction) > 0,
            "rule_broken_strict": len(strict_mismatch) > 0,
            "detail": detail}


# ------------------------------------------------------------------------ selftest

def _r(rid, ts, lat):
    return {"id": rid, "ts": ts, "latency_ms": lat,
            "method": "POST", "path": "[gw] /v1/chat/completions"}


def selftest():
    ok, fail = 0, []

    def chk(name, cond):
        nonlocal ok
        if cond:
            ok += 1
        else:
            fail.append(name)

    # --- binom_two_sided against textbook values (hand-rolled statistic, r678)
    chk("binom 1/10 == 22/1024", abs(binom_two_sided(1, 10) - 22 / 1024) < 1e-12)
    chk("binom 0/5 == 2/32", abs(binom_two_sided(0, 5) - 2 / 32) < 1e-12)
    chk("binom 5/10 == 1.0", abs(binom_two_sided(5, 10) - 1.0) < 1e-12)
    chk("binom 9/10 == 22/1024", abs(binom_two_sided(9, 10) - 22 / 1024) < 1e-12)
    chk("binom n=0 -> 1.0", binom_two_sided(0, 0) == 1.0)
    chk("binom symmetric", binom_two_sided(3, 20) == binom_two_sided(17, 20))
    chk("binom monotone", binom_two_sided(1, 20) < binom_two_sided(8, 20))

    # --- key_value
    chk("key ts", key_value(_r(1, 100.0, 2000.0), "ts") == 100.0)
    chk("key plus", key_value(_r(1, 100.0, 2000.0), "ts_plus_lat") == 102.0)
    chk("key minus", key_value(_r(1, 100.0, 2000.0), "ts_minus_lat") == 98.0)
    chk("key null lat", key_value({"id": 1, "ts": 5.0, "latency_ms": None}, "ts_plus_lat") == 5.0)

    # --- violations
    v = violations([_r(1, 0.0, 0.0), _r(2, 1.0, 0.0), _r(3, 0.5, 0.0)], "ts")
    chk("violations shape", v == [False, True])
    chk("ties not inversions by default", violations([_r(1, 1.0, 0.0), _r(2, 1.0, 0.0)], "ts") == [False])

    # --- sign_test: each input set INDEPENDENTLY, not derived from one another
    b, c, p = sign_test([False] * 10, [True] * 10)
    chk("sign b=10 c=0", (b, c) == (10, 0))
    chk("sign p small", p < 0.01)
    b, c, p = sign_test([True] * 10, [False] * 10)
    chk("sign b=0 c=10", (b, c) == (0, 10))
    b, c, p = sign_test([True, False], [True, False])
    chk("sign concordant -> 0/0", (b, c) == (0, 0))
    chk("sign concordant p=1", p == 1.0)

    # --- decide: drive every branch with hand-set inputs
    good_inv = {"ts": 0.20, "ts_plus_lat": 0.001, "ts_minus_lat": 0.30}
    strong = {"b": 30, "c": 0, "p": 0.0}
    chk("decide start", decide(good_inv, strong) == "TS_IS_START")
    chk("decide abs threshold",
        decide({"ts": 0.5, "ts_plus_lat": 0.4, "ts_minus_lat": 0.6}, strong) == "TS_UNRESOLVED_BY_ID")
    # b < c is structurally unreachable (asserted exhaustively below), so decide() is NOT
    # required to reject it; recording the actual behaviour rather than deleting the case.
    chk("decide on unreachable b<c falls through to the p gate",
        decide(good_inv, {"b": 0, "c": 30, "p": 0.0}) == "TS_IS_START")
    chk("decide p gate",
        decide(good_inv, {"b": 3, "c": 2, "p": 0.5}) == "TS_UNRESOLVED_BY_ID")
    chk("decide tie b==c",
        decide(good_inv, {"b": 5, "c": 5, "p": 1.0}) == "TS_UNRESOLVED_BY_ID")
    chk("decide end",
        decide({"ts": 0.2, "ts_plus_lat": 0.3, "ts_minus_lat": 0.001}, strong) == "TS_IS_END")
    chk("decide ts-best is unresolved",
        decide({"ts": 0.001, "ts_plus_lat": 0.2, "ts_minus_lat": 0.3}, strong) == "TS_UNRESOLVED_BY_ID")
    chk("decide p exactly at threshold passes",
        decide(good_inv, {"b": 10, "c": 0, "p": MAX_SIGN_P}) == "TS_IS_START")
    chk("decide best_inv exactly at threshold passes",
        decide({"ts": 0.2, "ts_plus_lat": MAX_BEST_INV, "ts_minus_lat": 0.3}, strong) == "TS_IS_START")

    # --- the deleted direction gate: both halves of its emptiness, asserted not assumed
    import itertools as _it
    bad_bc = 0
    for n in range(1, 7):
        for pb in _it.product([0, 1], repeat=n):
            for ps in _it.product([0, 1], repeat=n):
                if sum(pb) > sum(ps):
                    continue                      # pb must be argmin to be `best`
                bb = sum(1 for x, y in zip(pb, ps) if y and not x)
                cc = sum(1 for x, y in zip(pb, ps) if x and not y)
                if bb < cc:
                    bad_bc += 1
    chk("exhaustive: b >= c whenever best is argmin", bad_bc == 0)
    chk("exhaustive: b == c forces p == 1.0",
        all(binom_two_sided(b, 2 * b) == 1.0 for b in range(0, 201)))
    chk("so the p gate subsumes the deleted direction gate", 1.0 > MAX_SIGN_P)
    # with that gate gone, b/c labelling is no longer load-bearing: the p-value is
    # symmetric by construction, and DIRECTION is carried by the ranking (best_key).
    chk("exhaustive: binom p is symmetric in b<->c",
        all(binom_two_sided(b, b + c) == binom_two_sided(c, b + c)
            for b in range(0, 40) for c in range(0, 40) if b + c > 0))

    # --- analyze guards
    chk("dup ids -> BROKEN", analyze([_r(1, 0.0, 0.0), _r(1, 1.0, 0.0)]).get("verdict") == "BROKEN")
    chk("one row -> UNSCANNED", analyze([_r(1, 0.0, 0.0)]).get("verdict") == "UNSCANNED")
    small = analyze(_pop("start", n=20))
    chk("few pairs -> UNSCANNED", small.get("verdict") == "UNSCANNED")
    chk("few pairs keeps inv", "inv" in small)

    # --- combine_populations with INDEPENDENTLY set verdicts
    chk("combine agree",
        combine_populations({"verdict": "TS_IS_START"}, {"verdict": "TS_IS_START"})
        .get("verdict") == "TS_IS_START")
    chk("combine disagree",
        combine_populations({"verdict": "TS_IS_START"}, {"verdict": "TS_IS_END"})
        .get("verdict") == "TS_POPULATION_SENSITIVE")
    chk("combine flags sensitivity",
        combine_populations({"verdict": "A"}, {"verdict": "B"}).get("population_sensitive") is True)

    # --- calibration corpus behaves as prereg'd on the NEGATIVE side
    cal = calibrate()
    chk("calibration no wrong directions", cal.get("rule_broken") is False)
    chk("calibration has 6 directional pops", cal.get("directional") == 6)
    chk("calibration recovers at least one", cal.get("recovered", 0) >= 1)
    chk("strict reading is recorded too", isinstance(cal.get("strict_mismatch"), list))
    chk("strict reading currently differs", cal.get("rule_broken_strict") is True)
    # an ambiguous population that produced a direction MUST count as wrong direction
    chk("noise-with-direction would be caught",
        DIRECTION_OF.get("TS_IS_START") is not None and DIRECTION_OF.get("TS_UNRESOLVED_BY_ID") is None)

    print(f"selftest {ok}/{ok + len(fail)} passed")
    for f in fail:
        print("  FAIL:", f)
    return 0 if not fail else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", default=str(DEFAULT_SNAPSHOT))
    ap.add_argument("--json")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--calibrate", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.calibrate:
        print("calibration (two-directional):")
        cal = calibrate(verbose=True)
        print(f"recovered {cal['recovered']}/{cal['directional']} directional  "
              f"rule_broken={cal['rule_broken']} (wrong_direction={cal['wrong_direction']})  "
              f"rule_broken_strict={cal['rule_broken_strict']} "
              f"(strict_mismatch={[m['name'] for m in cal['strict_mismatch']]})")
        return 1 if cal["rule_broken"] else 0
    out = run(a.snapshot)
    cal = calibrate()
    out["calibration"] = cal
    if cal["rule_broken"]:
        out["verdict"] = "RULE_BROKEN"
    print(f"verdict {out['verdict']}  population_sensitive={out['population_sensitive']}")
    for pop in ("all", "chat"):
        r = out[pop]
        s = r.get("sign", {})
        print(f"  {pop:5s} {r.get('verdict'):22s} n_pairs={r.get('n_pairs')} "
              f"inv={ {k: round(v, 5) for k, v in (r.get('inv') or {}).items()} }")
        print(f"        sign best={s.get('best')} second={s.get('second')} "
              f"b={s.get('b')} c={s.get('c')} p={s.get('p')}")
    print(f"  calibration recovered {cal['recovered']}/{cal['directional']} directional  "
          f"rule_broken={cal['rule_broken']} wrong_direction={cal['wrong_direction']}")
    print(f"  calibration strict reading rule_broken_strict={cal['rule_broken_strict']} "
          f"strict_mismatch={[m['name'] for m in cal['strict_mismatch']]}")
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
