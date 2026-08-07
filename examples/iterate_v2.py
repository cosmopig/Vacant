"""迭代 v2（2026-08-07）——補上 2026-08-06 對抗式複驗留下的三個洞。

複驗報告第九節「還沒做的」列了三件事，這一支把它們做完。每一段的設計都
直接對應 `_index/methods.json` 的四條分析紀律（那四條是上一輪被推翻換來的）。

## S1 — slash 的取捨曲線

`reputation.Beta.slash` 現在做 `β += (α+β)(1/f−1)`。這**不是遺留 bug**：
2026-07-26 的獨立審查 P0-1 刻意從「α、β 同乘」改成這樣，因為同乘在數學上
等於「老化一個半衰期」，實測連 60 筆 0 分的破壞者每 slash 一次 mean 反而
上升（0.016→0.105），而且 n 減半讓 UCB 探索項變大、**被懲罰者反而更常被派工**。

2026-08-03 的複驗指出另一面：n 加倍讓回歸時間爆炸（觀測 3.4 要 ~1e8 次、
觀測 48 要 ~1e66），**懲罰把自己的赦免通道一起關小了**。

所以「擋住壞人繼續拿工作」與「讓他有機會翻身」是同一個機制的兩面，而這個
取捨點從來沒有被刻意選擇過。本段不修它，本段**把曲線量出來**：

  λ = `slash_n_factor` ∈ [0,1]  均值一律降到 factor 倍（與 λ 無關），
                                n 只上升 λ·Δ。λ=1 是現行行為。
  f = `slash_factor`            均值下降的幅度本身。**必須一起掃**：
                                f=0.5 時光是均值下降就足以永久排除，λ 動不動
                                n 都一樣——在那一點上量 λ 等於在效應為零的點
                                上量效應（紀律 2 的同一個坑換一個軸）。

兩個軸各有一臂：
  頑固者 persist（＝patient, build_rounds=0）  量**排除**：被 slash 之後
      還拿到多少工作（`routes_after_slash`）、還得手多少（`accepted_bad_after_slash`）
  悔改者 repent                                量**贖回**：被 slash 之後要等
      幾輪才再被路由（`rounds_to_next_route`），沒回來就是右設限，要跟
      `rounds_after_slash`（還剩幾輪可用）一起報

兩臂在被 slash 之前的行為完全相同（都是熬過見習期就開始作惡、都不換身份），
差別只在被抓之後。**沒有悔改者臂就只量得到排除。**

懲罰參數（λ 與 f）刻意不進亂數種子（`entrycost._SEED_EXEMPT_FIELDS`），所以
整個網格跑在**同一個隨機世界**上，λ 的比較是配對的。實測驗證：同一個 seed
在所有 λ 下 `first_slash_round` 與 `score_at_slash` 完全相同，只有
`obs_at_slash` 隨 λ 變——這正是「解耦」的定義。

## S1B — 每個候選 λ 都要過 B 層六情境

曲線再好看，也不能選一個讓牙齒失效的操作點。情境 ④reviewer_stake 與
⑤decay_slash 直接吃 slash，是 λ 的承重面。任一情境判準掉了 → 該 λ 標記不可用。

## S2 — E19 用綁得住的預算重跑

原本的 E19 宣稱「等預算下 whitewash 最強」，但預算 12 只對 whitewash（29/30）
與 sybil（30/30）生效，patient 只有 1/30、pulse 0–1/30。實際作惡 11.97 對 4.87
——whitewash 贏在**多作惡 2.5 倍**，不是贏在時機。舊判準只驗
`defected <= BUDGET`（上界恆成立）所以永遠抓不到。

本段掃預算，量每一臂的 `budget_bound_rate`＝`defected == BUDGET` 的 seed 佔比
（紀律 4），找出**每一臂都用得完**的窗口。**窗口有多窄本身就是結論**。

## S3 — E24 在多個盲區值上重做

原本 E24 的 15 格 (burst, recover) 網格全部跑在盲區 0.5，而那正是時間結構
效應為零的交叉點（p=0.868）。在效應為零的點上量到零，不能推廣成
「這個維度不重要」。本段做成 (burst, recover) × blindspot 的完整網格。

分析時**必須分解**（紀律 1）：

    得手 = 被路由次數（曝光） × 每次被路由的得手率（效率）

上一輪只看總數，做出「時間結構只差 1.81 倍」的結論；複驗拆開後發現曝光跨
6.06 倍、效率跨 8.45 倍，兩者反向抵消。三個量都要報。

盲區刻意不含 1.0（紀律 2：30 個 seed 塌成同一條軌跡、有效 n=1）。

## 誠實邊界

這是**機制模擬**不是生態效果。它回答「在這套規則下，這個設定值多少」，
不回答「真實攻擊者會不會這樣做」。攻擊者策略空間仍然是寫死的，本套件給的是
攻擊成本**上界的下界**——它證不了安全。

## 重跑

    .venv/bin/python examples/iterate_v2.py --out <DIR> --only S1 S1B S2 S3
"""
from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

from simgrid import DEFAULT_WORKERS, run_cell, write_manifest
from vacant.entrycost import SimConfig

SEEDS = [f"p{i}" for i in range(30)]
# 不含 1.0（退化端點）。**順序是刻意的**：機時被四個 agent 分著用，跑不完的
# 機率是實質風險，所以把資訊量最大的三個點排前面——
#   0.0  現行設計（sandbox 確定性重跑）
#   0.5  原 E24 十五格全部跑在這裡，也就是被推翻那條結論的操作點
#   0.7  高盲區端（但不是退化端點）
# 0.3 / 0.15 是補密度用的，跑得到就跑。
BLINDSPOTS = (0.0, 0.5, 0.7, 0.3, 0.15)

# ── S1 ───────────────────────────────────────────────────────────────────
S1_ROUNDS = 600
# 掃描範圍由 4.1 的解析解決定，不是拍腦袋決定的：
#   - f 是主旋鈕（f 0.5→0.9 讓回歸需求從 1e12 掉到 1e0.95），所以 f 掃三個點
#   - λ 只在「n 很小的時候被抓」那個角落有分辨力，而且是二選一的性質
#     （到得了／到不了），中間值不會多出新的行為，所以 λ 只掃兩個端點
# 把機時花在 f=0.5 的大 n 區沒有意義——那裡 λ=0 與 λ=1 都到不了。
S1_LAMBDAS = (0.0, 1.0)
# 順序＝資訊量優先（跑不完時手上要剩下能下結論的東西）：
# 0.5 是現行操作點、0.9 是解析解說 λ 可能有分辨力的區、0.7 是中間點。
S1_FACTORS = (0.5, 0.9, 0.7)
S1_ARMS = {
    # 排除軸：被 slash 之後繼續作惡、不換身份
    "頑固者": dict(strategy="patient", build_rounds=0),
    # 贖回軸：被 slash 之後永久只交好貨、不換身份
    "悔改者": dict(strategy="repent"),
}

# ── S2 ───────────────────────────────────────────────────────────────────
S2_ROUNDS = 600
S2_BUDGETS = (1, 2, 3, 4, 6, 12)
# 全長重跑用的預算（S2F）。篩選掃描開早停，**這一組不開**——曝光、身份數、
# 「到第幾輪還在接單」這些機制解釋只有跑滿才算得出來。
S2F_BUDGETS = (1, 2)
S2_STRATEGIES = {
    "whitewash": dict(strategy="whitewash"),
    "patient": dict(strategy="patient", build_rounds=10),
    "sybil": dict(strategy="sybil"),
    "pulse(3,10)": dict(strategy="pulse", pulse_burst=3, pulse_recover=10),
    "pulse(5,20)": dict(strategy="pulse", pulse_burst=5, pulse_recover=20),
}

# ── S3 ───────────────────────────────────────────────────────────────────
S3_ROUNDS = 600
S3_BURSTS = (1, 2, 3, 5, 8)
S3_RECOVERS = (3, 10, 20)


def _dump(out: Path, name: str, cells: list[dict], note: str, rounds: int,
          extra: dict | None = None) -> None:
    """收尾的 manifest。cells.jsonl 已經在 run_cell 逐格 flush 過了——
    這裡只補上完整的 note 與 extra，**不重寫資料**。"""
    d = out / name
    d.mkdir(parents=True, exist_ok=True)
    write_manifest(d, note=note, rounds=rounds, seeds=SEEDS, cells=cells,
                   extra={**(extra or {}), "complete": True})


# ═══ S1 slash 取捨曲線 ═══════════════════════════════════════════════════
def s1(out: Path, workers: int) -> list[dict]:
    cells = []
    d = out / "S1"
    d.mkdir(parents=True, exist_ok=True)
    with (d / "rows.jsonl").open("w", encoding="utf-8") as rows, \
            (d / "cells.jsonl").open("w", encoding="utf-8") as cf:
        # 迴圈順序：f → λ → arm。**兩臂相鄰**，因為排除軸與贖回軸要並排看才有
        # 意義；把 arm 放最外層會讓前半段只有排除、沒有贖回，跑不完就等於
        # 沒有取捨曲線可言。
        for fac in S1_FACTORS:
            for lam in S1_LAMBDAS:
                for arm, kw in S1_ARMS.items():
                    label = f"{arm}·f={fac}·λ={lam}"
                    cfgs = [SimConfig(rounds=S1_ROUNDS, seed=s, blindspot=0.0,
                                      slash_factor=fac, slash_n_factor=lam, **kw)
                            for s in SEEDS]
                    c = run_cell(label, cfgs, logdir=d / "logs", workers=workers,
                                 params={"arm": arm, "slash_factor": fac,
                                         "slash_n_factor": lam},
                                 rows_out=rows, cells_out=cf)
                    cells.append(c)
                    print(f"  {label:<26} 被slash {c['n_slashed']:>2}/{c['n_seeds']}"
                          f"  回來 {c['n_returned']:>2}"
                          f"  slash後路由 {c['routes_after_slash']['mean']:>7}"
                          f"  slash後得手 {c['accepted_bad_after_slash']['mean']:>6}"
                          f"  obs@slash {c['obs_at_slash']['mean']}", flush=True)
    _dump(out, "S1", cells,
          note="slash 取捨曲線：λ（n 上升幅度）× f（均值下降幅度）× 兩臂 × 30 seeds × "
               f"{S1_ROUNDS} 輪、blindspot=0（現行設計：sandbox 確定性重跑）。"
               "懲罰參數不進亂數種子，所以整個網格跑在同一個隨機世界上（配對）。",
          rounds=S1_ROUNDS,
          extra={"lambdas": list(S1_LAMBDAS), "factors": list(S1_FACTORS),
                 "arms": {k: v for k, v in S1_ARMS.items()},
                 "analytic_return": analytic_return_table()})
    return cells


def analytic_return_table() -> list[dict]:
    """解析版的贖回時間：UCB 要爬回門檻需要多少**總觀測數**。

    路由用 UCB = mean + c·sqrt(ln(total+1)/n)，c=0.3。被 slash 之後
    mean 掉到 f·m、n 變成 n+λ·Δ。要追上一個信譽 `target` 的老手，需要

        total ≥ exp( n' · ((target − mean') / c)² ) − 1

    n' 在指數裡——這就是複驗說的「n 是回歸時間的指數係數」。它同時說明
    為什麼**資深者更難翻身**：n 越大，同樣的均值缺口要指數倍多的觀測。
    這張表是確定性的，不吃機時，可以直接手算對照模擬結果。
    """
    from vacant.entrycost import SLASH_FACTOR      # noqa: F401  (文件用)
    rows = []
    c, target, m = 0.3, 0.95, 0.9
    for n0 in (1.0, 3.0, 10.0, 48.0):
        for f in (0.5, 0.7, 0.85, 0.9, 0.95):
            delta = (n0 + 2.0) * (1.0 / f - 1.0)   # Δ=(α+β)(1/f−1)，α+β=n+2
            for lam in S1_LAMBDAS:
                n1 = n0 + lam * delta
                gap = target - f * m
                # 指數可能溢位：只報 log10，不報一個假裝算得出來的數字
                log10_total = n1 * (gap / c) ** 2 / math.log(10)
                rows.append({"n_before": n0, "slash_factor": f, "slash_n_factor": lam,
                             "n_after": round(n1, 3), "mean_after": round(f * m, 4),
                             "log10_total_obs_needed": round(log10_total, 2)})
    return rows


# ═══ S1B B 層六情境（每個候選 λ）═══════════════════════════════════════
def s1b(out: Path, n_seeds: int, lambdas: tuple[float, ...] | None = None) -> list[dict]:
    """只驗**要建議的操作點**，不全掃。

    六情境裡只有 ④reviewer_stake 與 ⑤decay_slash 會呼叫 slash，其餘四個
    （簽章歸屬、同源降權、probation 洗白、M2 記憶）程式路徑上完全不碰它，
    所以它們對 λ 是結構性不變，不需要為每個 λ 各跑一次來「證明」。
    仍然六個都跑，是因為驗收的意思是「這個操作點上整套牙齒還成立」，
    不是「λ 有沒有動到某兩個情境」。
    """
    from vacant.blayer import run_all
    d = out / "S1B"
    d.mkdir(parents=True, exist_ok=True)
    res = []
    for lam in (lambdas or S1_LAMBDAS):
        t0 = time.time()
        reports = run_all(n_seeds=n_seeds, out_dir=d / f"lam{lam}",
                          slash_n_factor=lam)
        row = {"slash_n_factor": lam, "n_seeds": n_seeds,
               "elapsed_s": round(time.time() - t0, 1),
               "scenarios": {k: {"verdict": v.verdict, "detail": v.detail,
                                 "on": [c.to_json() for c in v.on_cells],
                                 "off": [c.to_json() for c in v.off_cells]}
                             for k, v in reports.items()},
               "all_pass": all(v.verdict for v in reports.values())}
        res.append(row)
        marks = " ".join(("✅" if v.verdict else "❌") + k
                         for k, v in reports.items())
        print(f"  λ={lam}  {'可用' if row['all_pass'] else '不可用'}  {marks}", flush=True)
    (d / "blayer_by_lambda.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


# ═══ S2 預算窗口 ═════════════════════════════════════════════════════════
def _s2_sweep(out: Path, workers: int, name: str, budgets, early: bool) -> list[dict]:
    cells = []
    d = out / name
    d.mkdir(parents=True, exist_ok=True)
    with (d / "rows.jsonl").open("w", encoding="utf-8") as rows, \
            (d / "cells.jsonl").open("w", encoding="utf-8") as cf:
        for budget in budgets:
            for strat, kw in S2_STRATEGIES.items():
                label = f"budget={budget}·{strat}"
                cfgs = [SimConfig(rounds=S2_ROUNDS, seed=s, blindspot=0.5,
                                  defect_budget=budget,
                                  stop_when_budget_spent=early, **kw) for s in SEEDS]
                c = run_cell(label, cfgs, logdir=d / "logs", workers=workers,
                             params={"budget": budget, "strategy": strat,
                                     "early_stop": early},
                             budget=budget, rows_out=rows, cells_out=cf)
                cells.append(c)
                expo = ("（早停，不可比）" if early
                        else f"{c['routed_to_attacker']['mean']:>7}")
                print(f"  {label:<24} 用滿 {c['budget_bound_rate']:>6}"
                      f"  作惡 {c['defected']['mean']:>6}"
                      f"  得手 {c['accepted_bad']['mean']:>6}"
                      f"  曝光 {expo}", flush=True)
    return cells


def s2(out: Path, workers: int) -> list[dict]:
    """篩選掃描：找出每一臂都用得完的預算窗口（開早停，機時便宜）。"""
    cells = _s2_sweep(out, workers, "S2", S2_BUDGETS, early=True)
    _dump(out, "S2", cells,
          note=f"預算窗口篩選：budget ∈ {S2_BUDGETS} × 5 策略 × 30 seeds × "
               f"{S2_ROUNDS} 輪、blindspot=0.5（沿用原 E19 的操作點）。"
               "判準是 defected == BUDGET（budget_bound_rate），不是 <= BUDGET"
               "——上界恆成立，抓不到「這一臂根本沒被綁住」。"
               "**本段開了 stop_when_budget_spent**：defected 與 accepted_bad "
               "在預算用完那一刻就定案，所以這兩個量與跑滿完全相同（判準逐位驗過）；"
               "代價是 routed_to_attacker 只算到停跑點，不可與別段比曝光。"
               "曝光與身份數看 S2F（全長重跑）。",
          rounds=S2_ROUNDS,
          extra={"budgets": list(S2_BUDGETS), "early_stop": True,
                 "strategies": {k: v for k, v in S2_STRATEGIES.items()}})
    return cells


def s2f(out: Path, workers: int) -> list[dict]:
    """在綁得住的預算上全長重跑：曝光、身份數、續航只有跑滿才算得出來。"""
    cells = _s2_sweep(out, workers, "S2F", S2F_BUDGETS, early=False)
    _dump(out, "S2F", cells,
          note=f"等預算比較（全長）：budget ∈ {S2F_BUDGETS} × 5 策略 × 30 seeds × "
               f"{S2_ROUNDS} 輪、blindspot=0.5，**不開早停**。"
               "S2 篩出窗口、S2F 在窗口內做真正的比較——複驗指出 whitewash 的優勢"
               "來自免費換身份重新取得路由權（用掉 4.7 個身份、到第 542 輪還在接單，"
               "而 pulse 第 160 輪就被餓死），那是入場成本問題，"
               "要看 identities_used 與 routed_to_attacker 才看得到。",
          rounds=S2_ROUNDS,
          extra={"budgets": list(S2F_BUDGETS), "early_stop": False,
                 "strategies": {k: v for k, v in S2_STRATEGIES.items()}})
    return cells


# ═══ S3 (burst, recover) × blindspot ═════════════════════════════════════
def s3(out: Path, workers: int) -> list[dict]:
    cells = []
    d = out / "S3"
    d.mkdir(parents=True, exist_ok=True)
    with (d / "rows.jsonl").open("w", encoding="utf-8") as rows, \
            (d / "cells.jsonl").open("w", encoding="utf-8") as cf:
        for blind in BLINDSPOTS:
            for b in S3_BURSTS:
                for r in S3_RECOVERS:
                    label = f"blind={blind}·({b},{r})"
                    cfgs = [SimConfig(rounds=S3_ROUNDS, seed=s, strategy="pulse",
                                      pulse_burst=b, pulse_recover=r,
                                      blindspot=blind) for s in SEEDS]
                    c = run_cell(label, cfgs, logdir=d / "logs", workers=workers,
                                 params={"blindspot": blind, "burst": b, "recover": r},
                                 rows_out=rows, cells_out=cf)
                    cells.append(c)
                    print(f"  {label:<22} 得手 {c['accepted_bad']['mean']:>6}"
                          f"  曝光 {c['routed_to_attacker']['mean']:>6}"
                          f"  效率 {c['bad_per_route']['mean']}"
                          f"  有效n {c['accepted_bad']['n_effective']:>3}", flush=True)
    _dump(out, "S3", cells,
          note=f"(burst, recover) × blindspot 完整網格：{len(S3_BURSTS)}×"
               f"{len(S3_RECOVERS)}×{len(BLINDSPOTS)} 格 × 30 seeds × {S3_ROUNDS} 輪。"
               "原 E24 十五格全部跑在盲區 0.5——那正是時間結構效應為零的交叉點。"
               "分析必須分解成『曝光 × 效率』，只看總數會重犯 1.81 倍那個錯。"
               "盲區不含 1.0（退化端點）。",
          rounds=S3_ROUNDS,
          extra={"blindspots": list(BLINDSPOTS), "bursts": list(S3_BURSTS),
                 "recovers": list(S3_RECOVERS)})
    return cells


STAGES = {"S1": s1, "S1B": s1b, "S2": s2, "S2F": s2f, "S3": s3}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--only", nargs="*", default=list(STAGES))
    ap.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    ap.add_argument("--blayer-seeds", type=int, default=100,
                    help="S1B 每格 seed 數。17 §P4 的正式規格是 ≥1000；"
                         "λ 篩選用較小值時報告必須標明（判準是門檻不是檢定）")
    ap.add_argument("--seeds", type=int, default=None,
                    help="覆寫 seed 數（只給冒煙測試用；正式跑不要給）")
    ap.add_argument("--blayer-lambdas", nargs="*", type=float, default=None,
                    help="S1B 只驗這幾個 λ（建議操作點）；不給＝掃 S1_LAMBDAS")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    if a.seeds:
        global SEEDS
        SEEDS = [f"p{i}" for i in range(a.seeds)]
        print(f"⚠ seed 數被覆寫成 {a.seeds}——這不是正式跑", flush=True)

    for name in a.only:
        t0 = time.time()
        print(f"── {name} ──", flush=True)
        if name == "S1B":
            STAGES[name](a.out, a.blayer_seeds,
                         tuple(a.blayer_lambdas) if a.blayer_lambdas else None)
        else:
            STAGES[name](a.out, a.workers)
        print(f"   （{round(time.time() - t0, 1)}s）", flush=True)


if __name__ == "__main__":
    main()
