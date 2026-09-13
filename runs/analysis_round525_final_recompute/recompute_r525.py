#!/usr/bin/env python3
"""round525：用 s1_votes_r523.jsonl 的 `final`（S1 解包裝後的正確性判定）重算
R522 的三個次要切法——281 同初稿 cell、persona 分層、bank179 限定跑。

不是新量測：join 既有兩份落盤產物，不重新解析 prompt、不重跑參考解。

key = (run, arm, task_id, agent_id, model)。round523 已驗證這個 join 對
gemma/qwen 有 413/415 可解析票對得上（缺 2 張是 cline-pass 模型，S1 腳本本來就
沒處理，不影響本輪）。
"""
import json, math, collections, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
RUNS = ROOT / "runs"
HERE = pathlib.Path(__file__).parent

v522 = [json.loads(l) for l in open(RUNS / "analysis_round522_acurve/votes_r522.jsonl")]
v523 = [json.loads(l) for l in open(RUNS / "analysis_round523_audit/s1_votes_r523.jsonl")]

def key(v):
    return (v["run"], v["arm"], v["task_id"], v["agent_id"], v["model"])

final_by_key = {key(v): v["final"] for v in v523}

G, Q = "gemma-4-12b-it-qat", "qwen/qwen3.6-35b-a3b"
par = [v for v in v522 if v["parseable"] and v["model"] in (G, Q)]

n_joined = sum(1 for v in par if key(v) in final_by_key)
n_missing = len(par) - n_joined
for v in par:
    v["final"] = final_by_key.get(key(v))
    v["final_ok"] = (v["final"] == "ok")

def wilson(k, n, z=1.959963985):
    if n == 0:
        return (0.0, 1.0)
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))

def two_prop_p(k1, n1, k2, n2):
    if n1 == 0 or n2 == 0:
        return None
    p = (k1 + k2) / (n1 + n2); se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    if se == 0:
        return 1.0
    z = (k1 / n1 - k2 / n2) / se
    return math.erfc(abs(z) / math.sqrt(2))

def A(sel):
    s = [v for v in par if sel(v)]
    k = sum(1 for v in s if v["final_ok"])
    return {"k": k, "n": len(s), "A": (k / len(s) if s else None), "wilson": wilson(k, len(s))}

report = {"join": {"n_par_gq": len(par), "n_joined": n_joined, "n_missing_from_s1": n_missing}}

# ---- 主曲線（final 版）----
report["curve_final"] = {mdl: A(lambda v, m=mdl: v["model"] == m) for mdl in (G, Q)}
report["delta_gemma_minus_qwen_final"] = two_prop_p(
    report["curve_final"][G]["k"], report["curve_final"][G]["n"],
    report["curve_final"][Q]["k"], report["curve_final"][Q]["n"])

# ---- (1) 281 個同初稿 cell，final 版 ----
# 沿用 R522 的 cell 定義：cell 成員資格看「全部票」(v522, 不限 parseable)，
# 只有算 A 時才收斂到 parseable 子集——這裡再收斂到有 final 資料的子集。
all_gq = [v for v in v522 if v["model"] in (G, Q)]
cells_all = collections.defaultdict(lambda: collections.defaultdict(list))
for v in all_gq:
    cells_all[(v["run"], v["arm"], v["task_id"])][v["model"]].append(v)
both_cells = [c for c, d in cells_all.items() if G in d and Q in d]
assert len(both_cells) == 281, f"cell 定義偏離 R522：算出 {len(both_cells)} 不是 281"

# 建 (run, arm, task_id) -> final-augmented parseable votes 的索引，只需查表即可
par_by_cell = collections.defaultdict(lambda: collections.defaultdict(list))
for v in par:
    par_by_cell[(v["run"], v["arm"], v["task_id"])][v["model"]].append(v)

def A_cells_final(mdl):
    s = [v for c in both_cells for v in par_by_cell[c][mdl]]
    k = sum(1 for v in s if v["final_ok"])
    n_total_in_cells = sum(len(cells_all[c][mdl]) for c in both_cells)
    return {"k": k, "n": len(s), "A": (k / len(s) if s else None), "wilson": wilson(k, len(s)),
            "claim_rate": len(s) / n_total_in_cells if n_total_in_cells else None}

report["same_draft_cells_final"] = {"n_cells": len(both_cells), G: A_cells_final(G), Q: A_cells_final(Q)}

# ---- (3) bank179 限定，final 版 ----
bank179 = {r.name for r in RUNS.iterdir() if (r / "summary.json").exists()
           and json.load(open(r / "summary.json")).get("n") == 179}
report["bank179_only_final"] = {mdl: A(lambda v, m=mdl: v["model"] == m and v["run"] in bank179) for mdl in (G, Q)}

# ---- (4) persona 分層，final 版 ----
per = {}
for mdl in (G, Q):
    per[mdl] = {}
    for p in sorted({v["persona"] for v in par if v["model"] == mdl}):
        d = A(lambda v, m=mdl, pp=p: v["model"] == m and v["persona"] == pp)
        per[mdl][p] = d
    vals = [d["A"] for d in per[mdl].values() if d["n"] >= 10 and d["A"] is not None]
    per[mdl]["_range_n>=10"] = (max(vals) - min(vals)) if len(vals) >= 2 else None
report["persona_final"] = per

with open(HERE / "recompute_r525.json", "w") as fh:
    json.dump(report, fh, indent=2, ensure_ascii=False)
print(json.dumps(report, indent=2, ensure_ascii=False))
