#!/usr/bin/env python3
"""R487-B: resolve whether the gateway's `ts` is the request START or END.

Criteria: DECISION_20260905_R487B_TS_SEMANTICS_PREREG.md (committed before this file).
Method uses ONLY the id ordering and latency -- deliberately independent of anything in
the concurrency-tax question, because the disclosure section records that the tax answer
under each hypothesis was already known when this was designed.
"""
import argparse, json, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SNAPSHOT = ROOT / "ops/gain/data/r486_gateway_snapshot_v2.json"

KEYS = ("ts", "ts_plus_lat", "ts_minus_lat")
MIN_PAIRS = 100
MAX_BEST_INV = 0.02
MIN_MARGIN = 0.05


def _mut(name):
    return os.environ.get("R487B_MUTANT", "") == name


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


def inversion_rate(rows, key):
    """Fraction of adjacent pairs (in id order) where `key` decreases."""
    s = sorted(rows, key=lambda r: r["id"])
    if len(s) < 2:
        return None, 0
    bad = 0
    for a, b in zip(s, s[1:]):
        va, vb = key_value(a, key), key_value(b, key)
        if _mut("M2_INV_COUNTS_TIES"):
            if vb <= va:
                bad += 1
        elif vb < va:
            bad += 1
    return bad / (len(s) - 1), len(s) - 1


def decide(inv):
    """inv: {key: rate}. Returns verdict string."""
    order = sorted(inv.items(), key=lambda kv: kv[1])
    best, second = order[0], order[1]
    margin = second[1] - best[1]
    if _mut("M3_DROP_MARGIN"):
        pass
    elif margin < MIN_MARGIN:
        return "TS_UNRESOLVED_BY_ID"
    if not _mut("M4_DROP_ABS_THRESHOLD") and best[1] > MAX_BEST_INV:
        return "TS_UNRESOLVED_BY_ID"
    return {"ts": "TS_UNRESOLVED_BY_ID",
            "ts_plus_lat": "TS_IS_START",
            "ts_minus_lat": "TS_IS_END"}[best[0]]


def analyze(rows):
    ids = [r["id"] for r in rows]
    if len(set(ids)) != len(ids):
        return {"verdict": "BROKEN", "reason": "duplicate ids", "n": len(rows)}
    inv = {}
    npairs = 0
    for k in KEYS:
        rate, npairs = inversion_rate(rows, k)
        if rate is None:
            return {"verdict": "UNSCANNED", "reason": "fewer than 2 rows", "n": len(rows)}
        inv[k] = rate
    if npairs < MIN_PAIRS and not _mut("M5_DROP_PAIR_GUARD"):
        return {"verdict": "UNSCANNED", "reason": f"n_pairs={npairs}<{MIN_PAIRS}",
                "inv": inv, "n_pairs": npairs}
    return {"verdict": decide(inv), "inv": inv, "n_pairs": npairs, "n": len(rows)}


def is_chat(row):
    return row.get("method") == "POST" and "/v1/chat/completions" in (row.get("path") or "")


def combine_populations(allr, chat):
    """Gate: the all-rows and chat-only populations must reach the same verdict.

    Split out of run() so a fixture can set the two verdicts INDEPENDENTLY; if they were
    derived from one another no fixture could see this gate fail.
    """
    agree = allr["verdict"] == chat["verdict"]
    if _mut("M6_DROP_POPULATION_AGREEMENT"):
        agree = True
    return {"all": allr, "chat": chat,
            "population_sensitive": not agree,
            "verdict": allr["verdict"] if agree else "TS_POPULATION_SENSITIVE"}


def run(path):
    d = json.loads(Path(path).read_text())
    rows = d["rows"]
    return combine_populations(analyze(rows), analyze([r for r in rows if is_chat(r)]))


# ---------------------------------------------------------------- selftest

def _r(rid, ts, lat):
    return {"id": rid, "ts": ts, "latency_ms": lat,
            "method": "POST", "path": "[gw] /v1/chat/completions"}


def selftest():
    ok = 0
    fail = []

    def chk(n, c):
        nonlocal ok
        if c:
            ok += 1
        else:
            fail.append(n)

    chk("key_ts", key_value(_r(1, 100.0, 2000.0), "ts") == 100.0)
    chk("key_plus", key_value(_r(1, 100.0, 2000.0), "ts_plus_lat") == 102.0)
    chk("key_minus", key_value(_r(1, 100.0, 2000.0), "ts_minus_lat") == 98.0)
    try:
        key_value(_r(1, 0, 0), "nope")
        chk("key_bad", False)
    except ValueError:
        chk("key_bad", True)

    # hand-built: END times strictly increasing with id, START times shuffled
    #   id1 ts=0   lat=10s -> end 10 ; id2 ts=5  lat=10s -> end 15 ; id3 ts=1 lat=20s -> end 21
    start_rows = [_r(1, 0.0, 10000.0), _r(2, 5.0, 10000.0), _r(3, 1.0, 20000.0)]
    i_ts, np1 = inversion_rate(start_rows, "ts")
    i_pl, _ = inversion_rate(start_rows, "ts_plus_lat")
    i_mi, _ = inversion_rate(start_rows, "ts_minus_lat")
    chk("inv_pairs", np1 == 2)
    chk("inv_ts_has_one", abs(i_ts - 0.5) < 1e-9)      # 5 -> 1 is a drop
    chk("inv_plus_zero", i_pl == 0.0)                   # 10,15,21 monotone
    chk("inv_minus_nonzero", i_mi > 0.0)                # -10,-5,-19
    chk("inv_short", inversion_rate([_r(1, 0, 0)], "ts") == (None, 0))
    # id order is what matters, not list order
    chk("inv_uses_id_order",
        inversion_rate(list(reversed(start_rows)), "ts_plus_lat")[0] == 0.0)

    chk("decide_start", decide({"ts": 0.5, "ts_plus_lat": 0.0, "ts_minus_lat": 0.6}) == "TS_IS_START")
    chk("decide_end", decide({"ts": 0.5, "ts_plus_lat": 0.6, "ts_minus_lat": 0.0}) == "TS_IS_END")
    chk("decide_ts_best_is_unresolved",
        decide({"ts": 0.0, "ts_plus_lat": 0.5, "ts_minus_lat": 0.6}) == "TS_UNRESOLVED_BY_ID")
    chk("decide_margin_too_small",
        decide({"ts": 0.5, "ts_plus_lat": 0.00, "ts_minus_lat": 0.04}) == "TS_UNRESOLVED_BY_ID")
    chk("decide_best_too_high",
        decide({"ts": 0.9, "ts_plus_lat": 0.10, "ts_minus_lat": 0.9}) == "TS_UNRESOLVED_BY_ID")
    chk("decide_margin_exact_ok",
        decide({"ts": 0.9, "ts_plus_lat": 0.00, "ts_minus_lat": 0.06}) == "TS_IS_START")

    chk("analyze_dupe_ids",
        analyze([_r(1, 0.0, 1.0), _r(1, 2.0, 1.0)])["verdict"] == "BROKEN")
    chk("analyze_pair_guard", analyze(start_rows)["verdict"] == "UNSCANNED")
    big = [_r(i, float(i), 1000.0) for i in range(1, 300)]
    a = analyze(big)
    chk("analyze_big_runs", a["n_pairs"] == 298)
    chk("analyze_ts_best_unresolved", a["verdict"] == "TS_UNRESOLVED_BY_ID")
    #   synthetic population where ts really is START (id assigned at completion)
    import random as _rd
    rnd = _rd.Random(7)
    ends = sorted(rnd.uniform(0, 10000) for _ in range(400))
    st = []
    for i, e in enumerate(ends, start=1):
        lat = rnd.uniform(1, 50)
        st.append(_r(i, e - lat, lat * 1000.0))
    asr = analyze(st)
    chk("analyze_synth_start", asr["verdict"] == "TS_IS_START")
    chk("analyze_synth_start_inv0", asr["inv"]["ts_plus_lat"] < 1e-9)
    #   mirror: ts really is END (id assigned at arrival)
    starts = sorted(rnd.uniform(0, 10000) for _ in range(400))
    en = []
    for i, s0 in enumerate(starts, start=1):
        lat = rnd.uniform(1, 50)
        en.append(_r(i, s0 + lat, lat * 1000.0))
    aen = analyze(en)
    chk("analyze_synth_end", aen["verdict"] == "TS_IS_END")
    chk("analyze_synth_end_inv0", aen["inv"]["ts_minus_lat"] < 1e-9)
    #   noise floor: constant latency => all three keys are the same ordering
    flat = [_r(i, float(i), 1000.0) for i in range(1, 300)]
    chk("analyze_flat_unresolved", analyze(flat)["verdict"] == "TS_UNRESOLVED_BY_ID")

    # ties must NOT count as inversions (equal timestamps are not a decrease)
    tied = [_r(1, 0.0, 0.0), _r(2, 0.0, 0.0), _r(3, 1.0, 0.0)]
    chk("inv_ties_not_inversions", inversion_rate(tied, "ts")[0] == 0.0)
    chk("inv_real_drop_still_counts",
        inversion_rate([_r(1, 5.0, 0.0), _r(2, 5.0, 0.0), _r(3, 1.0, 0.0)], "ts")[0] == 0.5)

    # population-agreement gate (two verdicts set independently)
    A = {"verdict": "TS_IS_START", "inv": {}, "n_pairs": 500}
    B = {"verdict": "TS_IS_START", "inv": {}, "n_pairs": 400}
    C = {"verdict": "TS_IS_END", "inv": {}, "n_pairs": 400}
    g1 = combine_populations(A, B)
    chk("pop_agree", g1["verdict"] == "TS_IS_START" and g1["population_sensitive"] is False)
    g2 = combine_populations(A, C)
    chk("pop_disagree", g2["verdict"] == "TS_POPULATION_SENSITIVE" and g2["population_sensitive"])
    g3 = combine_populations(C, C)
    chk("pop_agree_end", g3["verdict"] == "TS_IS_END")

    chk("is_chat_yes", is_chat(_r(1, 0, 0)))
    chk("is_chat_no_get", not is_chat(dict(_r(1, 0, 0), method="GET")))

    print(f"selftest {ok}/{ok + len(fail)} passed" + (f"  FAILED={fail}" if fail else ""))
    return 0 if not fail else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", default=str(DEFAULT_SNAPSHOT))
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    out = run(a.snapshot)
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=2, sort_keys=True))
    print(f"  verdict {out['verdict']}  population_sensitive={out['population_sensitive']}")
    for pop in ("all", "chat"):
        x = out[pop]
        print(f"  {pop:5s} {x['verdict']:24s} n_pairs={x.get('n_pairs')} "
              f"inv={{{', '.join(f'{k}={v:.5f}' for k, v in x['inv'].items())}}}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
