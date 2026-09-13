#!/usr/bin/env python3
"""round212: decompose ON's 5-call budget.

Contrast A: ON.initial_meets_demand (1 UCB-routed call) vs OFF.meets_demand (1 random call).
Contrast B: ON.meets_demand (5 calls) vs ON.initial_meets_demand (1 call), same row.

Zero model calls; reads only already-landed rows.jsonl. McNemar exact both ways.
"""
import json, sys, pathlib
from math import comb

ON_RUN = "runs/g_onoff5_371_r123_20260825"
OFF_RUN = "runs/g_off371_20260825"


def load(run, arm):
    out = {}
    for line in open(pathlib.Path(run) / "rows.jsonl"):
        r = json.loads(line)
        if r.get("arm") == arm:
            out[r["task_id"]] = r
    return out


def mcnemar_exact(b, c):
    """Two-sided exact binomial on discordant pairs."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def contrast(name, pairs, a_label, b_label):
    """pairs: list of (a_ok, b_ok). b = a wins, c = b wins."""
    b = sum(1 for x, y in pairs if x and not y)
    c = sum(1 for x, y in pairs if y and not x)
    both = sum(1 for x, y in pairs if x and y)
    neither = sum(1 for x, y in pairs if not x and not y)
    n = len(pairs)
    p = mcnemar_exact(b, c)
    print(f"--- {name} ---")
    print(f"  n_paired      = {n}")
    print(f"  {a_label:<22} = {sum(1 for x,_ in pairs if x)}/{n} = {sum(1 for x,_ in pairs if x)/n*100:.2f}%")
    print(f"  {b_label:<22} = {sum(1 for _,y in pairs if y)}/{n} = {sum(1 for _,y in pairs if y)/n*100:.2f}%")
    print(f"  both_ok={both}  neither_ok={neither}")
    print(f"  b (only {a_label} ok) = {b}")
    print(f"  c (only {b_label} ok) = {c}")
    print(f"  discordant b+c = {b+c}")
    print(f"  mcnemar_exact_p = {p:.4f}")
    return {"n_paired": n, "b": b, "c": c, "discordant": b + c, "p": p,
            "a_rate": sum(1 for x, _ in pairs if x) / n,
            "b_rate": sum(1 for _, y in pairs if y) / n}


on = load(ON_RUN, "ON")
off = load(OFF_RUN, "OFF")
off5 = load(ON_RUN, "OFF5")

# ---- 量具自檢：先對帳，不符就停 ----
summ = json.load(open(pathlib.Path(ON_RUN) / "summary.json"))
summ_off = json.load(open(pathlib.Path(OFF_RUN) / "summary.json"))
on_rate = sum(1 for r in on.values() if r["meets_demand"]) / len(on)
off_rate = sum(1 for r in off.values() if r["meets_demand"]) / len(off)
off5_rate = sum(1 for r in off5.values() if r["meets_demand"]) / len(off5)
print("=== 量具自檢（rows.jsonl 自算 vs summary.json）===")
KEY = "correct_delivery_rate"
for lbl, mine, s in (("ON", on_rate, summ["arms"]["ON"]),
                     ("OFF5", off5_rate, summ["arms"]["OFF5"]),
                     ("OFF", off_rate, summ_off["arms"]["OFF"])):
    if KEY not in s or s[KEY] is None:
        sys.exit(f"BROKEN：{lbl} 的 summary.json 沒有 {KEY} ⇒ 自檢量不到，停")
    ref = s[KEY]
    n = {"ON": on, "OFF5": off5, "OFF": off}[lbl]
    print(f"  {lbl:<5} rows={mine:.10f}  summary={ref:.10f}  n_rows={len(n)}")
    if abs(mine - ref) > 1e-9:
        sys.exit(f"量具自檢失敗：{lbl} rows={mine} vs summary={ref}  ⇒ 停，不做對比")
# 逐鍵比對 revision_transitions（ON 專屬），不比整檔
_tr_ref = summ["arms"]["ON"].get("revision_transitions")
_tr_mine = {}
for r in on.values():
    _tr_mine[r["revision_transition"]] = _tr_mine.get(r["revision_transition"], 0) + 1
if _tr_ref is None:
    sys.exit("BROKEN：ON 的 summary.json 沒有 revision_transitions ⇒ 自檢量不到，停")
for k in set(_tr_ref) | set(_tr_mine):
    if _tr_ref.get(k, 0) != _tr_mine.get(k, 0):
        sys.exit(f"量具自檢失敗：revision_transitions[{k}] rows={_tr_mine.get(k,0)} vs summary={_tr_ref.get(k,0)}")
print(f"  revision_transitions 逐鍵相符：{_tr_mine}")
print("  自檢通過 ✓\n")

res = {}
# ---- 對比 A：路由 ----
keys_a = sorted(set(on) & set(off))
pairs_a = [(on[k]["initial_meets_demand"], off[k]["meets_demand"]) for k in keys_a]
print(f"(對比A 配對：ON rows={len(on)}, OFF rows={len(off)}, 交集={len(keys_a)}, "
      f"ON獨有={len(set(on)-set(off))}, OFF獨有={len(set(off)-set(on))})")
res["A_routing"] = contrast("對比A 路由：ON_initial(1呼叫,UCB) vs OFF(1呼叫,隨機)",
                            pairs_a, "ON_initial", "OFF")
print()
# ---- 對比 B：審查+修訂 ----
pairs_b = [(r["meets_demand"], r["initial_meets_demand"]) for r in on.values()]
res["B_review_revise"] = contrast("對比B 審查+修訂：ON_final(5呼叫) vs ON_initial(1呼叫)",
                                  pairs_b, "ON_final", "ON_initial")
tr = {}
for r in on.values():
    tr[r["revision_transition"]] = tr.get(r["revision_transition"], 0) + 1
print(f"  revision_transitions = {tr}")
print(f"  selected_version     = " + str({v: sum(1 for r in on.values() if r['selected_version'] == v)
                                          for v in sorted({r['selected_version'] for r in on.values()})}))
res["transitions"] = tr
print()
print("=== 參考：三臂交付率（同一份 rows，未配對）===")
print(f"  OFF(1呼叫)={off_rate*100:.2f}%  ON_initial(1呼叫)={sum(1 for r in on.values() if r['initial_meets_demand'])/len(on)*100:.2f}%"
      f"  ON_final(5呼叫)={on_rate*100:.2f}%  OFF5(5呼叫)={off5_rate*100:.2f}%")
json.dump(res, open("runs/_analysis_r212/decomp.json", "w"), indent=2)
