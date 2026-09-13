"""把 S1/S2/S3 的 rows.jsonl 算成報告裡的每一個數字（2026-08-07）。

報告的每一條結論都要指得出「檔案、欄位、數值、重算方式」。重算方式就是這一支：

    .venv/bin/python examples/analyze_v2.py --iter <迭代v2 目錄> --base <基線目錄>

它只讀 `rows.jsonl`（一個 seed 一行），不讀逐輪紀錄，也不重跑模擬——所以
任何人都可以在零機時的情況下把報告裡的數字重算一遍，或改一個算法看結論會不會翻。

分析紀律（`_index/methods.json`，上一輪被推翻換來的）在這裡是可執行的：

  紀律 1  聚合量一律同時報**分解**。S3 的每一格都報
          `得手 / 曝光 / 效率`三個量，而不是只報得手。上一輪「時間結構只差
          1.81 倍」就是只看總數，沒看到曝光跨 6.06 倍、效率跨 8.45 倍、兩者
          反向抵消。
  紀律 2  每一格連 `n_effective`（不同軌跡數）一起報。退化端點會塌成 1，
          此時 sd=0 不是精準是沒有樣本。
  紀律 4  等預算一律用 `defected == BUDGET` 的佔比，不用 `<=`。

配對的誠實邊界：
  - S1 的 λ 比較是**真配對**——懲罰參數不進亂數種子，同一個 seed 在所有 λ
    下跑在逐位相同的隨機世界上（實測：first_slash_round 與 score_at_slash
    在所有 λ 下相同）。
  - S2 的策略間比較是**以 seed 標籤配對的區組設計**，不是同一個隨機世界
    （strategy 進 digest，本來就該進）。它消掉的是「這個 seed 標籤下的共同
    因素」，不是「同一組評審運氣」。這個區別要寫進報告，不能含糊帶過。
"""
from __future__ import annotations

import argparse
import json
import math
import statistics as st
from collections import defaultdict
from pathlib import Path
from typing import Any

from vacant.research import wilcoxon_signed_rank_exact


def load(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(st.mean(xs), 4) if xs else None


def _median(xs):
    xs = [x for x in xs if x is not None]
    return round(st.median(xs), 4) if xs else None


def _ratio(xs) -> float | None:
    """跨度＝max/min。分母為 0 時回 None——不要編一個「無限大」出來。"""
    xs = [x for x in xs if x is not None]
    if not xs or min(xs) <= 0:
        return None
    return round(max(xs) / min(xs), 4)


def _paired(a: dict[str, float], b: dict[str, float]) -> dict[str, Any]:
    """以 key（seed）配對，回配對差的敘述統計＋Wilcoxon 精確檢定。"""
    keys = sorted(set(a) & set(b))
    diffs = [a[k] - b[k] for k in keys if a[k] is not None and b[k] is not None]
    out: dict[str, Any] = {"n_pairs": len(diffs), "mean_diff": _mean(diffs),
                           "median_diff": _median(diffs),
                           "n_positive": sum(1 for d in diffs if d > 0),
                           "n_zero": sum(1 for d in diffs if d == 0),
                           "n_negative": sum(1 for d in diffs if d < 0)}
    if diffs and any(d != 0 for d in diffs):
        w = wilcoxon_signed_rank_exact(diffs)
        out.update({"p": round(w["p"], 6), "method": w["method"]})
    else:
        # 全部差為 0：H0 無法被拒絕，而且這通常代表「兩臂根本一樣」——
        # 直接寫出來，不要讓它以「無 p 值」的形式消失在表格裡。
        out.update({"p": None, "method": "all_zero_diffs"})
    return out


# ═══ S1 slash 取捨曲線 ═══════════════════════════════════════════════════
def analyse_s1(rows: list[dict]) -> dict[str, Any]:
    by = defaultdict(list)
    for r in rows:
        by[(r["arm"], r["slash_factor"], r["slash_n_factor"])].append(r)

    cells = []
    for (arm, fac, lam), rs in sorted(by.items()):
        slashed = [r for r in rs if r["first_slash_round"] is not None]
        returned = [r for r in slashed if r["rounds_to_next_route"] is not None]
        cells.append({
            "arm": arm, "slash_factor": fac, "slash_n_factor": lam,
            "n_seeds": len(rs),
            # 贖回軸的分母：沒被抓過的 seed **不算**「沒回來」
            "n_slashed": len(slashed), "n_returned": len(returned),
            "return_rate": round(len(returned) / len(slashed), 4) if slashed else None,
            "median_rounds_to_return": _median([r["rounds_to_next_route"] for r in returned]),
            "mean_rounds_to_return": _mean([r["rounds_to_next_route"] for r in returned]),
            # 排除軸
            "mean_routes_after_slash": _mean([r["routes_after_slash"] for r in slashed]),
            "mean_bad_after_slash": _mean([r["accepted_bad_after_slash"] for r in slashed]),
            # 解耦的直接讀數
            "mean_obs_at_slash": _mean([r["obs_at_slash"] for r in slashed]),
            "mean_score_at_slash": _mean([r["score_at_slash"] for r in slashed]),
            # 全場（不只 slash 之後）
            "mean_accepted_bad": _mean([r["accepted_bad"] for r in rs]),
            "mean_routed": _mean([r["routed_to_attacker"] for r in rs]),
        })

    # λ 的配對比較（同 factor、同 arm，λ=0 對 λ=1）
    paired = []
    for arm in sorted({c["arm"] for c in cells}):
        for fac in sorted({c["slash_factor"] for c in cells}):
            def pick(lam, field):
                return {r["seed"]: r[field] for r in by[(arm, fac, lam)]
                        if r["first_slash_round"] is not None and r[field] is not None}
            for field in ("routes_after_slash", "accepted_bad_after_slash", "obs_at_slash"):
                a, b = pick(0.0, field), pick(1.0, field)
                paired.append({"arm": arm, "slash_factor": fac, "field": field,
                               "contrast": "λ=0 − λ=1", **_paired(a, b)})
    # 解耦的實測驗證：同 seed 跨 λ，first_slash_round 與 score_at_slash 必須相同
    invariance = {"first_slash_round_identical": True, "score_at_slash_identical": True,
                  "checked": 0}
    for (arm, fac, lam), rs in by.items():
        if lam == 1.0:
            continue
        ref = {r["seed"]: r for r in by[(arm, fac, 1.0)]}
        for r in rs:
            o = ref.get(r["seed"])
            if o is None:
                continue
            invariance["checked"] += 1
            if r["first_slash_round"] != o["first_slash_round"]:
                invariance["first_slash_round_identical"] = False
            if r["score_at_slash"] != o["score_at_slash"]:
                invariance["score_at_slash_identical"] = False
    return {"cells": cells, "paired_lambda0_vs_lambda1": paired,
            "decoupling_check": invariance}


# ═══ S2 預算窗口 ═════════════════════════════════════════════════════════
def analyse_s2(rows: list[dict]) -> dict[str, Any]:
    by = defaultdict(list)
    for r in rows:
        by[(r["budget"], r["strategy"])].append(r)
    budgets = sorted({r["budget"] for r in rows})
    strategies = sorted({r["strategy"] for r in rows})

    table = []
    for bud in budgets:
        for s in strategies:
            rs = by[(bud, s)]
            if not rs:
                continue      # 跑到一半：這一格還沒有資料，如實跳過不要編數字
            bound = [r for r in rs if r["defected"] == bud]
            table.append({
                "budget": bud, "strategy": s, "n_seeds": len(rs),
                # 紀律 4：== BUDGET，不是 <= BUDGET
                "budget_bound_rate": round(len(bound) / len(rs), 4),
                "mean_defected": _mean([r["defected"] for r in rs]),
                "mean_accepted_bad": _mean([r["accepted_bad"] for r in rs]),
                "mean_routed": _mean([r["routed_to_attacker"] for r in rs]),
                "mean_identities": _mean([r["identities_used"] for r in rs]),
                "n_effective_bad": len({r["accepted_bad"] for r in rs}),
                # 早停格的曝光只算到停跑點，不可與別段比（在表上就標出來）
                "early_stop": bool(rs and rs[0].get("early_stop")),
                "mean_stopped_at": _mean([r.get("stopped_early_at") for r in rs]),
            })

    # 窗口：所有臂的 budget_bound_rate 都 ≥ 門檻的預算
    # 只有五臂都跑完的預算才算數——跑到一半的預算不能因為「缺的那臂還沒回報」
    # 就被算成全臂通過。這是紀律 4 的同一個念頭：不要讓「沒量到」偽裝成「合格」。
    complete = [b for b in budgets
                if len({t["strategy"] for t in table if t["budget"] == b}) == len(strategies)]
    windows = {"budgets_with_all_arms_measured": complete}
    for thr in (1.0, 0.9, 0.8):
        ok = [b for b in complete
              if all(t["budget_bound_rate"] >= thr for t in table if t["budget"] == b)]
        windows[f"all_arms_bound_rate_ge_{thr}"] = ok

    # 真正綁得住的預算下做等預算比較（以 seed 標籤配對的區組設計）
    comparisons = []
    strict = windows["all_arms_bound_rate_ge_1.0"]
    for bud in (strict or budgets[:1]):
        for i, s1 in enumerate(strategies):
            for s2 in strategies[i + 1:]:
                a = {r["seed"]: r["accepted_bad"] for r in by[(bud, s1)]}
                b = {r["seed"]: r["accepted_bad"] for r in by[(bud, s2)]}
                comparisons.append({"budget": bud, "a": s1, "b": s2,
                                    "mean_a": _mean(list(a.values())),
                                    "mean_b": _mean(list(b.values())),
                                    **_paired(a, b)})
    return {"table": table, "windows": windows, "equal_budget_comparisons": comparisons,
            "budgets": budgets, "strategies": strategies}


# ═══ S3 (burst, recover) × blindspot ═════════════════════════════════════
def _anova2(cells: dict[tuple, list[float]]) -> dict[str, float]:
    """兩因子 ANOVA（含交互作用），回各效應的 η²＝SS_effect / SS_total。

    上一輪的錯誤是只報主效應（「真正的變數是盲區」），而交互作用的 η²=0.264
    是時間結構主效應的 4 倍——「真正的變數是 X」這個句型本身不成立。
    所以這裡一定要把交互作用算出來並列在同一張表上。
    """
    all_vals = [v for vs in cells.values() for v in vs]
    n = len(all_vals)
    grand = st.mean(all_vals)
    ss_total = sum((v - grand) ** 2 for v in all_vals)
    lv_a = sorted({k[0] for k in cells})
    lv_b = sorted({k[1] for k in cells})

    def marg(idx, level):
        return [v for k, vs in cells.items() if k[idx] == level for v in vs]

    ss_a = sum(len(marg(0, a)) * (st.mean(marg(0, a)) - grand) ** 2 for a in lv_a)
    ss_b = sum(len(marg(1, b)) * (st.mean(marg(1, b)) - grand) ** 2 for b in lv_b)
    ss_cells = sum(len(vs) * (st.mean(vs) - grand) ** 2 for vs in cells.values())
    ss_ab = ss_cells - ss_a - ss_b
    ss_within = ss_total - ss_cells
    df_a, df_b = len(lv_a) - 1, len(lv_b) - 1
    df_ab = df_a * df_b
    df_w = n - len(cells)
    ms_w = ss_within / df_w if df_w else float("nan")
    return {
        "eta2_A_timing": round(ss_a / ss_total, 4) if ss_total else None,
        "eta2_B_blindspot": round(ss_b / ss_total, 4) if ss_total else None,
        "eta2_AB_interaction": round(ss_ab / ss_total, 4) if ss_total else None,
        "F_A": round((ss_a / df_a) / ms_w, 4) if df_a and ms_w else None,
        "F_B": round((ss_b / df_b) / ms_w, 4) if df_b and ms_w else None,
        "F_AB": round((ss_ab / df_ab) / ms_w, 4) if df_ab and ms_w else None,
        "df": [df_a, df_b, df_ab, df_w], "n": n,
    }


def _perm_p(groups: list[list[float]], n_perm: int = 5000, seed: int = 7) -> float:
    """單因子 permutation 檢定（統計量＝組間平方和）。確定性 seed。"""
    import random
    rng = random.Random(seed)
    pooled = [v for g in groups for v in g]
    sizes = [len(g) for g in groups]
    grand = st.mean(pooled)

    def stat(gs):
        return sum(len(g) * (st.mean(g) - grand) ** 2 for g in gs)

    obs = stat(groups)
    hit = 0
    for _ in range(n_perm):
        rng.shuffle(pooled)
        gs, i = [], 0
        for s in sizes:
            gs.append(pooled[i:i + s])
            i += s
        if stat(gs) >= obs - 1e-12:
            hit += 1
    return round((hit + 1) / (n_perm + 1), 6)


def analyse_s3(rows: list[dict]) -> dict[str, Any]:
    by = defaultdict(list)
    for r in rows:
        by[(r["blindspot"], r["burst"], r["recover"])].append(r)

    cells = []
    for (blind, b, rec), rs in sorted(by.items()):
        hits = [r["accepted_bad"] for r in rs]
        expo = [r["routed_to_attacker"] for r in rs]
        # 效率＝每次被路由的得手率。**用每個 seed 自己的比值再平均**，
        # 不是「總得手／總曝光」——後者會被曝光大的 seed 主導。
        eff = [r["bad_per_route"] for r in rs if r["bad_per_route"] is not None]
        cells.append({
            "blindspot": blind, "burst": b, "recover": rec, "n_seeds": len(rs),
            "mean_hits": _mean(hits), "mean_exposure": _mean(expo),
            "mean_efficiency": _mean(eff),
            "sd_hits": round(st.pstdev(hits), 4) if len(hits) > 1 else 0.0,
            # 紀律 2：有效樣本＝不同軌跡數。塌成 1 時 sd=0 不是精準。
            "n_effective_hits": len(set(hits)),
        })

    # 每個盲區水準上，時間結構跨了幾倍（三個量分開報——紀律 1）
    per_blind = []
    for blind in sorted({c["blindspot"] for c in cells}):
        sub = [c for c in cells if c["blindspot"] == blind]
        groups = [[r["accepted_bad"] for r in by[(blind, c["burst"], c["recover"])]]
                  for c in sub]
        per_blind.append({
            "blindspot": blind,
            "spread_hits": _ratio([c["mean_hits"] for c in sub]),
            "spread_exposure": _ratio([c["mean_exposure"] for c in sub]),
            "spread_efficiency": _ratio([c["mean_efficiency"] for c in sub]),
            "best_cell": max(sub, key=lambda c: c["mean_hits"] or -1),
            "worst_cell": min(sub, key=lambda c: c["mean_hits"] if c["mean_hits"] is not None else 1e9),
            "perm_p_timing": _perm_p(groups),
            "min_n_effective": min(c["n_effective_hits"] for c in sub),
        })

    # 兩因子分解：A＝時間結構(burst,recover)、B＝盲區。三個量都做——
    # 只做總得手就會重犯上一輪「只看聚合量」的錯。
    anovas = {}
    for name, key in (("hits", "accepted_bad"), ("exposure", "routed_to_attacker"),
                      ("efficiency", "bad_per_route")):
        grid: dict[tuple, list[float]] = defaultdict(list)
        for r in rows:
            v = r[key]
            if v is not None:
                grid[((r["burst"], r["recover"]), r["blindspot"])].append(v)
        anovas[name] = _anova2(grid)
    return {"cells": cells, "per_blindspot": per_blind, "anova2": anovas}


# ═══ 基線 ════════════════════════════════════════════════════════════════
def analyse_base(rows: list[dict]) -> dict[str, Any]:
    by = defaultdict(list)
    for r in rows:
        by[(r["strategy"], r["blindspot"])].append(r)
    out = []
    for (s, b), rs in sorted(by.items()):
        out.append({
            "strategy": s, "blindspot": b, "n_seeds": len(rs),
            "mean_hits": _mean([r["accepted_bad"] for r in rs]),
            "mean_exposure": _mean([r["routed_to_attacker"] for r in rs]),
            "mean_efficiency": _mean([r["bad_per_route"] for r in rs]),
            "mean_defected": _mean([r["defected"] for r in rs]),
            "mean_caught": _mean([r["caught"] for r in rs]),
            "mean_identities": _mean([r["identities_used"] for r in rs]),
            "shutout_rate": round(sum(1 for r in rs if r["accepted_bad"] == 0) / len(rs), 4),
            "n_effective_hits": len({r["accepted_bad"] for r in rs}),
        })
    return {"cells": out}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--iter", type=Path, help="迭代 v2 目錄（含 S1/S2/S3）")
    ap.add_argument("--base", type=Path, help="基線目錄")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()

    res: dict[str, Any] = {}
    if a.base and (a.base / "rows.jsonl").exists():
        res["baseline"] = analyse_base(load(a.base / "rows.jsonl"))
    if a.iter:
        for name, fn in (("S1", analyse_s1), ("S2", analyse_s2), ("S3", analyse_s3)):
            p = a.iter / name / "rows.jsonl"
            if p.exists():
                res[name] = fn(load(p))
        blp = a.iter / "S1B" / "blayer_by_lambda.json"
        if blp.exists():
            bl = json.loads(blp.read_text(encoding="utf-8"))
            res["S1B"] = [{"slash_n_factor": r["slash_n_factor"],
                           "n_seeds": r["n_seeds"], "all_pass": r["all_pass"],
                           "verdicts": {k: v["verdict"] for k, v in r["scenarios"].items()},
                           "details": {k: v["detail"] for k, v in r["scenarios"].items()}}
                          for r in bl]
    a.out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"寫出 {a.out}")


if __name__ == "__main__":
    main()
