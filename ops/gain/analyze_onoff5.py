"""三臂比較報表：OFF baseline vs ON vs OFF5，套用 SPEC_GAIN.md §4 的贏面判準。

只讀 summary.json，不重跑實驗、不改判準本身。判準逐字對應 SPEC_GAIN.md §3/§4：
「ON 要算贏，至少必須同時提高正確交付率，且等預算下不輸 OFF-5x」。

用法：
    python3 ops/gain/analyze_onoff5.py \
        runs/g_onoff5_qwenonly_v2_20260824 \
        --off-baseline runs/g_off60_qwenonly_20260824

`runs/g_onoff5_qwenonly_v2_20260824` 提供 ON 與 OFF5 兩臂；OFF baseline 來自
另一個獨立跑的 run 目錄（同 seed 同題序才可比，本工具不驗證 seed 相同，
呼叫端要自己核對兩個 summary.json 的 "seed" 欄位一致）。
"""
from __future__ import annotations

import argparse
import json
import math
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


def arm_row(name: str, arm_summary: dict | None, measured_n: int | None = None) -> dict:
    if arm_summary is None:
        return {"arm": name, "ok": False, "reason": "summary.json 裡沒有這個臂（可能還沒跑完，或臂名打錯）"}
    tasks = arm_summary["tasks"]
    infra_void = arm_summary["infra_void"]
    measured = tasks - infra_void
    cdr = arm_summary.get("correct_delivery_rate")
    row = {
        "arm": name,
        "ok": True,
        "complete": arm_summary.get("complete", False),
        "tasks": tasks,
        "infra_void": infra_void,
        "measured": measured,
        "calls_per_task": arm_summary.get("calls_per_task"),
        "correct_delivery_rate": cdr,
        "reviewer_accuracy": arm_summary.get("reviewer_accuracy"),
        "leaked": arm_summary.get("leaked"),
    }
    if cdr is not None and measured:
        n_correct = round(cdr * measured)
        row["correct_delivery_rate_wilson_95ci"] = list(wilson_interval(n_correct, measured))
    return row


def verdict(off: dict, on: dict, off5: dict, equal_budget_valid: bool) -> str:
    """SPEC_GAIN.md §4 逐字判準：ON 要算贏，至少必須同時
    (a) 正確交付率高於 OFF baseline，且 (b) 等預算下不輸 OFF5。
    這裡只做「點估計」比較，不是統計顯著性判定——CI 有沒有重疊要人另外看，
    本函式不擅自把「差一點」講成「有顯著差異」。
    """
    if not (off.get("ok") and on.get("ok") and off5.get("ok")):
        return "資料不齊（某一臂還沒有 summary.json 裡的紀錄）⇒ 不判定"
    if not on.get("complete") or not off5.get("complete"):
        return "ON 或 OFF5 尚未跑完（complete=false）⇒ 不判定，等 run_complete=true 再套判準"
    if not equal_budget_valid:
        return "equal_budget_comparison_valid=false（calls_per_task 未兩臂皆為 5）⇒ 等預算框架不成立，不判定"

    off_cdr = off.get("correct_delivery_rate")
    on_cdr = on.get("correct_delivery_rate")
    off5_cdr = off5.get("correct_delivery_rate")
    if off_cdr is None or on_cdr is None or off5_cdr is None:
        return "某臂 correct_delivery_rate 缺失 ⇒ 不判定"

    beats_off = on_cdr > off_cdr
    beats_off5 = on_cdr >= off5_cdr
    if beats_off and beats_off5:
        return (f"ON 贏：correct_delivery_rate ON={on_cdr:.4f} > OFF={off_cdr:.4f}，"
                f"且 ON >= OFF5={off5_cdr:.4f}（等預算下不輸 self-consistency）")
    if not beats_off:
        return f"ON 沒有超過 OFF baseline：ON={on_cdr:.4f} <= OFF={off_cdr:.4f} ⇒ 機制本身沒有提升正確交付率"
    return (f"ON 提升了正確交付率（ON={on_cdr:.4f} > OFF={off_cdr:.4f}），"
            f"但等預算下輸給 self-consistency：ON={on_cdr:.4f} < OFF5={off5_cdr:.4f} "
            f"⇒ 這一層打不贏同預算的多數決，照 SPEC_GAIN.md §3 這也是一個要寫進展場的結論")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("onoff5_run_dir", type=Path, help="含 ON,OFF5 兩臂的 run 目錄")
    ap.add_argument("--off-baseline", type=Path, required=True, help="OFF baseline 的 run 目錄")
    args = ap.parse_args()

    onoff5_summary = json.loads((args.onoff5_run_dir / "summary.json").read_text())
    off_summary = json.loads((args.off_baseline / "summary.json").read_text())

    seed_a = onoff5_summary.get("seed")
    seed_b = off_summary.get("seed")
    seed_note = None if seed_a == seed_b else (
        f"⚠ seed 不一致（{seed_a!r} vs {seed_b!r}）⇒ 兩個 run 的題目可能不是同一批，比較無效"
    )

    off_row = arm_row("OFF", off_summary.get("arms", {}).get("OFF"))
    on_row = arm_row("ON", onoff5_summary.get("arms", {}).get("ON"))
    off5_row = arm_row("OFF5", onoff5_summary.get("arms", {}).get("OFF5"))

    result = {
        "onoff5_run_dir": str(args.onoff5_run_dir),
        "off_baseline_run_dir": str(args.off_baseline),
        "seed_match": seed_a == seed_b,
        "seed_note": seed_note,
        "onoff5_run_complete": onoff5_summary.get("run_complete"),
        "equal_budget_comparison_valid": onoff5_summary.get("equal_budget_comparison_valid"),
        "arms": {"OFF": off_row, "ON": on_row, "OFF5": off5_row},
        "verdict": verdict(off_row, on_row, off5_row, bool(onoff5_summary.get("equal_budget_comparison_valid"))),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
