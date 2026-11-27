#!/usr/bin/env python3
"""Analysis for the external-exam pilot (exam37).

Computes from one or more redo.py run roots (e.g., part-1 + part-2 combined):
  - Per-arm success on independent hidden grading (+ hidden satisfaction ratio).
  - Paired exact two-sided McNemar on (task, rep): every arm vs N3 (main) and vs A.
  - Gain share = (arm - N3) / (GT - N3). If GT - N3 <= 0, prints "題組無法區分".
  - Qualification check per frozen prereg: gain_share >= 0.5 AND false_accept_rate <= 2 * GT's.
  - False-accept and false-block (false-reject) rates per arm (cell-level and attempt-level).
  - Stratified success-rate table by XM exam correctness (reference-pass 28 vs 9 tasks).
  - Tokens (total, mean/cell, per success) and wall clock per arm.
  - Per-stream tok/s and timeout counts from agent logs (session jsonl / agent.log).

Usage:
    python3 ops/redo/analysis/exam_metrics.py <root> [<part2_root> ...] [--json] [--json-out PATH]
    python3 ops/redo/analysis/exam_metrics.py <part1_root> <part2_root> --reference-ok-json <path>
"""
from __future__ import annotations

import argparse
from collections.abc import Sequence
import datetime as _dt
import json
import math
import pathlib
import statistics
from typing import Any

DEFAULT_REFERENCE_OK_JSON = pathlib.Path(__file__).resolve().parent / "exam37_xm_reference_ok.json"


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2.0 * sum(math.comb(n, i) for i in range(k + 1)) / (2.0 ** n))


def _iso_to_s(ts: str) -> float:
    return _dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()


def _quantile(xs: list[float], q: float) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    idx = min(len(s) - 1, int(q * (len(s) - 1) + 0.5))
    return round(s[idx], 2)


def _extract_stream_samples(cdir: pathlib.Path, n_attempts: int) -> tuple[str | None, list[tuple[int, float]]]:
    """Extract (output_tokens, duration_s) samples per assistant turn from pi session logs or agent.log.

    Returns (source_label, [(out_toks, dt_s), ...]).
    """
    # 1. Preferred: pi session JSONL files (exact assistant completion ISO timestamp vs msg start ms).
    sess_samples: list[tuple[int, float]] = []
    for k in range(1, n_attempts + 1):
        sdir = cdir / f"attempt_{k}" / "logs" / "sessions"
        if not sdir.is_dir():
            continue
        for sp in sorted(sdir.rglob("*.jsonl")):
            prev_ts: float | None = None
            try:
                lines = sp.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for line in lines:
                line = line.strip()
                if not line.startswith("{"):
                    continue
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if e.get("type") != "message" or "timestamp" not in e:
                    continue
                try:
                    ev_ts = _iso_to_s(str(e["timestamp"]))
                except ValueError:
                    continue
                msg = e.get("message") or {}
                role = msg.get("role")
                if role == "assistant":
                    u = msg.get("usage") or {}
                    out_tok = int(u.get("output") or u.get("output_tokens") or u.get("completion_tokens") or 0)
                    msg_ts_raw = msg.get("timestamp")
                    start_ts: float | None = None
                    if isinstance(msg_ts_raw, (int, float)) and msg_ts_raw > 0:
                        start_ts = float(msg_ts_raw) / 1000.0 if msg_ts_raw > 1e11 else float(msg_ts_raw)
                    elif prev_ts is not None:
                        start_ts = prev_ts
                    if start_ts is not None and out_tok > 0:
                        dt = ev_ts - start_ts
                        if dt > 0.0:
                            sess_samples.append((out_tok, dt))
                    prev_ts = None
                elif role in ("user", "toolResult"):
                    prev_ts = ev_ts
    if sess_samples:
        return "session_jsonl", sess_samples

    # 2. Fallback: agent.log message_end + next toolResult/turn timestamp delta.
    log_samples: list[tuple[int, float]] = []
    for k in range(1, n_attempts + 1):
        lp = cdir / f"attempt_{k}" / "agent.log"
        if not lp.is_file():
            continue
        try:
            lines = lp.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        pending_out: int | None = None
        pending_start_s: float | None = None
        for line in lines:
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            t = obj.get("type")
            msg = obj.get("message") if isinstance(obj.get("message"), dict) else None
            if t == "message_end" and msg is not None and msg.get("role") == "assistant":
                if msg.get("stopReason") == "error" or msg.get("errorMessage"):
                    pending_out = None
                    pending_start_s = None
                    continue
                u = msg.get("usage") or {}
                out_tok = int(u.get("output") or u.get("output_tokens") or u.get("completion_tokens") or 0)
                ts_raw = msg.get("timestamp")
                if out_tok > 0 and isinstance(ts_raw, (int, float)) and ts_raw > 0:
                    pending_out = out_tok
                    pending_start_s = float(ts_raw) / 1000.0 if ts_raw > 1e11 else float(ts_raw)
            elif t == "message_start" and msg is not None and msg.get("role") in ("toolResult", "user"):
                ts_raw = msg.get("timestamp")
                if pending_out is not None and pending_start_s is not None and isinstance(ts_raw, (int, float)) and ts_raw > 0:
                    end_s = float(ts_raw) / 1000.0 if ts_raw > 1e11 else float(ts_raw)
                    dt = end_s - pending_start_s
                    if dt > 0.0:
                        log_samples.append((pending_out, dt))
                pending_out = None
                pending_start_s = None
    if log_samples:
        return "agent_log", log_samples

    return None, []


def _summarize_tok_s(samples: list[tuple[int, float]], source: str | None) -> dict[str, Any]:
    if not samples:
        return {
            "source": source,
            "n_turns": 0,
            "total_output_tokens": 0,
            "total_gen_s": 0.0,
            "aggregate": None,
            "median": None,
            "mean": None,
            "p10": None,
            "p90": None,
        }
    rates = [tok / dt for tok, dt in samples if dt > 0]
    tot_tok = sum(tok for tok, _ in samples)
    tot_dt = sum(dt for _, dt in samples)
    return {
        "source": source,
        "n_turns": len(rates),
        "total_output_tokens": tot_tok,
        "total_gen_s": round(tot_dt, 2),
        "aggregate": round(tot_tok / tot_dt, 2) if tot_dt > 0 else None,
        "median": _quantile(rates, 0.5),
        "mean": round(statistics.fmean(rates), 2) if rates else None,
        "p10": _quantile(rates, 0.1),
        "p90": _quantile(rates, 0.9),
    }


def _load_cells(root: pathlib.Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    run = json.loads((root / "RUN.json").read_text(encoding="utf-8"))
    plan_sha = run["plan_sha256"]
    cells: list[dict[str, Any]] = []
    for cpath in sorted((root / "cells").glob("*/r*/*/cell.json")):
        cell = json.loads(cpath.read_text(encoding="utf-8"))
        if cell.get("plan_sha256") != plan_sha:
            continue
        cdir = cpath.parent
        n_att = int(cell.get("n_attempts") or len(cell.get("attempts") or []))
        afiles: list[dict[str, Any]] = []
        for k in range(1, n_att + 1):
            ap = cdir / f"attempt_{k}" / "attempt.json"
            if ap.is_file():
                try:
                    afiles.append(json.loads(ap.read_text(encoding="utf-8")))
                except (OSError, ValueError):
                    afiles.append({})
            else:
                afiles.append({})
        cell["_attempt_files"] = afiles
        cell["_cdir"] = cdir
        cells.append(cell)
    return run, cells


def _cell_tokens(cell: dict[str, Any]) -> tuple[int | None, int | None, int | None]:
    """Return (total, input, output) tokens across attempts, or (None, None, None) if missing."""
    atts = cell.get("attempts") or []
    if not atts:
        return None, None, None
    tin_sum = tout_sum = 0
    for a in atts:
        u = a.get("usage")
        if not isinstance(u, dict):
            return None, None, None
        tin = u.get("input")
        tout = u.get("output")
        if tin is None and tout is None:
            return None, None, None
        tin_sum += int(tin or 0)
        tout_sum += int(tout or 0)
    return tin_sum + tout_sum, tin_sum, tout_sum


def _cell_hidden_counts(cell: dict[str, Any]) -> tuple[int | None, int | None]:
    d_1 = cell.get("delivered_attempt")
    if not d_1:
        return None, None
    idx = int(d_1) - 1
    afiles = cell.get("_attempt_files") or []
    if 0 <= idx < len(afiles):
        det = (afiles[idx].get("grade") or {}).get("detail") or {}
        tp, tt = det.get("tests_passed"), det.get("tests_total")
        if isinstance(tp, int) and isinstance(tt, int) and tt > 0:
            return tp, tt
    return None, None


def _is_arm_gated(arm_cfg: dict[str, Any]) -> bool:
    if arm_cfg.get("acceptance_source") is not None:
        return True
    return arm_cfg.get("policy") in ("restart", "controller")


def _cell_fa_fr(cell: dict[str, Any], *, gated: bool) -> tuple[bool | None, bool | None, int, int]:
    """Return (cell_false_accept, cell_false_reject, fa_attempts, fr_attempts)."""
    if not gated:
        return None, None, 0, 0
    atts = cell.get("attempts") or []
    fa_att = sum(1 for a in atts if bool(a.get("accept")) and a.get("grade_pass") is False)
    fr_att = sum(1 for a in atts if (not bool(a.get("accept"))) and a.get("grade_pass") is True)
    fa = cell.get("false_accept")
    if fa is None:
        fa = bool(cell.get("accepted")) and (cell.get("pass") is False)
    fr = cell.get("false_reject")
    if fr is None:
        fr = fr_att > 0
    return bool(fa), bool(fr), fa_att, fr_att


def compute_arm_metrics(arm_name: str, arm_cfg: dict[str, Any], cells: list[dict[str, Any]]) -> tuple[dict[str, Any], list[tuple[int, float]], str | None]:
    scored = [c for c in cells if not c.get("infra_void")]
    n_scored = len(scored)
    n_pass = sum(1 for c in scored if c.get("pass") is True)
    success_rate = round(n_pass / n_scored, 4) if n_scored else None

    # Hidden satisfaction
    sat_ratios: list[float] = []
    hid_p = hid_t = 0
    for c in scored:
        tp, tt = _cell_hidden_counts(c)
        if tp is not None and tt is not None and tt > 0:
            sat_ratios.append(tp / tt)
            hid_p += tp
            hid_t += tt

    # False-accept & false-reject
    gated = _is_arm_gated(arm_cfg)
    fa_cells = fr_cells = fa_att = fr_att = accepted_cells = total_atts = hid_pass_atts = 0
    timeouts = cells_with_timeout = 0
    for c in scored:
        atts = c.get("attempts") or []
        total_atts += len(atts)
        if c.get("accepted"):
            accepted_cells += 1
        hid_pass_atts += sum(1 for a in atts if a.get("grade_pass") is True)
        n_to = sum(1 for a in atts if a.get("timed_out"))
        timeouts += n_to
        if n_to > 0:
            cells_with_timeout += 1
        fa, fr, fa_a, fr_a = _cell_fa_fr(c, gated=gated)
        if fa:
            fa_cells += 1
        if fr:
            fr_cells += 1
        fa_att += fa_a
        fr_att += fr_a

    # Tokens & wall
    toks_tot: list[int] = []
    toks_in: list[int] = []
    toks_out: list[int] = []
    for c in scored:
        t_tot, t_in, t_out = _cell_tokens(c)
        if t_tot is not None and t_in is not None and t_out is not None:
            toks_tot.append(t_tot)
            toks_in.append(t_in)
            toks_out.append(t_out)
    walls = [float(c.get("wall_s") or 0.0) for c in scored]
    agent_walls = [float(c.get("agent_wall_s") or 0.0) for c in scored]

    # Per-stream tok/s from agent logs
    stream_samples: list[tuple[int, float]] = []
    stream_source: str | None = None
    for c in scored:
        cdir = c.get("_cdir")
        if isinstance(cdir, pathlib.Path):
            src, smp = _extract_stream_samples(cdir, int(c.get("n_attempts") or len(c.get("attempts") or [])))
            if smp:
                stream_samples.extend(smp)
                if stream_source is None:
                    stream_source = src
    # Fallback to attempt-level output_tokens / wall_s if no timestamped logs found
    if not stream_samples:
        fb: list[tuple[int, float]] = []
        for c in scored:
            for a in c.get("attempts") or []:
                u = a.get("usage")
                ws = float(a.get("wall_s") or 0.0)
                if isinstance(u, dict) and u.get("output") and ws > 0:
                    fb.append((int(u["output"]), ws))
        if fb:
            stream_samples = fb
            stream_source = "attempt_wall"

    tok_s_summary = _summarize_tok_s(stream_samples, stream_source)

    metrics = {
        "arm": arm_name,
        "policy": arm_cfg.get("policy"),
        "acceptance_source": arm_cfg.get("acceptance_source"),
        "acceptance_pass_ratio": arm_cfg.get("acceptance_pass_ratio"),
        "gated": gated,
        "cells": len(cells),
        "scored": n_scored,
        "infra_void": len(cells) - n_scored,
        "hidden_pass": n_pass,
        "hidden_success_rate": success_rate,
        "hidden_satisfaction_macro": round(sum(sat_ratios) / len(sat_ratios), 4) if sat_ratios else None,
        "hidden_satisfaction_micro": round(hid_p / hid_t, 4) if hid_t > 0 else None,
        "accepted_cells": accepted_cells if gated else None,
        "false_accept_cells": fa_cells if gated else None,
        "false_accept_rate": round(fa_cells / n_scored, 4) if (gated and n_scored) else None,
        "false_accept_among_accepted": round(fa_cells / accepted_cells, 4) if (gated and accepted_cells) else None,
        "false_accept_attempts": fa_att if gated else None,
        "false_reject_cells": fr_cells if gated else None,
        "false_reject_rate": round(fr_cells / n_scored, 4) if (gated and n_scored) else None,
        "false_reject_attempts": fr_att if gated else None,
        "false_reject_attempt_rate": round(fr_att / total_atts, 4) if (gated and total_atts) else None,
        "false_reject_among_hidden_pass_attempts": round(fr_att / hid_pass_atts, 4) if (gated and hid_pass_atts) else None,
        "false_block_cells": fr_cells if gated else None,
        "false_block_cell_rate": round(fr_cells / n_scored, 4) if (gated and n_scored) else None,
        "false_block_rate": round(fr_cells / n_scored, 4) if (gated and n_scored) else None,
        "false_block_attempts": fr_att if gated else None,
        "false_block_attempt_rate": round(fr_att / total_atts, 4) if (gated and total_atts) else None,
        "false_block_among_hidden_pass_attempts": round(fr_att / hid_pass_atts, 4) if (gated and hid_pass_atts) else None,
        "total_tokens": sum(toks_tot) if toks_tot else None,
        "mean_tokens_per_cell": round(sum(toks_tot) / len(toks_tot), 1) if toks_tot else None,
        "mean_input_tokens": round(sum(toks_in) / len(toks_in), 1) if toks_in else None,
        "mean_output_tokens": round(sum(toks_out) / len(toks_out), 1) if toks_out else None,
        "tokens_per_success": round(sum(toks_tot) / n_pass, 1) if (toks_tot and n_pass > 0) else None,
        "tokens_known_cells": len(toks_tot),
        "mean_wall_s": round(sum(walls) / n_scored, 1) if n_scored else None,
        "median_wall_s": round(statistics.median(walls), 1) if n_scored else None,
        "total_wall_s": round(sum(walls), 1) if n_scored else None,
        "mean_agent_wall_s": round(sum(agent_walls) / n_scored, 1) if n_scored else None,
        "mean_attempts": round(total_atts / n_scored, 3) if n_scored else None,
        "total_attempts": total_atts,
        "timeouts": timeouts,
        "timeout_rate": round(timeouts / total_atts, 4) if total_atts else None,
        "cells_with_timeout": cells_with_timeout,
        "per_stream_tok_s": tok_s_summary,
    }
    return metrics, stream_samples, stream_source


def paired_mcnemar(
    plan: dict[str, Any],
    by_key: dict[tuple[str, int, str], dict[str, Any]],
    *,
    control: str,
    treatment: str,
) -> dict[str, Any]:
    both = b = c_ = neither = excluded_void = missing = 0
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
    p = mcnemar_exact(b, c_)
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
        "delta_pp": round(100.0 * (c_ - b) / n, 2) if n else None,
        "mcnemar_exact_p": round(p, 6),
    }


def _normalize_roots(
    root: pathlib.Path | str | Sequence[pathlib.Path | str],
    extra_roots: Sequence[pathlib.Path | str] | None = None,
) -> list[pathlib.Path]:
    if isinstance(root, (pathlib.Path, str)):
        roots = [pathlib.Path(root)]
    else:
        roots = [pathlib.Path(r) for r in root]
    if extra_roots:
        roots.extend(pathlib.Path(r) for r in extra_roots)
    if not roots:
        raise ValueError("At least one run root is required.")
    return roots


def _resolve_reference_ok(
    plan_tasks: list[str],
    reference_ok: dict[str, Any] | pathlib.Path | str | None,
) -> tuple[dict[str, Any] | None, str | None]:
    if reference_ok is None:
        if DEFAULT_REFERENCE_OK_JSON.is_file():
            try:
                data = json.loads(DEFAULT_REFERENCE_OK_JSON.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return None, None
            known = set(data.get("xm_reference_ok") or []) | set(data.get("xm_reference_fail") or [])
            if known and (set(plan_tasks) & known):
                return data, str(DEFAULT_REFERENCE_OK_JSON)
        return None, None
    if isinstance(reference_ok, (pathlib.Path, str)):
        p = pathlib.Path(reference_ok).expanduser().resolve()
        return json.loads(p.read_text(encoding="utf-8")), str(p)
    return dict(reference_ok), str(reference_ok.get("source_report") or "inline")


def _stratify_by_ok_set(
    plan_tasks: list[str],
    arms_cfg: dict[str, dict[str, Any]],
    cells: list[dict[str, Any]],
    ok_tasks: set[str],
) -> dict[str, Any]:
    ok_list = [t for t in plan_tasks if t in ok_tasks]
    fail_list = [t for t in plan_tasks if t not in ok_tasks]
    out: dict[str, Any] = {}
    for label, task_subset in (("xm_ref_ok", ok_list), ("xm_ref_fail", fail_list)):
        tset = set(task_subset)
        per_arm_s: dict[str, Any] = {}
        for arm_name, arm_cfg in arms_cfg.items():
            sub_cells = [c for c in cells if c["arm"] == arm_name and c["task"] in tset and not c.get("infra_void")]
            n_sc = len(sub_cells)
            n_p = sum(1 for c in sub_cells if c.get("pass") is True)
            gated = _is_arm_gated(arm_cfg)
            fa_c = fb_c = fb_a = tot_a = 0
            for c in sub_cells:
                atts = c.get("attempts") or []
                tot_a += len(atts)
                fa, fr, _fa_a, fr_a = _cell_fa_fr(c, gated=gated)
                if fa:
                    fa_c += 1
                if fr:
                    fb_c += 1
                fb_a += fr_a
            per_arm_s[arm_name] = {
                "scored": n_sc,
                "hidden_pass": n_p,
                "hidden_success_rate": round(n_p / n_sc, 4) if n_sc else None,
                "false_accept_cells": fa_c if gated else None,
                "false_accept_rate": round(fa_c / n_sc, 4) if (gated and n_sc) else None,
                "false_block_cells": fb_c if gated else None,
                "false_block_cell_rate": round(fb_c / n_sc, 4) if (gated and n_sc) else None,
                "false_block_attempts": fb_a if gated else None,
                "false_block_attempt_rate": round(fb_a / tot_a, 4) if (gated and tot_a) else None,
            }
        gt_r = (per_arm_s.get("GT") or {}).get("hidden_success_rate")
        n3_r = (per_arm_s.get("N3") or {}).get("hidden_success_rate")
        diff = round(gt_r - n3_r, 6) if (gt_r is not None and n3_r is not None) else None
        for m in per_arm_s.values():
            r = m["hidden_success_rate"]
            if diff is not None and diff > 0.0 and r is not None and n3_r is not None:
                m["gain_share"] = round((r - n3_r) / diff, 4)
            else:
                m["gain_share"] = None
        out[label] = {
            "n_tasks": len(task_subset),
            "tasks": task_subset,
            "gt_minus_n3": diff,
            "per_arm": per_arm_s,
        }
    return out


def analyse(
    root: pathlib.Path | str | Sequence[pathlib.Path | str],
    *,
    extra_roots: Sequence[pathlib.Path | str] | None = None,
    false_block_rates: dict[str, float] | None = None,
    reference_ok: dict[str, Any] | pathlib.Path | str | None = None,
) -> dict[str, Any]:
    roots = _normalize_roots(root, extra_roots)
    runs: list[dict[str, Any]] = []
    merged_arms: dict[str, dict[str, Any]] = {}
    arm_source_plan: dict[str, str] = {}
    cells: list[dict[str, Any]] = []
    roots_meta: list[dict[str, Any]] = []

    base_tasks: list[str] | None = None
    base_tasks_set: set[str] | None = None
    base_reps: int | None = None

    for rpath in roots:
        run, r_cells = _load_cells(rpath)
        plan = run["plan"]
        r_tasks = list(plan["tasks"])
        r_reps = int(plan["reps"])
        if base_tasks is None:
            base_tasks = r_tasks
            base_tasks_set = set(r_tasks)
            base_reps = r_reps
        else:
            if set(r_tasks) != base_tasks_set:
                diff_only_a = sorted((base_tasks_set or set()) - set(r_tasks))
                diff_only_b = sorted(set(r_tasks) - (base_tasks_set or set()))
                raise ValueError(
                    f"Cannot combine roots with different task sets: {rpath} "
                    f"(missing={diff_only_a[:5]}, extra={diff_only_b[:5]})"
                )
            if r_reps != base_reps:
                raise ValueError(
                    f"Cannot combine roots with different reps: expected {base_reps}, got {r_reps} in {rpath}"
                )
        for arm_name, arm_cfg in plan["arms"].items():
            if arm_name in merged_arms:
                raise ValueError(
                    f"Duplicate arm {arm_name!r} when combining roots ({arm_source_plan[arm_name]} vs {plan['id']})"
                )
            merged_arms[arm_name] = arm_cfg
            arm_source_plan[arm_name] = str(plan["id"])
        cells.extend(r_cells)
        runs.append(run)
        roots_meta.append({
            "root": str(rpath),
            "plan_id": plan["id"],
            "plan_sha256": run["plan_sha256"],
            "created": run.get("created"),
            "arms": list(plan["arms"].keys()),
        })

    assert base_tasks is not None and base_reps is not None
    merged_plan = {
        "id": runs[0]["plan"]["id"] if len(runs) == 1 else " + ".join(r["plan"]["id"] for r in runs),
        "tasks": base_tasks,
        "reps": base_reps,
        "arms": merged_arms,
    }
    plan_sha_label = (
        runs[0]["plan_sha256"]
        if len(runs) == 1
        else " + ".join(r["plan_sha256"][:12] for r in runs)
    )
    by_key = {(c["task"], c["rep"], c["arm"]): c for c in cells}

    per_arm: dict[str, Any] = {}
    all_samples: list[tuple[int, float]] = []
    all_source: str | None = None
    total_timeouts = 0
    total_attempts = 0

    for arm_name, arm_cfg in merged_arms.items():
        arm_cells = [c for c in cells if c["arm"] == arm_name]
        m, smp, src = compute_arm_metrics(arm_name, arm_cfg, arm_cells)
        m["source_plan_id"] = arm_source_plan[arm_name]
        if false_block_rates and arm_name in false_block_rates:
            m["premeasured_false_block_rate"] = false_block_rates[arm_name]
        per_arm[arm_name] = m
        all_samples.extend(smp)
        if all_source is None and src is not None:
            all_source = src
        total_timeouts += int(m["timeouts"] or 0)
        total_attempts += int(m["total_attempts"] or 0)

    # Paired McNemar vs N3 (main) and vs A
    vs_n3: dict[str, Any] = {}
    if "N3" in merged_arms:
        for arm_name in merged_arms:
            if arm_name != "N3":
                vs_n3[arm_name] = paired_mcnemar(merged_plan, by_key, control="N3", treatment=arm_name)

    vs_a: dict[str, Any] = {}
    if "A" in merged_arms:
        for arm_name in merged_arms:
            if arm_name != "A":
                vs_a[arm_name] = paired_mcnemar(merged_plan, by_key, control="A", treatment=arm_name)

    # Gain share = (arm - N3) / (GT - N3)
    gt_rate = (per_arm.get("GT") or {}).get("hidden_success_rate")
    n3_rate = (per_arm.get("N3") or {}).get("hidden_success_rate")
    gt_fa = (per_arm.get("GT") or {}).get("false_accept_rate")
    gt_minus_n3 = round(gt_rate - n3_rate, 6) if (gt_rate is not None and n3_rate is not None) else None
    discriminable = bool(gt_minus_n3 is not None and gt_minus_n3 > 0.0)
    verdict = "DISCRIMINABLE" if discriminable else "題組無法區分"

    gain_share: dict[str, float | None] = {}
    qualification: dict[str, dict[str, Any]] = {}
    for arm_name, m in per_arm.items():
        r = m["hidden_success_rate"]
        if discriminable and r is not None and n3_rate is not None and gt_minus_n3:
            gs = round((r - n3_rate) / gt_minus_n3, 4)
        else:
            gs = None
        gain_share[arm_name] = gs
        m["gain_share"] = gs
        if str(m.get("acceptance_source") or "").startswith("exam:"):
            fa = m["false_accept_rate"]
            fa_limit = (2.0 * gt_fa) if gt_fa is not None else None
            gs_ok = gs is not None and gs >= 0.5
            fa_ok = fa is not None and fa_limit is not None and fa <= fa_limit + 1e-12
            qual = bool(discriminable and gs_ok and fa_ok)
            qualification[arm_name] = {
                "qualifies": qual,
                "gain_share": gs,
                "gain_share_ge_0_5": gs_ok,
                "false_accept_rate": fa,
                "gt_false_accept_rate": gt_fa,
                "false_accept_le_2x_gt": fa_ok,
                "false_block_rate": m.get("false_block_rate"),
                "false_block_cell_rate": m.get("false_block_cell_rate"),
                "false_block_attempt_rate": m.get("false_block_attempt_rate"),
                "premeasured_false_block_rate": m.get("premeasured_false_block_rate"),
            }

    # Stratified table by XM exam correctness (reference solution passes fully vs rest)
    ref_ok_data, ref_ok_src = _resolve_reference_ok(base_tasks, reference_ok)
    stratified: dict[str, Any] | None = None
    if ref_ok_data is not None:
        xm_ok_list = ref_ok_data.get("xm_reference_ok")
        if xm_ok_list is None:
            xm_ok_list = ref_ok_data.get("reference_ok")
        if isinstance(xm_ok_list, list):
            stratified = {
                "source": ref_ok_src,
                **_stratify_by_ok_set(base_tasks, merged_arms, cells, set(xm_ok_list)),
            }

    return {
        "schema": "vacant.redo.exam_metrics/1",
        "plan_id": merged_plan["id"],
        "plan_sha256": plan_sha_label,
        "roots": roots_meta,
        "n_tasks": len(base_tasks),
        "reps": base_reps,
        "gt_rate": gt_rate,
        "n3_rate": n3_rate,
        "gt_minus_n3": gt_minus_n3,
        "discriminable": discriminable,
        "verdict": verdict,
        "per_arm": per_arm,
        "gain_share": gain_share,
        "qualification": qualification,
        "paired_vs_N3": vs_n3,
        "paired_vs_A": vs_a,
        "stratified_by_xm_reference_ok": stratified,
        "overall_per_stream_tok_s": _summarize_tok_s(all_samples, all_source),
        "overall_timeouts": {
            "timeouts": total_timeouts,
            "total_attempts": total_attempts,
            "timeout_rate": round(total_timeouts / total_attempts, 4) if total_attempts else None,
        },
    }


def render_report(res: dict[str, Any]) -> str:
    sha_disp = res["plan_sha256"][:16] + "…" if len(res["roots"]) == 1 else res["plan_sha256"]
    lines = [
        f"# {res['plan_id']} — External Exam Pilot Metrics",
        f"Plan sha256: `{sha_disp}`  Tasks: {res['n_tasks']} × {res['reps']} reps",
        f"GT - N3: `{res['gt_minus_n3']}`  Verdict: **{res['verdict']}**",
    ]
    if len(res.get("roots") or []) > 1:
        parts_s = "; ".join(f"{r['plan_id']} ({','.join(r['arms'])})" for r in res["roots"])
        lines.append(f"Combined roots ({len(res['roots'])}): {parts_s}")
    if not res["discriminable"]:
        lines.append("")
        lines.append("> **題組無法區分**（GT 相對於 N3 沒有正增益，GT − N3 ≤ 0；不做外考合格判定）")
    lines += [
        "",
        "## Per-Arm Summary",
        "",
        "| Arm | Source | Hidden Pass | Rate | Gain Share | FA (cell) | FB / FR (cell; att) | Mean Tok | Tok/Pass | Mean Wall | Timeouts | Tok/s (med/agg) | Void |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for arm, m in res["per_arm"].items():
        src_s = m["acceptance_source"] or "—"
        if m.get("acceptance_pass_ratio") is not None:
            src_s = f"{src_s} (≥{m['acceptance_pass_ratio']})"
        fa_s = f"{m['false_accept_rate']} ({m['false_accept_cells']}/{m['scored']})" if m["gated"] else "—"
        fb_s = (
            f"{m['false_block_cell_rate']} ({m['false_block_cells']}/{m['scored']}; "
            f"att {m['false_block_attempt_rate']} {m['false_block_attempts']}/{m['total_attempts']})"
            if m["gated"] else "—"
        )
        ts = m["per_stream_tok_s"]
        tps_s = f"{ts['median']}/{ts['aggregate']}" if ts["n_turns"] else "—"
        lines.append(
            f"| {arm} | {src_s} | {m['hidden_pass']}/{m['scored']} | {m['hidden_success_rate']} | "
            f"{m['gain_share']} | {fa_s} | {fb_s} | {m['mean_tokens_per_cell']} | {m['tokens_per_success']} | "
            f"{m['mean_wall_s']}s | {m['timeouts']}/{m['total_attempts']} | {tps_s} | {m['infra_void']} |"
        )

    if res["qualification"]:
        lines += [
            "",
            "## Exam Qualification (frozen prereg: gain_share >= 0.5 AND FA <= 2× GT)",
            "",
            "| Exam | Qualifies | Gain Share | FA Rate | 2× GT FA | False-Block (cell) | False-Block (att) |",
            "|---|---|---|---|---|---|---|",
        ]
        for arm, q in res["qualification"].items():
            lim = round(2.0 * q["gt_false_accept_rate"], 4) if q["gt_false_accept_rate"] is not None else None
            lines.append(
                f"| {arm} | {q['qualifies']} | {q['gain_share']} | {q['false_accept_rate']} | {lim} | "
                f"{q['false_block_cell_rate']} | {q['false_block_attempt_rate']} |"
            )

    strat = res.get("stratified_by_xm_reference_ok")
    if strat:
        ok_s = strat["xm_ref_ok"]
        fl_s = strat["xm_ref_fail"]
        lines += [
            "",
            f"## Stratified by XM Exam Correctness (Reference-Pass: {ok_s['n_tasks']} vs {fl_s['n_tasks']} tasks)",
            "",
            f"| Arm | All ({res['n_tasks']}t) | XM ref-ok ({ok_s['n_tasks']}t) | XM ref-fail ({fl_s['n_tasks']}t) | FB cell (ok / fail) |",
            "|---|---|---|---|---|",
        ]
        for arm, m in res["per_arm"].items():
            mo = ok_s["per_arm"][arm]
            mf = fl_s["per_arm"][arm]
            all_cell = f"{m['hidden_success_rate']} ({m['hidden_pass']}/{m['scored']})"
            ok_cell = f"{mo['hidden_success_rate']} ({mo['hidden_pass']}/{mo['scored']})"
            fl_cell = f"{mf['hidden_success_rate']} ({mf['hidden_pass']}/{mf['scored']})"
            fb_cell = f"{mo['false_block_cell_rate']} / {mf['false_block_cell_rate']}" if m["gated"] else "—"
            lines.append(f"| {arm} | {all_cell} | {ok_cell} | {fl_cell} | {fb_cell} |")

    for title, comp_map in (("Paired McNemar vs N3 (main)", res["paired_vs_N3"]), ("Paired McNemar vs A", res["paired_vs_A"])):
        if not comp_map:
            continue
        lines += [
            "",
            f"## {title}",
            "",
            "| Arm | Pairs | Ctrl Pass | Arm Pass | b (ctrl only) | c (arm only) | Delta (pp) | McNemar p |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for arm, c in comp_map.items():
            lines.append(
                f"| {arm} | {c['pairs_scored']} | {c['control_pass']} | {c['treatment_pass']} | "
                f"{c['control_only_b']} | {c['treatment_only_c']} | {c['delta_pp']} | {c['mcnemar_exact_p']} |"
            )

    ot = res["overall_per_stream_tok_s"]
    oto = res["overall_timeouts"]
    lines += [
        "",
        f"Overall per-stream tok/s ({ot['source']}): n={ot['n_turns']} median={ot['median']} mean={ot['mean']} "
        f"p10={ot['p10']} p90={ot['p90']} aggregate={ot['aggregate']}",
        f"Overall timeouts: {oto['timeouts']}/{oto['total_attempts']} ({oto['timeout_rate']})",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Analyze external-exam pilot results (single or combined part-1 + part-2 roots).")
    ap.add_argument("roots", nargs="+", help="One or more run root directories containing RUN.json and cells/")
    ap.add_argument("--json", action="store_true", help="Print JSON instead of markdown.")
    ap.add_argument("--json-out", help="Write full JSON output to this file.")
    ap.add_argument("--false-block-json", help="Optional JSON mapping exam arm name -> pre-measured reference false-block rate.")
    ap.add_argument("--reference-ok-json", help="Optional JSON listing XM reference-pass tasks (default: exam37_xm_reference_ok.json if tasks match).")
    a = ap.parse_args(argv)

    fb: dict[str, float] | None = None
    if a.false_block_json:
        fb = json.loads(pathlib.Path(a.false_block_json).expanduser().read_text(encoding="utf-8"))

    resolved_roots = [pathlib.Path(r).expanduser().resolve() for r in a.roots]
    res = analyse(resolved_roots, false_block_rates=fb, reference_ok=a.reference_ok_json)
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
