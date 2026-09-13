#!/usr/bin/env python3
"""R485: which stratum owns the heavy generation tail -- persona / arm / task.

Read-only. Zero API calls. Criteria live in
DECISION_20260905_R485_RUNAWAY_GENERATION_STRATA_PREREG.md and are mirrored as
the constants below; the prereg is the arbiter if they ever disagree.

Mutants are read INSIDE the functions under test (a module-level read would be
empty at import time and would look exactly like a toothless gauge).
"""
import argparse, json, os, random, statistics, sys

# --- contract constants pinned in the prereg (section 3/4) ---------------
RUNAWAY_FRAC = 0.5          # RUNAWAY: latency >= 0.5 * timeout_s * 1000
TIMEOUT_FRAC = 0.98         # TIMEOUT_HIT: latency >= 0.98 * timeout_s * 1000
CR_HI = 1.50                # >= HI  => CONCENTRATED
CR_LO = 1.25                # <  LO  => FLAT
TOP_K = 5                   # P-3 uses the top-5 tasks by summed latency
TASK_HI_MULT = 3.0          # P-3 CONCENTRATED at >= 3x the uniform null
TASK_LO_MULT = 1.5          # P-3 FLAT below 1.5x the uniform null
PERM_ITERS = 2000           # P-4 permutation iterations
MIN_TASKS = 20              # refutation cond 4
MIN_RUNAWAY_TASKS = 5       # refutation cond 5
SHARE_TOL = 1e-9            # refutation cond 2


def _mut():
    """Mutant flag, read at call time -- never at import time."""
    return os.environ.get("R485_MUTANT", "")


def load_calls(path):
    """Parse raw JSONL exactly as it sits on disk. No schema massaging."""
    out = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def gen_calls(calls):
    """Population = role 'gen'. preflight is excluded (different timeout_s)."""
    if _mut() == "M5_KEEP_PREFLIGHT":
        return list(calls)
    return [c for c in calls if c.get("role") == "gen"]


def _lat(c):
    return c.get("latency_ms") or 0


def is_runaway(c):
    t = c.get("timeout_s")
    if not t:
        return False
    frac = 0.05 if _mut() == "M2_RUNAWAY_FRAC" else RUNAWAY_FRAC
    return _lat(c) >= frac * t * 1000


def is_timeout_hit(c):
    t = c.get("timeout_s")
    return bool(t) and _lat(c) >= TIMEOUT_FRAC * t * 1000


def strata(calls, keyfn):
    """share_calls / share_time / CR per stratum. Shares must sum to 1."""
    tot_n = len(calls)
    tot_t = sum(_lat(c) for c in calls)
    buckets = {}
    for c in calls:
        buckets.setdefault(keyfn(c), []).append(c)
    keys = sorted(buckets)
    if _mut() == "M6_DROP_LAST_STRATUM" and len(keys) > 1:
        keys = keys[:-1]
    out = {}
    for k in keys:
        b = buckets[k]
        sc = len(b) / tot_n if tot_n else 0.0
        if _mut() == "M1_TIME_SHARE_IS_COUNT_SHARE":
            st = sc
        else:
            st = (sum(_lat(c) for c in b) / tot_t) if tot_t else 0.0
        out[k] = {
            "n": len(b),
            "sum_latency_ms": sum(_lat(c) for c in b),
            "share_calls": sc,
            "share_time": st,
            "cr": (st / sc) if sc else None,
            "n_runaway": sum(1 for c in b if is_runaway(c)),
            "n_timeout_hit": sum(1 for c in b if is_timeout_hit(c)),
        }
    return out


def cr_verdict(st, min_n_per_cell):
    """Three-way verdict on max CR, with the empty/thin-cell guards."""
    if not st:
        return "UNSCANNED", None
    thin = [k for k, v in st.items() if v["n"] < min_n_per_cell]
    if thin:
        return "UNSCANNED", None
    mx = max(v["cr"] for v in st.values() if v["cr"] is not None)
    if mx >= CR_HI:
        return "CONCENTRATED", mx
    if mx < CR_LO:
        return "FLAT", mx
    return "UNRESOLVED", mx


def top_task_share(calls):
    """P-3: top-K tasks by summed latency vs the uniform null K/N."""
    st = strata(calls, lambda c: (c.get("meta") or {}).get("task_id"))
    n_tasks = len(st)
    k = 1 if _mut() == "M7_TOPK_IS_TOP1" else TOP_K
    ranked = sorted(st.items(), key=lambda kv: -kv[1]["sum_latency_ms"])[:k]
    obs = sum(v["share_time"] for _, v in ranked)
    null = (k / n_tasks) if n_tasks else None
    if n_tasks < MIN_TASKS:
        verdict = "UNRESOLVED"
    elif obs >= TASK_HI_MULT * null:
        verdict = "TASK_CONCENTRATED"
    elif obs < TASK_LO_MULT * null:
        verdict = "TASK_FLAT"
    else:
        verdict = "UNRESOLVED"
    return {
        "n_tasks": n_tasks, "k": k, "top_share": obs, "uniform_null": null,
        "ratio": (obs / null) if null else None, "verdict": verdict,
        "top_tasks": [(t, v["sum_latency_ms"], v["n"]) for t, v in ranked],
    }


def multiarm_fraction(calls, arms=None):
    """P-4 statistic: of tasks with >=1 RUNAWAY, the fraction whose RUNAWAY
    calls span >=2 distinct arms."""
    if arms is None:
        arms = [(c.get("meta") or {}).get("arm") for c in calls]
    by_task = {}
    for c, a in zip(calls, arms):
        if is_runaway(c):
            by_task.setdefault((c.get("meta") or {}).get("task_id"), set()).add(a)
    if not by_task:
        return None, 0
    span = sum(1 for s in by_task.values() if len(s) >= 2)
    return span / len(by_task), len(by_task)


def perm_null(calls, iters, seed, within_task=False):
    """Null: reshuffle the arm labels. Global (prereg arbiter) or within-task
    (post-hoc sensitivity, NOT in the prediction ledger)."""
    rng = random.Random(seed)
    base = [(c.get("meta") or {}).get("arm") for c in calls]
    idx_by_task = {}
    for i, c in enumerate(calls):
        idx_by_task.setdefault((c.get("meta") or {}).get("task_id"), []).append(i)
    out = []
    for _ in range(iters):
        if _mut() == "M3_PERM_IS_IDENTITY":
            shuf = list(base)
        elif within_task:
            shuf = list(base)
            for idxs in idx_by_task.values():
                vals = [base[i] for i in idxs]
                rng.shuffle(vals)
                for i, v in zip(idxs, vals):
                    shuf[i] = v
        else:
            shuf = list(base)
            rng.shuffle(shuf)
        f, _n = multiarm_fraction(calls, shuf)
        if f is not None:
            out.append(f)
    return out


def pctl(xs, q):
    if not xs:
        return None
    s = sorted(xs)
    i = min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))
    return s[i]


def retry_verdict(calls):
    """P-5 (guard): does a retry land as its own line?"""
    atts = [c.get("attempt") for c in calls if c.get("attempt") is not None]
    mx = max(atts) if atts else None
    thresh_ok = (mx is not None and mx >= 1) if _mut() == "M4_ATTEMPT_GE1" \
        else (mx is not None and mx > 1)
    return ("RETRIES_LOGGED" if thresh_ok else "RETRIES_NOT_LOGGED"), mx


def analyze(path, seed=485, iters=PERM_ITERS):
    raw = load_calls(path)
    calls = gen_calls(raw)
    ev = {"path": path, "n_raw": len(raw), "n_gen": len(calls),
          "broken": [], "unscanned": []}

    per = strata(calls, lambda c: c.get("agent_id"))
    arm = strata(calls, lambda c: (c.get("meta") or {}).get("arm"))
    for name, st in (("persona", per), ("arm", arm)):
        s = sum(v["share_time"] for v in st.values())
        if abs(s - 1.0) > SHARE_TOL:
            ev["broken"].append(f"REFUT2_SHARE_SUM_{name}={s!r}")
        s2 = sum(v["share_calls"] for v in st.values())
        if abs(s2 - 1.0) > SHARE_TOL:
            ev["broken"].append(f"REFUT2_CALLSHARE_SUM_{name}={s2!r}")
        if any(v["n"] == 0 for v in st.values()):
            ev["unscanned"].append(name)

    ev["persona"] = per
    ev["arm"] = arm
    ev["P1_verdict"], ev["P1_max_cr"] = cr_verdict(per, 30)
    ev["P2_verdict"], ev["P2_max_cr"] = cr_verdict(arm, 100)
    ev["P3"] = top_task_share(calls)

    f_obs, n_rt = multiarm_fraction(calls)
    ev["P4_f_obs"], ev["P4_n_runaway_tasks"] = f_obs, n_rt
    ev["n_runaway"] = sum(1 for c in calls if is_runaway(c))
    ev["n_timeout_hit"] = sum(1 for c in calls if is_timeout_hit(c))
    n_tasks = ev["P3"]["n_tasks"]
    if n_tasks < MIN_TASKS:
        ev["P4_verdict"] = "UNRESOLVED"
        ev["P4_reason"] = f"REFUT4_n_tasks={n_tasks}<{MIN_TASKS}"
    elif n_rt < MIN_RUNAWAY_TASKS:
        ev["P4_verdict"] = "UNRESOLVED"
        ev["P4_reason"] = f"REFUT5_n_runaway_tasks={n_rt}<{MIN_RUNAWAY_TASKS}"
    else:
        null = perm_null(calls, iters, seed)
        ev["P4_null_p50"], ev["P4_null_p95"] = pctl(null, 0.50), pctl(null, 0.95)
        ev["P4_null_n"] = len(null)
        if f_obs > ev["P4_null_p95"]:
            ev["P4_verdict"] = "TASK_INTRINSIC"
        elif f_obs < ev["P4_null_p50"]:
            ev["P4_verdict"] = "NOT_TASK_INTRINSIC"
        else:
            ev["P4_verdict"] = "UNRESOLVED"
        wnull = perm_null(calls, iters, seed, within_task=True)
        ev["posthoc_within_task_null_p50"] = pctl(wnull, 0.50)
        ev["posthoc_within_task_null_p95"] = pctl(wnull, 0.95)

    ev["P5_verdict"], ev["P5_max_attempt"] = retry_verdict(calls)
    ev["n_not_ok"] = sum(1 for c in calls if not c.get("ok"))
    lats = [_lat(c) for c in calls]
    toks = [((c.get("usage") or {}).get("completion_tokens") or 0) for c in calls]
    ev["latency_ms_p50"] = statistics.median(lats) if lats else None
    ev["latency_ms_max"] = max(lats) if lats else None
    ev["completion_tokens_max"] = max(toks) if toks else None
    return ev


# ---------------------------------------------------------------- selftest
def _fixture(spec):
    """Fixtures are built here from literal dicts. They deliberately do NOT
    call gen_calls/strata/is_runaway -- a fixture derived from the module
    under test cannot see that module's own bugs."""
    return [dict(role="gen", agent_id=a, attempt=at, ok=True, timeout_s=600,
                 latency_ms=lat, usage={"completion_tokens": 10},
                 meta={"arm": arm, "task_id": t})
            for (a, arm, t, lat, at) in spec]


def _contract_constants():
    """Read the pinned constants back out of this file's own source text."""
    import ast
    src = open(__file__).read()
    tree = ast.parse(src)
    got = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name.isupper():
                try:
                    got[name] = ast.literal_eval(node.value)
                except Exception:
                    pass
    return got


def selftest():
    res = []

    def ck(name, cond, detail=""):
        res.append((name, bool(cond), detail))

    # -- contract constants match the prereg table (verbatim from source) --
    cc = _contract_constants()
    for k, want in [("RUNAWAY_FRAC", 0.5), ("TIMEOUT_FRAC", 0.98),
                    ("CR_HI", 1.50), ("CR_LO", 1.25), ("TOP_K", 5),
                    ("TASK_HI_MULT", 3.0), ("TASK_LO_MULT", 1.5),
                    ("PERM_ITERS", 2000), ("MIN_TASKS", 20),
                    ("MIN_RUNAWAY_TASKS", 5)]:
        ck(f"contract:{k}", cc.get(k) == want, f"{cc.get(k)} vs {want}")

    # -- F1 flat personas: every CR is exactly 1.0 -------------------------
    f1 = _fixture([(f"p{i%3}", f"A{i%3}", f"t{i//3}", 1000, 1)
                   for i in range(90)])
    s1 = strata(f1, lambda c: c["agent_id"])
    ck("F1_flat_cr", all(abs(v["cr"] - 1.0) < 1e-12 for v in s1.values()),
       str({k: v["cr"] for k, v in s1.items()}))
    ck("F1_share_sums", abs(sum(v["share_time"] for v in s1.values()) - 1.0) < 1e-12)
    ck("F1_verdict", cr_verdict(s1, 30)[0] == "FLAT", str(cr_verdict(s1, 30)))

    # -- F2 one persona 10x slower: CR >= 1.50 -----------------------------
    f2 = _fixture([(f"p{i%3}", f"A{i%3}", f"t{i//3}",
                    10000 if i % 3 == 0 else 1000, 1) for i in range(90)])
    s2 = strata(f2, lambda c: c["agent_id"])
    ck("F2_verdict", cr_verdict(s2, 30)[0] == "CONCENTRATED", str(cr_verdict(s2, 30)))
    # 30 calls @10000ms + 60 @1000ms => total 360000; p0 share_time=300000/360000
    ck("F2_max_cr", abs(cr_verdict(s2, 30)[1] - (300000 / 360000) / (1 / 3)) < 1e-9,
       str(cr_verdict(s2, 30)[1]))

    # -- F3 thin cell must be UNSCANNED, never FLAT ------------------------
    f3 = _fixture([("p0", "A", f"t{i}", 1000, 1) for i in range(5)])
    ck("F3_thin_unscanned", cr_verdict(strata(f3, lambda c: c["agent_id"]), 30)[0]
       == "UNSCANNED")

    # -- F4 runaway is a task property: spans both arms every time ---------
    f4 = _fixture([("p0", "A" if i % 2 else "B", f"t{i//2}",
                    400000 if i // 2 < 10 else 1000, 1) for i in range(60)])
    fo, nrt = multiarm_fraction(f4)
    ck("F4_f_obs_is_1", fo == 1.0 and nrt == 10, f"{fo} {nrt}")
    nl = perm_null(f4, 300, 4)
    ck("F4_beats_null", fo > pctl(nl, 0.95), f"obs={fo} p95={pctl(nl,0.95)}")

    # -- F5 runaway concentrated in ONE arm: must not read as task-intrinsic
    f5 = _fixture([("p0", "A" if i % 2 else "B", f"t{i//2}",
                    400000 if (i % 2 == 0 and i // 2 < 10) else 1000, 1)
                   for i in range(60)])
    fo5, _ = multiarm_fraction(f5)
    ck("F5_f_obs_is_0", fo5 == 0.0, str(fo5))
    ck("F5_not_above_null", not (fo5 > pctl(perm_null(f5, 300, 5), 0.95)))

    # -- F6 retry logging, both directions ---------------------------------
    ck("F6_not_logged", retry_verdict(_fixture([("p", "A", "t", 1, 1)]))[0]
       == "RETRIES_NOT_LOGGED")
    ck("F6_logged", retry_verdict(_fixture([("p", "A", "t", 1, 2)]))[0]
       == "RETRIES_LOGGED")

    # -- F7 too few tasks => P-3 UNRESOLVED (refutation cond 4) ------------
    f7 = _fixture([("p", "A", f"t{i%4}", 1000 * (10 if i % 4 == 0 else 1), 1)
                   for i in range(40)])
    ck("F7_few_tasks_unresolved", top_task_share(f7)["verdict"] == "UNRESOLVED",
       str(top_task_share(f7)))

    # -- F8 task concentration, both directions ----------------------------
    f8c = _fixture([("p", "A", f"t{i}", 100000 if i < 5 else 100, 1)
                    for i in range(50)])
    ck("F8_concentrated", top_task_share(f8c)["verdict"] == "TASK_CONCENTRATED",
       str(top_task_share(f8c)["ratio"]))
    f8f = _fixture([("p", "A", f"t{i}", 1000, 1) for i in range(50)])
    ck("F8_flat", top_task_share(f8f)["verdict"] == "TASK_FLAT",
       str(top_task_share(f8f)["ratio"]))

    # -- F12 top-K really is K=5 (the fixture that can see M7) -------------
    #    ratio_k = (sum of top-k share) * (N/k) is monotonically NON-increasing
    #    in k, so top-1 can only ever be >= top-5.  The discriminating direction
    #    is therefore FLAT: 50 tasks, one at 4000ms and 49 at 2000ms gives
    #    ratio_5 = 1.176 (FLAT) but ratio_1 = 1.961 (UNRESOLVED).
    f12 = _fixture([("p", "A", f"t{i}", 4000 if i == 0 else 2000, 1)
                    for i in range(50)])
    _T = 4000 + 49 * 2000
    ck("F12_fixture_discriminates", (50 * 4000 / _T) >= 1.5
       and (10 * (4000 + 4 * 2000) / _T) < 1.5,
       f"r1={50*4000/_T:.3f} r5={10*(4000+4*2000)/_T:.3f}")
    ck("F12_topk_is_5", top_task_share(f12)["verdict"] == "TASK_FLAT",
       str(top_task_share(f12)))

    # -- F9 preflight must be excluded from the population -----------------
    f9 = _fixture([("p0", "A", f"t{i}", 1000, 1) for i in range(30)])
    f9 = f9 + [dict(role="preflight", agent_id="preflight", attempt=1, ok=True,
                    timeout_s=120, latency_ms=99999999, usage={}, meta={})]
    ck("F9_preflight_excluded", len(gen_calls(f9)) == 30, str(len(gen_calls(f9))))
    ck("F9_preflight_no_time", sum(_lat(c) for c in gen_calls(f9)) == 30000)

    # -- F10 runaway threshold is derived from timeout_s, not a constant ---
    ck("F10_runaway_lo", not is_runaway(dict(timeout_s=600, latency_ms=299999)))
    ck("F10_runaway_hi", is_runaway(dict(timeout_s=600, latency_ms=300000)))
    ck("F10_timeout_hit", is_timeout_hit(dict(timeout_s=600, latency_ms=588000)))
    ck("F10_timeout_miss", not is_timeout_hit(dict(timeout_s=600, latency_ms=587999)))

    # -- F11 the share-sum guard actually fires when shares are truncated --
    #    (negative control for refutation condition 2)
    truncated = dict(list(s1.items())[:-1])
    ck("F11_guard_sees_truncation",
       abs(sum(v["share_time"] for v in truncated.values()) - 1.0) > SHARE_TOL)

    return res


def _run_selftest():
    res = selftest()
    bad = [r for r in res if not r[1]]
    for n, ok, d in res:
        if not ok:
            print(f"  FAIL {n}: {d}")
    print(f"selftest {len(res)-len(bad)}/{len(res)} passed"
          f"{' MUTANT=' + _mut() if _mut() else ''}")
    return 0 if not bad else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--calls")
    ap.add_argument("--json")
    ap.add_argument("--seed", type=int, default=485)
    ap.add_argument("--iters", type=int, default=PERM_ITERS)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(_run_selftest())
    if not a.calls:
        ap.error("--calls required")
    ev = analyze(a.calls, seed=a.seed, iters=a.iters)
    if a.json:
        with open(a.json, "w") as fh:
            json.dump(ev, fh, indent=2, ensure_ascii=False, default=str)
    print(json.dumps({k: v for k, v in ev.items()
                      if k not in ("persona", "arm")},
                     indent=2, ensure_ascii=False, default=str))
    for name in ("persona", "arm"):
        print(f"\n--- {name} ---")
        for k, v in sorted(ev[name].items(), key=lambda kv: -(kv[1]["cr"] or 0)):
            print(f"  {str(k):12s} n={v['n']:4d} share_calls={v['share_calls']:.4f} "
                  f"share_time={v['share_time']:.4f} CR={v['cr']:.3f} "
                  f"runaway={v['n_runaway']} timeout_hit={v['n_timeout_hit']}")
    sys.exit(2 if ev["broken"] else 0)


if __name__ == "__main__":
    main()
