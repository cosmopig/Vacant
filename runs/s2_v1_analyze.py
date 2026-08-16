"""S2／S2F 的探針與主表（第 92 輪）。唯讀既有產物，零手打數字。

探針的用意：主結果會長成「某幾個預算綁得住、某幾個綁不住」，而
**「綁不住」與「預算參數根本沒接上」在 cells.jsonl 裡長得一樣**。
所以先給尺一個已知答案（兩個方向），過了才出主數字。
"""
import json, sys
from pathlib import Path
from collections import defaultdict

root = Path(sys.argv[1] if len(sys.argv) > 1 else "runs/s2_v1")
rows = lambda n: [json.loads(l) for l in (root/n/"rows.jsonl").read_text().splitlines() if l.strip()]
cells = lambda n: [json.loads(l) for l in (root/n/"cells.jsonl").read_text().splitlines() if l.strip()]
S2, S2F = rows("S2"), rows("S2F")
C2, C2F = cells("S2"), cells("S2F")

print("── 探針（四個方向；缺一不出主數字）──")
# P1 / P1′：早停軸是配對的（stop_when_budget_spent 在 _SEED_EXEMPT_FIELDS）
key = lambda r: (r["budget"], r["strategy"], r["seed"])
f_idx = {key(r): r for r in S2F}
pairs = [(r, f_idx[key(r)]) for r in S2 if key(r) in f_idx]
same_def = sum(1 for a, b in pairs if a["defected"] == b["defected"])
same_acc = sum(1 for a, b in pairs if a["accepted_bad"] == b["accepted_bad"])
same_dig = sum(1 for a, b in pairs if a["config_digest"] == b["config_digest"])
diff_exp = sum(1 for a, b in pairs if a["routed_to_attacker"] != b["routed_to_attacker"])
P1 = len(pairs) == 300 and same_def == same_acc == same_dig == len(pairs)
P1b = diff_exp > 0
print(f"  P1  S2 vs S2F 配對 {len(pairs)}/300 對（預算 1、2）：")
print(f"      defected 逐位相同 {same_def}/{len(pairs)} · accepted_bad 相同 {same_acc}/{len(pairs)}"
      f" · config_digest 相同 {same_dig}/{len(pairs)}   (必須全同)  → {P1}")
print(f"  P1′ 同 {len(pairs)} 對 routed_to_attacker **不同** {diff_exp} 對"
      f"   (必須 >0，否則早停旗標沒生效、P1 是白過的) → {P1b}")

# P2：尺本身有沒有分辨力——舊判準 <= 對新判準 ==
le_rates, eq_rates = {}, {}
by_cell = defaultdict(list)
for r in S2: by_cell[(r["budget"], r["strategy"])].append(r)
for k, rs in by_cell.items():
    le_rates[k] = sum(1 for r in rs if r["defected"] <= k[0]) / len(rs)
    eq_rates[k] = round(sum(1 for r in rs if r["defected"] == k[0]) / len(rs), 4)
n_le_one = sum(1 for v in le_rates.values() if v == 1.0)
distinct_eq = sorted(set(eq_rates.values()))
P2 = n_le_one == 30 and len(distinct_eq) >= 3
print(f"  P2  舊判準 `defected <= budget` ＝1.0 的格數 {n_le_one}/30   (必須 30 ⇒ 零分辨力)")
print(f"      新判準 `defected == budget` 跨格相異值 {len(distinct_eq)} 個："
      f"{distinct_eq}   (必須 ≥3) → {P2}")
# 與 cells.jsonl 自己算的 budget_bound_rate 對帳（重算不採信）
mismatch = sum(1 for c in C2 if eq_rates[(c["params"]["budget"], c["params"]["strategy"])]
               != c["budget_bound_rate"])
print(f"      重算 vs cells.jsonl 的 budget_bound_rate 不一致 {mismatch}/30   (必須 0)")
nulls = sum(1 for c in C2 if c.get("budget_bound_rate") is None)
print(f"  產物點數：S2 cells {len(C2)}/30 · rows {len(S2)}/900 · bound_rate 為 null {nulls}"
      f" ｜ S2F cells {len(C2F)}/10 · rows {len(S2F)}/300")
print(f"  探針總結：P1={P1} P1′={P1b} P2={P2 and mismatch==0}（P3 見 STATE.md，另跑）")
if not (P1 and P1b and P2 and mismatch == 0):
    print("  ⇒ 探針沒過，不出主數字"); sys.exit(1)

BUDGETS = [1, 2, 3, 4, 6, 12]
ARMS = ["whitewash", "patient", "sybil", "pulse(3,10)", "pulse(5,20)"]
print("\n── 主表 1：budget_bound_rate（`defected == budget` 的 seed 佔比，30 seeds）──")
print(f"  {'預算':>4} " + " ".join(f"{a:>12}" for a in ARMS) + f" {'5臂最小':>8}  窗口")
window = []
for b in BUDGETS:
    vs = [eq_rates[(b, a)] for a in ARMS]
    mn = min(vs)
    inw = mn >= 0.9
    if inw: window.append(b)
    print(f"  {b:>4} " + " ".join(f"{v:>12.4f}" for v in vs) + f" {mn:>8.4f}  {'✔ 在窗口' if inw else '✘'}")
print(f"  ⇒ 窗口（事前定死：5 臂取最小 ≥ 0.9）＝ {window}")

print("\n── 主表 2：等預算比較（S2F 全長，預算 1 與 2）──")
f_cells = {(c["params"]["budget"], c["params"]["strategy"]): c for c in C2F}
for b in (1, 2):
    print(f"  budget={b}")
    print(f"    {'臂':<12} {'作惡':>7} {'得手':>7} {'每次作惡得手率':>14} {'曝光':>9} {'身份數':>8} {'有效n':>6}")
    for a in ARMS:
        c = f_cells[(b, a)]
        d, ab = c["defected"]["mean"], c["accepted_bad"]["mean"]
        print(f"    {a:<12} {d:>7.4f} {ab:>7.4f} {ab/d:>14.4f} "
              f"{c['routed_to_attacker']['mean']:>9.2f} {c['identities_used']['mean']:>8.2f}"
              f" {c['accepted_bad']['n_effective']:>6}")

print("\n── 事前押的六格對帳 ──")
r1 = all(eq_rates[(12, a)] < 0.9 for a in ("patient", "pulse(3,10)", "pulse(5,20)"))
r2 = len(window) > 0 and 1 in window
r3 = all(all(eq_rates[(BUDGETS[i], a)] >= eq_rates[(BUDGETS[i+1], a)]
             for i in range(len(BUDGETS)-1)) for a in ARMS)
ww1, pu1 = f_cells[(1, "whitewash")]["accepted_bad"]["mean"], f_cells[(1, "pulse(3,10)")]["accepted_bad"]["mean"]
r4 = (ww1 / pu1) < 2.0
ww_id = f_cells[(1, "whitewash")]["identities_used"]["mean"]
others = {a: f_cells[(1, a)]["identities_used"]["mean"] for a in ARMS if a not in ("whitewash", "sybil")}
r5 = all(ww_id >= 2 * v for v in others.values())
print(f"  R1 預算12 綁不住 patient/pulse（<0.9）: "
      f"{ {a: eq_rates[(12,a)] for a in ('patient','pulse(3,10)','pulse(5,20)')} } → {r1}")
print(f"  R2 窗口非空且含預算 1: 窗口={window} → {r2}")
print(f"  R3 每臂 bound_rate 隨預算單調不增 → {r3}")
print(f"  R4 whitewash/pulse(3,10) 的 accepted_bad 比值 < 2.0: "
      f"{ww1:.4f}/{pu1:.4f} = {ww1/pu1:.4f} → {r4}")
print(f"  R5 whitewash identities_used ≥ 非 sybil 各臂的 2 倍: "
      f"{ww_id:.2f} vs { {k: round(v,2) for k,v in others.items()} } → {r5}")
