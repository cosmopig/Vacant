"""infra_void 敏感度分析：把「沒量到的格子」當成區間，而不是當成缺陷。

動機（round77）：`runs/g_onoff5_qwenonly_v3_20260824` 兩臂都跑到 60/60
attempted，但 ON 有 1 格、OFF5 有 3 格 infra_void ⇒ `complete=false` ⇒
`analyze_onoff5.py` 的 `verdict()` 依 SPEC_GAIN §7 直接拒答。

本工具**不推翻也不修改** §7、不動 `run_complete`、不重跑任何呼叫。它問的是
一個 §7 沒有禁止的、比點估計更保守的問題：

    「那 4 個沒量到的格子，不管實際結果是什麼，三臂的排序會不會變？」

作法是給每條臂一個**區間**（分母固定為全部 tasks=60，不是 measured）：
    lower = k / T          （悲觀：所有 void 格全部算錯）
    upper = (k + v) / T    （樂觀：所有 void 格全部算對）
其中 k = accepted_and_meets_demand（實際量到的正確交付數），v = infra_void。
真實的完整-run 數值必定落在 [lower, upper] 內——這是**恆等式，不是估計**。

§7 禁止的是「拿部分臂／部分題的漂亮比例來比較」；區間分析做的是相反的事：
它把未量到的部分用最不利／最有利兩個方向都算一遍，只在**兩個方向都同號**
時才下結論。挑好看數字這件事在定義上做不到。

── 判準（round77 在看到任何數字之前寫死）────────────────────────────
規則 A（void-proof 排序）：只有當 lower(X) > upper(Y) 才宣告「X 嚴格優於 Y」。
    區間重疊 ⇒ 宣告「以區間法不可判定」，不准改用點估計去補。
規則 B（配對檢定）：在**三臂都量到**的共同題目子集上做 McNemar 精確檢定
    （雙尾，α=0.05）。這個子集會排除 4 題，因此規則 B 只在規則 A 之後
    當作補充證據報告，不能單獨用來下排序結論。
規則 C：規則 A 與規則 B 若給出方向相反的結論 ⇒ 兩者都不採信，照實寫矛盾。
── 什麼條件下這份分析該被推翻 ──────────────────────────────────
* 若日後補測那 4 格，實測值落在本工具算出的區間**之外** ⇒ k 或 v 的取數
  有 bug，本分析全部作廢（區間是恆等式，落在區間外只可能是程式錯）。
* 若 infra_void 的發生**與正確性相關**（例如難題比較容易 400），
  區間端點仍然成立（它不假設隨機性），但規則 B 的子集配對檢定會有選擇偏誤，
  屆時只能用規則 A。

用法：
    python3 ops/gain/analyze_void_bounds.py \
        runs/g_onoff5_qwenonly_v3_20260824 \
        --off-baseline runs/g_off60_qwenonly_20260824 [--json OUT]
"""
from __future__ import annotations

import argparse
import json
from itertools import combinations
from math import comb, sqrt
from pathlib import Path


def load_rows(d: Path) -> list[dict]:
    return [json.loads(l) for l in (d / "rows.jsonl").open() if l.strip()]


def load_summary(d: Path) -> dict:
    return json.loads((d / "summary.json").read_text())


def arm_bounds(rows: list[dict], arm: str, all_task_ids: list[str]) -> dict:
    mine = [r for r in rows if r.get("arm") == arm]
    measured_ids = {r["task_id"] for r in mine}
    void_ids = [t for t in all_task_ids if t not in measured_ids]
    k = sum(1 for r in mine if r.get("accepted") and r.get("meets_demand"))
    T = len(all_task_ids)
    v = len(void_ids)
    return {
        "arm": arm, "tasks_total": T, "measured": len(mine), "infra_void": v,
        "void_task_ids": void_ids,
        "correct_measured": k,
        "point_estimate_on_measured": (k / len(mine)) if mine else None,
        "lower_bound": k / T, "upper_bound": (k + v) / T,
    }


def mcnemar_exact(b: int, c: int) -> float:
    """雙尾精確 McNemar：discordant n=b+c 下 Binomial(n, 0.5) 的雙尾 p。"""
    n = b + c
    if n == 0:
        return 1.0
    lo = min(b, c)
    tail = sum(comb(n, i) for i in range(lo + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def paired_diff_ci(b: int, c: int, n: int, z: float = 1.959963985) -> dict:
    """配對比例差 (b-c)/n 的 95% Wald 區間（Agresti-Min 的簡化式）。"""
    if n == 0:
        return {"diff_pp": None, "ci95_pp": None}
    d = (b - c) / n
    se = sqrt(max(0.0, (b + c) - (b - c) ** 2 / n)) / n
    return {"diff_pp": 100 * d, "ci95_pp": [100 * (d - z * se), 100 * (d + z * se)]}


def mcnemar_required_n(b: int, c: int, n: int, z_a: float = 1.959963985,
                       z_b: float = 0.8416212336) -> float | None:
    """要在 80% power / α=.05 下偵測到「本次觀察到的效應量」，大約需要幾題。

    ⚠ 這是用**觀察到的**效應量回推的規劃數字（post-hoc），觀察值本身有雜訊，
    所以它是數量級參考，不是保證。效應量若被本次樣本高估，真實需求會更大。
    """
    p_disc = (b + c) / n
    d = (b - c) / n
    if d == 0 or p_disc == 0:
        return None
    inner = p_disc - d * d
    if inner < 0:
        return None
    num = (z_a * sqrt(p_disc) + z_b * sqrt(inner)) ** 2
    return num / (d * d)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--off-baseline", required=True)
    ap.add_argument("--json")
    a = ap.parse_args()

    rd, od = Path(a.run_dir), Path(a.off_baseline)
    rows, off_rows = load_rows(rd), load_rows(od)
    s_run, s_off = load_summary(rd), load_summary(od)

    if s_run.get("seed") != s_off.get("seed"):
        print(f"BROKEN: seed 不同（{s_run.get('seed')} vs {s_off.get('seed')}）⇒ 題序不可比")
        return 2

    # 全題目清單以 OFF baseline 為準（它 complete=true、量滿 60 題）
    all_ids = [r["task_id"] for r in off_rows if r.get("arm") == "OFF"]
    if len(all_ids) != len(set(all_ids)) or len(all_ids) != s_off.get("n"):
        print(f"BROKEN: OFF baseline 題目清單不完整（{len(all_ids)} 筆 / n={s_off.get('n')}）")
        return 2

    arms = {
        "OFF": arm_bounds(off_rows, "OFF", all_ids),
        "ON": arm_bounds(rows, "ON", all_ids),
        "OFF5": arm_bounds(rows, "OFF5", all_ids),
    }
    for name in ("ON", "OFF5"):
        stray = set(a_ for a_ in {r["task_id"] for r in rows if r.get("arm") == name}) - set(all_ids)
        if stray:
            print(f"BROKEN: {name} 有不在 OFF baseline 題單裡的題目 {sorted(stray)}")
            return 2

    # ── 規則 A ──
    order = []
    for x, y in combinations(arms, 2):
        X, Y = arms[x], arms[y]
        if X["lower_bound"] > Y["upper_bound"]:
            order.append({"pair": f"{x} > {y}", "resolved": True,
                          "margin_pp": 100 * (X["lower_bound"] - Y["upper_bound"])})
        elif Y["lower_bound"] > X["upper_bound"]:
            order.append({"pair": f"{y} > {x}", "resolved": True,
                          "margin_pp": 100 * (Y["lower_bound"] - X["upper_bound"])})
        else:
            order.append({"pair": f"{x} vs {y}", "resolved": False,
                          "reason": "區間重疊 ⇒ 以區間法不可判定"})

    # ── 規則 B ──
    def correct_map(rs, arm):
        return {r["task_id"]: bool(r.get("accepted") and r.get("meets_demand"))
                for r in rs if r.get("arm") == arm}
    cm = {"OFF": correct_map(off_rows, "OFF"), "ON": correct_map(rows, "ON"),
          "OFF5": correct_map(rows, "OFF5")}
    common = sorted(set(cm["OFF"]) & set(cm["ON"]) & set(cm["OFF5"]))
    paired = []
    for x, y in combinations(cm, 2):
        b = sum(1 for t in common if cm[x][t] and not cm[y][t])
        c = sum(1 for t in common if cm[y][t] and not cm[x][t])
        paired.append({"pair": f"{x} vs {y}", "n_common": len(common),
                       f"{x}_only_correct": b, f"{y}_only_correct": c,
                       "both_correct": sum(1 for t in common if cm[x][t] and cm[y][t]),
                       "neither": sum(1 for t in common if not cm[x][t] and not cm[y][t]),
                       "mcnemar_exact_p": mcnemar_exact(b, c),
                       "significant_at_0.05": mcnemar_exact(b, c) < 0.05,
                       **paired_diff_ci(b, c, len(common)),
                       "required_n_for_80pct_power_posthoc": mcnemar_required_n(b, c, len(common))})

    out = {"rule": "round77 pre-registered: A=void-proof bounds, B=paired McNemar on common subset",
           "run_dir": str(rd), "off_baseline": str(od), "seed": s_run.get("seed"),
           "task_ids_identical_across_arms": True,
           "arms": arms, "rule_A_bounds_ordering": order,
           "rule_B_paired_common_subset": paired,
           "n_common_all_three": len(common)}

    print(json.dumps(out, ensure_ascii=False, indent=2))
    if a.json:
        Path(a.json).write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
