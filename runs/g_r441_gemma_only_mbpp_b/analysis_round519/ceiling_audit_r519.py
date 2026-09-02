#!/usr/bin/env python3
"""R519 稽核（Fable 5.1）：獨立重算 round518 的 P-CEIL A，**不 import gain_run**。

不同的程式路徑：
  - 直接讀 MbppPlus jsonl.gz 取 canonical_solution / entry_point（不經 loader）
  - 自己的 claim parser（regex+literal_eval）
  - 參考解在獨立 subprocess 跑（官方碼，可信），不經 vacant sandbox
  - 三種相等判定並列：strict(==) / harness-like(isclose+list~tuple+dict) / loose(順序不敏感、
    set~list、str 化相等、bool~int)——loose 是 A 的**上界**，用來找 §十四 的「系統性誤判來源」
  - 逐票對到 rows.review_evidence 的 status（用 meta.target ↔ agent_id），重算分群 A
零 API 呼叫。
"""
import ast, collections, gzip, json, pathlib, re, subprocess, sys, hashlib

ROOT = pathlib.Path(__file__).resolve().parents[3]
RUN = ROOT / "runs/g_r441_gemma_only_mbpp_b"
DS = ROOT / ".vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz"
OUT = pathlib.Path(__file__).parent / "ceiling_audit_r519.json"

def sha8(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()[:8]

ds = {}
for line in gzip.open(DS, "rt"):
    d = json.loads(line)
    ds["mbppplus_" + d["task_id"]] = d

rows = {}
for line in open(RUN / "rows.jsonl"):
    r = json.loads(line)
    rows[(r["arm"], r["task_id"])] = r

def my_parse(text):
    f = {}
    for ln in text.splitlines():
        m = re.match(r"\s*(TEST_ARGS|EXPECTED)\s*:\s*(.*)$", ln, re.I)
        if m:
            f[m.group(1).upper()] = m.group(2).strip()
    if "TEST_ARGS" not in f or "EXPECTED" not in f:
        return None
    if f["TEST_ARGS"].upper() == "NONE" or f["EXPECTED"].upper() == "NONE":
        return None
    try:
        a = ast.literal_eval(f["TEST_ARGS"]); e = ast.literal_eval(f["EXPECTED"])
    except (SyntaxError, ValueError):
        return None
    if not isinstance(a, (list, tuple)):
        return None
    return a, e

def my_vote_pass(text):
    first = text.strip().splitlines()[0].strip().upper() if text.strip() else ""
    return first == "VERDICT: PASS"

CMP_SRC = r'''
import json, math, sys, ast
def eq_h(a, b):
    if isinstance(a, bool) != isinstance(b, bool) and (isinstance(a,(int,float)) and isinstance(b,(int,float))):
        pass
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(eq_h(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(eq_h(a[k], b[k]) for k in a)
    return a == b
def norm(x):
    if isinstance(x, bool): return ("n", float(x))
    if isinstance(x, (int, float)): return ("n", round(float(x), 6))
    if isinstance(x, str):
        try: return ("n", round(float(x), 6))
        except ValueError: return ("s", x)
    if isinstance(x, (list, tuple, set, frozenset)):
        return ("seq", tuple(sorted((repr(norm(i)) for i in x))))
    if isinstance(x, dict):
        return ("d", tuple(sorted((repr(norm(k)), repr(norm(v))) for k, v in x.items())))
    return ("o", repr(x))
def eq_loose(a, b):
    if eq_h(a, b): return True
    try:
        if norm(a) == norm(b): return True
    except Exception: pass
    return str(a) == str(b)
spec = json.loads(sys.stdin.read())
spec["args"] = ast.literal_eval(spec["args_repr"]); spec["expected"] = ast.literal_eval(spec["expected_repr"])
ns = {}
try:
    exec(spec["code"], ns)
    fn = ns[spec["entry_point"]]
    actual = fn(*spec["args"])
    out = {"exc": None, "actual": repr(actual)[:300],
           "strict": bool(actual == spec["expected"]),
           "harness": bool(eq_h(actual, spec["expected"])),
           "loose": bool(eq_loose(actual, spec["expected"]))}
except BaseException as e:
    out = {"exc": type(e).__name__, "actual": None, "strict": False, "harness": False, "loose": False}
print(json.dumps(out))
'''

def run_ref(code, entry_point, args, expected):
    spec = json.dumps({"code": code, "entry_point": entry_point, "args_repr": repr(list(args)), "expected_repr": repr(expected)})
    try:
        p = subprocess.run([sys.executable, "-I", "-c", CMP_SRC], input=spec, capture_output=True, text=True, timeout=15)
    except subprocess.TimeoutExpired:
        return {"exc": "Timeout", "actual": None, "strict": False, "harness": False, "loose": False}
    if p.returncode != 0 or not p.stdout.strip():
        return {"exc": "RunnerError:" + p.stderr.strip()[-200:], "actual": None, "strict": False, "harness": False, "loose": False}
    return json.loads(p.stdout.strip().splitlines()[-1])

votes = 0; parsed = 0; unparse = 0; not_fail = 0
detail = []
per_task_calls = collections.Counter()
for line in open(RUN / "calls.jsonl"):
    c = json.loads(line)
    m = c.get("meta") or {}
    if m.get("arm") != "ON" or c.get("role") != "review" or not c.get("ok"):
        continue
    tid = m["task_id"]
    if ("ON", tid) not in rows:
        continue
    votes += 1
    per_task_calls[tid] += 1
    row = rows[("ON", tid)]
    ev = [e for e in row["review_evidence"] if e.get("agent_id") == c.get("agent_id")]
    status = ev[0]["status"] if len(ev) == 1 else ("AMBIG:%d" % len(ev))
    if my_vote_pass(c["response"]):
        not_fail += 1
        continue
    claim = my_parse(c["response"])
    if claim is None:
        unparse += 1
        continue
    args, expected = claim
    parsed += 1
    d = ds[tid]
    res = run_ref(d["canonical_solution"], d["entry_point"], list(args), expected)
    detail.append({"task_id": tid, "agent": c.get("agent_id"), "status": status,
                   "initial_hidden_ok": row.get("initial_meets_demand"),
                   "args": repr(args)[:200], "expected": repr(expected)[:200], **res})

# 逐題票數 vs rows 的 review_evidence 筆數
mismatch = sum(1 for (arm, tid), r in rows.items() if arm == "ON" and per_task_calls[tid] != len(r["review_evidence"]))

def wilson(k, n, z=1.96):
    if not n: return (0.0, 0.0)
    p = k / n; d = 1 + z*z/n; c = (p + z*z/(2*n))/d
    h = z*((p*(1-p)/n + z*z/(4*n*n))**0.5)/d
    return (max(0.0, c-h), min(1.0, c+h))

def rep(label, sel):
    n = len(sel)
    for key in ("strict", "harness", "loose"):
        k = sum(1 for x in sel if x[key])
        lo, hi = wilson(k, n)
        print(f"  {label:28s} {key:8s} A={k}/{n}={k/n if n else 0:.4f}  W95[{lo:.4f},{hi:.4f}]")

print(f"rows.jsonl sha8={sha8(RUN/'rows.jsonl')} lines={sum(1 for _ in open(RUN/'rows.jsonl'))}")
print(f"calls.jsonl sha8={sha8(RUN/'calls.jsonl')} lines={sum(1 for _ in open(RUN/'calls.jsonl'))}")
print(f"ON review votes (rows-aligned) {votes}; per-task call count vs review_evidence mismatch tasks = {mismatch}")
print(f"  voted PASS {not_fail}; FAIL unparseable {unparse}; FAIL parseable {parsed}")
print(f"  status ambiguity (agent_id not unique in task): {sum(1 for x in detail if x['status'].startswith('AMBIG'))}")
print("\n=== A under three equality notions ===")
rep("ALL parseable", detail)
for st in ("candidate_passed_claim", "counterexample_confirmed", "outside_input_contract", "unparseable_claim", "review_not_fail"):
    sel = [x for x in detail if x["status"] == st]
    if sel: rep(st, sel)
print("\n=== why harness-A is False: categories ===")
bad = [x for x in detail if not x["harness"]]
cat = collections.Counter()
for x in bad:
    if x["exc"]: cat["ref_raised:" + x["exc"].split(":")[0]] += 1
    elif x["loose"]: cat["loose_only(order/type/str)"] += 1
    else: cat["genuinely_different_value"] += 1
for k, v in sorted(cat.items(), key=lambda kv: -kv[1]): print(f"  {k:36s} {v}")
print("\n=== confirmed votes: reviewer's EXPECTED wrong, but initial code fails hidden anyway ===")
conf = [x for x in detail if x["status"] == "counterexample_confirmed"]
print(f"  confirmed n={len(conf)}; initial hidden fail={sum(1 for x in conf if x['initial_hidden_ok'] is False)}; "
      f"expected-wrong & initial hidden ok={sum(1 for x in conf if not x['harness'] and x['initial_hidden_ok'])}; "
      f"expected-wrong & initial hidden FAIL={sum(1 for x in conf if not x['harness'] and x['initial_hidden_ok'] is False)}; "
      f"expected-right & initial hidden ok(!)={sum(1 for x in conf if x['harness'] and x['initial_hidden_ok'])}")
print("\n=== loose_only cases (potential systematic misjudgement) ===")
for x in bad:
    if x["loose"] and not x["exc"]:
        print(f"  {x['task_id']} {x['status']} args={x['args'][:60]} expected={x['expected'][:60]} actual={x['actual'][:60]}")
json.dump({"votes": votes, "not_fail": not_fail, "unparseable": unparse, "parseable": parsed,
           "rows_sha8": sha8(RUN/'rows.jsonl'), "calls_sha8": sha8(RUN/'calls.jsonl'),
           "detail": detail}, open(OUT, "w"), ensure_ascii=False, indent=1)
