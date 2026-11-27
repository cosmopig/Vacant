#!/usr/bin/env python3
"""Metrics and paired set-cluster bootstrap analysis for Experiment T.

Scores every cell strictly against the audited cycle-0 answer key using `score_d2 --strict`
logic (comparing all version numbers and numeric tokens in order), and reports:
  - Per arm (A, G, T, T0):
      * strict-scored correct lines per set (mean & proportion) and all-correct-set ratio (primary)
      * error-type breakdown (missing / fabricated / wrong_read / stale) before (c0) vs after (final)
      * harm: lines correct before feedback and broken after (all arms, for T vs G comparison)
      * flagged-line repair (T, T0): fraction of c0-flagged lines fixed (overall & among true errors)
      * tokens, calls, wall_s (total and extra after c0), source requests, rounds used
      * Ed25519 feedback chain verification counts
  - Paired comparisons on (set, rep):
      * T vs G (primary), T vs A, G vs A, T vs T0
      * set-cluster bootstrap 95% CI on per-set correct-line proportion difference (primary)
        and on all-correct-set ratio difference, plus harm difference
  - Frozen preregistration readout evaluation (exploratory; wrong_read blind spot noted).

Usage:
    python3 ops/d2/expT_metrics.py <root> [--json] [--json-out PATH] [--boot 2000] [--seed 20261127]
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import pathlib
import random
import re
import sys
from typing import Any

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import expT_feedback as FB  # noqa: E402
import score_d2 as SD  # noqa: E402
from vacant_network.logbook import ChainError  # noqa: E402
from vacant_network.trace import sources as S  # noqa: E402

ERROR_TYPES: tuple[str, ...] = ("missing", "fabricated", "wrong_read", "stale")


def canon_strict(v: str | None) -> str | None:
    """Exact `score_d2 --strict` canonicalization without mutating global module state."""
    if v is None:
        return None
    s = v.strip().strip("`*").strip()
    toks = [
        ("v" + t[1:].lstrip("v")) if t.lower().startswith("v") else t.replace(",", "")
        for t in re.findall(r"v?\d+(?:\.\d+){2,}|\d[\d,]*(?:\.\d+)?", s)
    ]
    toks = [t[:-2] if t.endswith(".0") else t for t in toks]
    return "|".join(toks) if toks else None


def strict_status(val: str | None, cid: str, truth: list[dict[str, str]], k: int = 0) -> str:
    """Exact `score_d2.status` under `--strict`."""
    cv = canon_strict(val)
    if cv is None:
        return "missing"
    if cv == canon_strict(truth[k][cid]):
        return "correct"
    if any(cv == canon_strict(truth[j][cid]) for j in range(k)):
        return "stale"
    return "wrong"


def classify_error_type(val: str | None, status: str, page_texts: list[str]) -> str:
    """Error taxonomy matching `exp1_flags.py`:
      - correct    : not an error
      - missing    : no numeric/version value parsed
      - stale      : matches an earlier revision's truth (0 in cycle 0)
      - wrong_read : wrong value appears in at least one cycle-0 site page (plain_contains)
      - fabricated : wrong value does not appear in any cycle-0 site page
    """
    if status != "wrong":
        return status
    if val is None or not val.strip():
        return "missing"
    if any(S.plain_contains(pt, val) for pt in page_texts):
        return "wrong_read"
    return "fabricated"


def _sha_file(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifests_with_truth(
    plan: dict[str, Any],
    override_dirs: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Load manifests including cycle-0 audited truth & site page texts for scoring."""
    raw = plan["materials"]
    entries = raw if isinstance(raw, list) else [raw]
    if override_dirs:
        if len(override_dirs) != len(entries):
            raise SystemExit(
                f"--materials count ({len(override_dirs)}) must match plan materials entries ({len(entries)})"
            )
        entries = [{**e, "dir": d} for e, d in zip(entries, override_dirs)]

    sets_truth: dict[str, dict[str, Any]] = {}
    for entry in entries:
        prefix = str(entry.get("prefix") or "").strip()
        mat_dir = pathlib.Path(os.path.expandvars(os.path.expanduser(str(entry["dir"]))))
        man_path = mat_dir / "manifest.json"
        if not man_path.is_file():
            raise SystemExit(f"manifest not found: {man_path}")
        expected_sha = entry.get("manifest_sha256")
        actual_sha = _sha_file(man_path)
        if expected_sha and actual_sha != expected_sha:
            raise SystemExit(f"manifest sha mismatch for {mat_dir}: got={actual_sha} expected={expected_sha}")
        man = json.loads(man_path.read_text(encoding="utf-8"))
        by_orig = {s["set"]: s for s in man["sets"]}
        wanted = list(entry.get("sets") or [s["set"] for s in man["sets"]])
        for orig_set in wanted:
            s = by_orig[orig_set]
            qid = f"{prefix}-{orig_set}" if prefix else orig_set
            site_dir = mat_dir / "sets" / orig_set / "cycle_0" / "site"
            page_texts = [
                p.read_text(encoding="utf-8", errors="replace")
                for p in sorted(site_dir.glob("*"))
                if p.is_file()
            ]
            sets_truth[qid] = {
                "set_id": qid,
                "orig_set": orig_set,
                "domain": str(s.get("domain") or ""),
                "claims": s["claims"],
                "truth": s["truth"],
                "page_texts": page_texts,
            }
    return sets_truth


def _usage_tokens(u: dict[str, Any] | None) -> tuple[int | None, int | None, int | None]:
    if not isinstance(u, dict):
        return None, None, None
    tin = u.get("input")
    tout = u.get("output")
    if tin is None and tout is None:
        return None, None, None
    in_tot = int(tin or 0) + int(u.get("cache_creation_input_tokens") or 0) + int(u.get("cache_read_input_tokens") or 0)
    out_tot = int(tout or 0)
    return in_tot, out_tot, in_tot + out_tot


def _usage_calls(u: dict[str, Any] | None) -> int | None:
    if not isinstance(u, dict) or u.get("calls") is None:
        return None
    return int(u["calls"])


def _load_access_counts(root: pathlib.Path) -> dict[tuple[str, int, str], int]:
    """Count agent HTTP requests from `access.jsonl` keyed by (set_id, rep, arm)."""
    p = root / "access.jsonl"
    counts: dict[tuple[str, int, str], int] = collections.Counter()
    if not p.is_file():
        return {}
    for raw in p.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            rec = json.loads(raw)
        except ValueError:
            continue
        if rec.get("ua") == "vacant-source-check":
            continue
        host = str(rec.get("host") or "")
        arm = rec.get("arm")
        rep = rec.get("rep")
        if not host.endswith(".d2-sources.example") or arm is None:
            continue
        sub = host[: -len(".d2-sources.example")]
        m = re.match(r"^(.*)-r(\d+)$", sub)
        if m:
            sid, rep_i = m.group(1), int(m.group(2))
        else:
            sid, rep_i = sub, int(rep or 1)
        counts[(sid, rep_i, str(arm))] += 1
    return dict(counts)


def score_cell(
    cell_doc: dict[str, Any],
    c0_text: str,
    final_text: str,
    set_truth: dict[str, Any],
    *,
    chain_path: pathlib.Path | None = None,
    verify_chain: bool = True,
) -> dict[str, Any]:
    """Strictly score one Experiment T cell before (c0) and after (final)."""
    claims = set_truth["claims"]
    truth = set_truth["truth"]
    page_texts = set_truth["page_texts"]

    v_before = SD.parse_report(c0_text, claims)
    v_after = SD.parse_report(final_text, claims)
    c0_flagged_set = set(cell_doc.get("c0_flagged_ids") or [])

    err_before = {k: 0 for k in ERROR_TYPES}
    err_after = {k: 0 for k in ERROR_TYPES}

    n_claims = len(claims)
    correct_before = 0
    correct_after = 0
    harm_count = 0
    fixed_count = 0

    c0_flagged_total = 0
    c0_flagged_fixed = 0
    c0_flagged_errors = 0
    c0_flagged_errors_fixed = 0

    line_rows: list[dict[str, Any]] = []
    for c in claims:
        cid = str(c["id"])
        vb = v_before.get(cid)
        va = v_after.get(cid)
        sb = strict_status(vb, cid, truth, 0)
        sa = strict_status(va, cid, truth, 0)
        eb = classify_error_type(vb, sb, page_texts)
        ea = classify_error_type(va, sa, page_texts)

        if sb == "correct":
            correct_before += 1
            if sa != "correct":
                harm_count += 1
        else:
            err_before[eb] = err_before.get(eb, 0) + 1
            if sa == "correct":
                fixed_count += 1

        if sa == "correct":
            correct_after += 1
        else:
            err_after[ea] = err_after.get(ea, 0) + 1

        was_flagged = cid in c0_flagged_set
        if was_flagged:
            c0_flagged_total += 1
            if sa == "correct":
                c0_flagged_fixed += 1
            if sb != "correct":
                c0_flagged_errors += 1
                if sa == "correct":
                    c0_flagged_errors_fixed += 1

        line_rows.append({
            "claim_id": cid,
            "before_value": vb,
            "after_value": va,
            "before_status": sb,
            "after_status": sa,
            "before_etype": eb,
            "after_etype": ea,
            "c0_flagged": was_flagged,
            "harm": sb == "correct" and sa != "correct",
        })

    chain_ok: bool | None = None
    chain_error: str | None = None
    if verify_chain and chain_path is not None:
        try:
            FB.reconstruct(chain_path, emit=False)
            chain_ok = True
        except ChainError as exc:
            chain_ok = False
            chain_error = str(exc)

    tin, tout, ttot = _usage_tokens(cell_doc.get("total_usage"))
    etin, etout, ettot = _usage_tokens(cell_doc.get("extra_usage"))
    calls = _usage_calls(cell_doc.get("total_usage"))
    ecalls = _usage_calls(cell_doc.get("extra_usage"))

    return {
        "set": cell_doc["set"],
        "domain": set_truth["domain"],
        "rep": int(cell_doc["rep"]),
        "arm": str(cell_doc["arm"]),
        "infra_void": False,
        "n_claims": n_claims,
        "correct_before": correct_before,
        "correct_after": correct_after,
        "correct_prop_before": (correct_before / n_claims) if n_claims else 0.0,
        "correct_prop_after": (correct_after / n_claims) if n_claims else 0.0,
        "all_correct_before": bool(n_claims > 0 and correct_before == n_claims),
        "all_correct_after": bool(n_claims > 0 and correct_after == n_claims),
        "err_before": err_before,
        "err_after": err_after,
        "harm_count": harm_count,
        "fixed_count": fixed_count,
        "c0_flagged_total": c0_flagged_total,
        "c0_flagged_fixed": c0_flagged_fixed,
        "c0_flagged_errors": c0_flagged_errors,
        "c0_flagged_errors_fixed": c0_flagged_errors_fixed,
        "rounds_run": int(cell_doc.get("rounds_run") or 0),
        "stop_reason": cell_doc.get("stop_reason"),
        "tokens_in": tin,
        "tokens_out": tout,
        "tokens_total": ttot,
        "extra_tokens_total": ettot,
        "calls_total": calls,
        "extra_calls_total": ecalls,
        "wall_s_total": float(cell_doc.get("total_wall_s") or 0.0),
        "extra_wall_s": float(cell_doc.get("extra_wall_s") or 0.0),
        "chain_ok": chain_ok,
        "chain_error": chain_error,
        "lines": line_rows,
    }


def summarize_arm(
    cells: list[dict[str, Any]],
    *,
    access_counts: dict[tuple[str, int, str], int] | None = None,
) -> dict[str, Any]:
    scored = [c for c in cells if not c.get("infra_void")]
    n_scored = len(scored)
    n_void = len(cells) - n_scored

    by_set: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for c in scored:
        by_set[c["set"]].append(c)

    set_correct_lines = [sum(x["correct_after"] for x in xs) / len(xs) for xs in by_set.values()]
    set_correct_props = [sum(x["correct_prop_after"] for x in xs) / len(xs) for xs in by_set.values()]
    set_all_correct = [sum(1.0 for x in xs if x["all_correct_after"]) / len(xs) for xs in by_set.values()]

    tot_lines = sum(c["n_claims"] for c in scored)
    tot_corr_before = sum(c["correct_before"] for c in scored)
    tot_corr_after = sum(c["correct_after"] for c in scored)
    tot_all_corr_before = sum(1 for c in scored if c["all_correct_before"])
    tot_all_corr_after = sum(1 for c in scored if c["all_correct_after"])

    eb_counts = {k: sum(c["err_before"].get(k, 0) for c in scored) for k in ERROR_TYPES}
    ea_counts = {k: sum(c["err_after"].get(k, 0) for c in scored) for k in ERROR_TYPES}
    eb_tot = sum(eb_counts.values())
    ea_tot = sum(ea_counts.values())

    harm_tot = sum(c["harm_count"] for c in scored)
    c0_fl_tot = sum(c["c0_flagged_total"] for c in scored)
    c0_fl_fix = sum(c["c0_flagged_fixed"] for c in scored)
    c0_fl_err = sum(c["c0_flagged_errors"] for c in scored)
    c0_fl_err_fix = sum(c["c0_flagged_errors_fixed"] for c in scored)

    toks = [c["tokens_total"] for c in scored if c.get("tokens_total") is not None]
    etoks = [c["extra_tokens_total"] for c in scored if c.get("extra_tokens_total") is not None]
    tins = [c["tokens_in"] for c in scored if c.get("tokens_in") is not None]
    touts = [c["tokens_out"] for c in scored if c.get("tokens_out") is not None]
    calls = [c["calls_total"] for c in scored if c.get("calls_total") is not None]
    ecalls = [c["extra_calls_total"] for c in scored if c.get("extra_calls_total") is not None]
    walls = [c["wall_s_total"] for c in scored]
    ewalls = [c["extra_wall_s"] for c in scored]

    src_req = None
    if access_counts is not None:
        src_req = sum(
            access_counts.get((c["set"], c["rep"], c["arm"]), 0)
            + access_counts.get((c["set"], c["rep"], "c0"), 0)
            for c in scored
        )

    chains_checked = [c for c in scored if c.get("chain_ok") is not None]
    chains_ok = sum(1 for c in chains_checked if c["chain_ok"] is True)
    chains_bad = sum(1 for c in chains_checked if c["chain_ok"] is False)

    return {
        "cells_total": len(cells),
        "scored_cells": n_scored,
        "infra_void_cells": n_void,
        "sets_covered": len(by_set),
        "total_lines": tot_lines,
        "correct_lines_before_total": tot_corr_before,
        "correct_lines_after_total": tot_corr_after,
        "correct_line_proportion_before": round(tot_corr_before / tot_lines, 4) if tot_lines else None,
        "correct_line_proportion_micro": round(tot_corr_after / tot_lines, 4) if tot_lines else None,
        "mean_correct_lines_per_set": round(sum(set_correct_lines) / len(set_correct_lines), 3) if set_correct_lines else None,
        "correct_line_proportion_per_set": round(sum(set_correct_props) / len(set_correct_props), 4) if set_correct_props else None,
        "all_correct_cells_before": tot_all_corr_before,
        "all_correct_cells_after": tot_all_corr_after,
        "all_correct_set_ratio": round(tot_all_corr_after / n_scored, 4) if n_scored else None,
        "all_correct_set_ratio_macro": round(sum(set_all_correct) / len(set_all_correct), 4) if set_all_correct else None,
        "error_breakdown_before": {
            **eb_counts,
            "total_errors": eb_tot,
            "rates": {k: (round(eb_counts[k] / tot_lines, 4) if tot_lines else None) for k in ERROR_TYPES},
        },
        "error_breakdown_after": {
            **ea_counts,
            "total_errors": ea_tot,
            "rates": {k: (round(ea_counts[k] / tot_lines, 4) if tot_lines else None) for k in ERROR_TYPES},
        },
        "harm": {
            "correct_before": tot_corr_before,
            "broken_after": harm_tot,
            "harm_rate_over_correct_before": round(harm_tot / tot_corr_before, 4) if tot_corr_before else 0.0,
            "harm_rate_over_all_lines": round(harm_tot / tot_lines, 4) if tot_lines else 0.0,
        },
        "flagged_fixed": {
            "c0_flagged": c0_fl_tot,
            "c0_flagged_fixed": c0_fl_fix,
            "c0_flagged_fixed_rate": round(c0_fl_fix / c0_fl_tot, 4) if c0_fl_tot else None,
            "c0_flagged_errors": c0_fl_err,
            "c0_flagged_errors_fixed": c0_fl_err_fix,
            "c0_flagged_errors_fixed_rate": round(c0_fl_err_fix / c0_fl_err, 4) if c0_fl_err else None,
        },
        "rounds_used_mean": round(sum(c["rounds_run"] for c in scored) / n_scored, 3) if n_scored else None,
        "early_stopped_cells": sum(1 for c in scored if c.get("stop_reason") == "stop_no_flags"),
        "tokens_in_total": sum(tins) if tins else None,
        "tokens_out_total": sum(touts) if touts else None,
        "tokens_total": sum(toks) if toks else None,
        "tokens_mean_per_cell": round(sum(toks) / len(toks), 1) if toks else None,
        "extra_tokens_total": sum(etoks) if etoks else None,
        "extra_tokens_mean_per_cell": round(sum(etoks) / len(etoks), 1) if etoks else None,
        "calls_total": sum(calls) if calls else None,
        "calls_mean_per_cell": round(sum(calls) / len(calls), 2) if calls else None,
        "extra_calls_total": sum(ecalls) if ecalls else None,
        "extra_calls_mean_per_cell": round(sum(ecalls) / len(ecalls), 2) if ecalls else None,
        "wall_s_total": round(sum(walls), 2) if scored else None,
        "wall_s_mean_per_cell": round(sum(walls) / n_scored, 2) if n_scored else None,
        "extra_wall_s_total": round(sum(ewalls), 2) if scored else None,
        "extra_wall_s_mean_per_cell": round(sum(ewalls) / n_scored, 2) if n_scored else None,
        "source_requests_agent": src_req,
        "chains_checked": len(chains_checked),
        "chains_ok": chains_ok,
        "chains_bad": chains_bad,
    }


def _cluster_boot_ci(
    values_by_set: list[float],
    *,
    n_boot: int = 2000,
    seed: int = 20261127,
) -> list[float] | None:
    n = len(values_by_set)
    if n == 0 or n_boot <= 0:
        return None
    rng = random.Random(seed)
    means = []
    for _ in range(n_boot):
        s = sum(values_by_set[rng.randrange(n)] for _ in range(n)) / n
        means.append(s)
    means.sort()
    lo = means[int(0.025 * len(means))]
    hi = means[max(0, int(0.975 * len(means)) - 1)]
    return [round(lo, 4), round(hi, 4)]


def paired_comparison(
    by_key: dict[tuple[str, int, str], dict[str, Any]],
    sets: list[str],
    reps: int,
    *,
    treatment: str,
    control: str,
    n_boot: int = 2000,
    seed: int = 20261127,
) -> dict[str, Any]:
    """Paired comparison (treatment - control) with set-cluster bootstrap 95% CI on per-set
    correct-line proportion difference.
    """
    missing = 0
    excluded_void = 0
    by_set_prop_diffs: dict[str, list[float]] = collections.defaultdict(list)
    by_set_allc_diffs: dict[str, list[float]] = collections.defaultdict(list)
    paired_t: list[dict[str, Any]] = []
    paired_c: list[dict[str, Any]] = []

    for sid in sets:
        for rep in range(1, reps + 1):
            t_cell = by_key.get((sid, rep, treatment))
            c_cell = by_key.get((sid, rep, control))
            if t_cell is None or c_cell is None:
                missing += 1
                continue
            if t_cell.get("infra_void") or c_cell.get("infra_void"):
                excluded_void += 1
                continue
            paired_t.append(t_cell)
            paired_c.append(c_cell)
            by_set_prop_diffs[sid].append(t_cell["correct_prop_after"] - c_cell["correct_prop_after"])
            by_set_allc_diffs[sid].append(float(t_cell["all_correct_after"]) - float(c_cell["all_correct_after"]))

    set_ids = sorted(by_set_prop_diffs.keys())
    per_set_prop_diffs = [sum(by_set_prop_diffs[s]) / len(by_set_prop_diffs[s]) for s in set_ids]
    per_set_allc_diffs = [sum(by_set_allc_diffs[s]) / len(by_set_allc_diffs[s]) for s in set_ids]

    point_prop = round(sum(per_set_prop_diffs) / len(per_set_prop_diffs), 4) if per_set_prop_diffs else None
    ci_prop = _cluster_boot_ci(per_set_prop_diffs, n_boot=n_boot, seed=seed)

    point_allc = round(sum(per_set_allc_diffs) / len(per_set_allc_diffs), 4) if per_set_allc_diffs else None
    ci_allc = _cluster_boot_ci(per_set_allc_diffs, n_boot=n_boot, seed=seed + 1)

    t_lines = sum(x["n_claims"] for x in paired_t)
    c_lines = sum(x["n_claims"] for x in paired_c)
    t_micro = (sum(x["correct_after"] for x in paired_t) / t_lines) if t_lines else None
    c_micro = (sum(x["correct_after"] for x in paired_c) / c_lines) if c_lines else None
    micro_diff = round(t_micro - c_micro, 4) if (t_micro is not None and c_micro is not None) else None

    t_cb = sum(x["correct_before"] for x in paired_t)
    c_cb = sum(x["correct_before"] for x in paired_c)
    t_harm = (sum(x["harm_count"] for x in paired_t) / t_cb) if t_cb else 0.0
    c_harm = (sum(x["harm_count"] for x in paired_c) / c_cb) if c_cb else 0.0

    return {
        "treatment": treatment,
        "control": control,
        "paired_cells": len(paired_t),
        "paired_sets": len(set_ids),
        "missing_pairs": missing,
        "excluded_void_pairs": excluded_void,
        "per_set_correct_prop_diff": point_prop,
        "per_set_correct_prop_diff_ci95": ci_prop,
        "micro_correct_prop_diff": micro_diff,
        "all_correct_ratio_diff": point_allc,
        "all_correct_ratio_diff_ci95": ci_allc,
        "treatment_harm_rate": round(t_harm, 4) if paired_t else None,
        "control_harm_rate": round(c_harm, 4) if paired_c else None,
        "harm_rate_diff": round(t_harm - c_harm, 4) if paired_t else None,
        "harm_not_more_than_control": (t_harm <= c_harm + 1e-12) if paired_t else None,
    }


def evaluate_readout(comparisons: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Apply the frozen preregistration readout rule."""
    tg = comparisons.get("T_vs_G") or {}
    ta = comparisons.get("T_vs_A") or {}
    ga = comparisons.get("G_vs_A") or {}

    tg_diff = tg.get("per_set_correct_prop_diff")
    tg_ci = tg.get("per_set_correct_prop_diff_ci95")
    tg_harm_ok = tg.get("harm_not_more_than_control")

    ta_ci = ta.get("per_set_correct_prop_diff_ci95")
    ga_ci = ga.get("per_set_correct_prop_diff_ci95")

    if tg_diff is None or tg_ci is None:
        verdict = "incomplete"
        reason = "insufficient paired T vs G data"
    elif tg_diff >= 0.10 and tg_ci[0] > 0.0 and tg_harm_ok is True:
        verdict = "T_useful"
        reason = (
            f"T exceeds G by {tg_diff * 100:.2f}pp (>=10pp), "
            f"95% CI [{tg_ci[0] * 100:.2f}pp, {tg_ci[1] * 100:.2f}pp] > 0, and harm_T <= harm_G"
        )
    elif ta_ci and ga_ci and ta_ci[0] > 0.0 and ga_ci[0] > 0.0:
        verdict = "more_rounds_help_records_dont"
        reason = (
            f"both T and G beat A (CI lower > 0), but T vs G did not clear the >=10pp & harm bar "
            f"(T-G={tg_diff * 100:.2f}pp, CI=[{tg_ci[0] * 100:.2f}pp, {tg_ci[1] * 100:.2f}pp])"
        )
    elif (not ta_ci or ta_ci[0] <= 0.0) and (not ga_ci or ga_ci[0] <= 0.0):
        verdict = "no_effect"
        reason = "neither T nor G beats A with 95% CI lower bound > 0"
    else:
        verdict = "mixed_or_below_threshold"
        reason = (
            f"T vs G = {tg_diff * 100:.2f}pp (CI [{tg_ci[0] * 100:.2f}pp, {tg_ci[1] * 100:.2f}pp], "
            f"harm_ok={tg_harm_ok}); did not satisfy T_useful bar"
        )

    return {
        "verdict": verdict,
        "reason": reason,
        "frozen_rule": (
            "primary T vs G; T counts as useful iff T's correct-line proportion exceeds G's by "
            ">=10 percentage points with paired CI lower bound >0 and harm not more than G's; "
            "T≈G with both > A => 'more rounds help, records don't'; neither > A => no effect"
        ),
        "caveat": (
            "exploratory: these 37 sets were used in experiment 1 and v5.2 was tuned on football data; "
            "known blind spot: wrong_read recall ~11-29%"
        ),
    }


def analyze_root(
    root: pathlib.Path,
    *,
    override_materials: list[str] | None = None,
    n_boot: int = 2000,
    seed: int = 20261127,
    verify_chains: bool = True,
) -> dict[str, Any]:
    run_path = root / "RUN.json"
    if not run_path.is_file():
        raise SystemExit(f"RUN.json not found in {root}")
    run_doc = json.loads(run_path.read_text(encoding="utf-8"))
    plan = run_doc["plan_body"]
    sets_truth = load_manifests_with_truth(plan, override_dirs=override_materials)
    sets_order = list(sets_truth.keys())
    reps = int(plan.get("reps") or 2)
    arms = list(plan.get("arms") or FB.EXPT_ARMS)

    access_counts = _load_access_counts(root)
    by_arm: dict[str, list[dict[str, Any]]] = {a: [] for a in arms}
    by_key: dict[tuple[str, int, str], dict[str, Any]] = {}

    cells_dir = root / "cells"
    if cells_dir.is_dir():
        for sid in sets_order:
            for rep in range(1, reps + 1):
                rdir = cells_dir / sid / f"r{rep}"
                c0_rep_path = rdir / "c0" / "report.md"
                c0_text = c0_rep_path.read_text(encoding="utf-8", errors="replace") if c0_rep_path.is_file() else ""
                for arm in arms:
                    adir = rdir / arm
                    cpath = adir / "cell.json"
                    if not cpath.is_file():
                        continue
                    cdoc = json.loads(cpath.read_text(encoding="utf-8"))
                    if cdoc.get("infra_void"):
                        rec = {"set": sid, "rep": rep, "arm": arm, "infra_void": True, "error": cdoc.get("error")}
                    else:
                        final_path = adir / "report.md"
                        final_text = final_path.read_text(encoding="utf-8", errors="replace") if final_path.is_file() else ""
                        chain_path = adir / "feedback_chain.ndjson"
                        rec = score_cell(
                            cdoc, c0_text, final_text, sets_truth[sid],
                            chain_path=chain_path if chain_path.is_file() else None,
                            verify_chain=verify_chains,
                        )
                    by_arm.setdefault(arm, []).append(rec)
                    by_key[(sid, rep, arm)] = rec

    arm_summaries = {
        arm: summarize_arm(by_arm.get(arm, []), access_counts=access_counts)
        for arm in arms
    }

    pair_specs = [
        ("T_vs_G", "T", "G"),
        ("T_vs_A", "T", "A"),
        ("G_vs_A", "G", "A"),
        ("T_vs_T0", "T", "T0"),
    ]
    comparisons = {}
    for idx, (name, treat, ctrl) in enumerate(pair_specs):
        comparisons[name] = paired_comparison(
            by_key, sets_order, reps,
            treatment=treat, control=ctrl,
            n_boot=n_boot, seed=seed + idx * 100,
        )

    return {
        "schema": "vacant.d2.expT.metrics/1",
        "root": str(root.name),
        "plan_id": plan.get("id"),
        "plan_sha256": run_doc.get("plan_sha256"),
        "sets_planned": len(sets_order),
        "reps_planned": reps,
        "arms": arms,
        "boot": n_boot,
        "seed": seed,
        "by_arm": arm_summaries,
        "comparisons": comparisons,
        "readout": evaluate_readout(comparisons),
    }


def format_report(res: dict[str, Any]) -> str:
    lines = [
        f"Experiment T Metrics — plan={res.get('plan_id')} root={res.get('root')} "
        f"(sets={res['sets_planned']}, reps={res['reps_planned']}, boot={res['boot']})",
        "",
        "Per-Arm Strict-Scored Summary:",
        f"  {'Arm':<4} {'Cells':>5} {'Corr/Set':>8} {'Prop/Set':>8} {'AllCorr':>8} {'Harm':>7} {'FlFix':>7} {'Calls':>6} {'Tokens':>9} {'Wall(s)':>8} {'Chains':>7}",
    ]
    for arm in res["arms"]:
        a = res["by_arm"][arm]
        cps = f"{a['mean_correct_lines_per_set']:.2f}" if a["mean_correct_lines_per_set"] is not None else "n/a"
        pps = f"{a['correct_line_proportion_per_set'] * 100:.1f}%" if a["correct_line_proportion_per_set"] is not None else "n/a"
        acr = f"{a['all_correct_set_ratio'] * 100:.1f}%" if a["all_correct_set_ratio"] is not None else "n/a"
        hrm = f"{a['harm']['harm_rate_over_correct_before'] * 100:.1f}%"
        flf = (
            f"{a['flagged_fixed']['c0_flagged_fixed_rate'] * 100:.1f}%"
            if a["flagged_fixed"]["c0_flagged_fixed_rate"] is not None
            else "n/a"
        )
        cls = f"{a['calls_mean_per_cell']:.1f}" if a["calls_mean_per_cell"] is not None else "n/a"
        tok = f"{a['tokens_mean_per_cell']:.0f}" if a["tokens_mean_per_cell"] is not None else "n/a"
        wll = f"{a['wall_s_mean_per_cell']:.1f}" if a["wall_s_mean_per_cell"] is not None else "n/a"
        chk = f"{a['chains_ok']}/{a['chains_checked']}"
        lines.append(
            f"  {arm:<4} {a['scored_cells']:>5} {cps:>8} {pps:>8} {acr:>8} {hrm:>7} {flf:>7} {cls:>6} {tok:>9} {wll:>8} {chk:>7}"
        )

    lines.append("")
    lines.append("Error Breakdown (Before c0 -> After final):")
    for arm in res["arms"]:
        a = res["by_arm"][arm]
        eb = a["error_breakdown_before"]
        ea = a["error_breakdown_after"]
        lines.append(
            f"  {arm:<4} before: missing={eb['missing']} fabricated={eb['fabricated']} "
            f"wrong_read={eb['wrong_read']} stale={eb['stale']} (tot={eb['total_errors']}) | "
            f"after: missing={ea['missing']} fabricated={ea['fabricated']} "
            f"wrong_read={ea['wrong_read']} stale={ea['stale']} (tot={ea['total_errors']})"
        )

    lines.append("")
    lines.append("Paired Comparisons (set-cluster bootstrap 95% CI on per-set correct-line proportion diff):")
    for name, comp in res["comparisons"].items():
        tag = " [PRIMARY]" if name == "T_vs_G" else ""
        diff = comp["per_set_correct_prop_diff"]
        ci = comp["per_set_correct_prop_diff_ci95"]
        if diff is None or ci is None:
            lines.append(f"  {name}{tag}: n/a (paired_cells={comp['paired_cells']})")
        else:
            lines.append(
                f"  {name}{tag}: diff={diff * 100:+.2f}pp "
                f"95%CI=[{ci[0] * 100:+.2f}pp, {ci[1] * 100:+.2f}pp] "
                f"all_corr_diff={comp['all_correct_ratio_diff'] * 100:+.2f}pp "
                f"harm_diff={comp['harm_rate_diff'] * 100:+.2f}pp "
                f"(sets={comp['paired_sets']}, pairs={comp['paired_cells']})"
            )

    ro = res["readout"]
    lines.append("")
    lines.append(f"Readout: {ro['verdict']} — {ro['reason']}")
    lines.append(f"Caveat:  {ro['caveat']}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Compute Experiment T strict-scored metrics & paired bootstrap CIs.")
    ap.add_argument("root", help="Experiment T run root directory (containing RUN.json and cells/)")
    ap.add_argument("--materials", nargs="+", help="Optional override material dirs matching plan order")
    ap.add_argument("--boot", type=int, default=2000, help="Set-cluster bootstrap resamples (default: 2000)")
    ap.add_argument("--seed", type=int, default=20261127, help="Bootstrap RNG seed (default: 20261127)")
    ap.add_argument("--no-verify-chains", action="store_true", help="Skip Ed25519 feedback chain verification")
    ap.add_argument("--json", action="store_true", help="Print JSON instead of human-readable summary")
    ap.add_argument("--json-out", help="Optional path to write full JSON output")
    a = ap.parse_args()

    res = analyze_root(
        pathlib.Path(a.root).expanduser().resolve(),
        override_materials=a.materials,
        n_boot=a.boot,
        seed=a.seed,
        verify_chains=not a.no_verify_chains,
    )
    if a.json_out:
        out_p = pathlib.Path(a.json_out).expanduser()
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(res, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(format_report(res))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
