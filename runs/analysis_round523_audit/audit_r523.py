#!/usr/bin/env python3
"""R523 fable audit: third-path recomputation of the R522 A-curve.
Zero shared code with R518/R519/R522 (no exec/import of their files).
In-process reference execution with signal.alarm; own parser; own equality."""
import ast, collections, gzip, hashlib, io, json, math, pathlib, signal, contextlib
ROOT = pathlib.Path(__file__).resolve().parents[2]
RUNS = ROOT / "runs"; DS = ROOT / ".vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz"
HERE = pathlib.Path(__file__).parent
R522 = RUNS / "analysis_round522_acurve/votes_r522.jsonl"

ds = {"mbppplus_" + d["task_id"]: d for d in (json.loads(l) for l in gzip.open(DS, "rt"))}

def parse_claim(text):
    ta = ex = None
    for raw in text.splitlines():
        s = raw.lstrip()
        up = s.upper()
        if up.startswith("TEST_ARGS") and ":" in s and ta is None:
            ta = s.partition(":")[2].strip()
        elif up.startswith("EXPECTED") and ":" in s and ex is None:
            ex = s.partition(":")[2].strip()
    # NOTE: R519 takes the LAST occurrence (dict overwrite); we take FIRST -> difference will surface in C2
    if ta is None or ex is None or ta.upper() == "NONE" or ex.upper() == "NONE":
        return None
    try:
        a = ast.literal_eval(ta); e = ast.literal_eval(ex)
    except Exception:
        return None
    if not isinstance(a, (list, tuple)): return None
    return list(a), e

def eq_harness(x, y):
    if isinstance(x, (int, float)) and isinstance(y, (int, float)):
        return math.isclose(x, y, rel_tol=1e-9, abs_tol=1e-9)
    if isinstance(x, (list, tuple)) and isinstance(y, (list, tuple)):
        return len(x) == len(y) and all(eq_harness(p, q) for p, q in zip(x, y))
    if isinstance(x, dict) and isinstance(y, dict):
        return set(x) == set(y) and all(eq_harness(x[k], y[k]) for k in x)
    return x == y

class _TO(Exception): pass
def _alarm(*_): raise _TO()
signal.signal(signal.SIGALRM, _alarm)

fn_cache = {}
def run_ref(tid, args):
    d = ds[tid]
    if tid not in fn_cache:
        ns = {}
        with contextlib.redirect_stdout(io.StringIO()):
            exec(d["canonical_solution"], ns)
        fn_cache[tid] = ns[d["entry_point"]]
    signal.alarm(10)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            return None, fn_cache[tid](*args)
    except BaseException as e:
        return type(e).__name__, None
    finally:
        signal.alarm(0)

def first_nonempty(text):
    for ln in text.splitlines():
        if ln.strip(): return ln.strip()
    return ""

def wilson(k, n, z=1.959963985):
    if n == 0: return (0.0, 1.0)
    p = k/n; d = 1+z*z/n; c = (p+z*z/(2*n))/d; h = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return (max(0, c-h), min(1, c+h))

# rows for in_rows
rows = {}
def in_rows(run, arm, tid):
    if run not in rows:
        f = RUNS/run/"rows.jsonl"; s = set()
        if f.exists():
            for l in open(f):
                r = json.loads(l); s.add((r["arm"], r["task_id"]))
        rows[run] = s
    return (arm, tid) in rows[run]

votes = []
for rd in sorted(RUNS.iterdir()):
    f = rd/"calls.jsonl"
    if not f.exists(): continue
    for l in open(f):
        try: c = json.loads(l)
        except Exception: continue
        if c.get("role") != "review" or not c.get("ok"): continue
        m = c.get("meta") or {}
        model = c.get("model_configured") or c.get("model")
        resp = c.get("response") or ""
        v = {"run": rd.name, "arm": m.get("arm"), "task_id": m.get("task_id"), "agent_id": c.get("agent_id"),
             "model": model, "in_rows": in_rows(rd.name, m.get("arm"), m.get("task_id")),
             "vote_pass_fne": first_nonempty(resp).upper() == "VERDICT: PASS",
             "vote_pass_r522style": (resp.strip().splitlines() or [""])[0].strip().upper() == "VERDICT: PASS",
             "n_testargs_lines": sum(1 for ln in resp.splitlines() if ln.lstrip().upper().startswith("TEST_ARGS"))}
        pc = parse_claim(resp) if m.get("task_id") in ds else None
        v["parseable"] = pc is not None
        if pc:
            args, exp = pc
            exc, actual = run_ref(m["task_id"], args)
            v["ref_exc"] = exc; v["actual"] = repr(actual)[:200]; v["expected"] = repr(exp)[:200]
            v["harness"] = (exc is None) and eq_harness(actual, exp)
        votes.append(v)

with open(HERE/"votes_r523.jsonl", "w") as fh:
    for v in votes: fh.write(json.dumps(v, ensure_ascii=False)+"\n")

G, Q = "gemma-4-12b-it-qat", "qwen/qwen3.6-35b-a3b"
def A(sel):
    s = [v for v in votes if v["parseable"] and sel(v)]
    k = sum(1 for v in s if v["harness"]); return k, len(s), (k/len(s) if s else None), wilson(k, len(s))

rep = {"n_votes": len(votes)}
for name, mdl, exp in (("C1_qwen", Q, (20, 108)), ("C1p_gemma", G, (162, 305))):
    k, n, a, ci = A(lambda v, m=mdl: v["model"] == m)
    rep[name] = {"k": k, "n": n, "A": a, "wilson": ci, "expected": exp, "pass": (k, n) == exp}

# C2 vote-level diff
r522 = {}
for l in open(R522):
    v = json.loads(l); r522[(v["run"], v["arm"], v["task_id"], v["agent_id"])] = v
diffs = []
for v in votes:
    o = r522.get((v["run"], v["arm"], v["task_id"], v["agent_id"]))
    if o is None: diffs.append({"kind": "missing_in_r522", **{k: v[k] for k in ("run","arm","task_id","agent_id")}}); continue
    if o["parseable"] != v["parseable"] or (v["parseable"] and bool(o.get("harness")) != v["harness"]):
        diffs.append({"kind": "parse" if o["parseable"] != v["parseable"] else "harness",
                      "run": v["run"], "task_id": v["task_id"], "agent_id": v["agent_id"], "model": v["model"],
                      "r522": {"parseable": o["parseable"], "harness": o.get("harness")},
                      "r523": {"parseable": v["parseable"], "harness": v.get("harness"), "exc": v.get("ref_exc"),
                               "actual": v.get("actual"), "expected": v.get("expected")}})
rep["C2"] = {"n_diff": len(diffs), "n_r522": len(r522), "diffs": diffs, "pass": len(diffs) == 0}

# C3
rep["C3"] = {"wilson_upper_qwen": rep["C1_qwen"]["wilson"][1], "pass": rep["C1_qwen"]["wilson"][1] < 0.80}

# C4 pass rate
qv = [v for v in votes if v["model"] == Q]
rep["C4"] = {"n_qwen": len(qv),
             "pass_rate_first_nonempty": sum(v["vote_pass_fne"] for v in qv)/len(qv),
             "pass_rate_r522style": sum(v["vote_pass_r522style"] for v in qv)/len(qv),
             "r522_claimed": 2311/2421}
rep["C4"]["pass"] = abs(rep["C4"]["pass_rate_first_nonempty"] - rep["C4"]["r522_claimed"]) < 0.01

# C5
k, n, a, ci = A(lambda v: v["model"] == Q and v["in_rows"])
rep["C5"] = {"qwen_in_rows": {"k": k, "n": n, "A": a, "wilson": ci}}
for lab, flag in (("qwen_vote_PASS", True), ("qwen_vote_nonPASS", False)):
    k, n, a, ci = A(lambda v, f=flag: v["model"] == Q and v["vote_pass_fne"] == f)
    rep["C5"][lab] = {"k": k, "n": n, "A": a}
k, n, a, ci = A(lambda v: v["model"] == G and v["in_rows"])
rep["C5"]["gemma_in_rows"] = {"k": k, "n": n, "A": a, "wilson": ci}
# multi TEST_ARGS lines (first vs last occurrence sensitivity)
rep["C5"]["votes_with_multiple_TEST_ARGS_lines"] = collections.Counter(v["model"] for v in votes if v["n_testargs_lines"] > 1)
rep["C5"]["qwen_ref_exceptions"] = collections.Counter(v.get("ref_exc") for v in votes if v["model"] == Q and v["parseable"] and v.get("ref_exc"))

rep["fingerprints"] = {"ds_sha8": hashlib.sha256(DS.read_bytes()).hexdigest()[:8],
                       "votes_r522_sha8": hashlib.sha256(R522.read_bytes()).hexdigest()[:8]}
(HERE/"audit_r523.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False, default=str))
for k in ("C1_qwen", "C1p_gemma", "C3", "C4"):
    print(k, json.dumps(rep[k], default=str))
print("C2 n_diff", rep["C2"]["n_diff"], "pass", rep["C2"]["pass"])
for d in diffs[:30]: print("  DIFF", json.dumps(d, ensure_ascii=False)[:400])
print("C5", json.dumps(rep["C5"], default=str))
print("n_votes", len(votes), rep["fingerprints"])
