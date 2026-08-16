"""S3 的探針與主表（第 93 輪）。唯讀既有產物，零手打數字。

探針的用意：主結果會長成「某些盲區上時間結構有效應、某些沒有」，而
**「這個盲區上效應真的是零」與「盲區參數根本沒接上」在 cells.jsonl 裡長得一樣**
——2026-08-06 複驗推翻 E24 靠的正是這個區分。所以先給尺已知答案（每條兩個方向），
過了才出主數字。

分解是三層不是兩層（事前登記，跑完不准換）：

    得手 = 曝光 × 作惡率(defected/routed) × 逃脫率(accepted_bad/defected)

格內用**和的比**（ratio-of-sums）而不是「每 seed 比值再平均」——前者讓恆等式在
格層級逐位成立，後者不會，而「分解得出來」正是紀律 1 要的東西。

用法：PYTHONPATH=.:examples python3 runs/s3_v1_analyze.py runs/s3_v1
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else "runs/s3_v1")
R = [json.loads(l) for l in (root / "S3" / "rows.jsonl").read_text().splitlines() if l.strip()]
C = [json.loads(l) for l in (root / "S3" / "cells.jsonl").read_text().splitlines() if l.strip()]
MAN = json.loads((root / "S3" / "manifest.json").read_text())

BLINDS = sorted({r["blindspot"] for r in R})
BRS = sorted({(r["burst"], r["recover"]) for r in R})
key = lambda r: (r["blindspot"], r["burst"], r["recover"])
by_cell = defaultdict(list)
for r in R:
    by_cell[key(r)].append(r)

ok = {}
print("── 探針（五條，缺一不出主數字）──")

# ── P1 參數真的接上了（兩個方向）──────────────────────────────────────
# 一定看不見那邊：(3,10)·blind=0.0 三個參數全預設 ⇒ digest 必須等於裸 pulse。
# 一定看得見那邊：其餘 74 格必須全部相異於它，且 75 個 digest 互不相同。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from vacant.entrycost import SimConfig                                  # noqa: E402

rounds = MAN["rounds"]
base = {s: SimConfig(rounds=rounds, seed=s, strategy="pulse").digest() for s in MAN["seeds"]}
dflt_rows = [r for r in R if key(r) == (0.0, 3, 10)]
p1_same = sum(1 for r in dflt_rows if r["config_digest"] == base[r["seed"]])
cell_dig = {k: v[0]["config_digest"] for k, v in by_cell.items()}
n_eq_base = sum(1 for k, d in cell_dig.items()
                if k != (0.0, 3, 10) and d in base.values())
n_distinct = len(set(cell_dig.values()))
ok["P1"] = (p1_same == len(dflt_rows) > 0 and n_eq_base == 0
            and n_distinct == len(cell_dig))
print(f"  P1  (3,10)·blind=0.0 的 digest ＝裸 pulse：{p1_same}/{len(dflt_rows)} 行（必須全同）")
print(f"      其餘 {len(cell_dig)-1} 格撞上裸 pulse digest 的：{n_eq_base}（必須 0）"
      f" · 75 格相異 digest {n_distinct}/{len(cell_dig)}（必須全異） → {ok['P1']}")

# ── P2 盲區真的作用了（驗後果不驗前提）────────────────────────────────
z = [r for r in R if r["blindspot"] == 0.0]
p2a = all(r["blind_passes"] == 0 for r in z)
hi = [k for k in by_cell if k[0] == max(BLINDS)]
p2b_bad = [k for k in hi
           if sum(x["blind_passes"] for x in by_cell[k]) / len(by_cell[k]) <= 0]
merged = {b: sum(r["blind_passes"] for r in R if r["blindspot"] == b)
             / max(1, sum(1 for r in R if r["blindspot"] == b)) for b in BLINDS}
seq = [merged[b] for b in BLINDS]
p2c = all(a < b for a, b in zip(seq, seq[1:]))
ok["P2"] = p2a and not p2b_bad and p2c
print(f"  P2  blind=0.0 的 {len(z)} 行 blind_passes 全 0：{p2a}（已知答案：_h01∈[0,1) 不可能 <0.0）")
print(f"      blind={max(BLINDS)} 的 15 格 mean>0：{15-len(p2b_bad)}/15（必須 15）")
print("      逐盲區合併 mean " + " ".join(f"{b}:{merged[b]:.3f}" for b in BLINDS)
      + f"  嚴格遞增 {p2c} → {ok['P2']}")

# ── P3 分解恆等式 ─────────────────────────────────────────────────────
bad3 = bad_ord = bad_bpr = 0
for r in R:
    ro, de, ac = r["routed_to_attacker"], r["defected"], r["accepted_bad"]
    if not (ac <= de <= ro):
        bad_ord += 1
    if ro > 0 and de > 0:
        if abs(ro * (de / ro) * (ac / de) - ac) >= 1e-6:
            bad3 += 1
    elif ac != 0:
        bad3 += 1
    if ro > 0 and r["bad_per_route"] is not None:
        if abs(r["bad_per_route"] - ac / ro) >= 5e-5:
            bad_bpr += 1
ok["P3"] = bad3 == 0 and bad_ord == 0 and bad_bpr == 0
print(f"  P3  三層乘積 ≠ 得手 的行 {bad3}/{len(R)} · 順序 ac≤de≤ro 違反 {bad_ord}"
      f" · 落盤 bad_per_route 對不上 {bad_bpr}（必須全 0） → {ok['P3']}")

# ── P4 配對結構（兩個方向）────────────────────────────────────────────
g = {r["blindspot"]: r["routed_to_attacker"]
     for r in R if r["burst"] == 3 and r["recover"] == 10 and r["seed"] == "p0"}
lo_b = [b for b in (0.15, 0.3) if b in g]
p4a = bool(lo_b) and 0.5 in g and any(g[b] != g[0.5] for b in lo_b)
p4b = all(len({x["routed_to_attacker"] for x in v}) > 1 for v in by_cell.values())
ok["P4"] = p4a and p4b
print(f"  P4  (3,10)·p0 的曝光 " + " ".join(f"{b}:{g[b]}" for b in sorted(g))
      + f"  低盲區≠0.5 {p4a}（必須 True＝盲區改到了世界）")
print(f"      格內 30 seeds 曝光不全相同：{sum(1 for v in by_cell.values() if len({x['routed_to_attacker'] for x in v})>1)}"
      f"/{len(by_cell)} 格 → {ok['P4']}")
print("      ⇒ 每一格是不同的隨機世界（blindspot/burst/recover 都在 _LATER_FIELDS）；")
print("        結論一律寫成組間比較，不做逐 seed 相減。")

# ── P5 退化格 ────────────────────────────────────────────────────────
degen = [c["label"] for c in C if c["accepted_bad"]["n_effective"] <= 1]
ok["P5"] = True   # 判準是「有報」，不是「沒有退化格」
print(f"  P5  n_effective≤1 的退化格 {len(degen)}/{len(C)}"
      + (f"：{degen}" if degen else "（無）") + "  → 有報")

print("\n── 產物點數（只數產物，不看返回值）──")
print(f"  cells {len(C)}/75 · rows {len(R)}/2250 · manifest.complete={MAN.get('complete')}"
      f" · rounds={rounds} · git_rev={MAN.get('git_rev','')[:8]}")

if not all(ok.values()):
    print("\n‼ 探針沒全過 —— 依事前登記，不出主數字。")
    sys.exit(1)


def cell_stats(k):
    v = by_cell[k]
    ro = sum(x["routed_to_attacker"] for x in v)
    de = sum(x["defected"] for x in v)
    ac = sum(x["accepted_bad"] for x in v)
    n = len(v)
    return {"expo": ro / n, "defrate": (de / ro if ro else None),
            "escape": (ac / de if de else None), "hits": ac / n,
            "ro": ro, "de": de, "ac": ac,
            "neff": len({x["accepted_bad"] for x in v})}


S = {k: cell_stats(k) for k in by_cell}


def ratio(vals):
    vals = [x for x in vals if x is not None]
    if not vals or min(vals) <= 0:
        return None
    return max(vals) / min(vals)


print("\n── 主表：三層分解全表（格內用和的比；每格 30 seeds × 600 輪）──")
print("  盲區  (b,r)     曝光    作惡率   逃脫率    得手   nominal b/(b+r)  相對誤差  n_eff")
for b in BLINDS:
    for (bu, re) in BRS:
        s = S[(b, bu, re)]
        nom = bu / (bu + re)
        err = (abs(s["defrate"] - nom) / nom) if s["defrate"] is not None else None
        mark = " ⚠退化" if s["neff"] <= 1 else ""
        print(f"  {b:<5} ({bu},{re})".ljust(17)
              + f"{s['expo']:>7.2f}"
              + (f"{s['defrate']:>9.4f}" if s['defrate'] is not None else "      n/a")
              + (f"{s['escape']:>9.4f}" if s['escape'] is not None else "      n/a")
              + f"{s['hits']:>8.3f}"
              + f"{nom:>13.4f}"
              + (f"{err:>11.1%}" if err is not None else "        n/a")
              + f"{s['neff']:>6}" + mark)
    print()

print("── 跨格離散度：每個盲區值上，15 個 (b,r) 的 max/min 比值 ──")
print("  （與 E24『時間結構只差 1.81 倍』同一把尺）")
print("  盲區    得手比值   曝光比值   作惡率比值  逃脫率比值   得手 min–max")
lines = {}
for b in BLINDS:
    ks = [(b, bu, re) for (bu, re) in BRS]
    rh = ratio([S[k]["hits"] for k in ks])
    rx = ratio([S[k]["expo"] for k in ks])
    rd = ratio([S[k]["defrate"] for k in ks])
    rs = ratio([S[k]["escape"] for k in ks])
    lines[b] = (rh, rx, rd, rs)
    hs = [S[k]["hits"] for k in ks]
    f = lambda x: "  n/a " if x is None else f"{x:>6.2f}"
    print(f"  {b:<6}{f(rh)}    {f(rx)}     {f(rd)}      {f(rs)}"
          f"     {min(hs):.3f}–{max(hs):.3f}")

print("\n── 事前押的六格 ──")
r05 = lines.get(0.5, (None,) * 4)
R1 = r05[0] is not None and 1.5 <= r05[0] <= 2.2
R2 = any(v[0] is not None and v[0] > 3.0 for v in lines.values())
R3 = all(v[0] is not None and v[1] is not None and v[2] is not None
         and v[1] > v[0] and v[2] > v[0] for v in lines.values())
z0 = lines.get(0.0, (None,) * 4)
R4 = p2a and z0[3] is not None and z0[3] < 1.3
errs = [abs(S[k]["defrate"] - k[1] / (k[1] + k[2])) / (k[1] / (k[1] + k[2]))
        for k in S if S[k]["defrate"] is not None]
R5 = len(errs) == len(S) and max(errs) < 0.25
print(f"  R1 blind=0.5 得手跨格比值 ∈[1.5,2.2]     實測 "
      + (f"{r05[0]:.2f}" if r05[0] else "n/a") + f"   {'✔' if R1 else '✘'}")
worst = max((v[0] for v in lines.values() if v[0]), default=0)
print(f"  R2 至少一個盲區 得手比值 >3.0            實測最大 {worst:.2f}   {'✔' if R2 else '✘'}")
print(f"  R3 每個盲區 曝光比值與作惡率比值 >得手比值        {'✔' if R3 else '✘'}")
print(f"  R4 blind=0 blind_passes 全 0 且逃脫率比值 <1.3  實測 "
      + (f"{z0[3]:.3f}" if z0[3] else "n/a") + f"   {'✔' if R4 else '✘'}")
print(f"  R5 作惡率相對誤差 75 格全 <25%          實測最大 {max(errs):.1%}   {'✔' if R5 else '✘'}")
print("  R6 wall ≤20 分鐘                        見 run log")

# ═══ 追加（不在事前登記；零額外機時，只讀同一份 rows.jsonl）══════════════
# 主表出來之後才問的兩件事。照第 92 輪的規矩標明「超出事前登記範圍」，
# 並且各自要有兩個方向——否則它就只是一個事後湊出來的說法。
print("\n── 追加 A：作惡『總次數』的跨格離散度 ──")
print("  （得手比值小，可能是曝光×作惡率互相抵消，也可能是作惡總量本身就被綁住。")
print("    這兩件事在得手數上長得一樣，所以要單獨把 defected 總量拉出來看。）")
print("  盲區   作惡總數比值   min–max          對照：曝光比值 / 作惡率比值")
for b in BLINDS:
    ks = [(b, bu, re) for (bu, re) in BRS]
    d = [S[k]["de"] / len(by_cell[k]) for k in ks]
    print(f"  {b:<6} {max(d)/min(d):>8.2f}     {min(d):.3f}–{max(d):.3f}"
          f"          {ratio([S[k]['expo'] for k in ks]):.2f}"
          f" / {ratio([S[k]['defrate'] for k in ks]):.2f}")

print("\n── 追加 B：R5 為什麼錯——相位時鐘跑在『被路由次數』上 ──")
import statistics as _st
cyc = lambda k: S[k]["expo"] / (k[1] + k[2])
rerr = lambda k: abs(S[k]["defrate"] - k[1] / (k[1] + k[2])) / (k[1] / (k[1] + k[2]))
print("  跑完週期數    格數   |相對誤差| 中位數     最大")
for nm, f in (("<1 個週期", lambda c: c < 1), ("1–2 個", lambda c: 1 <= c < 2),
              ("2–3 個", lambda c: 2 <= c < 3), ("≥3 個", lambda c: c >= 3)):
    ks = [k for k in S if f(cyc(k))]
    if ks:
        print(f"  {nm:<10} {len(ks):>5}    {_st.median(rerr(k) for k in ks):>9.1%}"
              f"   {max(rerr(k) for k in ks):>7.1%}")
print(f"  曝光全 75 格範圍 {min(S[k]['expo'] for k in S):.2f}–{max(S[k]['expo'] for k in S):.2f}"
      f"（總輪數 {rounds}）· 跑不完一個週期的格 {sum(1 for k in S if cyc(k)<1)}/75")
exc = sorted(k for k in S if cyc(k) < 1 and S[k]["defrate"] <= k[1]/(k[1]+k[2]))
print(f"  ⚠ 誠實邊界：『週期跑不完 ⇒ 只放得到 burst 那段 ⇒ 作惡率被高估』這個方向，")
print(f"     35 格裡只中 {35-len(exc)} 格。{len(exc)} 個例外全是 burst≥5 且 recover=3：")
for k in exc:
    print(f"       blind={k[0]} ({k[1]},{k[2]})  實測 {S[k]['defrate']:.4f}"
          f" < nominal {k[1]/(k[1]+k[2]):.4f}")
print("     為什麼低於 nominal，本輪沒有量出機制 ⇒ 記成未解，不編故事。")
