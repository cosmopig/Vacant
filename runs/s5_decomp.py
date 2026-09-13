"""S5 的探針與主表（第 95 輪）。唯讀既有產物，零額外機時，零手打數字。

問兩件事：

**Q1**（第 94 輪下一步 3）四個攻擊者格在 rounds=9600 仍有 6.2–15.4 次曝光。
這些曝光是誰貢獻的——被 slash 的 seed 在 slash **之前**那一段，還是那 8–13 個
**從沒被 slash** 的 seed？後者的曝光隨 rounds 放大嗎？

**Q2**（本輪讀碼發現的）`routes_after_slash` 只數 `slashed_vid`＝第一個被 slash
的身分（`entrycost.py:354`），而模型會重生身分（`entrycost.py:465–474`）。
程式自己的註解（`entrycost.py:322`）寫明這是刻意的取捨。⇒ 第 94 輪追加 A 的
「回來過的 seed 全 0」**就儀器而言是關於一個身分的斷言，不是關於行為者的**，
除非 `identities_used` 全等於 1。這件事本段要驗，不假設。

分解（逐行，整數）：

    routed_to_attacker = pre + post,  post = routes_after_slash（落盤欄位）
                                      pre  = routed − post（導出）

每格 30 seeds 依 `first_slash_round is None` 分兩群：
A＝被 slash 群的 pre 總和 · B＝被 slash 群的 post 總和 · C＝未被 slash 群的 routed 總和。

用法：PYTHONPATH=.:examples python3 runs/s5_decomp.py runs/s4_v1
"""
import json
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else "runs/s4_v1")
R = [json.loads(l) for l in (root / "S4" / "rows.jsonl").read_text().splitlines() if l.strip()]
S2F = Path("runs/s2_v1/S2F/rows.jsonl")          # P3 的「一定看得見」那一邊

key = lambda r: (r["rounds_n"], r["blindspot"], r["burst"], r["recover"])
by_cell = defaultdict(list)
for r in R:
    by_cell[key(r)].append(r)
ROUNDS = sorted({r["rounds_n"] for r in R})
CELLS = sorted(by_cell)
is_ctrl = lambda k: k[2] == 0                    # (burst=0) ＝ 恆不作惡的對照組

slashed = lambda r: r["first_slash_round"] is not None
POST = "routes_after_slash"


def decompose(rows, c_scale=1.0):
    """A/B/C 三分解。c_scale≠1 是 P1 的負對照（故意把 C 打折）。"""
    sl = [r for r in rows if slashed(r)]
    cl = [r for r in rows if not slashed(r)]
    A = sum(r["routed_to_attacker"] - r[POST] for r in sl)
    B = sum(r[POST] for r in sl)
    C = sum(r["routed_to_attacker"] for r in cl) * c_scale
    return A, B, C, len(sl), len(cl)


out = []
p = out.append
p("=" * 78)
p("S5 · 曝光的分母拆解（第 95 輪）— 唯讀 runs/s4_v1，額外機時 0")
p("=" * 78)

# ── 探針 ──────────────────────────────────────────────────────────────────
p("")
p("── 探針（五條，每條兩個方向）" + "─" * 42)

# P1 恆等式 ＋ 負對照
bad_ident = 0
for k in CELLS:
    A, B, C, _, _ = decompose(by_cell[k])
    if A + B + C != sum(r["routed_to_attacker"] for r in by_cell[k]):
        bad_ident += 1
neg_ident = 0
for k in CELLS:
    A, B, C, _, _ = decompose(by_cell[k], c_scale=0.9)
    if A + B + C != sum(r["routed_to_attacker"] for r in by_cell[k]):
        neg_ident += 1
p(f"  P1  A+B+C ≠ Σrouted 的格數 {bad_ident}/30（必須 0）")
p(f"      負對照（C 故意打 0.9 折）抓到的不符格數 {neg_ident}/30（必須 ≥1，"
  f"否則這條檢查是空轉）    {'✔' if bad_ident == 0 and neg_ident >= 1 else '✘'}")

# P2 F1：caught==0 ⟺ 沒被 slash
p2_bad = sum(1 for r in R if slashed(r) != (r["caught"] > 0))
n_c0 = sum(1 for r in R if r["caught"] == 0)
n_cp = sum(1 for r in R if r["caught"] > 0)
p(f"  P2  (first_slash_round is None) ≠ (caught==0) 的行數 {p2_bad}/900（必須 0）")
p(f"      兩種行都存在：caught==0 有 {n_c0} 行 · caught>0 有 {n_cp} 行（各須 >0）"
  f"        {'✔' if p2_bad == 0 and n_c0 > 0 and n_cp > 0 else '✘'}")

# P3 身分數
ids_s4 = Counter(r["identities_used"] for r in R)
if S2F.exists():
    ids_s2f = Counter(json.loads(l)["identities_used"]
                      for l in S2F.read_text().splitlines() if l.strip())
    s2f_max, s2f_n = max(ids_s2f), sum(ids_s2f.values())
else:
    ids_s2f, s2f_max, s2f_n = {}, 0, 0
p(f"  P3  S4 的 identities_used 分佈 {dict(sorted(ids_s4.items()))}（必須全 ==1）")
p(f"      S2F（含 sybil 臂）{s2f_n} 行的分佈 {dict(sorted(ids_s2f.items()))} max={s2f_max}"
  f"（必須 ≥2）  {'✔' if set(ids_s4) == {1} and s2f_max >= 2 else '✘'}")

# P4 對帳第 94 輪追加 A
ANCHOR = {(600, 0.0, 3, 10): 21, (9600, 0.0, 3, 10): 19, (600, 0.0, 8, 3): 21,
          (9600, 0.0, 8, 3): 20, (9600, 0.5, 3, 10): 20, (9600, 0.5, 8, 3): 20}
p4 = [(k, v, sum(1 for r in by_cell[k] if slashed(r))) for k, v in ANCHOR.items()]
p4_bad = sum(1 for _, want, got in p4 if want != got)
p(f"  P4  對帳第 94 輪追加 A 的 n_slashed："
  + " · ".join(f"{k[2],k[3]}·b{k[1]}·r{k[0]}={got}" for k, _, got in p4))
p(f"      與錨點不符的格數 {p4_bad}/6（必須 0）"
  f"                                      {'✔' if p4_bad == 0 else '✘'}")

# P5 早停 ＋ 對照組線性錨
early = [r for r in R if r.get("stopped_early_at") is not None]
lin_bad = []
for k in CELLS:
    if not is_ctrl(k):
        continue
    want = k[0] / 7.5 + 10
    for r in by_cell[k]:
        if r["routed_to_attacker"] != want:
            lin_bad.append((k, r["seed"], r["routed_to_attacker"], want))
p(f"  P5  stopped_early_at 非 null 的行數 {len(early)}/900（必須 0，"
  f"否則 rounds=9600 沒跑滿 ⇒ S4 的 16 倍是假的）")
p(f"      對照組 routed == rounds/7.5+10 的違反行數 {len(lin_bad)}/300"
  f"（＝真的跑滿了的獨立佐證）   {'✔' if not early and not lin_bad else '✘'}")

# ── 主表：30 格三分解 ─────────────────────────────────────────────────────
p("")
p("── 主表：A/B/C 三分解（30 格全印，不挑格）" + "─" * 26)
p("  A＝被slash群在slash之前的曝光 · B＝被slash群在slash之後 · C＝從未被slash的seed")
p("")
p(f"  {'(b,r)':>7} {'blind':>5} {'rounds':>6} │ {'n_sl':>4} {'n_cl':>4} │"
  f" {'A':>7} {'B':>5} {'C':>7} │ {'Σ':>7} │ {'C%':>6} {'A%':>6}")
p("  " + "─" * 74)
CPS = {}                                            # (blind,b,r,rounds) → C 的每-seed
for k in sorted(CELLS, key=lambda k: (k[2], k[3], k[1], k[0])):
    rows = by_cell[k]
    A, B, C, nsl, ncl = decompose(rows)
    tot = A + B + C
    cps = C / ncl if ncl else float("nan")
    CPS[k] = (cps, ncl)
    tag = "△" if is_ctrl(k) else " "
    p(f"  {str((k[2],k[3])):>6}{tag} {k[1]:>5} {k[0]:>6} │ {nsl:>4} {ncl:>4} │"
      f" {A:>7} {B:>5} {C:>7} │ {tot:>7} │"
      f" {100*C/tot if tot else float('nan'):>5.1f}% {100*A/tot if tot else float('nan'):>5.1f}%")
p("  △＝對照組（burst=0 ⇒ 恆不作惡 ⇒ 從不被抓 ⇒ 從不被 slash）")

# ── Q1 的正面回答 ────────────────────────────────────────────────────────
p("")
p("── Q1 剩餘曝光是誰貢獻的？（rounds=9600 的四個攻擊者格）" + "─" * 13)
q1 = []
for k in sorted(CELLS, key=lambda k: (k[2], k[3], k[1])):
    if k[0] != 9600 or is_ctrl(k):
        continue
    A, B, C, nsl, ncl = decompose(by_cell[k])
    tot = A + B + C
    q1.append(100 * C / tot)
    p(f"  {str((k[2],k[3])):>6} blind={k[1]}  C={C:>4}/{tot:<4} = {100*C/tot:5.1f}%"
      f"   （{ncl} 個未被 slash 的 seed 貢獻；被 slash 的 {nsl} 個貢獻 A={A}、B={B}）")
p(f"  ⇒ C 佔比範圍 {min(q1):.1f}–{max(q1):.1f}%（事前判準 R3：≥80%）")

# ── Q2 的正面回答 ────────────────────────────────────────────────────────
p("")
p("── Q2 「回不來」回不來的是誰？" + "─" * 38)
if set(ids_s4) == {1}:
    p("  S4 的 900 行 identities_used 全部 ==1 ⇒ 本組設定下沒有身分重生")
    p("  ⇒ 第 94 輪「slash 之後回來過的 seed 全 0」的**適用範圍**：")
    p("     回不來的是**那個身分**；而在 S4 這組設定（strategy=pulse）下身分＝行為者，")
    p("     因為 pulse 不觸發 discard（entrycost.py:465–471）。")
    p("     **這句話不可外推到 whitewash／sybil**——S2F 同一欄位量到 max="
      f"{s2f_max}，換身分那條路在別的策略下是通的。")
else:
    p(f"  ⚠ identities_used 不全為 1（分佈 {dict(sorted(ids_s4.items()))}）"
      " ⇒ 第 94 輪的結論當場降級")

# ── S_C：未被 slash 的 seed 的每-seed 曝光倍率 ────────────────────────────
p("")
p("── C 的每-seed 曝光：隨 rounds 放大嗎？（R4／R6）" + "─" * 21)
p(f"  {'(b,r)':>7} {'blind':>5} │ " + " ".join(f"{r:>8}" for r in ROUNDS) + f" │ {'S_C':>6}")
p("  " + "─" * 74)
SC = {}
for br in sorted({(k[2], k[3]) for k in CELLS}):
    for blind in sorted({k[1] for k in CELLS}):
        cells = [(r, CPS[(r, blind, br[0], br[1])]) for r in ROUNDS]
        vals = [c[0] for _, c in cells]
        sc = vals[-1] / vals[0] if vals[0] else float("nan")
        SC[(br, blind)] = sc
        tag = "△" if br[0] == 0 else " "
        p(f"  {str(br):>6}{tag} {blind:>5} │ "
          + " ".join(f"{v:>8.2f}" for v in vals) + f" │ {sc:>6.2f}")
p("  （每格數字＝該格未被 slash 的 seed 的**每-seed 平均曝光**；S_C＝9600/600）")

atk_sc = [v for kk, v in SC.items() if kk[0][0] != 0]
ctrl_sc = [v for kk, v in SC.items() if kk[0][0] == 0]
p(f"  ⇒ 攻擊者格 S_C ∈ [{min(atk_sc):.2f}, {max(atk_sc):.2f}]（R4：<4）"
  f" · 對照組 S_C ∈ [{min(ctrl_sc):.2f}, {max(ctrl_sc):.2f}]")

ctrl_9600 = st.mean([CPS[(9600, b, 0, 10)][0] for b in sorted({k[1] for k in CELLS})])
p("")
p("  R6（第二條排除通道）：rounds=9600 時，**從沒被抓過**的攻擊者每-seed 曝光 vs 對照組")
for br in sorted({(k[2], k[3]) for k in CELLS if k[2] != 0}):
    for blind in sorted({k[1] for k in CELLS}):
        v = CPS[(9600, blind, br[0], br[1])][0]
        p(f"    {str(br):>6} blind={blind}  {v:8.2f}   ＝對照組 {ctrl_9600:.0f} 的"
          f" {100*v/ctrl_9600:5.2f}%")

# ── A 的分佈（R5）──────────────────────────────────────────────────────
p("")
p("── R5 被 slash 群在 slash 之前拿到多少工作（A 的每-seed 分佈）" + "─" * 8)
pre_all = []
for k in sorted(CELLS, key=lambda k: (k[2], k[3], k[1], k[0])):
    if is_ctrl(k):
        continue
    v = sorted(r["routed_to_attacker"] - r[POST] for r in by_cell[k] if slashed(r))
    if not v:
        continue
    pre_all += v
    p(f"  {str((k[2],k[3])):>6} blind={k[1]} rounds={k[0]:>4} │ n={len(v):>2}"
      f" 中位數 {st.median(v):>5.1f}  min {min(v):>3}  max {max(v):>3}")
p(f"  ⇒ 全部被 slash 的 seed（n={len(pre_all)}）的 slash 前曝光中位數 "
  f"{st.median(pre_all):.1f}（R5：<30）")

# ── 追加 B（不在事前登記；零額外機時，只讀同一份 rows.jsonl）──────────────
# 主表出來之後才問的：R6 顯示「從沒被抓過」的攻擊者也只拿到對照組 0.57–1.84%
# 的工作 ⇒ 把它們擋住的**不是 slash**。那是什麼？先分掉最無聊的解釋：
# 「它們其實沒作惡，所以跟對照組沒得比」。
p("")
p("── 追加 B（不在事前登記）：擋住『從沒被抓過的攻擊者』的是什麼？" + "─" * 6)
p("  先分掉最無聊的解釋——它們其實沒作惡，所以本來就不該跟對照組比。")
p("")
p(f"  {'(b,r)':>7} {'blind':>5} {'rounds':>6} │ {'群':>4} {'n':>3} │"
  f" {'曝光/seed':>9} {'作惡/seed':>9} {'得手/seed':>9} │ {'作惡率':>7}")
p("  " + "─" * 74)
for k in sorted(CELLS, key=lambda kk: (kk[2], kk[3], kk[1], kk[0])):
    if is_ctrl(k) or k[0] not in (600, 9600):
        continue
    for name, sel in (("未slash", False), ("被slash", True)):
        g = [r for r in by_cell[k] if slashed(r) == sel]
        if not g:
            continue
        ro = sum(r["routed_to_attacker"] for r in g) / len(g)
        de = sum(r["defected"] for r in g) / len(g)
        ac = sum(r["accepted_bad"] for r in g) / len(g)
        p(f"  {str((k[2],k[3])):>6} {k[1]:>5} {k[0]:>6} │ {name:>4} {len(g):>3} │"
          f" {ro:>9.2f} {de:>9.2f} {ac:>9.2f} │ {de/ro if ro else float('nan'):>7.3f}")
nz = [r for r in R if not is_ctrl(key(r)) and not slashed(r)]
p(f"  ⇒ 未被 slash 的攻擊者 seed 共 {len(nz)} 個，其中 defected==0 的有 "
  f"{sum(1 for r in nz if r['defected'] == 0)} 個、defected>0 的有 "
  f"{sum(1 for r in nz if r['defected'] > 0)} 個")
p(f"     它們的 accepted_bad 總和 {sum(r['accepted_bad'] for r in nz)}"
  f"（＝作惡得手但一次都沒被抓的次數）")

txt = "\n".join(out)
print(txt)
(root / "S5_DECOMP.txt").write_text(txt + "\n", encoding="utf-8")
