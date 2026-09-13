#!/usr/bin/env python3
"""M-R528：把 counterexample_confirmed 拆成「初稿拋例外」／「初稿回傳不同值」。

判準見 DECISION_20260903_R528_CONFIRMED_STATUS_CRASH_SPLIT.md（量測前已 commit）。
重放路徑刻意不同於 runtime：初稿碼從 review prompt 反解（不呼叫 extract_code），
子行程 python3 -I 執行（不經 vacant sandbox）。零 API。
"""
import ast, collections, hashlib, json, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
RUN = ROOT / "runs/g_r441_gemma_only_mbpp_b"
OUT = pathlib.Path(__file__).parent / "crash_split_r528.json"

def sha8(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()[:8]

# --- 初稿碼從 review prompt 反解（獨立於 extract_code） ---
FENCE = re.compile(r"候選解答：\n```python\n(.*?)\n```", re.S)

def draft_from_review_prompt(prompt):
    m = FENCE.search(prompt or "")
    return m.group(1) if m else None

# --- claim parser（沿用 R519 的獨立實作） ---
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

RUNNER = r'''
import json, math, sys, ast, io, contextlib
def eq_h(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) \
       and not isinstance(a, bool) and not isinstance(b, bool):
        return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(eq_h(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return set(a) == set(b) and all(eq_h(a[k], b[k]) for k in a)
    return a == b

spec = json.loads(sys.stdin.read())
g = {"__name__": "__vacant__"}
try:
    with contextlib.redirect_stdout(io.StringIO()):
        exec(compile(spec["code"], "<draft>", "exec"), g)
except BaseException as e:
    print(json.dumps({"cls": "load_error", "exc": type(e).__name__ + ": " + str(e)[:200]}))
    sys.exit(0)
fn = g.get(spec["entry_point"])
if not callable(fn):
    print(json.dumps({"cls": "no_entry", "exc": "entry_point not defined"}))
    sys.exit(0)
args = ast.literal_eval(spec["args_repr"])
expected = ast.literal_eval(spec["expected_repr"])
try:
    with contextlib.redirect_stdout(io.StringIO()):
        actual = fn(*args)
except BaseException as e:
    print(json.dumps({"cls": "draft_raised", "exc": type(e).__name__ + ": " + str(e)[:200]}))
    sys.exit(0)
same = False
try:
    same = bool(eq_h(actual, expected))
except BaseException:
    same = False
print(json.dumps({"cls": "draft_value_matches" if same else "draft_value_differs",
                  "exc": None, "actual": repr(actual)[:200]}))
'''

def replay(code, entry_point, args, expected):
    spec = json.dumps({"code": code, "entry_point": entry_point,
                       "args_repr": repr(list(args)), "expected_repr": repr(expected)})
    try:
        p = subprocess.run([sys.executable, "-I", "-c", RUNNER], input=spec,
                           capture_output=True, text=True, timeout=15)
    except subprocess.TimeoutExpired:
        return {"cls": "draft_raised", "exc": "Timeout"}
    if p.returncode != 0 or not p.stdout.strip():
        return {"cls": "RunnerError", "exc": (p.stderr or "").strip()[-200:]}
    return json.loads(p.stdout.strip().splitlines()[-1])

rows = {}
for line in open(RUN / "rows.jsonl"):
    r = json.loads(line)
    rows[(r["arm"], r["task_id"])] = r

detail = []
no_draft = 0
for line in open(RUN / "calls.jsonl"):
    c = json.loads(line)
    m = c.get("meta") or {}
    if m.get("arm") != "ON" or c.get("role") != "review" or not c.get("ok"):
        continue
    tid = m["task_id"]
    if ("ON", tid) not in rows:
        continue
    row = rows[("ON", tid)]
    ev = [e for e in row["review_evidence"] if e.get("agent_id") == c.get("agent_id")]
    if len(ev) != 1:
        continue
    status = ev[0]["status"]
    if status not in ("counterexample_confirmed", "candidate_passed_claim"):
        continue
    claim = my_parse(c["response"])
    if claim is None:
        continue
    draft = draft_from_review_prompt(c.get("prompt"))
    if draft is None:
        no_draft += 1
        continue
    args, expected = claim
    res = replay(draft, row.get("entry_point"), list(args), expected)
    detail.append({"task_id": tid, "reviewer": c.get("agent_id"), "status": status,
                   "initial_hidden_ok": row.get("initial_meets_demand"),
                   "args": repr(args)[:160], "expected": repr(expected)[:160], **res})

def wilson(k, n, z=1.96):
    if not n: return (0.0, 0.0)
    p = k / n; d = 1 + z*z/n; c = (p + z*z/(2*n))/d
    h = z*((p*(1-p)/n + z*z/(4*n*n))**0.5)/d
    return (max(0.0, c-h), min(1.0, c+h))

print(f"rows.jsonl sha8={sha8(RUN/'rows.jsonl')} lines={sum(1 for _ in open(RUN/'rows.jsonl'))}")
print(f"calls.jsonl sha8={sha8(RUN/'calls.jsonl')} lines={sum(1 for _ in open(RUN/'calls.jsonl'))}")
print(f"prompt 反解不到初稿的票數 = {no_draft}")

conf = [x for x in detail if x["status"] == "counterexample_confirmed"]
cpc  = [x for x in detail if x["status"] == "candidate_passed_claim"]
print(f"\n重放到的票：confirmed {len(conf)}（預期 61）／candidate_passed_claim {len(cpc)}（預期 64）")

print("\n=== 量具雙向驗證 ===")
c_match = sum(1 for x in conf if x["cls"] == "draft_value_matches")
p_ok    = sum(1 for x in cpc if x["cls"] == "draft_value_matches")
print(f"  正向：confirmed 裡 draft_value_matches = {c_match}（判準要求 0）")
print(f"  反向：candidate_passed_claim 裡 draft_value_matches = {p_ok}/{len(cpc)}（判準要求全中）")
gauge_ok = (c_match == 0) and (p_ok == len(cpc)) and len(cpc) > 0
print(f"  => 量具{'通過' if gauge_ok else '不通過（本輪數字作廢）'}")

print("\n=== confirmed 61 票分類 ===")
cls = collections.Counter(x["cls"] for x in conf)
for k, v in cls.most_common(): print(f"  {k:22s} {v}")
print("\n  拋例外的型別分佈：")
exc = collections.Counter(x["exc"].split(":")[0] for x in conf if x["cls"] == "draft_raised")
for k, v in exc.most_common(): print(f"    {k:24s} {v}")
print("\n  RunnerError（不算 raised，判準 §五-2）：")
for x in conf:
    if x["cls"] in ("RunnerError", "load_error", "no_entry"):
        print(f"    {x['task_id']} {x['cls']} {x['exc'][:120]}")

raised = [x for x in conf if x["cls"] == "draft_raised"]
differs = [x for x in conf if x["cls"] == "draft_value_differs"]

print("\n=== 精度（初稿真的被 hidden 打掉）===")
def prec(label, sel):
    n = len(sel); k = sum(1 for x in sel if x["initial_hidden_ok"] is False)
    lo, hi = wilson(k, n)
    print(f"  {label:26s} {k}/{n} = {k/n if n else 0:.4f}  W95[{lo:.4f},{hi:.4f}]")
    return k / n if n else None
print("  -- 票級（票不獨立，見判準 §三）--")
p_r_vote = prec("draft_raised", raised)
p_d_vote = prec("draft_value_differs", differs)

# 題級
by_task = collections.defaultdict(list)
for x in conf: by_task[x["task_id"]].append(x)
t_raised, t_differs, t_mixed = [], [], []
for tid, xs in by_task.items():
    kinds = {x["cls"] for x in xs}
    rec = {"task_id": tid, "initial_hidden_ok": xs[0]["initial_hidden_ok"], "votes": len(xs)}
    if kinds == {"draft_raised"}: t_raised.append(rec)
    elif kinds == {"draft_value_differs"}: t_differs.append(rec)
    else: t_mixed.append({**rec, "kinds": sorted(kinds)})
print(f"  -- 題級（{len(by_task)} 題；混合題 {len(t_mixed)} 排除在 Δ 之外）--")
p_r = prec("draft_raised", t_raised)
p_d = prec("draft_value_differs", t_differs)
for t in t_mixed:
    print(f"    混合題 {t['task_id']} kinds={t['kinds']} votes={t['votes']} hidden_ok={t['initial_hidden_ok']}")

print("\n=== 裁決輸入 ===")
n_raised_vote = len(raised)
print(f"  n_raised（票級）= {n_raised_vote}")
print(f"  題級 n_raised = {len(t_raised)}／n_differs = {len(t_differs)}")
if p_r is not None and p_d is not None:
    print(f"  Δ（題級）= |{p_r:.4f} - {p_d:.4f}| = {abs(p_r - p_d):.4f}")
else:
    print("  Δ（題級）= 無法計算（某一類題級 n=0）")

json.dump({"rows_sha8": sha8(RUN/'rows.jsonl'), "calls_sha8": sha8(RUN/'calls.jsonl'),
           "gauge_ok": gauge_ok, "gauge_forward_bad": c_match,
           "gauge_reverse_ok": p_ok, "gauge_reverse_n": len(cpc),
           "no_draft": no_draft, "detail": detail,
           "task_level": {"raised": t_raised, "differs": t_differs, "mixed": t_mixed}},
          open(OUT, "w"), ensure_ascii=False, indent=1)
print(f"\nwrote {OUT}")
