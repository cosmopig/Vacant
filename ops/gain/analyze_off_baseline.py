"""機械套用 DECISION_20260824_OFF_BASELINE.md 第三節判決表，避免手算誤判。

用法：
    python3 ops/gain/analyze_off_baseline.py runs/g_off60_relay2_20260824 [--arm OFF]

只讀 summary.json／rows.jsonl，不重跑實驗、不改判決表本身。
判決表逐字對應 DECISION_20260824_OFF_BASELINE.md §3；改表要同時改那份文件。
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path


def wilson_interval(k: int, n: int, z: float = 1.959963985) -> tuple[float, float]:
    """95% Wilson score interval for a binomial proportion k/n."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((centre - margin) / denom, (centre + margin) / denom)


def gate_decision(f: float) -> str:
    """DECISION_20260824_OFF_BASELINE.md §3 判決表——不准改表，只准改資料來源。

    f>0.60 的「太難」優先於 f>=0.20 的「量測窗口可用」——原表就是這樣排的
    （太難的池子量到的不是「機制能不能救」，是池子太弱）。
    """
    if f > 0.60:
        return "f>0.60: 太難 ⇒ 池子太弱、量不到機制能不能救，要換強一點的 worker"
    if f >= 0.20:
        return "f>=0.20: 量測窗口可用 ⇒ 直接在這批題上跑三臂（ON/OFF5），worker 池不動"
    if f >= 0.05:
        return "0.05<=f<0.20: 邊緣 ⇒ 加大 n 到 150 或改 hasty-only 池，擇一並記成條件改變"
    return "f<0.05: 天花板確認 ⇒ 現池答不出這題，必須改 hasty-only worker 池重量 OFF"


def analyze(run_dir: Path, arm: str) -> dict:
    summary = json.loads((run_dir / "summary.json").read_text())
    arm_summary = summary.get("arms", {}).get(arm)
    if arm_summary is None:
        return {"ok": False, "reason": f"summary.json 裡沒有 arms.{arm}（可能還沒跑完，或臂名打錯）"}

    tasks = arm_summary["tasks"]
    infra_void = arm_summary["infra_void"]
    measured = tasks - infra_void
    cdr = arm_summary.get("correct_delivery_rate")

    gate_blocked = infra_void > 6
    result = {
        "ok": True,
        "arm": arm,
        "tasks": tasks,
        "infra_void": infra_void,
        "measured": measured,
        "gate_blocked_infra_void_gt_6": gate_blocked,
    }
    if gate_blocked:
        result["verdict"] = "擋門觸發（infra_void>6，>10%）⇒ 這輪 f 不准拿去對判決表，記成 incomplete"
        result["f"] = None
        return result

    if cdr is None or measured == 0:
        result["verdict"] = "measured=0 或 correct_delivery_rate 缺失 ⇒ 無法判定"
        result["f"] = None
        return result

    f = 1.0 - cdr
    n_wrong = round(f * measured)
    ci_lo, ci_hi = wilson_interval(n_wrong, measured)
    result.update({
        "f": f,
        "f_wilson_95ci": [ci_lo, ci_hi],
        "verdict": gate_decision(f),
    })

    if run_dir.joinpath("rows.jsonl").exists():
        rows = [json.loads(l) for l in run_dir.joinpath("rows.jsonl").read_text().splitlines() if l.strip()]
        arm_rows = [r for r in rows if r.get("arm") == arm]
        failed = [r for r in arm_rows if r.get("meets_demand") is False]
        result["failed_task_ids"] = [r["task_id"] for r in failed]
        result["failed_by_worker"] = dict(Counter(r.get("worker") for r in failed))
        result["attempted_by_worker"] = dict(Counter(r.get("worker") for r in arm_rows))
        # 推翻條件：失敗是否集中在單一 worker/家族（§4）
        if failed:
            worst_worker, worst_n = Counter(r.get("worker") for r in failed).most_common(1)[0]
            result["failure_concentration_flag"] = (
                worst_n == len(failed) and len(failed) > 1
            )
            result["worst_worker"] = worst_worker

    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--arm", default="OFF")
    args = ap.parse_args()
    result = analyze(args.run_dir, args.arm)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
