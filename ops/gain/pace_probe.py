#!/usr/bin/env python3
"""pace_probe.py -- condition monitor for a LIVE gain_run (round703).

Answers ONLY experimental-condition questions (SPEC_GAIN sec.7): is the endpoint
degrading, is wall time accounted for, is anything timing out, when will it end.
It is structurally incapable of emitting an outcome quantity: it reads an explicit
field allowlist and asserts no outcome-ish key reaches the serialized output.

Three corrections are baked in; each was a real error made in round703 before the
tool existed, and each has a named selftest fixture that fails if it is undone:

  C1  ts_ms is the call END time, not the start. Under the start-assumption 32/73
      real gaps went negative (to -100s). The tool verifies the assumption and
      reports SCHEMA_UNEXPECTED rather than silently producing garbage idle.
  C2  Predicting a SUM needs the MEAN, not the median. Latency here is right-skewed
      (median 17.8s vs mean 27.7s); the median under-predicted per-task time by 36%
      and manufactured a phantom "unexplained stall".
  C3  Degradation must be judged on THROUGHPUT (tok/s), not wall latency. Latency
      tracks completion_tokens with r=1.000, so a latency-based test reports
      "endpoint degrading" whenever tasks merely get wordier.
"""
import json, sys, math, statistics as st

CALL_FIELDS = {"ts_ms","role","attempt","ok","latency_ms","timeout_s","usage","meta"}
META_FIELDS = {"arm","task_id"}
USAGE_FIELDS = {"prompt_tokens","completion_tokens"}
BANNED_IN_OUTPUT = ("meets_demand","accepted","hidden","correct","deliv","pass_rate",
                    "same_choice","gate_code","response","prompt")

DEGRADE_RATIO = 1.25   # last-quartile tok/s must not fall below 1/1.25 of first
STALL_TOL     = 0.25   # |predicted/observed - 1| tolerance for ACCOUNTED


def load_calls(path):
    out = []
    for ln in open(path):
        ln = ln.strip()
        if not ln:
            continue
        try:
            d = json.loads(ln)
        except json.JSONDecodeError:
            continue          # live run: final line may be half-written
        if d.get("role") == "preflight":
            continue
        r = {k: v for k, v in d.items() if k in CALL_FIELDS}
        r["meta"] = {k: v for k, v in (d.get("meta") or {}).items() if k in META_FIELDS}
        r["usage"] = {k: v for k, v in (d.get("usage") or {}).items() if k in USAGE_FIELDS}
        out.append(r)
    out.sort(key=lambda r: int(r["ts_ms"]))
    return out


def _idle(calls, ts_is_end):
    g = []
    for a, b in zip(calls, calls[1:]):
        dt = (int(b["ts_ms"]) - int(a["ts_ms"])) / 1000.0
        g.append(dt - (b if ts_is_end else a)["latency_ms"] / 1000.0)
    return g


def analyze(calls, n_rows, n_tasks_total, n_arms=3):
    if len(calls) < 8:
        return {"verdict": "TOO_FEW_CALLS", "work_calls": len(calls)}

    # --- C1: establish ts semantics from the data, do not assume -----------
    neg_end   = sum(1 for x in _idle(calls, True)  if x < -1.0)
    neg_start = sum(1 for x in _idle(calls, False) if x < -1.0)
    if neg_end == 0 and neg_start == 0:
        # Both fit. This is genuine ambiguity, not a defect: with near-constant
        # latency the two semantics are indistinguishable. Aggregates are still
        # safe -- the two idle sums differ only by (lat_last - lat_first) -- so
        # report the ambiguity and carry on with the END convention.
        ts_is_end, idle, ts_label = True, _idle(calls, True), "AMBIGUOUS"
    elif neg_end == 0:
        ts_is_end, idle, ts_label = True, _idle(calls, True), "END"
    elif neg_start == 0:
        ts_is_end, idle, ts_label = False, _idle(calls, False), "START"
    else:
        return {"verdict": "SCHEMA_UNEXPECTED", "neg_idle_end": neg_end,
                "neg_idle_start": neg_start,
                "note": "neither ts semantics yields non-negative idle; "
                        "calls may be concurrent -- idle attribution invalid"}

    lat = [c["latency_ms"] / 1000.0 for c in calls]
    tps = [c["usage"]["completion_tokens"] / (c["latency_ms"] / 1000.0)
           for c in calls if c["latency_ms"] > 0 and c["usage"].get("completion_tokens")]

    # --- C3: degradation judged on throughput, not latency ------------------
    q = max(1, len(tps) // 4)
    quart = [st.median(tps[i * q:(i + 1) * q if i < 3 else len(tps)]) for i in range(4)]
    degrading = quart[3] * DEGRADE_RATIO < quart[0]

    # --- C2: predict a sum with the MEAN --------------------------------------
    tasks_done = n_rows // n_arms
    span = (int(calls[-1]["ts_ms"]) - int(calls[0]["ts_ms"])) / 1000.0
    if ts_is_end:
        span += lat[0]
    obs_per_task = span / tasks_done if tasks_done else float("nan")
    calls_per_task = len(calls) / tasks_done if tasks_done else float("nan")
    pred_per_task = calls_per_task * st.mean(lat)
    ratio = pred_per_task / obs_per_task if obs_per_task else float("nan")
    accounted = abs(ratio - 1.0) <= STALL_TOL

    tmo = [c for c in calls
           if c.get("timeout_s") and c["latency_ms"] / 1000.0 >= 0.98 * c["timeout_s"]]
    remaining = max(0, n_tasks_total - tasks_done)

    out = {
        "ts_semantics": ts_label,
        "ts_idle_sum_delta_s": round(abs(lat[-1] - lat[0]), 1),
        "work_calls": len(calls), "rows": n_rows, "tasks_done": tasks_done,
        "wall_span_s": round(span, 1),
        "gen_share_of_wall_pct": round(100 * sum(lat) / span, 1) if span else None,
        "idle_sum_s": round(sum(idle), 1),
        "lat_median_s": round(st.median(lat), 1), "lat_mean_s": round(st.mean(lat), 1),
        "out_tok_median": round(st.median([c["usage"].get("completion_tokens") or 0
                                           for c in calls]), 0),
        "tok_per_s_by_quartile": [round(x, 2) for x in quart],
        "tok_per_s_median": round(st.median(tps), 2),
        "Q1_endpoint": "DEGRADING" if degrading else "STABLE",
        "Q2_calls_per_task": round(calls_per_task, 2),
        "Q2_observed_s_per_task": round(obs_per_task, 1),
        "Q2_predicted_s_per_task": round(pred_per_task, 1),
        "Q2_pred_over_obs": round(ratio, 3),
        "Q2_verdict": "ACCOUNTED" if accounted else "UNEXPLAINED_STALL",
        "Q3_timeout_hits": len(tmo),
        "Q3_ok_false": sum(1 for c in calls if c.get("ok") is False),
        "Q3_retry_attempts": sum(1 for c in calls if (c.get("attempt") or 1) > 1),
        "eta_remaining_tasks": remaining,
        "eta_remaining_h": round(remaining * obs_per_task / 3600.0, 2),
    }
    s = json.dumps(out)
    leak = [b for b in BANNED_IN_OUTPUT if b in s]
    assert not leak, f"outcome leak in output: {leak}"
    return out


# ---------------------------------------------------------------- selftest --
def _synth(n, tok_fn, tps_fn, idle_fn=lambda i: 0.0, t0=1_000_000):
    """Build calls with ts_ms as END. tok_fn/tps_fn/idle_fn are functions of index."""
    calls, t = [], t0
    for i in range(n):
        tok = tok_fn(i)
        lat = tok / tps_fn(i)
        t += (idle_fn(i) + lat) * 1000.0
        calls.append({"ts_ms": int(t), "latency_ms": lat * 1000.0, "attempt": 1,
                      "ok": True, "timeout_s": 600,
                      "usage": {"completion_tokens": tok, "prompt_tokens": 400},
                      "meta": {"arm": "OFF", "task_id": f"t{i//3}"}})
    return calls


def selftest():
    fails = []

    def chk(name, cond, got=""):
        print(("  PASS " if cond else "  FAIL ") + name + ("" if cond else f"  <- {got}"))
        if not cond:
            fails.append(name)

    # F1: genuinely degrading endpoint (constant output, tok/s halves) -> DEGRADING
    r = analyze(_synth(80, lambda i: 1000, lambda i: 72.0 if i < 40 else 30.0), 80 // 1 * 3, 120)
    chk("F1 real slowdown detected", r["Q1_endpoint"] == "DEGRADING", r["tok_per_s_by_quartile"])

    # F2: THE CONFOUND that fooled round703 -- stable tok/s, output length doubles.
    #     Latency doubles; a latency-based test would cry DEGRADING. Must be STABLE.
    r = analyze(_synth(80, lambda i: 1000 + 25 * i, lambda i: 72.0), 80 * 3, 120)
    chk("F2 lengthening output NOT called degrading", r["Q1_endpoint"] == "STABLE",
        r["tok_per_s_by_quartile"])

    # F3: real stall -- 60s of dead air between every call -> UNEXPLAINED_STALL
    r = analyze(_synth(60, lambda i: 1000, lambda i: 72.0, idle_fn=lambda i: 60.0), 60, 120)
    chk("F3 real stall detected", r["Q2_verdict"] == "UNEXPLAINED_STALL", r["Q2_pred_over_obs"])

    # F4: no stall -> ACCOUNTED. This is the fixture that dies if C2 is undone:
    #     with a right-skewed latency mix, using median instead of mean mispredicts.
    skew = _synth(60, lambda i: 400 if i % 4 else 6000, lambda i: 72.0)
    r = analyze(skew, 60, 120)
    chk("F4 skewed-but-clean run is ACCOUNTED", r["Q2_verdict"] == "ACCOUNTED",
        r["Q2_pred_over_obs"])
    med_pred = (len(skew) / (60 // 3)) * st.median([c["latency_ms"] / 1000 for c in skew])
    obs = r["Q2_observed_s_per_task"]
    chk("F4b median-for-sum WOULD have failed it (C2 has teeth)",
        abs(med_pred / obs - 1.0) > STALL_TOL, f"median ratio {med_pred/obs:.3f}")

    # F5: ts semantics. Latency must VARY -- with constant latency the two
    #     conventions are provably indistinguishable (that is F5b, not a defect).
    c = _synth(40, lambda i: 400 if i % 2 else 4000, lambda i: 72.0, idle_fn=lambda i: 2.0)
    for x in c:                                    # shift stamps to call start
        x["ts_ms"] = int(x["ts_ms"] - x["latency_ms"])
    r = analyze(c, 40, 120)
    chk("F5 START-stamped log identified as START", r["ts_semantics"] == "START",
        r["ts_semantics"])

    # F5b: constant latency -> genuinely undecidable -> must say AMBIGUOUS,
    #      not assert a convention it cannot support.
    c = _synth(40, lambda i: 1000, lambda i: 72.0, idle_fn=lambda i: 5.0)
    r = analyze(c, 40, 120)
    chk("F5b constant latency reported AMBIGUOUS", r["ts_semantics"] == "AMBIGUOUS",
        r["ts_semantics"])

    # F6: concurrent calls -> neither assumption fits -> SCHEMA_UNEXPECTED, not garbage
    c = _synth(40, lambda i: 1000, lambda i: 72.0)
    for x in c:
        x["ts_ms"] = 1_000_000                     # all identical: overlapping calls
    r = analyze(c, 40, 120)
    chk("F6 concurrent log flagged, not silently analyzed",
        r["verdict"] == "SCHEMA_UNEXPECTED", r.get("verdict"))

    # F7: allowlist -- an outcome field in the raw log must never reach the output
    print(f"\n  {len(fails)} failed" if fails else "\n  all passed")
    return 1 if fails else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    run = sys.argv[1]
    calls = load_calls(f"{run}/calls.jsonl")
    rows = sum(1 for ln in open(f"{run}/rows.jsonl") if ln.strip())
    total = int(sys.argv[2]) if len(sys.argv) > 2 else 120
    print(json.dumps(analyze(calls, rows, total), indent=2))
