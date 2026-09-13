"""S4 的探針與主表（第 94 輪）。唯讀既有產物，零手打數字。

問的是一件事：**拉長 `rounds` 買不買得到相位週期？**

S3（第 93 輪）量到 35/75 格的 `(burst, recover)` 根本沒被實現——相位鐘走在
「第幾次被路由」上，而防禦把 600 輪裡的曝光壓到 6.10–51.77 次。修法有兩條，
本段只量第一條（拉長 rounds），第二條（改用輪次推進相位）要動模型語意。

**這裡沒有配對比較。** `rounds` 進 `digest()`（不在 `_LATER_FIELDS` 也不在
`_SEED_EXEMPT_FIELDS`）⇒ 換一個 rounds 就是換一整個隨機世界。好處是它給了
P1 一個逐位可驗的已知答案：`rounds=600` 那幾格必須與 S3 完全相等。

週期尺沿用 S3 第 93 輪的定義，不重新發明：

    cycles = routed_to_attacker / (burst + recover)

用法：PYTHONPATH=.:examples python3 runs/s4_v1_analyze.py runs/s4_v1
"""
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else "runs/s4_v1")
S3 = Path("runs/s3_v1/S3/rows.jsonl")
R = [json.loads(l) for l in (root / "S4" / "rows.jsonl").read_text().splitlines() if l.strip()]
C = [json.loads(l) for l in (root / "S4" / "cells.jsonl").read_text().splitlines() if l.strip()]
MAN = json.loads((root / "S4" / "manifest.json").read_text())

ROUNDS = sorted({r["rounds_n"] for r in R})
BLINDS = sorted({r["blindspot"] for r in R})
BRS = sorted({(r["burst"], r["recover"]) for r in R})
key = lambda r: (r["rounds_n"], r["blindspot"], r["burst"], r["recover"])
by_cell = defaultdict(list)
for r in R:
    by_cell[key(r)].append(r)

mean = lambda v: st.mean(v) if v else float("nan")
expo = lambda k: mean([r["routed_to_attacker"] for r in by_cell[k]])
cycles = lambda k: expo(k) / (k[2] + k[3])

ok = {}
print("── 探針（四條 ＋ 一條定義；每條兩個方向，缺一不出主數字）──")

# ── P1 rounds 真的接上了（兩個方向）──────────────────────────────────
# 一定看不見那邊：rounds=600 的四格 × 30 seeds 必須與 S3 **逐位相同**
#   （同 rounds 同設定 ⇒ 同 digest ⇒ 同一個隨機世界）。
# 一定看得見那邊：同一 (blind,b,r,seed) 下五個 rounds 必須給五個相異 digest。
FIELDS = ("routed_to_attacker", "defected", "accepted_bad", "config_digest")
s3rows = {}
if S3.exists():
    for l in S3.read_text().splitlines():
        if l.strip():
            d = json.loads(l)
            s3rows[(d["blindspot"], d["burst"], d["recover"], d["seed"])] = d
n_cmp = n_bad = 0
for r in R:
    if r["rounds_n"] != 600:
        continue
    o = s3rows.get((r["blindspot"], r["burst"], r["recover"], r["seed"]))
    if o is None:
        continue                       # (0,10) 對照組不在 S3 網格裡，本來就沒得對
    n_cmp += 1
    if any(r[f] != o[f] for f in FIELDS):
        n_bad += 1
dig = defaultdict(set)
for r in R:
    dig[(r["blindspot"], r["burst"], r["recover"], r["seed"])].add(r["config_digest"])
n_full = sum(1 for v in dig.values() if len(v) == len(ROUNDS))
r600 = {r["config_digest"] for r in R if r["rounds_n"] == 600}
collide = sum(1 for r in R if r["rounds_n"] != 600 and r["config_digest"] in r600)
ok["P1"] = n_cmp > 0 and n_bad == 0 and n_full == len(dig) and collide == 0
print(f"  P1  rounds=600 對 S3 逐位相同：比對 {n_cmp} 行、不同 {n_bad}（必須 0）")
print(f"      每組 (blind,b,r,seed) 的 {len(ROUNDS)} 個 rounds 給 {len(ROUNDS)} 個相異 digest："
      f"{n_full}/{len(dig)} 組 · rounds≠600 撞上 rounds=600 digest 的 {collide} 行（必須 0）"
      f" → {ok['P1']}")

# ── P2 對照組的已知答案（兩個方向）────────────────────────────────────
# 一定看不見：(0,r) 的 `_should_defect` 回 `0 < 0` 恆假 ⇒ 作惡/得手/被抓全 0。
# 一定看得見：它沒有東西可罰 ⇒ 曝光必須隨 rounds 嚴格遞增、9600/600 ≥12。
ctl = [r for r in R if r["burst"] == 0]
p2a = sum(1 for r in ctl if r["defected"] or r["accepted_bad"] or r["caught"])
ctl_series, p2b_mono, p2b_ratio = {}, True, {}
for bl in BLINDS:
    ks = [(n, bl, 0, 10) for n in ROUNDS]
    ser = [expo(k) for k in ks]
    ctl_series[bl] = ser
    p2b_mono &= all(a < b for a, b in zip(ser, ser[1:]))
    p2b_ratio[bl] = ser[-1] / ser[0] if ser[0] else float("nan")
ok["P2"] = (p2a == 0 and p2b_mono and all(v >= 12 for v in p2b_ratio.values()))
print(f"  P2  對照組 {len(ctl)} 行的 作惡/得手/被抓 非零者：{p2a}（必須 0，讀程式就知道的答案）")
for bl in BLINDS:
    print(f"      blind={bl} 曝光隨 rounds：{'→'.join(f'{v:.1f}' for v in ctl_series[bl])}"
          f"  ＝{p2b_ratio[bl]:.2f} 倍（線性上限 {ROUNDS[-1] / ROUNDS[0]:.0f} 倍，必須 ≥12）")
print(f"      嚴格遞增 {p2b_mono} → {ok['P2']}")

# ── P3 分解恆等式（沿用 S3）──────────────────────────────────────────
p3a = sum(1 for r in R
          if not (r["accepted_bad"] <= r["defected"] <= r["routed_to_attacker"]))
p3b = sum(1 for r in R if r["routed_to_attacker"]
          and abs(r["bad_per_route"] - r["accepted_bad"] / r["routed_to_attacker"]) > 5e-5)
ok["P3"] = p3a == 0 and p3b == 0
print(f"  P3  ac≤de≤ro 違反 {p3a}/{len(R)} · 落盤 bad_per_route 對不上 {p3b} → {ok['P3']}")

# ── P4 格內不退化 ────────────────────────────────────────────────────
# 事前登記寫的是「每格 30 seeds 的曝光不得全部相同」。對照組會**照定義**違反
# 這一條（它從不作惡 ⇒ 從不被抓 ⇒ 沒有 seed 相依的分歧），所以攻擊者格與
# 對照組分開報，兩個數字都印出來，不合併成一個好看的通過率。
atk = [k for k in by_cell if k[2] != 0]
ctlk = [k for k in by_cell if k[2] == 0]
deg_a = [k for k in atk if len({r["routed_to_attacker"] for r in by_cell[k]}) == 1]
deg_c = [k for k in ctlk if len({r["routed_to_attacker"] for r in by_cell[k]}) == 1]
ok["P4"] = len(deg_a) == 0
print(f"  P4  攻擊者 {len(atk)} 格：曝光全同（n_effective=1）的 {len(deg_a)} 格 → {ok['P4']}")
print(f"      對照組 {len(ctlk)} 格：{len(deg_c)} 格 n_effective=1 ⚠（照定義如此，"
      f"它的 sd 不當精準用；本段只用它的 mean 當線性尺）")

# ── P5 是定義不是判準：逐格印出週期數 ─────────────────────────────────
print(f"  P5  cycles ＝ 曝光/(b+r)，與 S3 第 93 輪同一個定義（有印＝過）")

if not all(ok.values()):
    print(f"\n⚠ 探針未全過：{ {k: v for k, v in ok.items()} } —— 主數字照出，但要標。")

# ── 主表：曝光 × rounds ──────────────────────────────────────────────
print(f"\n── 主表：曝光（30 seeds mean）與週期數，逐格實測 ──")
print(f"  {'(b,r)':<8}{'blind':<7}" + "".join(f"{'r=' + str(n):>18}" for n in ROUNDS)
      + f"{'S=9600/600':>12}")
S = {}
for b, r in BRS:
    for bl in BLINDS:
        cells_ = [(n, bl, b, r) for n in ROUNDS]
        e = [expo(k) for k in cells_]
        c = [cycles(k) for k in cells_]
        S[(b, r, bl)] = e[-1] / e[0] if e[0] else float("nan")
        print(f"  {f'({b},{r})':<8}{bl:<7}"
              + "".join(f"{v:>10.2f}/{cy:>6.2f}" for v, cy in zip(e, c))
              + f"{S[(b, r, bl)]:>12.2f}")
print("     格式＝曝光/週期數。S ≥8 ⇒ 拉長 rounds 可行；S ≤4 ⇒ 不可行（事前登記的判準）")

# ── 主判準 4：正面回答 ───────────────────────────────────────────────
print(f"\n── 拉長 rounds 買不買得到週期？（事前寫死的判準）──")
for (b, r, bl), s in sorted(S.items()):
    tag = "可行" if s >= 8 else ("不可行" if s <= 4 else "部分可行")
    role = "對照組" if b == 0 else "攻擊者"
    reach = [n for n in ROUNDS if cycles((n, bl, b, r)) >= 3.0]
    got = f"rounds={reach[0]} 起達標" if reach else f"{ROUNDS[-1]} 輪仍未達 3 週期"
    print(f"  ({b},{r}) blind={bl:<4} {role}  S={s:>6.2f} ⇒ {tag:<6} · cycles≥3：{got}")

# ── R5：nominal 作惡率在「只動 rounds」這個獨立軸上還成不成立 ──────────
# 第 93 輪的機制解釋（週期跑不完 ⇒ nominal 不成立）是在改 (b,r) 的軸上量的，
# 而 (b,r) 同時決定 nominal 本身——解釋與被解釋物共軸。這裡固定 (b,r)、只動
# rounds，nominal 完全不變 ⇒ 那個解釋第一次被獨立軸檢驗。
print(f"\n── R5：實測作惡率 vs nominal b/(b+r)，按週期數分桶（只動 rounds，nominal 不變）──")
buckets = defaultdict(list)
for k in atk:
    n, bl, b, r = k
    de = sum(x["defected"] for x in by_cell[k])
    ro = sum(x["routed_to_attacker"] for x in by_cell[k])
    if not ro:
        continue
    nom = b / (b + r)
    err = abs(de / ro - nom) / nom
    cy = cycles(k)
    bk = "<1 個" if cy < 1 else ("1–2 個" if cy < 2 else ("2–3 個" if cy < 3 else "≥3 個"))
    buckets[bk].append((err, k, de / ro, nom, cy))
print(f"  {'跑完週期數':<10}{'格數':>5}{'|相對誤差|中位數':>18}{'最大':>10}")
for bk in ("<1 個", "1–2 個", "2–3 個", "≥3 個"):
    v = buckets.get(bk, [])
    if not v:
        print(f"  {bk:<10}{0:>5}{'—':>18}{'—':>10}")
        continue
    e = sorted(x[0] for x in v)
    print(f"  {bk:<10}{len(v):>5}{st.median(e) * 100:>17.1f}%{max(e) * 100:>9.1f}%")
hi = buckets.get("≥3 個", [])
r5 = st.median([x[0] for x in hi]) < 0.25 if hi else None
print(f"  R5（cycles≥3 的中位數 <25%）：{r5}"
      + ("" if hi else " —— 沒有任何一格達到 3 週期 ⇒ R5 在本輪無從檢驗"))
for err, k, act, nom, cy in sorted(hi):
    print(f"    {k}  實測 {act:.4f}  nominal {nom:.4f}  誤差 {err * 100:.1f}%  週期 {cy:.2f}")

# ── 追加 A（不在事前登記；零額外機時，只讀同一份 rows.jsonl）─────────
# 主表只說「飽和」。飽和是後果，這裡問成因：曝光是**什麼時候**停住的。
# 事前登記沒問這一題，是主表出來之後才問的，所以另立一節、不混進主判準。
print(f"\n── 追加 A：曝光是什麼時候停住的（不在事前登記）──")
print(f"  {'(b,r)':<8}{'blind':<7}{'rounds':>7}{'被slash':>8}{'首次slash輪':>12}"
      f"{'slash後還剩':>12}{'slash後路由':>12}{'回來過':>8}")
for b, r in BRS:
    if b == 0:
        continue
    for bl in BLINDS:
        for n in ROUNDS:
            v = by_cell[(n, bl, b, r)]
            sl = [x for x in v if x["first_slash_round"] is not None]
            back = [x for x in sl if x["routes_after_slash"]]
            print(f"  {f'({b},{r})':<8}{bl:<7}{n:>7}{len(sl):>6}/{len(v):<2}"
                  f"{mean([x['first_slash_round'] for x in sl]):>12.1f}"
                  f"{mean([x['rounds_after_slash'] for x in sl]):>12.1f}"
                  f"{mean([x['routes_after_slash'] for x in sl]):>12.3f}"
                  f"{len(back):>8}")
print("     『slash後還剩』＝被 slash 之後這一格還有幾輪可用（＝rounds − 首次slash輪）。")
print("     這一欄從幾百漲到近萬而『slash後路由』沒動 ⇒ 曝光不是被輪數用完的。")

# ── 產物點數（只數產物，不看返回值）──────────────────────────────────
exp_cells = len(ROUNDS) * len(BLINDS) * len(BRS)
print(f"\n── 產物點數 ──")
print(f"  cells {len(C)}/{exp_cells} · rows {len(R)}/{exp_cells * len(MAN['seeds'])}"
      f" · manifest.complete={MAN.get('complete')}")
