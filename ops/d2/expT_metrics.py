#!/usr/bin/env python3
"""Metrics, paired set-cluster bootstrap analysis, and secondary offline draft selection for Experiment T.

Scores every cell strictly against the audited cycle-0 answer key using `score_d2 --strict`
logic (comparing all version numbers and numeric tokens in order), and reports:
  1. Three primary metrics side by side for every arm (`A, G, T, TB, TO, TE, TER`):
       (a) per-set correct-line proportion (plus micro proportion & all-correct-set ratio)
       (b) filled-line precision (correct among lines that have a value; micro & per-set),
           plus originally-filled-lines (`c0_filled`) correct proportion
       (c) harm, reported separately:
             - correct->wrong/deleted count (and breakdown: correct->wrong vs correct->deleted)
             - blank->wrong-value count
  2. Error-type breakdown (missing / fabricated / wrong_read / stale) before (c0) vs after (final),
     fix rate of sent-back lines, stratification by truth numeric length, tokens/calls/wall,
     source requests, rounds used, withheld-line count, and Ed25519 feedback/escalation chain checks.
  3. Host-side Haiku escalation (TE / TER): Haiku USD and tokens per report, TE vs TER paired
     comparison, and comparison against optional whole-report Haiku A-arm reference point.
  4. Frozen preregistration readout:
       - Primary comparisons: T vs G, T vs TB, T vs TO, TE vs TER
       - Indistinguishable guards: A > 85% or A < 10% or T sent feedback in < 1/4 of cells
       - Harm warning: any arm with clearly higher harm than A is labelled "trading errors for fills"
       - Recorded prediction (vacant-cloud, marked as a prediction): T beats A, indistinguishable from TB
  5. Frozen revision-0 page snapshot verification against `access.jsonl`.
  6. Secondary offline analysis (no new runs): best-of-N draft selection per set by RECORD-ONLY
     evidence score (`supported - unsupported`, ties by fewer blanks) vs random pick vs oracle best.

Usage:
    python3 ops/d2/expT_metrics.py <root> [--haiku-full-root DIR] [--json] [--json-out PATH]
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
RECORDED_PREDICTION: str = (
    "Recorded prediction (vacant-cloud, marked as a prediction): "
    "T beats A but is indistinguishable from TB."
)


def canon_strict(v: str | None) -> str | None:
    """Exact `score_d2 --strict` canonicalization without mutating global module state."""
    return FB.canon_strict(v)


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


def digit_length_bucket(truth_val: str | None) -> str:
    """Stratification bucket by digit count in truth canonical value (`<=2`, `3-4`, `>=5`)."""
    digits = re.sub(r"\D+", "", str(truth_val or ""))
    n = len(digits)
    if n <= 2:
        return "le2"
    if n <= 4:
        return "3to4"
    return "ge5"


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
    in_tot = (
        int(tin or 0)
        + int(u.get("cache_creation_input_tokens") or 0)
        + int(u.get("cache_read_input_tokens") or 0)
    )
    out_tot = int(tout or 0)
    return in_tot, out_tot, in_tot + out_tot


def _usage_calls(u: dict[str, Any] | None) -> int | None:
    if not isinstance(u, dict) or u.get("calls") is None:
        return None
    return int(u["calls"])


def _parse_access_log(root: pathlib.Path) -> list[dict[str, Any]]:
    p = root / "access.jsonl"
    if not p.is_file():
        return []
    out: list[dict[str, Any]] = []
    for raw in p.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            out.append(json.loads(raw))
        except ValueError:
            continue
    return out


def _access_counts_from_rows(rows: list[dict[str, Any]]) -> dict[tuple[str, int, str], int]:
    counts: dict[tuple[str, int, str], int] = collections.Counter()
    for rec in rows:
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


def verify_snapshot_pinning(
    root: pathlib.Path,
    sets_order: list[str],
    reps: int,
    access_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Verify every HTTP 200 access across all arms/rounds hit revision 0's exact frozen SHA-256."""
    pinned: dict[tuple[str, int], dict[str, str]] = {}
    for sid in sets_order:
        for rep in range(1, reps + 1):
            sp = root / "cells" / sid / f"r{rep}" / "c0" / "site_snapshot_sha256.json"
            if sp.is_file():
                safe = re.sub(r"[^a-z0-9-]+", "-", sid.lower()).strip("-")
                pinned[(safe, rep)] = json.loads(sp.read_text(encoding="utf-8"))

    checked = 0
    mismatches: list[dict[str, Any]] = []
    for rec in access_rows:
        if int(rec.get("status") or 0) != 200:
            continue
        host = str(rec.get("host") or "")
        if not host.endswith(".d2-sources.example"):
            continue
        sub = host[: -len(".d2-sources.example")]
        m = re.match(r"^(.*)-r(\d+)$", sub)
        if not m:
            continue
        key = (m.group(1), int(m.group(2)))
        if key not in pinned:
            continue
        rel = str(rec.get("path") or "").lstrip("/") or "index.html"
        expected_sha = pinned[key].get(rel)
        actual_sha = rec.get("sha256")
        cyc = rec.get("cycle")
        checked += 1
        if cyc not in (0, None) or (expected_sha is not None and actual_sha != expected_sha):
            mismatches.append({
                "host": host,
                "path": rel,
                "arm": rec.get("arm"),
                "cycle": cyc,
                "expected_sha256": expected_sha,
                "actual_sha256": actual_sha,
            })

    return {
        "pinned_set_reps": len(pinned),
        "requests_checked": checked,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches[:20],
        "ok": len(mismatches) == 0,
    }


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
    if "sent_back_ids" in cell_doc and cell_doc["sent_back_ids"] is not None:
        sent_back_set = set(cell_doc["sent_back_ids"])
    else:
        sent_back_set = set(c0_flagged_set) if cell_doc.get("arm") not in ("A", "G") else set()

    err_before = {k: 0 for k in ERROR_TYPES}
    err_after = {k: 0 for k in ERROR_TYPES}

    n_claims = len(claims)
    correct_before = 0
    correct_after = 0
    filled_before = 0
    filled_after = 0
    blank_before = 0
    c0_filled_correct_after = 0

    harm_c2w_count = 0          # correct -> wrong / stale
    harm_c2d_count = 0          # correct -> deleted / missing
    harm_b2w_count = 0          # blank (missing) -> wrong / stale
    fixed_count = 0

    sent_total = 0
    sent_fixed = 0
    sent_errors = 0
    sent_errors_fixed = 0

    line_rows: list[dict[str, Any]] = []
    for c in claims:
        cid = str(c["id"])
        vb = v_before.get(cid)
        va = v_after.get(cid)
        sb = strict_status(vb, cid, truth, 0)
        sa = strict_status(va, cid, truth, 0)
        eb = classify_error_type(vb, sb, page_texts)
        ea = classify_error_type(va, sa, page_texts)

        is_filled_before = sb != "missing"
        is_filled_after = sa != "missing"
        if is_filled_before:
            filled_before += 1
            if sa == "correct":
                c0_filled_correct_after += 1
        else:
            blank_before += 1
        if is_filled_after:
            filled_after += 1

        line_harm_c2w_or_d = False
        line_harm_b2w = False

        if sb == "correct":
            correct_before += 1
            if sa == "missing":
                harm_c2d_count += 1
                line_harm_c2w_or_d = True
            elif sa != "correct":
                harm_c2w_count += 1
                line_harm_c2w_or_d = True
        else:
            err_before[eb] = err_before.get(eb, 0) + 1
            if sa == "correct":
                fixed_count += 1
            if sb == "missing" and sa not in ("correct", "missing"):
                harm_b2w_count += 1
                line_harm_b2w = True

        if sa == "correct":
            correct_after += 1
        else:
            err_after[ea] = err_after.get(ea, 0) + 1

        was_sent = cid in sent_back_set
        if was_sent:
            sent_total += 1
            if sa == "correct":
                sent_fixed += 1
            if sb != "correct":
                sent_errors += 1
                if sa == "correct":
                    sent_errors_fixed += 1

        line_rows.append({
            "claim_id": cid,
            "before_value": vb,
            "after_value": va,
            "before_status": sb,
            "after_status": sa,
            "before_etype": eb,
            "after_etype": ea,
            "digit_bucket": digit_length_bucket(truth[0].get(cid)),
            "c0_flagged": cid in c0_flagged_set,
            "sent_back": was_sent,
            "harm_c2w_or_d": line_harm_c2w_or_d,
            "harm_b2w": line_harm_b2w,
        })

    harm_c2w_or_d = harm_c2w_count + harm_c2d_count
    harm_total = harm_c2w_or_d + harm_b2w_count

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

    hesc = cell_doc.get("haiku_escalation") if isinstance(cell_doc.get("haiku_escalation"), dict) else None
    haiku_in = int(hesc.get("input_tokens") or 0) if hesc else None
    haiku_out = int(hesc.get("output_tokens") or 0) if hesc else None
    haiku_cost = float(hesc.get("cost_usd") or 0.0) if hesc else None
    haiku_called = bool(hesc.get("called")) if hesc else False

    rounds_run = int(cell_doc.get("rounds_run") or 0)
    fb_sent = int(cell_doc.get("feedback_sent_count") if cell_doc.get("feedback_sent_count") is not None else rounds_run)

    return {
        "set": cell_doc["set"],
        "domain": set_truth["domain"],
        "rep": int(cell_doc["rep"]),
        "arm": str(cell_doc["arm"]),
        "infra_void": False,
        "n_claims": n_claims,
        "correct_before": correct_before,
        "correct_after": correct_after,
        "filled_before": filled_before,
        "filled_after": filled_after,
        "blank_before": blank_before,
        "c0_filled_correct_after": c0_filled_correct_after,
        "correct_prop_before": (correct_before / n_claims) if n_claims else 0.0,
        "correct_prop_after": (correct_after / n_claims) if n_claims else 0.0,
        "filled_precision_before": (correct_before / filled_before) if filled_before else None,
        "filled_precision_after": (correct_after / filled_after) if filled_after else None,
        "c0_filled_correct_prop": (c0_filled_correct_after / filled_before) if filled_before else None,
        "all_correct_before": bool(n_claims > 0 and correct_before == n_claims),
        "all_correct_after": bool(n_claims > 0 and correct_after == n_claims),
        "err_before": err_before,
        "err_after": err_after,
        "harm_c2w_or_d": harm_c2w_or_d,
        "harm_c2w": harm_c2w_count,
        "harm_c2d": harm_c2d_count,
        "harm_b2w": harm_b2w_count,
        "harm_total": harm_total,
        "harm_c2w_or_d_rate": (harm_c2w_or_d / n_claims) if n_claims else 0.0,
        "harm_b2w_rate": (harm_b2w_count / n_claims) if n_claims else 0.0,
        "harm_total_rate": (harm_total / n_claims) if n_claims else 0.0,
        "fixed_count": fixed_count,
        "sent_back_total": sent_total,
        "sent_back_fixed": sent_fixed,
        "sent_back_errors": sent_errors,
        "sent_back_errors_fixed": sent_errors_fixed,
        "rounds_run": rounds_run,
        "feedback_sent_count": fb_sent,
        "withheld_total": int(cell_doc.get("withheld_total") or 0),
        "stop_reason": cell_doc.get("stop_reason"),
        "tokens_in": tin,
        "tokens_out": tout,
        "tokens_total": ttot,
        "extra_tokens_total": ettot,
        "calls_total": calls,
        "extra_calls_total": ecalls,
        "wall_s_total": float(cell_doc.get("total_wall_s") or 0.0),
        "extra_wall_s": float(cell_doc.get("extra_wall_s") or 0.0),
        "haiku_called": haiku_called,
        "haiku_input_tokens": haiku_in,
        "haiku_output_tokens": haiku_out,
        "haiku_tokens_total": (haiku_in + haiku_out) if (haiku_in is not None and haiku_out is not None) else None,
        "haiku_cost_usd": haiku_cost,
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

    set_filled_precs: list[float] = []
    set_c0_filled_props: list[float] = []
    for xs in by_set.values():
        fps = [x["filled_precision_after"] for x in xs if x["filled_precision_after"] is not None]
        if fps:
            set_filled_precs.append(sum(fps) / len(fps))
        c0ps = [x["c0_filled_correct_prop"] for x in xs if x["c0_filled_correct_prop"] is not None]
        if c0ps:
            set_c0_filled_props.append(sum(c0ps) / len(c0ps))

    tot_lines = sum(c["n_claims"] for c in scored)
    tot_corr_before = sum(c["correct_before"] for c in scored)
    tot_corr_after = sum(c["correct_after"] for c in scored)
    tot_filled_before = sum(c["filled_before"] for c in scored)
    tot_filled_after = sum(c["filled_after"] for c in scored)
    tot_blank_before = sum(c["blank_before"] for c in scored)
    tot_c0_filled_corr_after = sum(c["c0_filled_correct_after"] for c in scored)
    tot_all_corr_before = sum(1 for c in scored if c["all_correct_before"])
    tot_all_corr_after = sum(1 for c in scored if c["all_correct_after"])

    eb_counts = {k: sum(c["err_before"].get(k, 0) for c in scored) for k in ERROR_TYPES}
    ea_counts = {k: sum(c["err_after"].get(k, 0) for c in scored) for k in ERROR_TYPES}
    eb_tot = sum(eb_counts.values())
    ea_tot = sum(ea_counts.values())

    harm_c2w_or_d_tot = sum(c["harm_c2w_or_d"] for c in scored)
    harm_c2w_tot = sum(c["harm_c2w"] for c in scored)
    harm_c2d_tot = sum(c["harm_c2d"] for c in scored)
    harm_b2w_tot = sum(c["harm_b2w"] for c in scored)
    harm_tot = harm_c2w_or_d_tot + harm_b2w_tot

    sent_tot = sum(c["sent_back_total"] for c in scored)
    sent_fix = sum(c["sent_back_fixed"] for c in scored)
    sent_err = sum(c["sent_back_errors"] for c in scored)
    sent_err_fix = sum(c["sent_back_errors_fixed"] for c in scored)

    # Stratification by digit length bucket
    by_digit: dict[str, dict[str, int]] = {
        b: {"lines": 0, "correct_before": 0, "correct_after": 0}
        for b in ("le2", "3to4", "ge5")
    }
    for c in scored:
        for ln in c["lines"]:
            b = ln.get("digit_bucket") or "le2"
            by_digit[b]["lines"] += 1
            if ln["before_status"] == "correct":
                by_digit[b]["correct_before"] += 1
            if ln["after_status"] == "correct":
                by_digit[b]["correct_after"] += 1
    digit_strat = {
        b: {
            **d,
            "prop_before": round(d["correct_before"] / d["lines"], 4) if d["lines"] else None,
            "prop_after": round(d["correct_after"] / d["lines"], 4) if d["lines"] else None,
        }
        for b, d in by_digit.items()
    }

    toks = [c["tokens_total"] for c in scored if c.get("tokens_total") is not None]
    etoks = [c["extra_tokens_total"] for c in scored if c.get("extra_tokens_total") is not None]
    tins = [c["tokens_in"] for c in scored if c.get("tokens_in") is not None]
    touts = [c["tokens_out"] for c in scored if c.get("tokens_out") is not None]
    calls = [c["calls_total"] for c in scored if c.get("calls_total") is not None]
    ecalls = [c["extra_calls_total"] for c in scored if c.get("extra_calls_total") is not None]
    walls = [c["wall_s_total"] for c in scored]
    ewalls = [c["extra_wall_s"] for c in scored]

    h_costs = [c["haiku_cost_usd"] for c in scored if c.get("haiku_cost_usd") is not None]
    h_in = [c["haiku_input_tokens"] for c in scored if c.get("haiku_input_tokens") is not None]
    h_out = [c["haiku_output_tokens"] for c in scored if c.get("haiku_output_tokens") is not None]
    h_tot = [c["haiku_tokens_total"] for c in scored if c.get("haiku_tokens_total") is not None]
    h_called = sum(1 for c in scored if c.get("haiku_called"))

    fb_sent_cells = sum(1 for c in scored if int(c.get("feedback_sent_count") or 0) > 0)
    withheld_tot = sum(int(c.get("withheld_total") or 0) for c in scored)

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
        # Primary metric (a): per-set correct-line proportion
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
        # Primary metric (b): filled-line precision (correct among lines that have a value)
        "filled_lines_before_total": tot_filled_before,
        "filled_lines_after_total": tot_filled_after,
        "filled_precision_before_micro": round(tot_corr_before / tot_filled_before, 4) if tot_filled_before else None,
        "filled_precision_micro": round(tot_corr_after / tot_filled_after, 4) if tot_filled_after else None,
        "filled_precision_per_set": round(sum(set_filled_precs) / len(set_filled_precs), 4) if set_filled_precs else None,
        "c0_filled_correct_prop_micro": round(tot_c0_filled_corr_after / tot_filled_before, 4) if tot_filled_before else None,
        "c0_filled_correct_prop_per_set": round(sum(set_c0_filled_props) / len(set_c0_filled_props), 4) if set_c0_filled_props else None,
        # Primary metric (c): harm reported separately
        "harm": {
            "correct_before": tot_corr_before,
            "blank_before": tot_blank_before,
            "correct_to_wrong_or_deleted": harm_c2w_or_d_tot,
            "correct_to_wrong": harm_c2w_tot,
            "correct_to_deleted": harm_c2d_tot,
            "blank_to_wrong": harm_b2w_tot,
            "harm_total": harm_tot,
            "correct_to_wrong_or_deleted_rate_over_correct_before": (
                round(harm_c2w_or_d_tot / tot_corr_before, 4) if tot_corr_before else 0.0
            ),
            "blank_to_wrong_rate_over_blank_before": (
                round(harm_b2w_tot / tot_blank_before, 4) if tot_blank_before else 0.0
            ),
            "correct_to_wrong_or_deleted_rate_over_all_lines": (
                round(harm_c2w_or_d_tot / tot_lines, 4) if tot_lines else 0.0
            ),
            "blank_to_wrong_rate_over_all_lines": (
                round(harm_b2w_tot / tot_lines, 4) if tot_lines else 0.0
            ),
            "harm_total_rate_over_all_lines": (
                round(harm_tot / tot_lines, 4) if tot_lines else 0.0
            ),
        },
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
        "sent_back_fixed": {
            "sent_back_total": sent_tot,
            "sent_back_fixed": sent_fix,
            "sent_back_fixed_rate": round(sent_fix / sent_tot, 4) if sent_tot else None,
            "sent_back_errors": sent_err,
            "sent_back_errors_fixed": sent_err_fix,
            "sent_back_errors_fixed_rate": round(sent_err_fix / sent_err, 4) if sent_err else None,
        },
        "by_digit_length": digit_strat,
        "rounds_used_mean": round(sum(c["rounds_run"] for c in scored) / n_scored, 3) if n_scored else None,
        "feedback_sent_cells": fb_sent_cells,
        "feedback_sent_rate": round(fb_sent_cells / n_scored, 4) if n_scored else None,
        "withheld_total": withheld_tot,
        "early_stopped_cells": sum(1 for c in scored if c.get("stop_reason") in ("stop_no_flags", "stop_yoked_no_flags")),
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
        "haiku": (
            {
                "calls_total": h_called,
                "input_tokens_total": sum(h_in),
                "output_tokens_total": sum(h_out),
                "tokens_total": sum(h_tot),
                "tokens_mean_per_report": round(sum(h_tot) / len(h_tot), 1) if h_tot else 0.0,
                "cost_usd_total": round(sum(h_costs), 6),
                "cost_usd_mean_per_report": round(sum(h_costs) / len(h_costs), 6) if h_costs else 0.0,
            }
            if h_costs
            else None
        ),
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
    """Paired comparison (treatment - control) with set-cluster bootstrap 95% CIs on (a), (b), c0-filled, and (c)."""
    missing = 0
    excluded_void = 0
    by_set_prop: dict[str, list[float]] = collections.defaultdict(list)
    by_set_allc: dict[str, list[float]] = collections.defaultdict(list)
    by_set_fprec: dict[str, list[float]] = collections.defaultdict(list)
    by_set_c0fill: dict[str, list[float]] = collections.defaultdict(list)
    by_set_hc2w: dict[str, list[float]] = collections.defaultdict(list)
    by_set_hb2w: dict[str, list[float]] = collections.defaultdict(list)
    by_set_htot: dict[str, list[float]] = collections.defaultdict(list)
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
            by_set_prop[sid].append(t_cell["correct_prop_after"] - c_cell["correct_prop_after"])
            by_set_allc[sid].append(float(t_cell["all_correct_after"]) - float(c_cell["all_correct_after"]))
            if t_cell["filled_precision_after"] is not None and c_cell["filled_precision_after"] is not None:
                by_set_fprec[sid].append(t_cell["filled_precision_after"] - c_cell["filled_precision_after"])
            if t_cell["c0_filled_correct_prop"] is not None and c_cell["c0_filled_correct_prop"] is not None:
                by_set_c0fill[sid].append(t_cell["c0_filled_correct_prop"] - c_cell["c0_filled_correct_prop"])
            by_set_hc2w[sid].append(t_cell["harm_c2w_or_d_rate"] - c_cell["harm_c2w_or_d_rate"])
            by_set_hb2w[sid].append(t_cell["harm_b2w_rate"] - c_cell["harm_b2w_rate"])
            by_set_htot[sid].append(t_cell["harm_total_rate"] - c_cell["harm_total_rate"])

    def _agg(d: dict[str, list[float]], off: int) -> tuple[float | None, list[float] | None]:
        sids = sorted(d.keys())
        vals = [sum(d[s]) / len(d[s]) for s in sids]
        pt = round(sum(vals) / len(vals), 4) if vals else None
        ci = _cluster_boot_ci(vals, n_boot=n_boot, seed=seed + off)
        return pt, ci

    point_prop, ci_prop = _agg(by_set_prop, 0)
    point_allc, ci_allc = _agg(by_set_allc, 1)
    point_fprec, ci_fprec = _agg(by_set_fprec, 2)
    point_c0fill, ci_c0fill = _agg(by_set_c0fill, 3)
    point_hc2w, ci_hc2w = _agg(by_set_hc2w, 4)
    point_hb2w, ci_hb2w = _agg(by_set_hb2w, 5)
    point_htot, ci_htot = _agg(by_set_htot, 6)

    t_lines = sum(x["n_claims"] for x in paired_t)
    c_lines = sum(x["n_claims"] for x in paired_c)
    t_micro = (sum(x["correct_after"] for x in paired_t) / t_lines) if t_lines else None
    c_micro = (sum(x["correct_after"] for x in paired_c) / c_lines) if c_lines else None
    micro_diff = round(t_micro - c_micro, 4) if (t_micro is not None and c_micro is not None) else None

    t_hc2w_tot = sum(x["harm_c2w_or_d"] for x in paired_t)
    c_hc2w_tot = sum(x["harm_c2w_or_d"] for x in paired_c)
    t_hb2w_tot = sum(x["harm_b2w"] for x in paired_t)
    c_hb2w_tot = sum(x["harm_b2w"] for x in paired_c)
    t_htot_rate = ((t_hc2w_tot + t_hb2w_tot) / t_lines) if t_lines else 0.0
    c_htot_rate = ((c_hc2w_tot + c_hb2w_tot) / c_lines) if c_lines else 0.0
    t_hc2w_rate = (t_hc2w_tot / t_lines) if t_lines else 0.0
    c_hc2w_rate = (c_hc2w_tot / c_lines) if c_lines else 0.0

    return {
        "treatment": treatment,
        "control": control,
        "paired_cells": len(paired_t),
        "paired_sets": len(by_set_prop),
        "missing_pairs": missing,
        "excluded_void_pairs": excluded_void,
        "per_set_correct_prop_diff": point_prop,
        "per_set_correct_prop_diff_ci95": ci_prop,
        "micro_correct_prop_diff": micro_diff,
        "all_correct_ratio_diff": point_allc,
        "all_correct_ratio_diff_ci95": ci_allc,
        "per_set_filled_precision_diff": point_fprec,
        "per_set_filled_precision_diff_ci95": ci_fprec,
        "per_set_c0_filled_correct_prop_diff": point_c0fill,
        "per_set_c0_filled_correct_prop_diff_ci95": ci_c0fill,
        "per_set_harm_c2w_or_d_rate_diff": point_hc2w,
        "per_set_harm_c2w_or_d_rate_diff_ci95": ci_hc2w,
        "per_set_harm_b2w_rate_diff": point_hb2w,
        "per_set_harm_b2w_rate_diff_ci95": ci_hb2w,
        "per_set_harm_total_rate_diff": point_htot,
        "per_set_harm_total_rate_diff_ci95": ci_htot,
        "treatment_harm_c2w_or_d": t_hc2w_tot,
        "control_harm_c2w_or_d": c_hc2w_tot,
        "treatment_harm_b2w": t_hb2w_tot,
        "control_harm_b2w": c_hb2w_tot,
        "treatment_harm_total_rate": round(t_htot_rate, 4) if paired_t else None,
        "control_harm_total_rate": round(c_htot_rate, 4) if paired_c else None,
        "harm_c2w_not_more_than_control": (t_hc2w_rate <= c_hc2w_rate + 1e-12) if paired_t else None,
        "harm_not_more_than_control": (t_htot_rate <= c_htot_rate + 1e-12) if paired_t else None,
    }


def load_haiku_full_reference(
    ref_root: pathlib.Path,
    sets_truth: dict[str, dict[str, Any]],
    sets_order: list[str],
    reps: int,
) -> dict[str, Any]:
    """Load a whole-report Haiku A-arm run root for TE cost-saving & correctness-gap comparison."""
    cells_dir = ref_root / "cells"
    if not cells_dir.is_dir():
        raise SystemExit(f"haiku_full_root cells/ not found: {cells_dir}")

    scored_by_set: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    costs: list[float] = []
    toks: list[int] = []
    n_cells = 0

    for sid in sets_order:
        st = sets_truth[sid]
        orig_sid = st["orig_set"]
        for rep in range(1, reps + 1):
            candidates = [
                cells_dir / sid / f"r{rep}" / "A",
                cells_dir / sid / f"r{rep}" / "c0",
                cells_dir / orig_sid / f"r{rep}" / "A",
                cells_dir / orig_sid / f"r{rep}" / "c0",
            ]
            if rep == 1:
                candidates += [cells_dir / sid / "c0", cells_dir / orig_sid / "c0"]
            hit_dir = next((p for p in candidates if (p / "report.md").is_file()), None)
            if hit_dir is None:
                continue
            text = (hit_dir / "report.md").read_text(encoding="utf-8", errors="replace")
            vals = SD.parse_report(text, st["claims"])
            n_cl = len(st["claims"])
            corr = sum(1 for c in st["claims"] if strict_status(vals.get(c["id"]), c["id"], st["truth"], 0) == "correct")
            filled = sum(1 for c in st["claims"] if strict_status(vals.get(c["id"]), c["id"], st["truth"], 0) != "missing")

            cost_usd: float | None = None
            tot_tok: int | None = None
            for meta_name in ("cell.json", "done.json"):
                mp = hit_dir / meta_name
                if mp.is_file():
                    md = json.loads(mp.read_text(encoding="utf-8"))
                    if md.get("infra_void"):
                        cost_usd = None
                        break
                    if md.get("cost_usd") is not None:
                        cost_usd = float(md["cost_usd"])
                    elif isinstance(md.get("haiku_escalation"), dict) and md["haiku_escalation"].get("cost_usd") is not None:
                        cost_usd = float(md["haiku_escalation"]["cost_usd"])
                    u = md.get("total_usage") or md.get("usage")
                    _, _, tt = _usage_tokens(u)
                    if tt is not None:
                        tot_tok = tt
            if cost_usd is None:
                for log_p in (hit_dir / "run" / "agent.log", hit_dir / "agent.log"):
                    if log_p.is_file():
                        cost_usd = SD._cost_usd(log_p)
                        if cost_usd is not None:
                            break
            n_cells += 1
            if cost_usd is not None:
                costs.append(cost_usd)
            if tot_tok is not None:
                toks.append(tot_tok)
            scored_by_set[sid].append({
                "set": sid,
                "rep": rep,
                "correct_prop": (corr / n_cl) if n_cl else 0.0,
                "filled_precision": (corr / filled) if filled else None,
                "cost_usd": cost_usd,
                "tokens_total": tot_tok,
            })

    set_props = [sum(x["correct_prop"] for x in xs) / len(xs) for xs in scored_by_set.values()]
    return {
        "root": str(ref_root.name),
        "scored_cells": n_cells,
        "sets_covered": len(scored_by_set),
        "correct_line_proportion_per_set": round(sum(set_props) / len(set_props), 4) if set_props else None,
        "cost_usd_total": round(sum(costs), 6) if costs else None,
        "cost_usd_mean_per_report": round(sum(costs) / len(costs), 6) if costs else None,
        "tokens_mean_per_report": round(sum(toks) / len(toks), 1) if toks else None,
        "_by_set": {s: sum(x["correct_prop"] for x in xs) / len(xs) for s, xs in scored_by_set.items()},
    }


def analyze_draft_selection(
    drafts_by_set: dict[str, list[dict[str, Any]]],
    *,
    n_boot: int = 2000,
    seed: int = 20261127,
) -> dict[str, Any]:
    """Secondary offline analysis (no new runs): for each set with >=1 available draft, pick one by
    RECORD-ONLY evidence score (`supported - unsupported`, ties broken by fewer blanks) vs random
    pick vs oracle best by answer key.
    """
    per_set: list[dict[str, Any]] = []
    rec_props: list[float] = []
    rnd_props: list[float] = []
    ora_props: list[float] = []
    rec_vs_rnd_diffs: list[float] = []
    rec_vs_ora_diffs: list[float] = []
    ora_hits = 0
    rng = random.Random(seed + 999)

    for sid in sorted(drafts_by_set.keys()):
        ds = drafts_by_set[sid]
        if not ds:
            continue
        # Record-only pick: maximize (evidence_score, -blank_count), deterministic tie-break by order
        best_rec = max(ds, key=lambda d: (int(d["evidence_score"]), -int(d["blank_count"])))
        # Random pick: exact expectation across available drafts + one seeded draw
        rnd_expected = sum(float(d["correct_prop"]) for d in ds) / len(ds)
        rnd_draw = rng.choice(ds)
        # Oracle best by answer key
        best_ora = max(ds, key=lambda d: float(d["correct_prop"]))

        rp = float(best_rec["correct_prop"])
        op = float(best_ora["correct_prop"])
        if abs(rp - op) <= 1e-12:
            ora_hits += 1

        rec_props.append(rp)
        rnd_props.append(rnd_expected)
        ora_props.append(op)
        rec_vs_rnd_diffs.append(rp - rnd_expected)
        rec_vs_ora_diffs.append(rp - op)

        per_set.append({
            "set": sid,
            "n_drafts": len(ds),
            "record_pick_draft": best_rec["draft_id"],
            "record_pick_evidence_score": best_rec["evidence_score"],
            "record_pick_blanks": best_rec["blank_count"],
            "record_pick_correct_prop": round(rp, 4),
            "random_pick_expected_correct_prop": round(rnd_expected, 4),
            "random_pick_draw_draft": rnd_draw["draft_id"],
            "random_pick_draw_correct_prop": round(float(rnd_draw["correct_prop"]), 4),
            "oracle_best_draft": best_ora["draft_id"],
            "oracle_best_correct_prop": round(op, 4),
        })

    n_sets = len(per_set)
    mean_drafts = round(sum(x["n_drafts"] for x in per_set) / n_sets, 2) if n_sets else 0.0
    rec_mean = round(sum(rec_props) / n_sets, 4) if n_sets else None
    rnd_mean = round(sum(rnd_props) / n_sets, 4) if n_sets else None
    ora_mean = round(sum(ora_props) / n_sets, 4) if n_sets else None
    diff_rr = round(sum(rec_vs_rnd_diffs) / n_sets, 4) if n_sets else None
    ci_rr = _cluster_boot_ci(rec_vs_rnd_diffs, n_boot=n_boot, seed=seed + 777)
    diff_ro = round(sum(rec_vs_ora_diffs) / n_sets, 4) if n_sets else None

    return {
        "rule": (
            "Record-only evidence score = supported_lines - unsupported_lines (blank + non-blank flagged); "
            "ties broken by fewer blanks; evaluated offline on available shared drafts per set vs uniform "
            "random pick (expected value) and oracle best by answer key."
        ),
        "sets_evaluated": n_sets,
        "drafts_per_set_mean": mean_drafts,
        "record_pick_correct_prop": rec_mean,
        "random_pick_correct_prop": rnd_mean,
        "oracle_best_correct_prop": ora_mean,
        "record_vs_random_diff": diff_rr,
        "record_vs_random_diff_ci95": ci_rr,
        "record_vs_oracle_gap": diff_ro,
        "oracle_hit_rate": round(ora_hits / n_sets, 4) if n_sets else None,
        "per_set": per_set,
    }


def collect_offline_drafts(
    root: pathlib.Path,
    sets_truth: dict[str, dict[str, Any]],
    sets_order: list[str],
    reps: int,
    flags_name: str = "flags.json",
) -> dict[str, list[dict[str, Any]]]:
    """Collect all non-void shared c0 drafts per set for secondary offline draft-selection analysis."""
    drafts_by_set: dict[str, list[dict[str, Any]]] = {}
    cells_dir = root / "cells"
    if not cells_dir.is_dir():
        return drafts_by_set

    for sid in sets_order:
        st = sets_truth[sid]
        claims = st["claims"]
        truth = st["truth"]
        n_claims = len(claims)
        ds: list[dict[str, Any]] = []
        for rep in range(1, reps + 1):
            c0_dir = cells_dir / sid / f"r{rep}" / "c0"
            done_p = c0_dir / "done.json"
            rep_p = c0_dir / "report.md"
            fl_p = c0_dir / flags_name
            if not (done_p.is_file() and rep_p.is_file() and fl_p.is_file()):
                continue
            done_doc = json.loads(done_p.read_text(encoding="utf-8"))
            if done_doc.get("infra_void"):
                continue
            fl = json.loads(fl_p.read_text(encoding="utf-8"))
            flagged_count = int(fl.get("flagged_count") or len(fl.get("flagged") or []))
            supported_count = int(fl.get("supported_count")) if fl.get("supported_count") is not None else (n_claims - flagged_count)
            if fl.get("blank_count") is not None:
                blank_count = int(fl["blank_count"])
            else:
                vals_fl = fl.get("values") or {}
                blank_count = sum(1 for c in claims if vals_fl.get(c["id"]) is None)
            evidence_score = supported_count - flagged_count

            text = rep_p.read_text(encoding="utf-8", errors="replace")
            vals = SD.parse_report(text, claims)
            corr = sum(1 for c in claims if strict_status(vals.get(c["id"]), c["id"], truth, 0) == "correct")
            ds.append({
                "draft_id": f"r{rep}",
                "rep": rep,
                "supported_count": supported_count,
                "unsupported_count": flagged_count,
                "blank_count": blank_count,
                "evidence_score": evidence_score,
                "correct_count": corr,
                "n_claims": n_claims,
                "correct_prop": (corr / n_claims) if n_claims else 0.0,
            })
        if ds:
            drafts_by_set[sid] = ds
    return drafts_by_set


def evaluate_readout(
    by_arm: dict[str, dict[str, Any]],
    comparisons: dict[str, dict[str, Any]],
    *,
    haiku_full_ref: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply the frozen preregistration readout rules."""
    # 1) Indistinguishable guards
    indist_reasons: list[str] = []
    a_arm = by_arm.get("A") or {}
    t_arm = by_arm.get("T") or {}
    a_prop = a_arm.get("correct_line_proportion_per_set")
    t_sent_rate = t_arm.get("feedback_sent_rate")
    if a_prop is not None and a_prop > 0.85:
        indist_reasons.append(f"A correct-line proportion {a_prop * 100:.2f}% > 85%")
    if a_prop is not None and a_prop < 0.10:
        indist_reasons.append(f"A correct-line proportion {a_prop * 100:.2f}% < 10%")
    if t_sent_rate is not None and t_sent_rate < 0.25:
        indist_reasons.append(f"T sent feedback in {t_sent_rate * 100:.2f}% < 25% (1/4) of cells")
    indistinguishable = len(indist_reasons) > 0

    # 2) Harm warnings ("trading errors for fills") for any arm clearly higher harm than A
    harm_warnings: dict[str, dict[str, Any]] = {}
    for arm in sorted(by_arm.keys()):
        if arm == "A":
            continue
        comp = comparisons.get(f"{arm}_vs_A")
        if not comp:
            continue
        ci_htot = comp.get("per_set_harm_total_rate_diff_ci95")
        htot_diff = comp.get("per_set_harm_total_rate_diff")
        if ci_htot is not None and ci_htot[0] > 0.0:
            harm_warnings[arm] = {
                "label": "trading errors for fills",
                "harm_total_rate_diff": htot_diff,
                "harm_total_rate_diff_ci95": ci_htot,
                "correct_to_wrong_or_deleted": comp.get("treatment_harm_c2w_or_d"),
                "blank_to_wrong": comp.get("treatment_harm_b2w"),
            }

    # 3) T vs G readout
    tg = comparisons.get("T_vs_G") or {}
    tg_diff = tg.get("per_set_correct_prop_diff")
    tg_ci = tg.get("per_set_correct_prop_diff_ci95")
    tg_harm_ok = tg.get("harm_not_more_than_control")
    if tg_diff is None or tg_ci is None:
        tg_verdict = "incomplete"
        tg_reason = "insufficient paired T vs G data"
    elif indistinguishable:
        tg_verdict = "indistinguishable"
        tg_reason = "; ".join(indist_reasons)
    elif tg_diff >= 0.10 and tg_ci[0] > 0.0 and tg_harm_ok is True:
        tg_verdict = "T_beats_G"
        tg_reason = (
            f"T exceeds G by {tg_diff * 100:+.2f}pp (>=10pp), "
            f"95% CI [{tg_ci[0] * 100:+.2f}pp, {tg_ci[1] * 100:+.2f}pp] > 0, harm_T <= harm_G"
        )
    else:
        tg_verdict = "T_does_not_beat_G"
        tg_reason = (
            f"T vs G = {tg_diff * 100:+.2f}pp (95% CI [{tg_ci[0] * 100:+.2f}pp, {tg_ci[1] * 100:+.2f}pp], "
            f"harm_ok={tg_harm_ok}); did not clear >=10pp, CI>0, harm<=G bar"
        )

    # 4) T vs TB readout (record adds value iff >=5pp with CI lower > 0)
    ttb = comparisons.get("T_vs_TB") or {}
    ttb_diff = ttb.get("per_set_correct_prop_diff")
    ttb_ci = ttb.get("per_set_correct_prop_diff_ci95")
    ttb_fprec = ttb.get("per_set_filled_precision_diff")
    ttb_fprec_ci = ttb.get("per_set_filled_precision_diff_ci95")
    ttb_c0fill = ttb.get("per_set_c0_filled_correct_prop_diff")
    ttb_c0fill_ci = ttb.get("per_set_c0_filled_correct_prop_diff_ci95")
    if ttb_diff is None or ttb_ci is None:
        ttb_verdict = "incomplete"
        ttb_reason = "insufficient paired T vs TB data"
    elif indistinguishable:
        ttb_verdict = "indistinguishable"
        ttb_reason = "; ".join(indist_reasons)
    elif ttb_diff >= 0.05 and ttb_ci[0] > 0.0:
        ttb_verdict = "record_adds_value"
        ttb_reason = (
            f"T exceeds TB by {ttb_diff * 100:+.2f}pp (>=5pp), "
            f"95% CI [{ttb_ci[0] * 100:+.2f}pp, {ttb_ci[1] * 100:+.2f}pp] > 0"
        )
    else:
        ttb_verdict = "record_does_not_add_value"
        ttb_reason = (
            f"record does not add value over blank-only control TB "
            f"(T-TB={ttb_diff * 100:+.2f}pp, 95% CI [{ttb_ci[0] * 100:+.2f}pp, {ttb_ci[1] * 100:+.2f}pp]; "
            f"requires >=5pp and CI lower > 0)"
        )

    # 5) T vs TO (oracle ceiling)
    tto = comparisons.get("T_vs_TO") or {}
    toa = comparisons.get("TO_vs_A") or {}
    tto_summary = {
        "T_minus_TO": tto.get("per_set_correct_prop_diff"),
        "T_minus_TO_ci95": tto.get("per_set_correct_prop_diff_ci95"),
        "TO_minus_A_ceiling": toa.get("per_set_correct_prop_diff"),
        "TO_minus_A_ci95": toa.get("per_set_correct_prop_diff_ci95"),
    }

    # 6) TE vs TER readout + whole-report Haiku reference
    teter = comparisons.get("TE_vs_TER") or {}
    te_diff = teter.get("per_set_correct_prop_diff")
    te_ci = teter.get("per_set_correct_prop_diff_ci95")
    if te_diff is None or te_ci is None:
        te_verdict = "incomplete"
        te_reason = "insufficient paired TE vs TER data"
    elif te_diff >= 0.10 and te_ci[0] > 0.0:
        te_verdict = "TE_beats_TER"
        te_reason = (
            f"TE exceeds TER by {te_diff * 100:+.2f}pp (>=10pp), "
            f"95% CI [{te_ci[0] * 100:+.2f}pp, {te_ci[1] * 100:+.2f}pp] > 0"
        )
    else:
        te_verdict = "TE_does_not_beat_TER"
        te_reason = (
            f"record-guided escalation does not beat random escalation "
            f"(TE-TER={te_diff * 100:+.2f}pp, 95% CI [{te_ci[0] * 100:+.2f}pp, {te_ci[1] * 100:+.2f}pp]; "
            f"requires >=10pp and CI lower > 0)"
        )

    te_vs_haiku_full: dict[str, Any] = {"provided": False}
    te_arm = by_arm.get("TE") or {}
    if haiku_full_ref is not None:
        te_cost = (te_arm.get("haiku") or {}).get("cost_usd_mean_per_report")
        hf_cost = haiku_full_ref.get("cost_usd_mean_per_report")
        te_prop = te_arm.get("correct_line_proportion_per_set")
        hf_prop = haiku_full_ref.get("correct_line_proportion_per_set")
        saving_usd = round(hf_cost - te_cost, 6) if (hf_cost is not None and te_cost is not None) else None
        saving_pct = round((hf_cost - te_cost) / hf_cost, 4) if (hf_cost and te_cost is not None) else None
        corr_gap = round(te_prop - hf_prop, 4) if (te_prop is not None and hf_prop is not None) else None
        te_vs_haiku_full = {
            "provided": True,
            "haiku_full_root": haiku_full_ref["root"],
            "haiku_full_sets_covered": haiku_full_ref["sets_covered"],
            "te_cost_usd_mean_per_report": te_cost,
            "haiku_full_cost_usd_mean_per_report": hf_cost,
            "cost_saving_usd_per_report": saving_usd,
            "cost_saving_pct": saving_pct,
            "te_correct_prop_per_set": te_prop,
            "haiku_full_correct_prop_per_set": hf_prop,
            "correctness_gap_te_minus_haiku_full": corr_gap,
        }

    # Overall summary verdict
    if indistinguishable:
        overall = "indistinguishable"
    elif tg_verdict == "T_beats_G" and ttb_verdict == "record_adds_value":
        overall = "T_useful_and_record_adds_value"
    elif tg_verdict == "T_beats_G" and ttb_verdict == "record_does_not_add_value":
        overall = "T_beats_G_but_indistinguishable_from_TB"
    elif tg_verdict == "incomplete":
        overall = "incomplete"
    else:
        overall = "no_record_advantage_shown"

    return {
        "verdict": overall,
        "indistinguishable": indistinguishable,
        "indistinguishable_reasons": indist_reasons,
        "T_vs_G": {"verdict": tg_verdict, "reason": tg_reason},
        "T_vs_TB": {
            "verdict": ttb_verdict,
            "reason": ttb_reason,
            "filled_precision_diff": ttb_fprec,
            "filled_precision_diff_ci95": ttb_fprec_ci,
            "c0_filled_correct_prop_diff": ttb_c0fill,
            "c0_filled_correct_prop_diff_ci95": ttb_c0fill_ci,
        },
        "T_vs_TO": tto_summary,
        "TE_vs_TER": {"verdict": te_verdict, "reason": te_reason},
        "TE_vs_haiku_full": te_vs_haiku_full,
        "harm_warnings": harm_warnings,
        "recorded_prediction": RECORDED_PREDICTION,
        "frozen_rule": (
            "Primary comparisons: T vs G, T vs TB, T vs TO, TE vs TER. "
            "T vs TB: record adds value only if filled-line correct count is >=5 pp higher with paired "
            "(set-cluster bootstrap) CI lower bound >0; otherwise write that it doesn't. "
            "T vs G: >=10 pp on (a) with CI lower bound >0 and harm not more than G's. "
            "TE vs TER: record-guided escalation beats random escalation only if correct-line proportion "
            "difference >=10 pp with paired CI lower bound >0; also report TE's cost saving and correctness "
            "gap vs whole-report Haiku. "
            "Harm: if any arm's harm (c) is clearly higher than A's (CI lower >0), describe it as "
            "'trading errors for fills' even if (a) rises. "
            "Indistinguishable if A's correct-line proportion >85% or <10%, or T sent feedback in <1/4 of cells."
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
    haiku_full_root: pathlib.Path | None = None,
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

    access_rows = _parse_access_log(root)
    access_counts = _access_counts_from_rows(access_rows)
    snapshot_pin = verify_snapshot_pinning(root, sets_order, reps, access_rows)

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

    all_pair_specs = [
        ("T_vs_G", "T", "G"),
        ("T_vs_TB", "T", "TB"),
        ("T_vs_TO", "T", "TO"),
        ("TE_vs_TER", "TE", "TER"),
        ("T_vs_A", "T", "A"),
        ("G_vs_A", "G", "A"),
        ("TB_vs_A", "TB", "A"),
        ("TO_vs_A", "TO", "A"),
        ("TE_vs_A", "TE", "A"),
        ("TER_vs_A", "TER", "A"),
    ]
    arm_set = set(arms)
    comparisons: dict[str, dict[str, Any]] = {}
    for idx, (name, treat, ctrl) in enumerate(all_pair_specs):
        if treat in arm_set and ctrl in arm_set:
            comparisons[name] = paired_comparison(
                by_key, sets_order, reps,
                treatment=treat, control=ctrl,
                n_boot=n_boot, seed=seed + idx * 100,
            )

    ref_root_resolved: pathlib.Path | None = haiku_full_root
    if ref_root_resolved is None and plan.get("haiku_full_root"):
        ref_root_resolved = pathlib.Path(os.path.expandvars(os.path.expanduser(str(plan["haiku_full_root"]))))
    haiku_full_ref = (
        load_haiku_full_reference(ref_root_resolved, sets_truth, sets_order, reps)
        if ref_root_resolved is not None and ref_root_resolved.is_dir()
        else None
    )

    drafts_by_set = collect_offline_drafts(root, sets_truth, sets_order, reps)
    secondary = analyze_draft_selection(drafts_by_set, n_boot=n_boot, seed=seed)

    readout = evaluate_readout(arm_summaries, comparisons, haiku_full_ref=haiku_full_ref)

    return {
        "schema": "vacant.d2.expT.metrics/2",
        "root": str(root.name),
        "plan_id": plan.get("id"),
        "plan_sha256": run_doc.get("plan_sha256"),
        "sets_planned": len(sets_order),
        "reps_planned": reps,
        "arms": arms,
        "boot": n_boot,
        "seed": seed,
        "snapshot_pin": snapshot_pin,
        "by_arm": arm_summaries,
        "comparisons": comparisons,
        "haiku_full_reference": (
            {k: v for k, v in haiku_full_ref.items() if not k.startswith("_")}
            if haiku_full_ref is not None
            else None
        ),
        "readout": readout,
        "secondary_offline_draft_selection": secondary,
    }


def format_report(res: dict[str, Any]) -> str:
    lines = [
        f"Experiment T Metrics — plan={res.get('plan_id')} root={res.get('root')} "
        f"(sets={res['sets_planned']}, reps={res['reps_planned']}, boot={res['boot']})",
        f"Snapshot pin (revision 0): ok={res['snapshot_pin']['ok']} "
        f"(checked={res['snapshot_pin']['requests_checked']}, mismatches={res['snapshot_pin']['mismatch_count']})",
        "",
        "Per-Arm Strict-Scored Summary (Primary Metrics (a), (b), (c) side by side):",
        f"  {'Arm':<4} {'Cells':>5} {'(a)Prop':>8} {'(b)FPrec':>8} {'(c)C->W/D':>9} {'(c)B->W':>7} "
        f"{'SentFix':>8} {'Calls':>6} {'Tokens':>9} {'Wall(s)':>8} {'Haiku$':>8} {'Chains':>7}",
    ]
    for arm in res["arms"]:
        a = res["by_arm"][arm]
        pps = f"{a['correct_line_proportion_per_set'] * 100:.1f}%" if a["correct_line_proportion_per_set"] is not None else "n/a"
        fpr = f"{a['filled_precision_per_set'] * 100:.1f}%" if a["filled_precision_per_set"] is not None else "n/a"
        c2w = str(a["harm"]["correct_to_wrong_or_deleted"])
        b2w = str(a["harm"]["blank_to_wrong"])
        sfix = (
            f"{a['sent_back_fixed']['sent_back_fixed_rate'] * 100:.1f}%"
            if a["sent_back_fixed"]["sent_back_fixed_rate"] is not None
            else "n/a"
        )
        cls = f"{a['calls_mean_per_cell']:.1f}" if a["calls_mean_per_cell"] is not None else "n/a"
        tok = f"{a['tokens_mean_per_cell']:.0f}" if a["tokens_mean_per_cell"] is not None else "n/a"
        wll = f"{a['wall_s_mean_per_cell']:.1f}" if a["wall_s_mean_per_cell"] is not None else "n/a"
        h_usd = (
            f"${a['haiku']['cost_usd_mean_per_report']:.4f}"
            if a.get("haiku") is not None
            else "—"
        )
        chk = f"{a['chains_ok']}/{a['chains_checked']}"
        lines.append(
            f"  {arm:<4} {a['scored_cells']:>5} {pps:>8} {fpr:>8} {c2w:>9} {b2w:>7} "
            f"{sfix:>8} {cls:>6} {tok:>9} {wll:>8} {h_usd:>8} {chk:>7}"
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
    lines.append("Paired Comparisons (set-cluster bootstrap 95% CI):")
    primary_names = {"T_vs_G", "T_vs_TB", "T_vs_TO", "TE_vs_TER"}
    for name, comp in res["comparisons"].items():
        tag = " [PRIMARY]" if name in primary_names else ""
        diff = comp["per_set_correct_prop_diff"]
        ci = comp["per_set_correct_prop_diff_ci95"]
        if diff is None or ci is None:
            lines.append(f"  {name}{tag}: n/a (paired_cells={comp['paired_cells']})")
        else:
            fpd = comp["per_set_filled_precision_diff"]
            fpd_s = f"{fpd * 100:+.2f}pp" if fpd is not None else "n/a"
            htd = comp["per_set_harm_total_rate_diff"]
            htd_s = f"{htd * 100:+.2f}pp" if htd is not None else "n/a"
            lines.append(
                f"  {name}{tag}: (a)={diff * 100:+.2f}pp 95%CI=[{ci[0] * 100:+.2f}pp, {ci[1] * 100:+.2f}pp] "
                f"(b)fprec={fpd_s} harm_diff={htd_s} (sets={comp['paired_sets']}, pairs={comp['paired_cells']})"
            )

    ro = res["readout"]
    lines.append("")
    lines.append(f"Readout: {ro['verdict']}")
    if ro["indistinguishable"]:
        lines.append(f"  INDISTINGUISHABLE: {'; '.join(ro['indistinguishable_reasons'])}")
    lines.append(f"  T vs G   : {ro['T_vs_G']['verdict']} — {ro['T_vs_G']['reason']}")
    lines.append(f"  T vs TB  : {ro['T_vs_TB']['verdict']} — {ro['T_vs_TB']['reason']}")
    lines.append(f"  TE vs TER: {ro['TE_vs_TER']['verdict']} — {ro['TE_vs_TER']['reason']}")
    if ro["TE_vs_haiku_full"].get("provided"):
        hf = ro["TE_vs_haiku_full"]
        lines.append(
            f"  TE vs Haiku-full: saving={hf['cost_saving_pct'] * 100:.1f}% "
            f"(${hf['cost_saving_usd_per_report']:.4f}/report), "
            f"correctness_gap={hf['correctness_gap_te_minus_haiku_full'] * 100:+.2f}pp"
        )
    if ro["harm_warnings"]:
        for arm, hw in ro["harm_warnings"].items():
            lines.append(
                f"  HARM WARNING ({arm}): {hw['label']} "
                f"(C->W/D={hw['correct_to_wrong_or_deleted']}, B->W={hw['blank_to_wrong']})"
            )
    lines.append(f"  Prediction: {ro['recorded_prediction']}")

    sec = res["secondary_offline_draft_selection"]
    lines.append("")
    lines.append(
        f"Secondary Offline Draft Selection (sets={sec['sets_evaluated']}, "
        f"drafts/set={sec['drafts_per_set_mean']}): "
        f"record_pick={sec['record_pick_correct_prop']} vs "
        f"random_pick={sec['random_pick_correct_prop']} vs "
        f"oracle_best={sec['oracle_best_correct_prop']} "
        f"(rec-rnd={sec['record_vs_random_diff']}, CI95={sec['record_vs_random_diff_ci95']})"
    )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Compute Experiment T strict-scored metrics & paired bootstrap CIs.")
    ap.add_argument("root", help="Experiment T run root directory (containing RUN.json and cells/)")
    ap.add_argument("--materials", nargs="+", help="Optional override material dirs matching plan order")
    ap.add_argument("--haiku-full-root", help="Optional whole-report Haiku A-arm run root for TE reference")
    ap.add_argument("--boot", type=int, default=2000, help="Set-cluster bootstrap resamples (default: 2000)")
    ap.add_argument("--seed", type=int, default=20261127, help="Bootstrap RNG seed (default: 20261127)")
    ap.add_argument("--no-verify-chains", action="store_true", help="Skip Ed25519 feedback chain verification")
    ap.add_argument("--json", action="store_true", help="Print JSON instead of human-readable summary")
    ap.add_argument("--json-out", help="Optional path to write full JSON output")
    a = ap.parse_args()

    res = analyze_root(
        pathlib.Path(a.root).expanduser().resolve(),
        override_materials=a.materials,
        haiku_full_root=pathlib.Path(a.haiku_full_root).expanduser().resolve() if a.haiku_full_root else None,
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
