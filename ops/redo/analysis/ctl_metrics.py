#!/usr/bin/env python3
"""Metrics and paired comparisons for the evidence-controller experiment (DECISION_20261127).

Computes the five frozen metrics per arm:
  1. Independent grading final success rate (hidden half all passed).
  2. Hidden test satisfaction ratio (tests_passed / tests_total on delivered attempt).
  3. Actual tokens per successful task (and total/mean tokens per cell).
  4. Broken-after-pass ratio: acceptance tests that passed on some attempt in the cell
     but failed on the delivered attempt, divided by all acceptance tests that ever passed.
  5. Wall-clock waiting time (cell wall_s & agent_wall_s).

Paired comparisons on (task, rep): C vs B and C vs R with exact two-sided McNemar and
paired cost differences.

Usage:
    python3 ops/redo/analysis/ctl_metrics.py <root> [--json] [--json-out PATH]
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import statistics
import sys
from typing import Any


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2.0 * sum(math.comb(n, i) for i in range(k + 1)) / (2.0 ** n))


def _load_cell_details(root: pathlib.Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    run = json.loads((root / "RUN.json").read_text(encoding="utf-8"))
    plan_sha = run["plan_sha256"]
    cells: list[dict[str, Any]] = []
    for cpath in sorted((root / "cells").glob("*/r*/*/cell.json")):
        cell = json.loads(cpath.read_text(encoding="utf-8"))
        if cell.get("plan_sha256") != plan_sha:
            continue
        attempt_recs: list[dict[str, Any]] = []
        n_att = int(cell.get("n_attempts") or len(cell.get("attempts") or []))
        for k in range(1, n_att + 1):
            ap = cpath.parent / f"attempt_{k}" / "attempt.json"
            if ap.is_file():
                try:
                    attempt_recs.append(json.loads(ap.read_text(encoding="utf-8")))
                except (OSError, ValueError):
                    attempt_recs.append({})
            else:
                attempt_recs.append({})
        cell["_attempt_files"] = attempt_recs
        cells.append(cell)
    return run, cells


def _cell_tokens(cell: dict[str, Any]) -> int | None:
    """Total input+output tokens across all attempts in a cell, or None if any attempt lacks usage."""
    atts = cell.get("attempts") or []
    if not atts:
        return None
    total = 0
    for a in atts:
        u = a.get("usage")
        if not isinstance(u, dict):
            return None
        tin = u.get("input")
        tout = u.get("output")
        if tin is None and tout is None:
            return None
        total += int(tin or 0) + int(tout or 0)
    return total


def _cell_calls(cell: dict[str, Any]) -> int | None:
    atts = cell.get("attempts") or []
    if not atts:
        return None
    total = 0
    for a in atts:
        u = a.get("usage")
        if not isinstance(u, dict) or u.get("calls") is None:
            return None
        total += int(u["calls"])
    return total


def _cell_hidden_counts(cell: dict[str, Any]) -> tuple[int | None, int | None]:
    d_1 = cell.get("delivered_attempt")
    if not d_1:
        return None, None
    idx = int(d_1) - 1
    afiles = cell.get("_attempt_files") or []
    if 0 <= idx < len(afiles):
        gr = afiles[idx].get("grade") or {}
        det = gr.get("detail") or {}
        tp = det.get("tests_passed")
        tt = det.get("tests_total")
        if isinstance(tp, int) and isinstance(tt, int) and tt > 0:
            return tp, tt
    # Fallback: binary pass if detail unavailable
    return None, None


def _cell_broken_after_pass(cell: dict[str, Any]) -> tuple[int, int]:
    """Return (broken_count, ever_passed_count) on acceptance tests for one scored cell."""
    d_1 = cell.get("delivered_attempt")
    if not d_1:
        return 0, 0
    idx = int(d_1) - 1
    afiles = cell.get("_attempt_files") or []
    ever_passed: set[str] = set()
    for af in afiles:
        acc = af.get("acc") or {}
        tr = acc.get("test_results") or {}
        for tname, ok in tr.items():
            if ok:
                ever_passed.add(str(tname))
    if not ever_passed:
        return 0, 0
    delivered_tr: dict[str, Any] = {}
    if 0 <= idx < len(afiles):
        delivered_tr = (afiles[idx].get("acc") or {}).get("test_results") or {}
    broken = [t for t in ever_passed if not delivered_tr.get(t, False)]
    return len(broken), len(ever_passed)


def compute_arm_metrics(cells: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [c for c in cells if not c.get("infra_void")]
    n_scored = len(scored)
    n_pass = sum(1 for c in scored if c.get("pass") is True)
    success_rate = round(n_pass / n_scored, 4) if n_scored else None

    # Hidden satisfaction ratio
    cell_sat_ratios: list[float] = []
    sum_hid_p = 0
    sum_hid_t = 0
    for c in scored:
        tp, tt = _cell_hidden_counts(c)
        if tp is not None and tt is not None and tt > 0:
            cell_sat_ratios.append(tp / tt)
            sum_hid_p += tp
            sum_hid_t += tt
    sat_macro = round(sum(cell_sat_ratios) / len(cell_sat_ratios), 4) if cell_sat_ratios else None
    sat_micro = round(sum_hid_p / sum_hid_t, 4) if sum_hid_t > 0 else None

    # Tokens
    tok_vals = [_cell_tokens(c) for c in scored]
    known_toks = [t for t in tok_vals if t is not None]
    all_toks_known = len(known_toks) == n_scored and n_scored > 0
    total_tokens = sum(known_toks) if known_toks else None
    mean_tokens = round(sum(known_toks) / len(known_toks), 1) if known_toks else None
    tokens_per_success = (
        round(sum(known_toks) / n_pass, 1) if (known_toks and n_pass > 0) else None
    )

    # Broken-after-pass ratio
    total_broken = 0
    total_ever_passed = 0
    cell_broken_ratios: list[float] = []
    for c in scored:
        brk, ever = _cell_broken_after_pass(c)
        total_broken += brk
        total_ever_passed += ever
        if ever > 0:
            cell_broken_ratios.append(brk / ever)
    broken_micro = round(total_broken / total_ever_passed, 4) if total_ever_passed > 0 else None
    broken_macro = (
        round(sum(cell_broken_ratios) / len(cell_broken_ratios), 4)
        if cell_broken_ratios
        else None
    )

    # Wall clock
    walls = [float(c.get("wall_s") or 0.0) for c in scored]
    agent_walls = [float(c.get("agent_wall_s") or 0.0) for c in scored]
    calls_known = [x for x in (_cell_calls(c) for c in scored) if x is not None]

    # Controller action histogram (if present)
    actions: dict[str, int] = {}
    for c in scored:
        for a in c.get("attempts") or []:
            act = a.get("action")
            if act:
                actions[act] = actions.get(act, 0) + 1

    return {
        "cells": len(cells),
        "scored": n_scored,
        "infra_void": len(cells) - n_scored,
        "hidden_pass": n_pass,
        "hidden_success_rate": success_rate,
        "hidden_satisfaction_macro": sat_macro,
        "hidden_satisfaction_micro": sat_micro,
        "hidden_tests_passed": sum_hid_p,
        "hidden_tests_total": sum_hid_t,
        "hidden_detail_cells": len(cell_sat_ratios),
        "total_tokens": total_tokens,
        "mean_tokens_per_cell": mean_tokens,
        "tokens_per_success": tokens_per_success,
        "tokens_known_cells": len(known_toks),
        "all_tokens_known": all_toks_known,
        "broken_after_pass_micro": broken_micro,
        "broken_after_pass_macro": broken_macro,
        "broken_tests": total_broken,
        "ever_passed_tests": total_ever_passed,
        "mean_wall_s": round(sum(walls) / n_scored, 1) if n_scored else None,
        "median_wall_s": round(statistics.median(walls), 1) if n_scored else None,
        "total_wall_s": round(sum(walls), 1) if n_scored else None,
        "mean_agent_wall_s": round(sum(agent_walls) / n_scored, 1) if n_scored else None,
        "mean_attempts": round(sum(c.get("n_attempts", 0) for c in scored) / n_scored, 3) if n_scored else None,
        "mean_model_calls": round(sum(calls_known) / len(calls_known), 2) if calls_known else None,
        "controller_actions": dict(sorted(actions.items())) if actions else None,
    }


def paired_comparison(
    plan: dict[str, Any],
    by_key: dict[tuple[str, int, str], dict[str, Any]],
    *,
    control: str,
    treatment: str,
) -> dict[str, Any]:
    both = b = c_ = neither = 0
    excluded_void = 0
    missing = 0
    ctrl_cells: list[dict[str, Any]] = []
    treat_cells: list[dict[str, Any]] = []
    for t in plan["tasks"]:
        for r in range(1, int(plan["reps"]) + 1):
            x = by_key.get((t, r, control))
            y = by_key.get((t, r, treatment))
            if x is None or y is None:
                missing += 1
                continue
            if x.get("infra_void") or y.get("infra_void"):
                excluded_void += 1
                continue
            ctrl_cells.append(x)
            treat_cells.append(y)
            xp, yp = bool(x.get("pass")), bool(y.get("pass"))
            if xp and yp:
                both += 1
            elif xp:
                b += 1
            elif yp:
                c_ += 1
            else:
                neither += 1

    n = both + b + c_ + neither
    p_val = mcnemar_exact(b, c_)
    delta_pp = round(100.0 * (c_ - b) / n, 2) if n else None

    cm = compute_arm_metrics(ctrl_cells)
    tm = compute_arm_metrics(treat_cells)

    def _diff(a: float | None, z: float | None, ndigits: int = 2) -> float | None:
        if a is None or z is None:
            return None
        return round(a - z, ndigits)

    return {
        "name": f"{treatment}_vs_{control}",
        "control": control,
        "treatment": treatment,
        "pairs_scored": n,
        "pairs_excluded_void": excluded_void,
        "pairs_missing": missing,
        "both": both,
        "control_only_b": b,
        "treatment_only_c": c_,
        "neither": neither,
        "control_pass": both + b,
        "treatment_pass": both + c_,
        "delta_pp": delta_pp,
        "mcnemar_exact_p": round(p_val, 6),
        "cost_diff": {
            "delta_mean_tokens_per_cell": _diff(tm["mean_tokens_per_cell"], cm["mean_tokens_per_cell"], 1),
            "delta_tokens_per_success": _diff(tm["tokens_per_success"], cm["tokens_per_success"], 1),
            "delta_mean_wall_s": _diff(tm["mean_wall_s"], cm["mean_wall_s"], 1),
            "delta_mean_agent_wall_s": _diff(tm["mean_agent_wall_s"], cm["mean_agent_wall_s"], 1),
            "delta_mean_attempts": _diff(tm["mean_attempts"], cm["mean_attempts"], 3),
            "delta_mean_model_calls": _diff(tm["mean_model_calls"], cm["mean_model_calls"], 2),
        },
        "delta_hidden_satisfaction_macro": _diff(tm["hidden_satisfaction_macro"], cm["hidden_satisfaction_macro"], 4),
        "delta_broken_after_pass_micro": _diff(tm["broken_after_pass_micro"], cm["broken_after_pass_micro"], 4),
    }


def analyse(root: pathlib.Path) -> dict[str, Any]:
    run, cells = _load_cell_details(root)
    plan = run["plan"]
    by_key = {(c["task"], c["rep"], c["arm"]): c for c in cells}

    arms_out: dict[str, Any] = {}
    for arm_name in plan["arms"]:
        arm_cells = [c for c in cells if c["arm"] == arm_name]
        arms_out[arm_name] = compute_arm_metrics(arm_cells)

    comparisons: dict[str, Any] = {}
    for treat, ctrl in (("C", "B"), ("C", "R")):
        if treat in plan["arms"] and ctrl in plan["arms"]:
            comp = paired_comparison(plan, by_key, control=ctrl, treatment=treat)
            comparisons[comp["name"]] = comp

    return {
        "schema": "vacant.redo.ctl_metrics/1",
        "plan_id": plan["id"],
        "plan_sha256": run["plan_sha256"],
        "n_tasks": len(plan["tasks"]),
        "reps": int(plan["reps"]),
        "exploratory_note": f"這是 {len(plan['tasks'])} 題 × {int(plan['reps'])} 次的探索，只判斷方向（DECISION_20261127_EVIDENCE_CONTROLLER.md）。",
        "per_arm": arms_out,
        "comparisons": comparisons,
    }


def render_report(res: dict[str, Any]) -> str:
    lines = [
        f"# {res['plan_id']} — Evidence Controller Metrics",
        f"Plan sha256: `{res['plan_sha256'][:16]}…`  Tasks: {res['n_tasks']} × {res['reps']} reps",
        f"Note: {res['exploratory_note']}",
        "",
        "| Arm | Hidden Pass | Hidden Rate | Hidden Sat (macro/micro) | Tokens/Success | Broken-After-Pass | Mean Wall | Mean Attempts | Void |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for arm, m in res["per_arm"].items():
        sat = f"{m['hidden_satisfaction_macro']}/{m['hidden_satisfaction_micro']}"
        brk = f"{m['broken_after_pass_micro']} ({m['broken_tests']}/{m['ever_passed_tests']})"
        lines.append(
            f"| {arm} | {m['hidden_pass']}/{m['scored']} | {m['hidden_success_rate']} | {sat} | "
            f"{m['tokens_per_success']} | {brk} | {m['mean_wall_s']}s | {m['mean_attempts']} | {m['infra_void']} |"
        )
    if res["comparisons"]:
        lines += [
            "",
            "## Paired Comparisons (task × rep)",
            "",
            "| Comparison | Pairs | Ctrl Pass | Treat Pass | b (ctrl only) | c (treat only) | Delta (pp) | McNemar p | Delta Tokens/Cell | Delta Tokens/Success | Delta Wall (s) |",
            "|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for cname, c in res["comparisons"].items():
            cd = c["cost_diff"]
            lines.append(
                f"| {cname} | {c['pairs_scored']} | {c['control_pass']} | {c['treatment_pass']} | "
                f"{c['control_only_b']} | {c['treatment_only_c']} | {c['delta_pp']} | {c['mcnemar_exact_p']} | "
                f"{cd['delta_mean_tokens_per_cell']} | {cd['delta_tokens_per_success']} | {cd['delta_mean_wall_s']} |"
            )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Compute the 5 evidence-controller metrics and paired comparisons.")
    ap.add_argument("root", help="Run root directory containing RUN.json and cells/")
    ap.add_argument("--json", action="store_true", help="Print JSON instead of markdown summary.")
    ap.add_argument("--json-out", help="Write full JSON output to this file.")
    a = ap.parse_args(argv)

    res = analyse(pathlib.Path(a.root).expanduser().resolve())
    txt = json.dumps(res, ensure_ascii=False, indent=2)
    if a.json_out:
        pathlib.Path(a.json_out).write_text(txt + "\n", encoding="utf-8")
    if a.json:
        print(txt)
    else:
        print(render_report(res))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
