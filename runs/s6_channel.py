"""S6 的探針與主表（第 96 輪）：指認第二條排除通道。唯讀既有產物，零額外機時。

這支在架構裡承重什麼：第 95 輪（`runs/s5_decomp.py`）量到「215 個從沒被抓過的
作惡 seed 只拿到對照組 0.57–1.84% 的工作」，但誠實邊界 1、2 寫明**只量到效果、
沒有指認機制**，而且**反向因果沒有被排除**。本支把 `runs/s4_v1/S4/logs/` 的
逐輪 `score` 軌跡拉出來，用「盲區」這個外生指派做同一 seed 內的對照：

    同一個 seed、同樣作惡了、行為逐位相同，只差同儕評審看不看得見。

依據的機制事實（全部讀自程式碼，不是假設）：
  F1 信譽只有兩條寫入路徑 `record_review`→`Beta.update`（registry.py:550）與
     `apply_slash`→`Beta.slash`（registry.py:358）⇒ 對 caught==0 的 seed，
     score 的每一次變動都只可能來自同儕評審。
  F2 `_peer_reviews(blind=True)` 三位評審一律投 1.0（entrycost.py:531–535），
     與乾淨交付逐位相同 ⇒ 盲區內的作惡，評審看不見。
  F3 `in_blind = bad and _h01(f"{seed}:blind:{rnd}") < blindspot`（entrycost.py:376）
     ——由 (seed, 輪次) 的 sha256 決定，與誰被路由、與行為無關 ⇒ 外生指派。
  F4 S4 的 audit_accuracy=1.0 ⇒ `caught == bad ∧ audit_ran ∧ ¬in_blind` 是恆等式。
  F5 `route()` 是 UCB 的確定性 argmax（registry.py:773），輸入只有 (rep, obs)。

誠實邊界（不可省，寫進報告）：
  - decay 的時間軸是**全網事件序**（reputation.py:106），所以兩次路由之間
    score 會向先驗回歸。Δscore 因此混了「評審」與「decay」兩項。本支逐類
    一併報**路由間隔中位數**，讓讀者自己判斷這個混淆有沒有吃掉結論。
  - 盲區只在 blindspot>0 的格子裡有變異；blind=0.0 的 450 行對「盲區 vs 可見」
    這條對照**沒有檢定力**（in_blind 恆假），負對照的檢定力也只來自 blind=0.5。

用法：PYTHONPATH=.:examples python3 runs/s6_channel.py runs/s4_v1
"""
from __future__ import annotations

import hashlib
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else "runs/s4_v1")
S4 = root / "S4"
LOGS = S4 / "logs"
OUT = S4 / "S6_CHANNEL.txt"

_lines: list[str] = []


def p(s: str = "") -> None:
    print(s)
    _lines.append(s)


def h01(s: str) -> float:
    """entrycost._h01 的逐位複製。改一個字元，P3 負對照就該抓到。"""
    return int(hashlib.sha256(s.encode()).hexdigest()[:8], 16) / 0x1_0000_0000


ROWS = [json.loads(l) for l in (S4 / "rows.jsonl").read_text().splitlines() if l.strip()]

# ── 掃 900 個 log。一次讀完，所有探針與主表共用同一趟 ────────────────────
# per-row 累加器
per_row: dict[str, dict] = {}
# P1/P2/P3 的計數
p1_bad = 0          # bad ∧ audit_ran 的行數（這條檢查的檢定力來源）
p1_viol = 0
p1_caught_dist_b05: Counter = Counter()
p2_viol = 0
p2_b00_nonzero = 0
p2_b05_pos = 0
neg_p1_viol = 0     # 負對照（:blind2:）
neg_p2_viol = 0
neg_power_rows = 0  # 負對照有檢定力的行數（blind>0）

# Δscore 分類桶（只收 caught==0 的 seed）
DCLS = ("clean", "bad_blind", "bad_visible")
deltas: dict[str, list[float]] = {k: [] for k in DCLS}
gaps: dict[str, list[int]] = {k: [] for k in DCLS}
ctrl_delta: list[float] = []   # 恆不作惡對照組的乾淨輪（參考線，不進三類對照）
ctrl_gap: list[int] = []

missing = []
for r in ROWS:
    fn = LOGS / (r["label"].replace("=", "") + f"__{r['seed']}.jsonl")
    if not fn.exists():
        missing.append(fn.name)
        continue
    bs = r["blindspot"]
    seed = r["seed"]
    # 「從沒被抓的作惡 seed」＝ caught==0 **且非對照組**。第 96 輪第一次跑時
    # 這裡漏了 `not control`，於是 515（＝215 作惡 + 300 恆不作惡對照）被當成 215，
    # 乾淨輪的 Δscore 桶也混進了對照組的 12 萬筆。P4 就是為了抓這件事存在的。
    never_caught = (r["caught"] == 0) and not r["control"]

    routed = 0
    blind_passes = 0
    neg_blind_passes = 0
    last_round = None
    prev_score = None
    prev_round = None
    with fn.open(encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if not d["attacker"]:
                continue
            routed += 1
            rnd = d["round"]
            last_round = rnd
            bad = d["bad"]
            in_blind = bad and h01(f"{seed}:blind:{rnd}") < bs
            neg_blind = bad and h01(f"{seed}:blind2:{rnd}") < bs

            if bad and d["audit_ran"]:
                p1_bad += 1
                if d["caught"] != (not in_blind):
                    p1_viol += 1
                if d["caught"] != (not neg_blind):
                    neg_p1_viol += 1
                if bs > 0:
                    p1_caught_dist_b05[d["caught"]] += 1
                    neg_power_rows += 1
                if in_blind:
                    blind_passes += 1
                if neg_blind:
                    neg_blind_passes += 1

            # Δscore：只在從沒被抓的 seed 上量（那裡 slash 不存在，F1 ⇒ 只剩評審）
            if prev_score is not None:
                if never_caught:
                    cls = "clean" if not bad else ("bad_blind" if in_blind else "bad_visible")
                    deltas[cls].append(d["score"] - prev_score)
                    gaps[cls].append(rnd - prev_round)
                elif r["control"]:
                    ctrl_delta.append(d["score"] - prev_score)
                    ctrl_gap.append(rnd - prev_round)
            prev_score = d["score"]
            prev_round = rnd

    if blind_passes != r["blind_passes"]:
        p2_viol += 1
    if neg_blind_passes != r["blind_passes"]:
        neg_p2_viol += 1
    if bs == 0.0 and r["blind_passes"] != 0:
        p2_b00_nonzero += 1
    if bs > 0.0 and r["blind_passes"] > 0:
        p2_b05_pos += 1

    per_row[f"{r['label']}|{seed}"] = {
        "row": r, "routed": routed, "last_round": last_round,
        "never_caught": never_caught,
    }

p("=" * 78)
p("S6 · 指認第二條排除通道（第 96 輪）  唯讀 runs/s4_v1/S4/logs（671M，不進版控）")
p("=" * 78)
if missing:
    p(f"!! 缺 log 檔 {len(missing)} 個：{missing[:3]} …")

# ── 探針 ────────────────────────────────────────────────────────────────
p("")
p("── 探針（五條，每條兩個方向）──")
ok = True

p1_ok = (p1_viol == 0) and (len(p1_caught_dist_b05) == 2)
ok &= p1_ok
p(f"  P1  F4 恆等式 caught == ¬in_blind（限 bad∧audit_ran 的 {p1_bad} 行）")
p(f"      反例 {p1_viol}/{p1_bad}（必須 0）")
p(f"      blind=0.5 格內兩種 caught 都要有："
  f"caught=True {p1_caught_dist_b05[True]} 行 · False {p1_caught_dist_b05[False]} 行"
  f"   {'✔' if p1_ok else '✘'}")

p2_ok = (p2_viol == 0) and (p2_b00_nonzero == 0) and (p2_b05_pos > 0)
ok &= p2_ok
p(f"  P2  逐行對帳 rows.jsonl 的 blind_passes：不符 {p2_viol}/{len(ROWS)}（必須 0）")
p(f"      blind=0.0 的行 blind_passes≠0 的有 {p2_b00_nonzero} 行（必須 0，F3 已知答案）")
p(f"      blind=0.5 的行 blind_passes>0 的有 {p2_b05_pos} 行（必須 >0，否則空轉）"
  f"   {'✔' if p2_ok else '✘'}")

p3_ok = (neg_p1_viol + neg_p2_viol) > 0
ok &= p3_ok
p(f"  P3  負對照：把雜湊字串改成 ':blind2:' 之後重跑 P1+P2")
p(f"      P1 抓到 {neg_p1_viol} 個不符 · P2 抓到 {neg_p2_viol}/{len(ROWS)} 個不符"
  f"（合計必須 ≥1）   {'✔' if p3_ok else '✘'}")
p(f"      檢定力來源：只有 blind>0 的 {neg_power_rows} 行——blind=0.0 的行"
  f" in_blind 恆假，換雜湊也不會變，這條對它們沒有檢定力（誠實邊界）")

route_viol = sum(1 for v in per_row.values() if v["routed"] != v["row"]["routed_to_attacker"])
n_never = sum(1 for v in per_row.values() if v["never_caught"])
n_ctrl = sum(1 for v in per_row.values() if v["row"]["control"])
n_slashed = sum(1 for v in per_row.values()
                if v["row"]["caught"] > 0 and not v["row"]["control"])
p4_ok = (route_viol == 0) and (n_never == 215) and (n_slashed == 385) and (n_ctrl == 300)
ok &= p4_ok
p(f"  P4  對帳第 95 輪：log 重算的 routed_to_attacker 不符 {route_viol}/{len(per_row)}（必須 0）")
p(f"      作惡格未被抓 {n_never}（須 215）· 作惡格被抓 {n_slashed}（須 385）"
  f" · 恆不作惡對照 {n_ctrl}（須 300）   {'✔' if p4_ok else '✘'}")
p(f"      註：215+385+300 = {n_never + n_slashed + n_ctrl}；第 95 輪 P2 的『caught==0 有 515 行』"
  f"＝ 215 作惡 + 300 對照，兩個數指的不是同一群")


def mean(xs):
    return statistics.fmean(xs) if xs else float("nan")


def med(xs):
    return statistics.median(xs) if xs else float("nan")


p5_ok = (mean(deltas["clean"]) > 0) and (mean(deltas["bad_visible"]) < 0)
ok &= p5_ok
p(f"  P5  尺本身的已知答案（限 caught==0 的 {n_never} 個 seed）")
p(f"      乾淨輪 Δscore 均值 {mean(deltas['clean']):+.5f}（必須 >0）")
p(f"      可見作惡輪 Δscore 均值 {mean(deltas['bad_visible']):+.5f}（必須 <0）"
  f"   {'✔' if p5_ok else '✘'}")
p("")
p(f"  探針總結：{'全過' if ok else '有沒過的——結論以沒過的那條為準，見上'}")

# ── Q1／Q2：三類輪次的 Δscore ───────────────────────────────────────────
p("")
p("── Q1 score 的下跌發生在哪一類輪次（只看 caught==0 的 215 個 seed；那裡 slash 不存在）──")
p("  類別          │     n │ Δscore 均值 │ Δscore 中位數 │ Δ<0 佔比 │ 路由間隔中位數")
NAME = {"clean": "乾淨交付    ", "bad_blind": "作惡·盲區內", "bad_visible": "作惡·評審看得見"}
for k in DCLS:
    xs = deltas[k]
    neg = sum(1 for x in xs if x < 0) / len(xs) * 100 if xs else float("nan")
    p(f"  {NAME[k]:<14s}│ {len(xs):5d} │ {mean(xs):+11.5f} │ {med(xs):+13.5f} │"
      f" {neg:6.1f}% │ {med(gaps[k]):>10.1f} 輪")
_cn = sum(1 for x in ctrl_delta if x < 0) / len(ctrl_delta) * 100 if ctrl_delta else float("nan")
p(f"  {'（參考）恆不作惡對照':<14s}│ {len(ctrl_delta):5d} │ {mean(ctrl_delta):+11.5f} │"
  f" {med(ctrl_delta):+13.5f} │ {_cn:6.1f}% │ {med(ctrl_gap):>10.1f} 輪")

p("")
p("  ⇒ 讀法：三類的**行為**是「作惡 vs 不作惡」，但盲區內的作惡在評審端與乾淨交付")
p("     逐位相同（F2）。若只有『看得見』那一類讓 score 掉，掉的原因就是被看見，")
p("     不是作惡本身、也不是被抓（這 215 個 seed 一次都沒被抓）。")

# ── Q2：同一 seed 內的配對（把 seed 層級的差異也扣掉）────────────────────
# ── decay 混淆的直球處理（超出事前登記；主表出來之後才問的）───────────────
# Δscore = (兩次路由之間向先驗回歸的 decay) + (這一輪三位評審的更新)。
# decay 只由「間隔幾輪」決定，所以把間隔固定住，剩下的就只有評審。
p("")
p("── Q1 附錄 decay 混淆：把『路由間隔』固定住之後，盲區 vs 可見還差多少 ──")
p(f"  路由間隔均值：乾淨 {mean(gaps['clean']):.2f} · 盲區作惡 {mean(gaps['bad_blind']):.2f}"
  f" · 可見作惡 {mean(gaps['bad_visible']):.2f} 輪")
by_gap: dict[str, dict[int, list[float]]] = {k: defaultdict(list) for k in DCLS}
for k in DCLS:
    for g, d in zip(gaps[k], deltas[k]):
        by_gap[k][g].append(d)
shared = sorted(g for g in by_gap["bad_blind"]
                if len(by_gap["bad_blind"][g]) >= 20 and len(by_gap["bad_visible"].get(g, [])) >= 20)
if shared:
    p("  間隔 │ 盲區作惡 n / Δ均值 │ 可見作惡 n / Δ均值 │      差")
    for g in shared:
        a, b = by_gap["bad_blind"][g], by_gap["bad_visible"][g]
        p(f"  {g:4d} │ {len(a):5d} / {mean(a):+9.5f} │ {len(b):5d} / {mean(b):+9.5f} │"
          f" {mean(a) - mean(b):+9.5f}")
    p("  ⇒ 同一個間隔內 decay 完全相同，所以這一欄的差只剩『評審看不看得見』。")
else:
    p("  沒有任何一個間隔在兩類裡都湊到 n≥20 ⇒ 這條除不掉 decay，照報除不掉。")

p("")
p("── Q2 反向因果：同一個 seed 內同時有兩類作惡輪的，逐 seed 配對 ──")
per_seed: dict[str, dict[str, list[float]]] = defaultdict(lambda: {k: [] for k in DCLS})
for r in ROWS:
    if r["caught"] != 0 or r["blindspot"] == 0.0:
        continue
fn_pairs = []
# 重掃一次，只掃 blind>0 且 caught==0 的 seed（配對用；量小）
for r in ROWS:
    if r["caught"] != 0 or r["blindspot"] <= 0.0:
        continue
    fn = LOGS / (r["label"].replace("=", "") + f"__{r['seed']}.jsonl")
    if not fn.exists():
        continue
    seed = r["seed"]
    bs = r["blindspot"]
    prev_score = None
    bucket = {k: [] for k in DCLS}
    with fn.open(encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            if not d["attacker"]:
                continue
            rnd, bad = d["round"], d["bad"]
            in_blind = bad and h01(f"{seed}:blind:{rnd}") < bs
            if prev_score is not None:
                cls = "clean" if not bad else ("bad_blind" if in_blind else "bad_visible")
                bucket[cls].append(d["score"] - prev_score)
            prev_score = d["score"]
    if bucket["bad_blind"] and bucket["bad_visible"]:
        fn_pairs.append((f"{r['label']}|{seed}",
                         mean(bucket["bad_blind"]), mean(bucket["bad_visible"])))

n_pair = len(fn_pairs)
n_right = sum(1 for _, b, v in fn_pairs if b > v)
p(f"  同時有『盲區作惡輪』與『可見作惡輪』的 seed：{n_pair} 個")
if n_pair:
    p(f"  其中 mean Δ(盲區) > mean Δ(可見) 的：{n_right}/{n_pair}"
      f"（{n_right / n_pair * 100:.1f}%）")
    diffs = [b - v for _, b, v in fn_pairs]
    p(f"  逐 seed 差值 (盲區 − 可見) 均值 {mean(diffs):+.5f} · 中位數 {med(diffs):+.5f}"
      f" · min {min(diffs):+.5f} · max {max(diffs):+.5f}")
    p("  ⇒ 這是**同一個 seed、同樣作惡了**的內部對照。反向因果（『工作少所以沒被抓』）")
    p("    解釋不了為什麼同一個 seed 的兩類作惡輪次結果不同——它們的行為一樣，")
    p("    差別只有 sha256(seed,輪次) 指派的『評審看不看得見』（F3，與行為正交）。")

# ── Q3：餓死多早、是不是永久 ────────────────────────────────────────────
p("")
p("── Q3 從沒被抓的 seed，最後一次拿到工作是第幾輪（rounds=9600）──")
p("  (b,r)   blind │  n │ 最後路由輪次中位數 │ 佔 9600 │ 該格總曝光中位數")
cells = defaultdict(list)
for v in per_row.values():
    r = v["row"]
    if r["rounds_n"] != 9600 or not v["never_caught"]:
        continue
    cells[(r["burst"], r["recover"], r["blindspot"])].append(v)
for key in sorted(cells):
    b, rc, bs = key
    vs = cells[key]
    lasts = [v["last_round"] for v in vs]
    tag = "對照組" if b == 0 else "     "
    p(f"  ({b},{rc}){tag:<4s} {bs:<4} │ {len(vs):2d} │ {med(lasts):18.1f} │"
      f" {med(lasts) / 9600 * 100:6.1f}% │ {med([v['routed'] for v in vs]):10.1f}")
p("")
p("  誠實邊界：『最後一次拿到工作』的觀測窗只有 9600 輪。中位數落在窗內很前面，")
p("  說得上的是『在這 9600 輪內沒再回來』，說不上『永遠』。")

OUT.write_text("\n".join(_lines) + "\n", encoding="utf-8")
print(f"\n[寫出] {OUT}")
