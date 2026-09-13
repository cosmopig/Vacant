#!/usr/bin/env python3
"""R518：反例否決（L1v）在 E1 落盤資料上的**精確重放**。

判準寫在 DECISION_20260902_R518_COUNTEREXAMPLE_VETO_REPLAY.md，先 commit 才跑這支。
零 API 呼叫：revise 在 E1 是無條件呼叫的，每題的 revised_code 都已在 calls.jsonl。
"""
import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from ops.gain.gain_run import load_tasks, meets_demand, extract_code  # noqa: E402

RUN = ROOT / "runs/g_r441_gemma_only_mbpp_b"
rows = [json.loads(l) for l in open(RUN / "rows.jsonl")]
on = [r for r in rows if r["arm"] == "ON"]
calls = [json.loads(l) for l in open(RUN / "calls.jsonl")]
summ = json.load(open(RUN / "summary.json"))

tasks = {t["task_id"]: t for t in load_tasks("evalplus", summ["seed"], summ["n"])}
print(f"bank tasks loaded: {len(tasks)}  ON rows: {len(on)}")


def select(passed_review, ivo, rvo, rfc, veto_on_cec, cec):
    """arm_on 的選擇分支。veto_on_cec=False ⇒ 現行邏輯；True ⇒ L1v。"""
    first = passed_review and ivo and (not (veto_on_cec and cec > 0))
    if first:
        return "initial"
    if rvo and rfc:
        return "revised"
    if ivo:
        return "initial_fallback"
    if rvo:
        return "revised_unconfirmed_fallback"
    return "revised_both_visible_fail"


# ── G2：用 rows 的欄位重建**現行**選擇，必須逐題逐字元相同 ──────────────
g2_bad = [r["task_id"] for r in on
          if select(r["passed_review"], r["initial_visible_ok"], r["revised_visible_ok"],
                    r["revised_fixes_counterexamples"], False,
                    r["confirmed_counterexample_count"]) != r["selected_version"]]
print(f"\nG2 (rebuild current selection) mismatches: {len(g2_bad)}  {g2_bad[:10]}")
if g2_bad:
    sys.exit("G2 != 0 ⇒ 重放作廢（我對選擇邏輯的理解是錯的）")

# ── 從 calls.jsonl 取每題的 initial_code / revised_code ────────────────
def banked(role):
    out = {}
    for c in calls:
        m = c.get("meta") or {}
        if m.get("arm") != "ON" or c.get("role") != role or not c.get("ok"):
            continue
        out.setdefault(m["task_id"], []).append(c["response"])
    return out

gen, rev = banked("gen"), banked("revise")
dup = {k: len(v) for k, v in {**{f"gen:{k}": v for k, v in gen.items()},
                              **{f"rev:{k}": v for k, v in rev.items()}}.items() if len(v) > 1}
print(f"banked ON gen tasks={len(gen)} revise tasks={len(rev)} duplicates={dup}")

# ── G3（額外守恆量）：重算 initial 真值，必須等於 rows 的 initial_meets_demand ──
g3_bad, init_truth, rev_truth = [], {}, {}
for r in on:
    tid = r["task_id"]
    t = tasks[tid]
    ic = extract_code(gen[tid][0])
    ok, _ = meets_demand(ic, t["hidden_check"]["code"], entry_point=t.get("entry_point"))
    init_truth[tid] = ok
    if ok != r["initial_meets_demand"]:
        g3_bad.append(tid)
print(f"\nG3 (recomputed initial truth vs rows) mismatches: {len(g3_bad)}  {g3_bad[:10]}")

for r in on:
    tid = r["task_id"]
    t = tasks[tid]
    rc = extract_code(rev[tid][0])
    ok, _ = meets_demand(rc, t["hidden_check"]["code"], entry_point=t.get("entry_point"))
    rev_truth[tid] = ok

# ── 重放 L1v ──────────────────────────────────────────────────────────
def truth_of(r, sel):
    return init_truth[r["task_id"]] if sel.startswith("initial") else rev_truth[r["task_id"]]

churn, g1_bad, b, c, harm, gain = [], [], 0, 0, [], []
for r in on:
    old = r["selected_version"]
    new = select(r["passed_review"], r["initial_visible_ok"], r["revised_visible_ok"],
                 r["revised_fixes_counterexamples"], True,
                 r["confirmed_counterexample_count"])
    if r["confirmed_counterexample_count"] == 0 and new != old:
        g1_bad.append(r["task_id"])
    old_truth = r["meets_demand"]
    new_truth = truth_of(r, new)
    if new != old:
        churn.append((r["task_id"], old, new, old_truth, new_truth))
    if new_truth and not old_truth:
        b += 1; gain.append(r["task_id"])
    elif old_truth and not new_truth:
        c += 1; harm.append(r["task_id"])

print(f"\nG1 (cec==0 tasks must not change selection) mismatches: {len(g1_bad)}  {g1_bad[:10]}")

# 交付真值一致性：現行政策下重算的交付真值必須等於 rows 的 meets_demand
recon_bad = [r["task_id"] for r in on if truth_of(r, r["selected_version"]) != r["meets_demand"]]
print(f"G4 (recomputed delivered truth under CURRENT policy vs rows) mismatches: "
      f"{len(recon_bad)}  {recon_bad[:10]}")

n = len(on)
old_rate = sum(r["meets_demand"] for r in on) / n
new_rate = sum(truth_of(r, select(r["passed_review"], r["initial_visible_ok"],
                                  r["revised_visible_ok"], r["revised_fixes_counterexamples"],
                                  True, r["confirmed_counterexample_count"])) for r in on) / n
print(f"\n=== L1v replay (n={n}) ===")
print(f"churn (selection changed): {len(churn)}/{n}")
for row in churn:
    print(f"   {row[0]:22s} {row[1]:28s} -> {row[2]:28s} truth {row[3]} -> {row[4]}")
print(f"\nE1 actual   correct delivery: {old_rate*100:.2f}%  ({sum(r['meets_demand'] for r in on)}/{n})")
print(f"L1v replay  correct delivery: {new_rate*100:.2f}%")
print(f"paired  b (L1v right, E1 wrong) = {b}  {gain}")
print(f"        c (E1 right, L1v wrong) = {c}  {harm}")
print(f"        diff = {(b-c)/n*100:+.2f}pp")

try:
    from vacant.research import mcnemar_exact
    print(f"McNemar exact p = {mcnemar_exact(b, c):.4f}  (報告用，不當閘門)")
except Exception as e:
    print(f"mcnemar_exact unavailable: {e}")

# ── 反例精度 ──────────────────────────────────────────────────────────
a = summ["arms"]["ON"]
cc, cw = a.get("confirmed_claims"), a.get("confirmed_on_wrong")
print(f"\ncounterexample precision: confirmed_on_wrong/confirmed_claims = {cw}/{cc}"
      f" = {cw/cc:.4f}" if cc else "\nconfirmed_claims missing from summary")

json.dump({"n": n, "b": b, "c": c, "gain": gain, "harm": harm,
           "churn": churn, "old_rate": old_rate, "new_rate": new_rate,
           "g1": g1_bad, "g2": g2_bad, "g3": g3_bad, "g4": recon_bad,
           "confirmed_claims": cc, "confirmed_on_wrong": cw},
          open(pathlib.Path(__file__).parent / "replay_r518.json", "w"),
          ensure_ascii=False, indent=2)
