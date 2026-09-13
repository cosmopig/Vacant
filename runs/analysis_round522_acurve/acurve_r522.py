#!/usr/bin/env python3
"""R522：A（評審宣稱的 EXPECTED 是否與官方參考解一致）對**評審模型**的曲線。

零 API 呼叫。資料＝runs/ 底下所有已落盤的 review 呼叫。
定義與 R518 §十一 / R519 逐字相同，只多一個分組維度（model / run / persona / arm）。

程式路徑聲明（誠實）：claim parser 與 CMP_SRC 參考解執行器**沿用**
`runs/g_r441_gemma_only_mbpp_b/analysis_round519/ceiling_audit_r519.py`——
那一份是 fable 稽核輪寫的、與 round518 的 `ceiling_r518.py` 兩條獨立實作逐位相同。
本輪的目的不是第三次重驗 gemma，而是把同一把尺套到別的模型上，
所以「用同一把已被交叉驗證過的尺」是刻意的；G1 守恆量就是為此設的。
"""
import ast, collections, gzip, hashlib, json, math, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
RUNS = ROOT / "runs"
DS = ROOT / ".vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz"
OUT = pathlib.Path(__file__).parent / "acurve_r522.json"
R519 = RUNS / "g_r441_gemma_only_mbpp_b/analysis_round519/ceiling_audit_r519.py"

ds = {}
for line in gzip.open(DS, "rt"):
    d = json.loads(line)
    ds["mbppplus_" + d["task_id"]] = d

# ---- 沿用 R519 的 parser 與執行器（逐字取自該檔，避免我自己重打時引入差異）----
src = R519.read_text()
CMP_SRC = re.search(r"CMP_SRC = r'''(.*?)'''", src, re.S).group(1)
ns = {"re": re, "ast": ast}
exec(re.search(r"def my_parse\(text\):.*?\n(?=def )", src, re.S).group(0), ns)
my_parse = ns["my_parse"]

def run_ref(code, entry_point, args, expected):
    spec = json.dumps({"code": code, "entry_point": entry_point,
                       "args_repr": repr(list(args)), "expected_repr": repr(expected)})
    try:
        p = subprocess.run([sys.executable, "-I", "-c", CMP_SRC], input=spec,
                           capture_output=True, text=True, timeout=15)
    except subprocess.TimeoutExpired:
        return {"exc": "Timeout", "actual": None, "strict": False, "harness": False, "loose": False}
    if p.returncode != 0 or not p.stdout.strip():
        return {"exc": "RunnerError:" + p.stderr.strip()[-200:], "actual": None,
                "strict": False, "harness": False, "loose": False}
    return json.loads(p.stdout.strip().splitlines()[-1])

def wilson(k, n, z=1.959963985):
    if n == 0: return (0.0, 1.0)
    p = k / n; d = 1 + z*z/n
    c = (p + z*z/(2*n)) / d
    h = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / d
    return (max(0.0, c-h), min(1.0, c+h))

def two_prop_p(k1, n1, k2, n2):
    if n1 == 0 or n2 == 0: return None
    p = (k1+k2)/(n1+n2); se = math.sqrt(p*(1-p)*(1/n1+1/n2))
    if se == 0: return 1.0
    z = (k1/n1 - k2/n2)/se
    return math.erfc(abs(z)/math.sqrt(2))

def mcnemar_exact(b, c):
    n = b + c
    if n == 0: return 1.0
    lo = min(b, c)
    tail = sum(math.comb(n, i) for i in range(lo+1)) / (2**n)
    return min(1.0, 2*tail)

def norm_model(m):
    return (m or "?").replace("qwen_", "qwen/")

# ---- 收集所有 review 票 ----
rows_cache = {}
def rows_of(run):
    if run not in rows_cache:
        d = {}
        f = RUNS / run / "rows.jsonl"
        if f.exists():
            for line in open(f):
                r = json.loads(line)
                d[(r["arm"], r["task_id"])] = r
        rows_cache[run] = d
    return rows_cache[run]

votes = []
for rd in sorted(RUNS.iterdir()):
    f = rd / "calls.jsonl"
    if not f.exists(): continue
    for line in open(f):
        try: c = json.loads(line)
        except Exception: continue
        if c.get("role") != "review" or not c.get("ok"): continue
        m = c.get("meta") or {}
        tid = m.get("task_id")
        votes.append({
            "run": rd.name, "arm": m.get("arm"), "task_id": tid,
            "agent_id": c.get("agent_id"),
            "model": norm_model(c.get("model")),
            "persona": hashlib.sha256((c.get("system") or "").encode()).hexdigest()[:8],
            "resp": c.get("response") or "",
            "in_rows": (m.get("arm"), tid) in rows_of(rd.name),
            "in_ds": tid in ds,
        })

# ---- 解析 + 跑參考解（帶快取）----
cache = {}
for v in votes:
    pc = my_parse(v["resp"])
    v["parseable"] = bool(pc) and v["in_ds"]
    v["vote_pass"] = (v["resp"].strip().splitlines() or [""])[0].strip().upper() == "VERDICT: PASS"
    if not v["parseable"]:
        continue
    args, exp = pc
    d = ds[v["task_id"]]
    key = (v["task_id"], repr(list(args)), repr(exp))
    if key not in cache:
        cache[key] = run_ref(d["canonical_solution"], d["entry_point"], args, exp)
    r = cache[key]
    v["strict"], v["harness"], v["loose"], v["ref_exc"] = r["strict"], r["harness"], r["loose"], r["exc"]

par = [v for v in votes if v["parseable"]]

def A(sel, key="harness"):
    s = [v for v in par if sel(v)]
    k = sum(1 for v in s if v[key])
    return k, len(s), (k/len(s) if s else None), wilson(k, len(s))


# ---- 逐票落盤（給稽核與 post-hoc 用；不含 prompt 全文，那些在原 calls.jsonl）----
with open(pathlib.Path(__file__).parent / "votes_r522.jsonl", "w") as fh:
    for v in votes:
        fh.write(json.dumps({k: v[k] for k in v if k != "resp"}, ensure_ascii=False) + "\n")

report = {}

# ---- G1 / G1b ----
e1 = lambda v: v["run"] == "g_r441_gemma_only_mbpp_b" and v["arm"] == "ON" and v["in_rows"]
k, n, a, ci = A(e1)
e1_all = [v for v in par if v["run"] == "g_r441_gemma_only_mbpp_b"]
e1_unaligned = [v for v in e1_all if not (v["arm"] == "ON" and v["in_rows"])]
report["G1"] = {"k": k, "n": n, "A": a, "wilson": ci,
                "expected": "95/156=0.6090", "pass": (k == 95 and n == 156)}
report["G1b"] = {"e1_parseable_all": len(e1_all), "aligned": n,
                 "unaligned": [{"task_id": v["task_id"], "arm": v["arm"], "in_rows": v["in_rows"],
                                "agent_id": v["agent_id"]} for v in e1_unaligned],
                 "pass": len(e1_all) - n == len(e1_unaligned) and all(not v["in_rows"] for v in e1_unaligned)}

# ---- 主：A 對模型 ----
models = collections.Counter(v["model"] for v in votes)
curve = {}
for mdl in models:
    tot = sum(1 for v in votes if v["model"] == mdl)
    k, n, a, ci = A(lambda v, m=mdl: v["model"] == m)
    ks, _, as_, _ = A(lambda v, m=mdl: v["model"] == m, "strict")
    kl, _, al, cil = A(lambda v, m=mdl: v["model"] == m, "loose")
    curve[mdl] = {"total_votes": tot, "parseable": n, "claim_rate": n/tot if tot else None,
                  "A_harness": a, "wilson_harness": ci, "k_harness": k,
                  "A_strict": as_, "A_loose": al, "wilson_loose": cil,
                  "ref_exceptions": sum(1 for v in par if v["model"] == mdl and v["ref_exc"])}
report["curve"] = curve

G, Q = "gemma-4-12b-it-qat", "qwen/qwen3.6-35b-a3b"

# ---- 次要 1：281 個同初稿 cell ----
cells = collections.defaultdict(lambda: collections.defaultdict(list))
for v in votes:
    cells[(v["run"], v["arm"], v["task_id"])][v["model"]].append(v)
both_cells = [k for k, d in cells.items() if G in d and Q in d]
def A_cells(mdl):
    s = [v for c in both_cells for v in cells[c][mdl] if v["parseable"]]
    k = sum(1 for v in s if v["harness"])
    return {"k": k, "n": len(s), "A": (k/len(s) if s else None), "wilson": wilson(k, len(s)),
            "claim_rate": len(s)/sum(len(cells[c][mdl]) for c in both_cells)}
report["same_draft_cells"] = {"n_cells": len(both_cells), G: A_cells(G), Q: A_cells(Q)}

# ---- 次要 2：兩邊都出 claim 的 cell 配對 ----
b = c_ = 0; pairs = []
for cell in both_cells:
    gv = [v for v in cells[cell][G] if v["parseable"]]
    qv = [v for v in cells[cell][Q] if v["parseable"]]
    if not gv or not qv: continue
    g_ok = any(v["harness"] for v in gv); q_ok = any(v["harness"] for v in qv)
    pairs.append({"cell": list(cell), "gemma_correct": g_ok, "qwen_correct": q_ok})
    if g_ok and not q_ok: b += 1
    elif q_ok and not g_ok: c_ += 1
report["paired_both_claim"] = {"n": len(pairs), "gemma_only_correct": b, "qwen_only_correct": c_,
                               "mcnemar_exact_p": mcnemar_exact(b, c_), "pairs": pairs}

# ---- 次要 3：只用 179 題庫的 run ----
bank179 = {r.name for r in RUNS.iterdir() if (r/"summary.json").exists()
           and json.load(open(r/"summary.json")).get("n") == 179}
report["bank179_only"] = {"runs": sorted(bank179)}
for mdl in (G, Q):
    k, n, a, ci = A(lambda v, m=mdl: v["model"] == m and v["run"] in bank179)
    report["bank179_only"][mdl] = {"k": k, "n": n, "A": a, "wilson": ci}

# ---- 次要 4：persona 分層 ----
per = {}
for mdl in (G, Q):
    per[mdl] = {}
    for p in sorted({v["persona"] for v in par if v["model"] == mdl}):
        k, n, a, ci = A(lambda v, m=mdl, pp=p: v["model"] == m and v["persona"] == pp)
        per[mdl][p] = {"k": k, "n": n, "A": a}
    vals = [d["A"] for d in per[mdl].values() if d["n"] >= 10 and d["A"] is not None]
    per[mdl]["_range_n>=10"] = (max(vals)-min(vals)) if len(vals) >= 2 else None
report["persona"] = per

# ---- 兩比例檢定 ----
report["delta_gemma_minus_qwen"] = {
    "A_gemma": curve.get(G, {}).get("A_harness"), "A_qwen": curve.get(Q, {}).get("A_harness"),
    "p_two_prop": two_prop_p(curve.get(G, {}).get("k_harness", 0), curve.get(G, {}).get("parseable", 0),
                             curve.get(Q, {}).get("k_harness", 0), curve.get(Q, {}).get("parseable", 0))}

# ---- 事前指定的檢查：qwen 不可解析票抽 12 張 ----
import random
rng = random.Random(522)
qun = [v for v in votes if v["model"] == Q and not v["parseable"]]
report["qwen_unparseable_sample"] = {
    "n_unparseable": len(qun),
    "sample": [{"run": v["run"], "task_id": v["task_id"], "vote_pass": v["vote_pass"],
                "resp": v["resp"][:400]} for v in rng.sample(qun, min(12, len(qun)))]}

report["fingerprints"] = {"n_review_votes_total": len(votes), "n_parseable": len(par),
                          "ds_sha8": hashlib.sha256(DS.read_bytes()).hexdigest()[:8]}
OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False))

# ---- 人看的摘要 ----
print("G1 (E1 ON rows-aligned):", report["G1"]["k"], "/", report["G1"]["n"],
      "A=%.4f" % report["G1"]["A"], "PASS" if report["G1"]["pass"] else "*** FAIL ***")
print("G1b:", "PASS" if report["G1b"]["pass"] else "*** FAIL ***",
      "unaligned parseable =", len(report["G1b"]["unaligned"]))
print()
print("=== A curve by reviewer model (harness) ===")
for m, d in sorted(curve.items(), key=lambda kv: -kv[1]["parseable"]):
    if d["parseable"] == 0:
        print(f"  {m:30s} parseable=0 / {d['total_votes']}"); continue
    lo, hi = d["wilson_harness"]
    print(f"  {m:30s} A={d['A_harness']:.4f} [{lo:.4f},{hi:.4f}] n={d['parseable']:4d}"
          f"  claim_rate={d['claim_rate']:.3f}  loose={d['A_loose']:.4f}")
print()
print("same-draft cells:", report["same_draft_cells"]["n_cells"])
for m in (G, Q):
    d = report["same_draft_cells"][m]
    print(f"  {m:30s} A={d['A']} n={d['n']} claim_rate={d['claim_rate']:.3f}")
print("paired both-claim:", report["paired_both_claim"]["n"],
      "b(gemma only)=", report["paired_both_claim"]["gemma_only_correct"],
      "c(qwen only)=", report["paired_both_claim"]["qwen_only_correct"],
      "p=%.4f" % report["paired_both_claim"]["mcnemar_exact_p"])
print("bank179:", {m: (report["bank179_only"][m]["k"], report["bank179_only"][m]["n"],
                       report["bank179_only"][m]["A"]) for m in (G, Q)})
print("persona range (n>=10): gemma", per[G]["_range_n>=10"], " qwen", per[Q]["_range_n>=10"])
print("two-prop p:", report["delta_gemma_minus_qwen"]["p_two_prop"])
print("total review votes:", len(votes), " parseable:", len(par))
