"""simgrid — 平行跑「一格 N 個 seed」並把原始資料完整落盤的共用小工具。

## 這支在架構裡承重什麼

`pulse_suite.py` 的 `_cell()` 只保留 mean/sd/min/max。2026-08-06 的對抗式複驗
（`脈衝攻擊_2026-08-03/報告_脈衝攻擊與稽核盲區.md` 第六節）推翻的四條結論裡，
有三條是同一個錯：**看聚合量，然後把它當成某個單一因子的效應**。複驗之所以
做得到，是因為逐輪 JSONL 還在——但那是繞遠路：要重算「曝光 × 效率」得從
1,041,246 行逐輪紀錄反推。

所以這支多做一件事：除了逐輪 JSONL，**每一格再落一份 `rows.jsonl`，
一個 seed 一行、帶完整摘要欄位**。分解、配對檢定、重算效應量都直接讀它，
不必回頭 parse 逐輪紀錄，也就不會因為「分解太麻煩」而只報聚合量。

紀律（對應 methods.json 的四條分析紀律）：
  - 聚合值一律連同 per-seed 原值一起落盤（紀律 1：分解得出來才有資格下結論）
  - `n_effective` 記錄「這一格有幾個**不同**的軌跡」——退化端點會塌成 1，
    此時 sd=0 不代表精準，代表沒有樣本（紀律 2）
  - 等預算格另記 `budget_bound_rate`＝`defected == BUDGET` 的 seed 佔比，
    不是 `<=`（紀律 4）

平行化只動排程不動語意：`simulate()` 對 cfg 是純函式、種子完全由
`f"{seed}:{digest()}"` 決定，所以行程數不影響任何數字（`--workers 1`
與 `--workers 10` 必須逐位相同，見 tests/test_simgrid.py）。
"""
from __future__ import annotations

import json
import os
import statistics as st
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

from vacant.entrycost import SimConfig, simulate

# 落盤的數值欄位（rows.jsonl 一律全寫；聚合只對這些算 mean/sd）
NUMERIC_KEYS = (
    "accepted_bad", "high_value_hits", "defected", "caught", "routed_to_attacker",
    "clean_paid", "identities_used", "blocked_no_endorser", "blind_passes",
    "n_bursts", "hits_per_burst", "max_burst_hits", "react_lag_mean",
    "bursts_never_caught", "honest_damage", "gain", "cost", "roi", "bad_per_route",
    # slash 之後（排除軸／贖回軸）
    "first_slash_round", "routes_after_slash", "accepted_bad_after_slash",
    "rounds_to_next_route", "score_at_slash", "obs_at_slash",
    "score_final", "obs_final", "rounds_after_slash", "stopped_early_at",
)

DEFAULT_WORKERS = max(1, min(10, (os.cpu_count() or 4) - 2))


def _run_one(job: tuple[SimConfig, str | None]) -> dict[str, Any]:
    cfg, lp = job
    return simulate(cfg, log_path=Path(lp) if lp else None)


def _stat(vals: list[float]) -> dict[str, Any]:
    """mean/sd/min/max/n ＋ n_effective（不同值的個數）。

    `n_effective` 是紀律 2 的可執行版本：`blindspot=1.0` 時 30 個 seed 塌成
    同一條軌跡，sd=0、有效樣本 1。只報 sd 會讓端點看起來最精準，而它其實
    最沒有資訊。把「這一格實際上只有幾種結果」寫在旁邊，讀的人就躲不掉。
    """
    if not vals:
        return {"mean": None, "sd": None, "min": None, "max": None,
                "n": 0, "n_effective": 0}
    return {"mean": round(st.mean(vals), 4),
            "sd": round(st.pstdev(vals), 4) if len(vals) > 1 else 0.0,
            "min": min(vals), "max": max(vals), "n": len(vals),
            "n_effective": len(set(vals))}


def run_cell(
    label: str,
    cfgs: list[SimConfig],
    *,
    logdir: Path | None,
    workers: int = DEFAULT_WORKERS,
    params: dict[str, Any] | None = None,
    budget: int | None = None,
    rows_out: Any = None,
    cells_out: Any = None,
) -> dict[str, Any]:
    """跑一格（同參數、多 seed）。回聚合 dict；`rows_out` 給就逐 seed 寫一行、
    `cells_out` 給就把這一格的聚合立刻附加上去（兩者都每格 flush）。"""
    jobs: list[tuple[SimConfig, str | None]] = []
    safe = label.replace("/", "_").replace("=", "").replace(" ", "")
    for cfg in cfgs:
        lp = None
        if logdir is not None:
            logdir.mkdir(parents=True, exist_ok=True)
            lp = str(logdir / f"{safe}__{cfg.seed}.jsonl")
        jobs.append((cfg, lp))

    if workers <= 1:
        runs = [_run_one(j) for j in jobs]
    else:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            runs = list(ex.map(_run_one, jobs, chunksize=1))

    if rows_out is not None:
        for cfg, r in zip(cfgs, runs):
            row = {"label": label, "seed": cfg.seed, **(params or {})}
            row.update({k: r.get(k) for k in NUMERIC_KEYS})
            row["config_digest"] = r["config_digest"]
            row["run_key"] = cfg.run_key()
            rows_out.write(json.dumps(row, ensure_ascii=False) + "\n")
        # 每格跑完就 flush。2026-08-07 學到的：跑到一半被砍掉時，沒 flush 的
        # 東西等於沒跑過——**落盤順序要跟計算順序一致，不要累積在記憶體裡等最後
        # 一次寫**。鐵律 3 說的「全 I/O JSONL 落盤」包含這個時序。
        rows_out.flush()

    agg: dict[str, Any] = {
        "label": label, "params": params or {}, "n_seeds": len(runs),
        # digest＝亂數世界（懲罰參數豁免）、run_key＝完整設定。兩個都留，
        # 因為「同一個隨機世界、不同懲罰參數」正是配對比較的前提。
        "config_digest": runs[0]["config_digest"],
        "run_key": cfgs[0].run_key(),
    }
    for k in NUMERIC_KEYS:
        agg[k] = _stat([r[k] for r in runs if r.get(k) is not None])
    # 全數擋下的比例：得手 0 的 seed 佔比（平均值會被離群值帶偏）
    agg["shutout_rate"] = round(
        sum(1 for r in runs if r["accepted_bad"] == 0) / len(runs), 4)
    # 有多少 seed 真的被 slash 過——贖回軸的分母。沒被抓過的 seed 不能當
    # 「沒回來」算（那是右設限與從未進入的混淆，複驗抓到過一次）。
    agg["n_slashed"] = sum(1 for r in runs if r.get("first_slash_round") is not None)
    agg["n_returned"] = sum(1 for r in runs if r.get("rounds_to_next_route") is not None)
    if budget is not None:
        # 紀律 4：等預算比較要驗 == BUDGET，不是 <= BUDGET。
        # 上界恆成立，抓不到「這一臂根本沒被綁住」。
        agg["budget"] = budget
        agg["budget_bound_rate"] = round(
            sum(1 for r in runs if r["defected"] == budget) / len(runs), 4)
    if cells_out is not None:
        cells_out.write(json.dumps(agg, ensure_ascii=False) + "\n")
        cells_out.flush()
    return agg


def write_manifest(out: Path, *, note: str, rounds: int, seeds: list[str],
                   cells: Iterable[dict[str, Any]], extra: dict[str, Any] | None = None) -> None:
    """落 manifest：每一格的 config digest 都寫進去，之後可逐位比對。"""
    import subprocess
    import time
    try:
        rev = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                             text=True, cwd=Path(__file__).resolve().parent.parent
                             ).stdout.strip() or None
    except Exception:
        rev = None
    payload = {
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "git_rev": rev,
        "rounds": rounds,
        "seeds": seeds,
        "note": note,
        "defaults": asdict(SimConfig()),
        "digests": {c["label"]: c["config_digest"] for c in cells},
        "run_keys": {c["label"]: c.get("run_key") for c in cells},
        **(extra or {}),
    }
    (out / "manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
