#!/usr/bin/env python3
"""R484: attribute a gain run's wall-clock time to server-wait vs client-side gap.

Read-only. Zero API calls. Criteria live in
DECISION_20260905_R484_RUN_SLOWNESS_ATTRIBUTION_PREREG.md and are mirrored as
constants below; the prereg is the arbiter if they ever disagree.
"""
import argparse, json, os, statistics, sys

MUT = os.environ.get("R484_MUTANT", "")

# --- thresholds pinned in the prereg (section 4) -------------------------
P0_SERVER_BOUND = 0.70
P0_CLIENT_BOUND = 0.30
P1_DEGRADE_RATIO = 1.5
P1_MIN_PER_BUCKET = 10
P1_MIN_BUCKETS = 4
P2_MIN_CALLS = 10
P2_SAME_SPEED_PCT = 0.25
BAD_LATENCY_FRAC = 0.05


def load(path):
    """Parse raw JSONL exactly as it sits on disk. No schema massaging."""
    out = []
    with open(path) as fh:
        for ln, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def ms_per_tok(c):
    u = c.get("usage") or {}
    ct = u.get("completion_tokens")
    lat = c.get("latency_ms")
    if not ct or lat is None:
        return None
    return lat / ct


def idle_gaps(calls, ts_is_end):
    """Time between consecutive calls that is NOT inside a request.

    ts_is_end=True  -> ts_ms marks when the call finished.
    ts_is_end=False -> ts_ms marks when the call started.
    """
    gaps = []
    for a, b in zip(calls, calls[1:]):
        if ts_is_end:
            g = b["ts_ms"] - a["ts_ms"] - b["latency_ms"]
        else:
            g = b["ts_ms"] - (a["ts_ms"] + a["latency_ms"])
        gaps.append(g)
    return gaps


def resolve_ts_semantics(calls):
    """Pick the ts_ms meaning that yields no negative idle gaps (prereg s.3)."""
    ev = {}
    for name, is_end in (("end", True), ("start", False)):
        g = idle_gaps(calls, is_end)
        ev[name] = sum(1 for x in g if x < 0)
    if MUT == "M1_TS_ASSUME_END":
        return "end", ev
    end_ok, start_ok = ev["end"] == 0, ev["start"] == 0
    if end_ok and not start_ok:
        return "end", ev
    if start_ok and not end_ok:
        return "start", ev
    if end_ok and start_ok:
        return "either", ev
    return None, ev


def analyse(calls, census_window=None):
    out = {"n_calls_raw": len(calls)}
    calls = [c for c in calls if c.get("ts_ms") is not None]
    calls.sort(key=lambda c: c["ts_ms"])
    out["n_calls"] = len(calls)
    if len(calls) < 2:
        out["verdict"] = "UNSCANNED"
        out["reason"] = "fewer than 2 timestamped calls"
        return out

    # --- refutation cond 2: latency integrity -----------------------------
    bad_lat = [c for c in calls if not c.get("latency_ms")]
    out["n_bad_latency"] = len(bad_lat)
    out["bad_latency_frac"] = round(len(bad_lat) / len(calls), 4)
    out["n_not_ok"] = sum(1 for c in calls if not c.get("ok"))
    if out["bad_latency_frac"] > BAD_LATENCY_FRAC:
        out["verdict"] = "UNRESOLVED"
        out["reason"] = "REFUTE_2: missing/zero latency_ms above 5%"
        return out
    calls = [c for c in calls if c.get("latency_ms")]

    # --- refutation cond 3: requests cannot be serial (semantics-free) ----
    # Pigeonhole: the most generous serial packing occupies span + max(lat).
    _busy = sum(c["latency_ms"] for c in calls)
    _span = calls[-1]["ts_ms"] - calls[0]["ts_ms"]
    _maxlat = max(c["latency_ms"] for c in calls)
    out["serial_slack_ms"] = _span + _maxlat - _busy
    if out["serial_slack_ms"] < 0 and MUT != "M5_SKIP_CONCURRENCY":
        out["verdict"] = "MODEL_INVALID"
        out["reason"] = ("REFUTE_3: sum(latency) exceeds span+max(latency) => requests overlap, "
                         "the serial time-decomposition model does not hold")
        return out

    # --- ts semantics (prereg s.3) ---------------------------------------
    sem, sem_ev = resolve_ts_semantics(calls)
    out["ts_semantics"] = sem
    out["ts_negative_gap_counts"] = sem_ev
    if sem is None:
        out["verdict"] = "UNRESOLVED"
        out["reason"] = "REFUTE_1: TS_SEMANTICS_UNRESOLVED (both assumptions give negative gaps)"
        return out

    # --- P-0 -------------------------------------------------------------
    # wall = first request's START to last request's END, under either reading.
    busy = sum(c["latency_ms"] for c in calls)
    span = calls[-1]["ts_ms"] - calls[0]["ts_ms"]
    wall_end = span + calls[0]["latency_ms"]    # ts_ms marks call end
    wall_start = span + calls[-1]["latency_ms"]  # ts_ms marks call start
    if MUT == "M6_ASYMMETRIC_WALL":
        wall = span + (calls[0]["latency_ms"] if sem != "start" else 0)
    elif sem == "end":
        wall = wall_end
    elif sem == "start":
        wall = wall_start
    else:  # "either": tie-break pinned BEFORE measurement -- take the wall that
        # yields the SMALLER busy_frac, i.e. the reading least favourable to the
        # SERVER_BOUND verdict this round expects. Reason is conservatism, not
        # any observed number (prereg s.3 amendment, R484).
        wall = max(wall_end, wall_start)
    out["busy_ms"], out["wall_ms"] = busy, wall
    out["wall_ms_both"] = {"if_ts_is_end": wall_end, "if_ts_is_start": wall_start}
    ratio = busy / wall if wall > 0 else None
    out["busy_frac"] = round(ratio, 4) if ratio is not None else None
    if ratio is None:
        out["verdict"] = "UNRESOLVED"; out["reason"] = "zero wall time"; return out
    # Refutation cond 3 lives in the semantics-free pigeonhole test above.
    # Given non-negative gaps, busy <= wall is an IDENTITY, not a live guard:
    #   end-reading   span >= sum(lat[1:])  => wall = span+lat[0]  >= busy
    #   start-reading span >= sum(lat[:-1]) => wall = span+lat[-1] >= busy
    # Verified empirically to be unreachable (R484 results, 200k random inputs).
    # Kept as an assertion so a future edit that breaks it fails loudly.
    if MUT != "M2_DROP_IDENTITY_ASSERT":
        assert busy <= wall + 1e-6, (
            f"IDENTITY_VIOLATED busy={busy} wall={wall} sem={sem}")
    if ratio >= P0_SERVER_BOUND:
        out["verdict"] = "SERVER_BOUND"
    elif ratio <= P0_CLIENT_BOUND:
        out["verdict"] = "CLIENT_GAP_BOUND"
    else:
        out["verdict"] = "MIXED"
    out["h_cpu_explanatory_ceiling"] = round(1.0 - ratio, 4)

    # --- ms/token, with named exclusions ---------------------------------
    speeds = [(c["ts_ms"], ms_per_tok(c)) for c in calls]
    excl = [t for t, s in speeds if s is None]
    speeds = [(t, s) for t, s in speeds if s is not None]
    out["n_excluded_no_tokens"] = len(excl)
    out["n_speed_samples"] = len(speeds)

    # --- P-1: hourly buckets ---------------------------------------------
    t0 = calls[0]["ts_ms"]
    buckets = {}
    for t, s in speeds:
        buckets.setdefault(int((t - t0) // 3600000), []).append(s)
    rows, thin = [], []
    for k in sorted(buckets):
        v = buckets[k]
        rec = {"hour": k, "n": len(v), "median_ms_per_tok": round(statistics.median(v), 2)}
        if len(v) < P1_MIN_PER_BUCKET and MUT != "M3_KEEP_THIN_BUCKETS":
            rec["thin"] = True
            thin.append(k)
        else:
            rows.append(rec)
        buckets[k] = rec
    out["hourly"] = [buckets[k] for k in sorted(buckets)]
    out["thin_buckets"] = thin
    if len(rows) < P1_MIN_BUCKETS:
        out["p1"] = {"verdict": "UNSCANNED",
                     "reason": f"only {len(rows)} usable buckets (< {P1_MIN_BUCKETS})"}
    else:
        first = statistics.median([r["median_ms_per_tok"] for r in rows[:2]])
        last = statistics.median([r["median_ms_per_tok"] for r in rows[-2:]])
        r = last / first if first else None
        out["p1"] = {"first2_ms_per_tok": round(first, 2), "last2_ms_per_tok": round(last, 2),
                     "ratio": round(r, 3) if r else None,
                     "verdict": "ENDPOINT_DEGRADING" if r and r >= P1_DEGRADE_RATIO else "ENDPOINT_FLAT"}

    # --- P-2: census window ----------------------------------------------
    if census_window:
        lo, hi = census_window
        inw = [s for t, s in speeds if lo <= t <= hi]
        outw = [s for t, s in speeds if not (lo <= t <= hi)]
        p2 = {"window_ms": [lo, hi], "n_in": len(inw), "n_out": len(outw)}
        if len(inw) < P2_MIN_CALLS and MUT != "M4_IGNORE_THIN_WINDOW":
            p2["verdict"] = "UNSCANNED"
            p2["reason"] = f"only {len(inw)} calls in window (< {P2_MIN_CALLS}); NOT evidence of no effect"
        else:
            mi, mo = statistics.median(inw), statistics.median(outw)
            d = abs(mi - mo) / mo if mo else None
            p2.update({"median_in": round(mi, 2), "median_out": round(mo, 2),
                       "rel_diff": round(d, 3) if d is not None else None,
                       "verdict": "SAME_SERVER_SPEED" if d is not None and d < P2_SAME_SPEED_PCT
                                  else "SERVER_SPEED_DIFFERS"})
        out["p2"] = p2

    # --- idle gap descriptives (section 6: compatible-with, not proof) ----
    g = idle_gaps(calls, sem != "start")
    if g:
        out["idle_gap_ms"] = {"median": round(statistics.median(g), 1),
                              "mean": round(statistics.mean(g), 1),
                              "max": max(g), "n": len(g)}
    return out


# ------------------------------------------------------------------ selftest
def _write(path, recs):
    with open(path, "w") as fh:
        for r in recs:
            fh.write(json.dumps(r) + "\n")


def _call(ts, lat, tok=100, ok=True):
    """Fixture rows are plain dicts shaped like the real file, NOT built by
    any helper that analyse() also uses."""
    d = {"ts_ms": ts, "latency_ms": lat, "ok": ok}
    if tok is not None:
        d["usage"] = {"completion_tokens": tok}
    return d


def selftest():
    import tempfile
    res, fails = [], []

    def chk(name, cond):
        res.append((name, bool(cond)))
        if not cond:
            fails.append(name)

    td = tempfile.mkdtemp()

    def safe(*a, **k):
        try:
            return analyse(*a, **k)
        except Exception as ex:                       # noqa: BLE001
            return {"verdict": "EXCEPTION", "reason": f"{type(ex).__name__}: {ex}"}

    # A: pure server-bound, ts = end time, no gaps at all
    p = os.path.join(td, "a.jsonl")
    _write(p, [_call(1000 + i * 10000, 10000) for i in range(20)])
    a = analyse(load(p))
    chk("A1_ts_end_detected", a["ts_semantics"] in ("end", "either"))
    chk("A2_server_bound", a["verdict"] == "SERVER_BOUND")
    chk("A3_busy_frac_one", abs(a["busy_frac"] - 1.0) < 1e-6)
    chk("A4_ceiling_zero", a["h_cpu_explanatory_ceiling"] == 0.0)

    # B: client-gap bound -- 1s requests, 20s apart
    p = os.path.join(td, "b.jsonl")
    _write(p, [_call(1000 + i * 20000, 1000) for i in range(20)])
    b = analyse(load(p))
    chk("B1_client_gap_bound", b["verdict"] == "CLIENT_GAP_BOUND")
    chk("B2_ceiling_high", b["h_cpu_explanatory_ceiling"] > 0.9)
    chk("B3_gap_median", abs(b["idle_gap_ms"]["median"] - 19000) < 1)

    # C: mixed
    p = os.path.join(td, "c.jsonl")
    _write(p, [_call(1000 + i * 20000, 10000) for i in range(20)])
    chk("C1_mixed", analyse(load(p))["verdict"] == "MIXED")

    # D: gross concurrency -> MODEL_INVALID via the pigeonhole test
    p = os.path.join(td, "d.jsonl")
    _write(p, [_call(1000 + i * 1000, 50000) for i in range(20)])
    d = analyse(load(p))
    chk("D1_model_invalid", d["verdict"] == "MODEL_INVALID")
    chk("D2_names_refutation", "REFUTE_3" in d.get("reason", ""))
    chk("D3_not_server_bound", d["verdict"] != "SERVER_BOUND")
    chk("D4_slack_negative", d["serial_slack_ms"] < 0)

    # E: bad latency > 5% -> UNRESOLVED (refutation cond 2)
    p = os.path.join(td, "e.jsonl")
    recs = [_call(1000 + i * 10000, 5000) for i in range(20)]
    for i in (0, 1, 2):
        recs[i]["latency_ms"] = 0
    e = analyse(load_write(p, recs))
    chk("E1_unresolved", e["verdict"] == "UNRESOLVED")
    chk("E2_names_refutation", "REFUTE_2" in e.get("reason", ""))

    # F: mild overlap the pigeonhole test is too coarse to see, but which makes
    #    BOTH ts readings produce a negative gap -> REFUTE_1 (the two guards
    #    catch different scales; neither subsumes the other)
    p = os.path.join(td, "f.jsonl")
    f = analyse(load_write(p, [_call(0, 100), _call(50, 100), _call(10000, 100)]))
    chk("F1_ts_unresolved", f["verdict"] == "UNRESOLVED")
    chk("F2_names_refutation", "REFUTE_1" in f.get("reason", ""))
    chk("F3_pigeonhole_missed_it", f["serial_slack_ms"] >= 0)

    # G: thin census window must be UNSCANNED, never "no effect"
    p = os.path.join(td, "g.jsonl")
    recs = [_call(1000 + i * 10000, 5000) for i in range(40)]
    g = analyse(load_write(p, recs), census_window=(1000, 30000))
    chk("G1_window_unscanned", g["p2"]["verdict"] == "UNSCANNED")
    chk("G2_unscanned_is_named", "NOT evidence" in g["p2"].get("reason", ""))

    # H: thin hourly buckets excluded and named; too few buckets -> UNSCANNED
    p = os.path.join(td, "h.jsonl")
    h = analyse(load_write(p, [_call(1000 + i * 10000, 5000) for i in range(20)]))
    chk("H1_p1_unscanned", h["p1"]["verdict"] == "UNSCANNED")

    # I: 5 fat hourly buckets, flat speed -> ENDPOINT_FLAT
    recs, t = [], 1000
    for hr in range(5):
        for i in range(12):
            recs.append(_call(t + hr * 3600000 + i * 60000, 5000, tok=100))
    p = os.path.join(td, "i.jsonl")
    i_ = analyse(load_write(p, recs))
    chk("I1_flat", i_["p1"]["verdict"] == "ENDPOINT_FLAT")
    chk("I2_five_buckets", len(i_["hourly"]) == 5)

    # J: same shape but last 2 buckets 3x slower per token -> DEGRADING
    recs = []
    for hr in range(5):
        for i in range(12):
            lat = 15000 if hr >= 3 else 5000
            recs.append(_call(1000 + hr * 3600000 + i * 60000, lat, tok=100))
    p = os.path.join(td, "j.jsonl")
    j = analyse(load_write(p, recs))
    chk("J1_degrading", j["p1"]["verdict"] == "ENDPOINT_DEGRADING")
    chk("J2_ratio_3x", abs(j["p1"]["ratio"] - 3.0) < 0.01)

    # K: token-less calls are excluded but counted, never silently dropped
    recs = [_call(1000 + i * 10000, 5000, tok=None if i < 4 else 100) for i in range(20)]
    p = os.path.join(td, "k.jsonl")
    k = analyse(load_write(p, recs))
    chk("K1_excluded_counted", k["n_excluded_no_tokens"] == 4)
    chk("K2_samples_right", k["n_speed_samples"] == 16)
    chk("K3_busy_uses_all", k["busy_ms"] == 20 * 5000)

    # L: not-ok calls counted separately
    recs = [_call(1000 + i * 10000, 5000, ok=(i > 2)) for i in range(20)]
    p = os.path.join(td, "l.jsonl")
    chk("L1_not_ok_counted", analyse(load_write(p, recs))["n_not_ok"] == 3)

    # M: blank lines and unordered input tolerated
    p = os.path.join(td, "m.jsonl")
    recs = [_call(1000 + i * 10000, 10000) for i in range(20)][::-1]
    with open(p, "w") as fh:
        for r in recs:
            fh.write(json.dumps(r) + "\n\n")
    m = analyse(load(p))
    chk("M1_sorted_ok", m["verdict"] == "SERVER_BOUND")
    chk("M2_all_kept", m["n_calls"] == 20)

    # N: a THIN tail bucket that is wildly slow must NOT be able to manufacture
    #    an ENDPOINT_DEGRADING verdict (this is what excluding thin buckets buys)
    recs = []
    for hr in range(4):
        for i in range(12):
            recs.append(_call(1000 + hr * 3600000 + i * 60000, 5000, tok=100))
    for i in range(3):                       # 5th hour: 3 calls, 10x slower
        recs.append(_call(1000 + 4 * 3600000 + i * 60000, 50000, tok=100))
    p = os.path.join(td, "n.jsonl")
    n_ = safe(load_write(p, recs))
    chk("N1_thin_tail_excluded", n_["p1"]["verdict"] == "ENDPOINT_FLAT")
    chk("N2_thin_named", n_["thin_buckets"] == [4])
    chk("N3_thin_still_reported", any(b.get("thin") for b in n_["hourly"]))

    # O: ts_ms marks call START (end-reading goes negative). Exercises the
    #    start branch of wall, which no other fixture reaches.
    p = os.path.join(td, "o.jsonl")
    o = safe(load_write(p, [_call(0, 1000), _call(15000, 20000), _call(40000, 39000)]))
    chk("O1_start_semantics", o.get("ts_semantics") == "start")
    chk("O2_wall_is_first_start_to_last_end", o.get("wall_ms") == 79000)
    chk("O3_server_bound", o["verdict"] == "SERVER_BOUND")
    chk("O4_no_exception", o["verdict"] != "EXCEPTION")

    ok = not fails
    print(f"selftest {'SELFTEST_PASS' if ok else 'SELFTEST_FAIL'} {len(res)-len(fails)}/{len(res)}"
          + ("" if ok else f"  failed={fails}"))
    return 0 if ok else 1


def load_write(path, recs):
    _write(path, recs)
    return load(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run")
    ap.add_argument("--census-artifact")
    ap.add_argument("--census-elapsed-s", type=float)
    ap.add_argument("--json")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.run:
        ap.error("--run required")
    win = None
    if a.census_artifact and a.census_elapsed_s:
        hi = int(os.path.getmtime(a.census_artifact) * 1000)
        win = (int(hi - a.census_elapsed_s * 1000), hi)
    out = analyse(load(os.path.join(a.run, "calls.jsonl")), census_window=win)
    out["run"] = a.run
    print(json.dumps(out, indent=2))
    if a.json:
        with open(a.json, "w") as fh:
            json.dump(out, fh, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
