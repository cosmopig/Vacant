#!/usr/bin/env python3
"""R523 S1: arg-repacking sensitivity of A (pre-registered in DECISION R523 before running).
Parser = runtime convention (LAST TEST_ARGS/EXPECTED). Ref exec in-process with alarm."""
import ast, collections, gzip, io, json, math, pathlib, signal, contextlib, hashlib
ROOT = pathlib.Path(__file__).resolve().parents[2]; RUNS = ROOT/"runs"; HERE = pathlib.Path(__file__).parent
DS = ROOT/".vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz"
ds = {"mbppplus_"+d["task_id"]: d for d in (json.loads(l) for l in gzip.open(DS, "rt"))}

def parse_last(text):
    f = {}
    for ln in text.splitlines():
        k, sep, v = ln.partition(":")
        if sep and k.strip().upper() in ("TEST_ARGS", "EXPECTED"): f[k.strip().upper()] = v.strip()
    if "TEST_ARGS" not in f or "EXPECTED" not in f or f["TEST_ARGS"].upper() == "NONE" or f["EXPECTED"].upper() == "NONE": return None
    try: a = ast.literal_eval(f["TEST_ARGS"]); e = ast.literal_eval(f["EXPECTED"])
    except Exception: return None
    if not isinstance(a, (list, tuple)): return None
    return list(a), e

def eq(x, y):
    if isinstance(x, (int, float)) and isinstance(y, (int, float)): return math.isclose(x, y, rel_tol=1e-9, abs_tol=1e-9)
    if isinstance(x, (list, tuple)) and isinstance(y, (list, tuple)): return len(x) == len(y) and all(eq(p, q) for p, q in zip(x, y))
    if isinstance(x, dict) and isinstance(y, dict): return set(x) == set(y) and all(eq(x[k], y[k]) for k in x)
    return x == y

class TO(Exception): pass
signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TO()))
fns = {}
def call(tid, args):
    if tid not in fns:
        ns = {}
        with contextlib.redirect_stdout(io.StringIO()): exec(ds[tid]["canonical_solution"], ns)
        fns[tid] = ns[ds[tid]["entry_point"]]
    signal.alarm(10)
    try:
        with contextlib.redirect_stdout(io.StringIO()): return None, fns[tid](*args)
    except BaseException as e: return type(e).__name__, None
    finally: signal.alarm(0)

# rows review_evidence status index
ev = {}
for rd in RUNS.iterdir():
    f = rd/"rows.jsonl"
    if not f.exists(): continue
    for l in open(f):
        r = json.loads(l)
        for e in r.get("review_evidence") or []:
            ev[(rd.name, r["arm"], r["task_id"], e.get("agent_id"))] = e.get("status")

out = []
for rd in sorted(RUNS.iterdir()):
    f = rd/"calls.jsonl"
    if not f.exists(): continue
    for l in open(f):
        try: c = json.loads(l)
        except Exception: continue
        if c.get("role") != "review" or not c.get("ok"): continue
        m = c.get("meta") or {}; tid = m.get("task_id")
        model = c.get("model_configured") or c.get("model")
        if model not in ("gemma-4-12b-it-qat", "qwen/qwen3.6-35b-a3b") or tid not in ds: continue
        pc = parse_last(c.get("response") or "")
        if not pc: continue
        args, exp = pc
        exc, act = call(tid, args)
        asis = "exc:"+exc if exc else ("ok" if eq(act, exp) else "wrong")
        repacked = None; final = asis
        if exc == "TypeError" and len(args) == 1 and isinstance(args[0], (list, tuple)):
            exc2, act2 = call(tid, list(args[0]))
            repacked = "exc:"+exc2 if exc2 else ("ok" if eq(act2, exp) else "wrong")
            final = repacked
        out.append({"run": rd.name, "arm": m.get("arm"), "task_id": tid, "agent_id": c.get("agent_id"), "model": model,
                    "args": repr(args)[:150], "expected": repr(exp)[:100], "asis": asis, "repacked": repacked, "final": final,
                    "runtime_status": ev.get((rd.name, m.get("arm"), tid, c.get("agent_id")))})
with open(HERE/"s1_votes_r523.jsonl", "w") as fh:
    for o in out: fh.write(json.dumps(o, ensure_ascii=False)+"\n")

def wilson(k, n, z=1.959963985):
    p = k/n; d = 1+z*z/n; c = (p+z*z/(2*n))/d; h = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return (max(0, c-h), min(1, c+h))
rep = {}
for mdl in ("qwen/qwen3.6-35b-a3b", "gemma-4-12b-it-qat"):
    s = [o for o in out if o["model"] == mdl]
    k0 = sum(o["asis"] == "ok" for o in s); k1 = sum(o["final"] == "ok" for o in s); n = len(s)
    trans = collections.Counter((o["asis"].split(":")[0], (o["repacked"] or "-").split(":")[0]) for o in s if o["repacked"])
    rt = collections.Counter((o["asis"].split(":")[0], o["runtime_status"]) for o in s)
    rep[mdl] = {"n": n, "A_asis": {"k": k0, "A": k0/n, "wilson": wilson(k0, n)}, "A_repacked": {"k": k1, "A": k1/n, "wilson": wilson(k1, n)},
                "n_retried": sum(1 for o in s if o["repacked"]), "transitions(asis->repacked)": {f"{a}->{b}": v for (a, b), v in trans.items()},
                "runtime_status_by_asis": {f"{a}|{b}": v for (a, b), v in rt.items()}}
    print(mdl, json.dumps(rep[mdl], indent=1))
rep["S1_gate"] = {"qwen_repacked_wilson_upper": rep["qwen/qwen3.6-35b-a3b"]["A_repacked"]["wilson"][1],
                  "downgrade": rep["qwen/qwen3.6-35b-a3b"]["A_repacked"]["wilson"][1] >= 0.80}
print("S1 gate:", rep["S1_gate"])
(HERE/"s1_r523.json").write_text(json.dumps(rep, indent=2, ensure_ascii=False))
