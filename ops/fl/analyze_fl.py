#!/usr/bin/env python3
"""ops.fl.analyze_fl — Fast-lane experiment analyzer.

Computes per-arm success rate, paired McNemar vs B0x3 (main comparison) and vs B0,
gain share = (arm - B0x3) / (GT - B0x3), false-accept / false-reject / undetermined rates
(both task-level and attempt-level), cost and wall-clock per task, and the pre-registered
qualification check for local 9B confirmation:
    gain_share >= 0.5  AND  false_accept_rate <= 2 * GT.false_accept_rate

Usage:
  python3 ops/fl/analyze_fl.py <root> [--json [OUT.json]]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import statistics
import sys
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from ops.e1.analyze_e1 import mcnemar_exact
from ops.fl import ANALYSIS_SCHEMA, ARMS_FL, JUDGE_ARMS, atomic_write_json


def load_dedup_records(root: pathlib.Path) -> list[dict[str, Any]]:
    """Load `ROOT/results.jsonl`, deduplicating by `(task_id, arm)` (last wins)."""
    p = root / "results.jsonl"
    if not p.is_file():
        raise FileNotFoundError(f"Results file not found: {p}")
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s:
            continue
        obj = json.loads(s)
        key = (str(obj["task_id"]), str(obj["arm"]))
        by_key[key] = obj
    return [by_key[k] for k in sorted(by_key)]


def _mean(vals: list[float]) -> float | None:
    return round(sum(vals) / len(vals), 4) if vals else None


def _median(vals: list[float]) -> float | None:
    return round(float(statistics.median(vals)), 4) if vals else None


def _paired_mcnemar(
    arm_map: dict[str, bool],
    base_map: dict[str, bool],
    base_label: str,
) -> dict[str, Any]:
    common = sorted(set(arm_map) & set(base_map))
    both_pass = sum(1 for t in common if arm_map[t] and base_map[t])
    arm_only = sum(1 for t in common if arm_map[t] and (not base_map[t]))
    base_only = sum(1 for t in common if (not arm_map[t]) and base_map[t])
    both_fail = sum(1 for t in common if (not arm_map[t]) and (not base_map[t]))
    return {
        "n_paired_tasks": len(common),
        "both_pass": both_pass,
        "arm_only_pass": arm_only,
        f"{base_label}_only_pass": base_only,
        "both_fail": both_fail,
        "mcnemar_exact_p": round(mcnemar_exact(arm_only, base_only), 6),
    }


def analyze_root(root: pathlib.Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    records = load_dedup_records(root)
    run_meta = json.loads((root / "RUN.json").read_text(encoding="utf-8")) if (root / "RUN.json").is_file() else {}

    by_arm: dict[str, dict[str, dict[str, Any]]] = {}
    for r in records:
        by_arm.setdefault(str(r["arm"]), {})[str(r["task_id"])] = r

    arms_order = [a for a in ARMS_FL if a in by_arm]
    for a in sorted(by_arm):
        if a not in arms_order:
            arms_order.append(a)

    arm_stats: dict[str, dict[str, Any]] = {}
    correct_by_arm_task: dict[str, dict[str, bool]] = {}
    total_incremental_cost = 0.0
    any_incremental_cost = False

    for arm in arms_order:
        task_map = by_arm[arm]
        valid_recs: list[dict[str, Any]] = []
        void_tids: list[str] = []
        for tid, rec in sorted(task_map.items()):
            if rec.get("infra_void"):
                void_tids.append(tid)
            else:
                valid_recs.append(rec)

        n_tasks = len(valid_recs)
        cmap = {str(r["task_id"]): bool(r.get("delivered_correct")) for r in valid_recs}
        correct_by_arm_task[arm] = cmap
        n_correct = sum(1 for ok in cmap.values() if ok)
        success_rate = round(n_correct / n_tasks, 4) if n_tasks else None

        by_diff: dict[str, dict[str, Any]] = {}
        for diff in sorted({str(r.get("difficulty") or "unknown") for r in valid_recs}):
            sub = [r for r in valid_recs if str(r.get("difficulty") or "unknown") == diff]
            d_ok = sum(1 for r in sub if r.get("delivered_correct"))
            by_diff[diff] = {
                "passed": d_ok,
                "total": len(sub),
                "rate": round(d_ok / len(sub), 4) if sub else None,
            }

        n_fa = sum(1 for r in valid_recs if r.get("false_accept"))
        n_fr = sum(1 for r in valid_recs if r.get("false_reject"))
        n_undet = sum(1 for r in valid_recs if r.get("undetermined"))
        n_gate_acc = sum(1 for r in valid_recs if (not r.get("undetermined")) and (r.get("gate_passed") is True))

        att_tp = sum(int((r.get("attempt_confusion") or {}).get("tp") or 0) for r in valid_recs)
        att_fp = sum(int((r.get("attempt_confusion") or {}).get("fp") or 0) for r in valid_recs)
        att_tn = sum(int((r.get("attempt_confusion") or {}).get("tn") or 0) for r in valid_recs)
        att_fn = sum(int((r.get("attempt_confusion") or {}).get("fn") or 0) for r in valid_recs)
        att_gated = sum(int((r.get("attempt_confusion") or {}).get("n_gated") or 0) for r in valid_recs)

        walls = [float(r.get("wall_s") or 0.0) for r in valid_recs]
        costs = [float(r["cost_usd"]) for r in valid_recs if isinstance(r.get("cost_usd"), (int, float))]
        inc_costs = [
            float(r["incremental_cost_usd"])
            for r in valid_recs
            if isinstance(r.get("incremental_cost_usd"), (int, float))
        ]
        if inc_costs:
            any_incremental_cost = True
            total_incremental_cost += sum(inc_costs)
        tins = [int(r["tokens_in"]) for r in valid_recs if r.get("tokens_in") is not None]
        touts = [int(r["tokens_out"]) for r in valid_recs if r.get("tokens_out") is not None]
        atts = [int(r.get("attempts_count") or 0) for r in valid_recs]

        fb_per_task = [
            int(
                r.get("feedback_bytes_total")
                if r.get("feedback_bytes_total") is not None
                else sum(int(a.get("feedback_bytes") or 0) for a in (r.get("attempts") or []))
            )
            for r in valid_recs
        ]
        fb_per_retry = [
            int(a.get("feedback_bytes") or 0)
            for r in valid_recs
            for a in (r.get("attempts") or [])
            if a.get("feedback_sent")
        ]
        exam_costs_arm = [
            float(r["exam_cost_usd"])
            for r in valid_recs
            if isinstance(r.get("exam_cost_usd"), (int, float))
        ]

        fa_rate = round(n_fa / n_tasks, 4) if n_tasks else None
        fr_rate = round(n_fr / n_tasks, 4) if n_tasks else None
        undet_rate = round(n_undet / n_tasks, 4) if n_tasks else None

        arm_stats[arm] = {
            "n_tasks": n_tasks,
            "n_infra_void_tasks": len(void_tids),
            "infra_void_tasks": void_tids,
            "n_correct": n_correct,
            "success_rate": success_rate,
            "by_difficulty": by_diff,
            "gain_share": None,  # filled below once B0x3 and GT are computed
            "false_accept_count": n_fa,
            "false_accept_rate": fa_rate,
            "false_accept_given_accepted_rate": round(n_fa / n_gate_acc, 4) if n_gate_acc else None,
            "gate_accepted_count": n_gate_acc,
            "false_reject_count": n_fr,
            "false_reject_rate": fr_rate,
            "undetermined_count": n_undet,
            "undetermined_rate": undet_rate,
            "attempt_confusion": {
                "tp": att_tp,
                "fp": att_fp,
                "tn": att_tn,
                "fn": att_fn,
                "n_gated": att_gated,
                "attempt_false_accept_rate": round(att_fp / att_gated, 4) if att_gated else None,
                "attempt_false_reject_rate": round(att_fn / att_gated, 4) if att_gated else None,
            },
            "qualifies_for_9b": None,  # filled below for judge arms
            "attempts_total": sum(atts),
            "attempts_per_task_mean": _mean([float(x) for x in atts]),
            "feedback_bytes_total": sum(fb_per_task),
            "feedback_bytes_per_task_mean": _mean([float(x) for x in fb_per_task]),
            "feedback_bytes_per_retry_mean": _mean([float(x) for x in fb_per_retry]),
            "feedback_bytes_max": max(fb_per_retry) if fb_per_retry else 0,
            "feedback_retry_count": len(fb_per_retry),
            "exam_cost_usd_per_task_mean": round(sum(exam_costs_arm) / len(exam_costs_arm), 6) if exam_costs_arm else None,
            "wall_s_total": round(sum(walls), 3),
            "wall_s_per_task_mean": _mean(walls),
            "wall_s_per_task_median": _median(walls),
            "tokens_in_per_task_mean": _mean([float(x) for x in tins]),
            "tokens_out_per_task_mean": _mean([float(x) for x in touts]),
            "cost_usd_total": round(sum(costs), 6) if costs else None,
            "cost_usd_per_task_mean": round(sum(costs) / len(costs), 6) if costs else None,
            "incremental_cost_usd_total": round(sum(inc_costs), 6) if inc_costs else None,
        }

    # Compute gain_share = (arm - B0x3) / (GT - B0x3), gt_gain = GT - B0x3, and pre-registered 9B qualification
    b0x3_rate = (arm_stats.get("B0x3") or {}).get("success_rate")
    gt_rate = (arm_stats.get("GT") or {}).get("success_rate")
    gt_fa_rate = (arm_stats.get("GT") or {}).get("false_accept_rate")

    gt_gain: dict[str, Any] | None = None
    if b0x3_rate is not None and gt_rate is not None:
        abs_diff = round(gt_rate - b0x3_rate, 4)
        abs_diff_pp = round((gt_rate - b0x3_rate) * 100.0, 2)
        gt_gain = {
            "gt_rate": gt_rate,
            "b0x3_rate": b0x3_rate,
            "abs_diff": abs_diff,
            "abs_diff_pp": abs_diff_pp,
            "paired_mcnemar": _paired_mcnemar(
                correct_by_arm_task.get("GT", {}),
                correct_by_arm_task.get("B0x3", {}),
                "b0x3",
            ),
            "indistinguishable": bool((gt_rate - b0x3_rate) < 0.10),
        }

    for arm, st in arm_stats.items():
        if b0x3_rate is not None and gt_rate is not None and st["success_rate"] is not None:
            denom = gt_rate - b0x3_rate
            if denom != 0:
                st["gain_share"] = round((st["success_rate"] - b0x3_rate) / denom, 4)
        if arm in JUDGE_ARMS:
            gs = st["gain_share"]
            fa = st["false_accept_rate"]
            if gs is not None and fa is not None and gt_fa_rate is not None:
                st["qualifies_for_9b"] = bool((gs >= 0.5) and (fa <= 2.0 * gt_fa_rate))

    # Collect unique per-task Haiku exam cost (cached once per task across XMH/XMVH, or from XM/CT)
    exam_cost_by_task: dict[str, float] = {}
    cache_dir = root / "exam_cache"
    if cache_dir.is_dir():
        for mp in sorted(cache_dir.glob("*/exam_meta.json")):
            try:
                em = json.loads(mp.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            tid = str(em.get("task_id") or mp.parent.name)
            cval = em.get("cost_usd")
            if cval is None and isinstance(em.get("session"), dict):
                cval = em["session"].get("cost_usd")
            if isinstance(cval, (int, float)):
                exam_cost_by_task[tid] = float(cval)
    for r in records:
        if r.get("infra_void"):
            continue
        if r.get("arm") in ("XMH", "XMVH", "XM", "CT"):
            tid = str(r["task_id"])
            cval = r.get("exam_cost_usd")
            if isinstance(cval, (int, float)) and tid not in exam_cost_by_task:
                exam_cost_by_task[tid] = float(cval)

    haiku_exam_cost: dict[str, Any] = {
        "n_tasks": len(exam_cost_by_task),
        "total_usd": round(sum(exam_cost_by_task.values()), 6) if exam_cost_by_task else None,
        "per_task_mean_usd": (
            round(sum(exam_cost_by_task.values()) / len(exam_cost_by_task), 6) if exam_cost_by_task else None
        ),
    }

    # Paired McNemar vs B0x3 (main comparison) and vs B0
    paired_vs_b0x3: dict[str, dict[str, Any]] = {}
    if "B0x3" in correct_by_arm_task:
        base = correct_by_arm_task["B0x3"]
        for arm in arms_order:
            if arm == "B0x3":
                continue
            paired_vs_b0x3[arm] = _paired_mcnemar(correct_by_arm_task[arm], base, "b0x3")

    paired_vs_b0: dict[str, dict[str, Any]] = {}
    if "B0" in correct_by_arm_task:
        base = correct_by_arm_task["B0"]
        for arm in arms_order:
            if arm == "B0":
                continue
            paired_vs_b0[arm] = _paired_mcnemar(correct_by_arm_task[arm], base, "b0")

    return {
        "schema": ANALYSIS_SCHEMA,
        "root": str(root),
        "plan_id": run_meta.get("plan_id"),
        "task_format": run_meta.get("task_format", "function"),
        "gt_source": run_meta.get("gt_source"),
        "agent": run_meta.get("agent"),
        "model": run_meta.get("model"),
        "exam_agent": run_meta.get("exam_agent"),
        "exam_model": run_meta.get("exam_model"),
        "bank_sha256": run_meta.get("bank_sha256"),
        "seed": run_meta.get("seed"),
        "gt_gain": gt_gain,
        "haiku_exam_cost": haiku_exam_cost,
        "total_incremental_cost_usd": round(total_incremental_cost, 6) if any_incremental_cost else None,
        "arms": arm_stats,
        "paired_vs_B0x3": paired_vs_b0x3,
        "paired_vs_B0": paired_vs_b0,
    }


def format_report(summary: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"# Fast-Lane Analysis — {summary.get('plan_id') or summary['root']}")
    lines.append(
        f"Model: `{summary.get('model')}` | Exam model: `{summary.get('exam_model')}` | "
        f"Seed: `{summary.get('seed')}` | Actual total spend: "
        f"`${summary['total_incremental_cost_usd']}`"
        if summary.get("total_incremental_cost_usd") is not None
        else f"Model: `{summary.get('model')}` | Exam model: `{summary.get('exam_model')}` | Seed: `{summary.get('seed')}`"
    )

    gg = summary.get("gt_gain")
    if isinstance(gg, dict):
        pm = gg["paired_mcnemar"]
        lines.append(
            f"GT gain (GT - B0x3): `{gg['abs_diff']:+.4f}` (`{gg['abs_diff_pp']:+.2f}` pp) | "
            f"paired McNemar `p={pm['mcnemar_exact_p']}` "
            f"(GT-only={pm['arm_only_pass']}, B0x3-only={pm['b0x3_only_pass']}, n={pm['n_paired_tasks']})"
        )
        if gg.get("indistinguishable"):
            lines.append("題組無法區分")

    hec = summary.get("haiku_exam_cost") or {}
    if hec.get("per_task_mean_usd") is not None:
        lines.append(
            f"Haiku exam cost/task: `${hec['per_task_mean_usd']:.6f}` "
            f"(total `${hec['total_usd']:.6f}` across {hec['n_tasks']} task(s))"
        )

    lines.append("")
    lines.append("## Per-Arm Summary (Scored on `eval_hidden` Only)")
    lines.append(
        "| Arm | Tasks | Void | Correct | Rate | Gain Share | False Acc | False Rej | Undet | "
        "Qualifies 9B | Att/Task | Fb(B)/Task | Cost($)/Task | Wall(s)/Task |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for arm, st in summary["arms"].items():
        gs = str(st["gain_share"]) if st["gain_share"] is not None else "n/a"
        fa = f"{st['false_accept_count']}/{st['n_tasks']} ({st['false_accept_rate']})"
        fr = f"{st['false_reject_count']}/{st['n_tasks']} ({st['false_reject_rate']})"
        un = f"{st['undetermined_count']}/{st['n_tasks']} ({st['undetermined_rate']})"
        q9 = "YES" if st["qualifies_for_9b"] is True else ("NO" if st["qualifies_for_9b"] is False else "-")
        fb = str(st["feedback_bytes_per_task_mean"]) if st.get("feedback_bytes_per_task_mean") is not None else "0"
        cost = f"{st['cost_usd_per_task_mean']:.5f}" if st["cost_usd_per_task_mean"] is not None else "n/a"
        wall = str(st["wall_s_per_task_mean"]) if st["wall_s_per_task_mean"] is not None else "n/a"
        lines.append(
            f"| {arm} | {st['n_tasks']} | {st['n_infra_void_tasks']} | {st['n_correct']} | {st['success_rate']} | "
            f"{gs} | {fa} | {fr} | {un} | {q9} | {st['attempts_per_task_mean']} | {fb} | {cost} | {wall} |"
        )

    if summary.get("paired_vs_B0x3"):
        lines.append("")
        lines.append("## Paired McNemar vs B0x3 (Main Same-Budget Comparison)")
        lines.append("| Arm | Paired | Both Pass | Arm Only | B0x3 Only | Both Fail | McNemar p |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|")
        for arm, pv in summary["paired_vs_B0x3"].items():
            lines.append(
                f"| {arm} | {pv['n_paired_tasks']} | {pv['both_pass']} | "
                f"{pv['arm_only_pass']} | {pv['b0x3_only_pass']} | {pv['both_fail']} | {pv['mcnemar_exact_p']} |"
            )

    if summary.get("paired_vs_B0"):
        lines.append("")
        lines.append("## Paired McNemar vs B0")
        lines.append("| Arm | Paired | Both Pass | Arm Only | B0 Only | Both Fail | McNemar p |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|")
        for arm, pv in summary["paired_vs_B0"].items():
            lines.append(
                f"| {arm} | {pv['n_paired_tasks']} | {pv['both_pass']} | "
                f"{pv['arm_only_pass']} | {pv['b0_only_pass']} | {pv['both_fail']} | {pv['mcnemar_exact_p']} |"
            )

    lines.append("")
    lines.append(
        "> Pre-written read-out: a judge qualifies for local 9B confirmation iff "
        "`gain_share >= 0.5` AND `false_accept_rate <= 2 * GT.false_accept_rate`."
    )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Fast-lane experiment analyzer")
    ap.add_argument("root", type=pathlib.Path, help="Experiment output directory ROOT")
    ap.add_argument(
        "--json",
        nargs="?",
        const="-",
        default=None,
        dest="json_out",
        help="Print JSON summary to stdout (no arg) or write JSON summary to OUT.json",
    )
    args = ap.parse_args()

    summary = analyze_root(args.root)
    if args.json_out == "-":
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    if args.json_out is not None:
        atomic_write_json(pathlib.Path(args.json_out), summary)
    print(format_report(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
