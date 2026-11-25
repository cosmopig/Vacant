#!/usr/bin/env python3
"""D2′ 單一報告產生器：以函式庫方式呼叫 score_d2／audit_d2／analyze_d2，產出繁體中文 Markdown 報告與 JSON sidecar。

只用標準函式庫，不呼叫外部子行程，不呼叫任何模型 API。
所有表格組裝與文字渲染函式皆為純函式（pure functions），便於單元測試與離線重現。

用法：
  python3 ops/d2/report_d2.py --root <執行目錄> --manifest <manifest.json> [--plan <plan.json>] [--out <report.md>] [--json-out <report.json>]
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys
from collections.abc import Mapping, Sequence
from typing import Any

try:
    from . import analyze_d2, audit_d2, score_d2
except ImportError:
    _HERE = pathlib.Path(__file__).resolve().parent
    if str(_HERE) not in sys.path:
        sys.path.insert(0, str(_HERE))
    import analyze_d2  # type: ignore[no-redef]
    import audit_d2  # type: ignore[no-redef]
    import score_d2  # type: ignore[no-redef]

DEFAULT_ARMS = ("a", "b", "c", "d")
DEFAULT_CYCLES = (1, 2, 3)


# ---------------------------------------------------------------------------
# Pure formatting helpers
# ---------------------------------------------------------------------------

def _fmt_float(x: float | None, digits: int = 4, *, signed: bool = False) -> str:
    if x is None:
        return "n/a"
    if math.isinf(x):
        return "+inf" if (signed and x > 0) else ("-inf" if x < 0 else "inf")
    spec = f"+.{digits}f" if signed else f".{digits}f"
    return format(x, spec)


def _fmt_pct(x: float | None, digits: int = 2) -> str:
    if x is None:
        return "n/a"
    if math.isinf(x):
        return "inf"
    return f"{x * 100:.{digits}f}%"


def _fmt_ratio(x: float | None, digits: int = 2) -> str:
    if x is None:
        return "n/a"
    if math.isinf(x):
        return "inf"
    return f"{x:.{digits}f}x"


def _fmt_ci(ci: Sequence[float | None] | None, digits: int = 2, *, signed: bool = False) -> str:
    if not ci or len(ci) < 2:
        return "[n/a, n/a]"
    return f"[{_fmt_float(ci[0], digits, signed=signed)}, {_fmt_float(ci[1], digits, signed=signed)}]"


def _fmt_frac(num: int | None, den: int | None) -> str:
    if num is None or den is None:
        return "n/a"
    if den == 0:
        return f"{num}/0 (n/a)"
    return f"{num}/{den} ({num / den * 100:.2f}%)"


def _ordered_arms(present: Sequence[str], preferred: Sequence[str] = DEFAULT_ARMS) -> list[str]:
    seen: list[str] = []
    for a in preferred:
        if a not in seen:
            seen.append(a)
    for a in sorted(present):
        if a not in seen:
            seen.append(a)
    return seen


def _md_escape(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


PROV_FIELDS = ("claims", "write_step", "product_provenance", "product_provenance_correct_page", "candidates_only",
               "server_saw_fetch")


def _md_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    lines = [
        "| " + " | ".join(_md_escape(h) for h in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_md_escape(cell) for cell in row) + " |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Pure computation & table-building functions
# ---------------------------------------------------------------------------

def compare_audit_harness(
    audit_rows: Sequence[Mapping[str, Any]],
    harness_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """逐列比對稽核重建分數與執行器分數（與 audit_d2.main 相同口徑）。"""
    def _key(r: Mapping[str, Any]) -> tuple[str, str, int, str]:
        return (str(r["set"]), str(r["arm"]), int(r["cycle"]), str(r["claim"]))

    a_map = {_key(r): r.get("status") for r in audit_rows}
    h_map = {_key(r): r.get("status") for r in harness_rows}
    mismatches = [
        {"row": list(k), "audit": a_map.get(k), "harness": h_map.get(k)}
        for k in sorted(set(a_map) | set(h_map))
        if a_map.get(k) != h_map.get(k)
    ]
    return {
        "rows": len(h_map),
        "audit_rows": len(a_map),
        "mismatches": len(mismatches),
        "examples": mismatches[:20],
    }


def summarize_sources_check(
    checks_by_set: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """彙整 c 臂第 1 週期 `sources_check.json` 的 picked_by（context vs blame）與 ambiguous 計數。"""
    total_claims = 0
    with_source = 0
    no_source = 0
    picked_context = 0
    picked_blame = 0
    picked_unset = 0
    picked_other: dict[str, int] = {}
    ambiguous_count = 0
    per_set: dict[str, dict[str, int]] = {}

    for sid in sorted(checks_by_set):
        doc = checks_by_set[sid]
        claims = doc.get("claims") if isinstance(doc, Mapping) else None
        if not isinstance(claims, Sequence) or isinstance(claims, (str, bytes)):
            claims = []
        s_stat = {
            "claims": 0,
            "with_source": 0,
            "no_source": 0,
            "picked_by_context": 0,
            "picked_by_blame": 0,
            "picked_by_unset": 0,
            "ambiguous": 0,
        }
        for entry in claims:
            if not isinstance(entry, Mapping):
                continue
            total_claims += 1
            s_stat["claims"] += 1
            src = entry.get("source")
            if isinstance(src, Mapping):
                with_source += 1
                s_stat["with_source"] += 1
                pb = src.get("picked_by")
                if pb == "context":
                    picked_context += 1
                    s_stat["picked_by_context"] += 1
                elif pb == "blame":
                    picked_blame += 1
                    s_stat["picked_by_blame"] += 1
                elif pb is None:
                    picked_unset += 1
                    s_stat["picked_by_unset"] += 1
                else:
                    key = str(pb)
                    picked_other[key] = picked_other.get(key, 0) + 1
                if src.get("ambiguous"):
                    ambiguous_count += 1
                    s_stat["ambiguous"] += 1
            else:
                no_source += 1
                s_stat["no_source"] += 1
        per_set[sid] = s_stat

    return {
        "sets": len(per_set),
        "claims": total_claims,
        "with_source": with_source,
        "no_source": no_source,
        "picked_by_context": picked_context,
        "picked_by_blame": picked_blame,
        "picked_by_unset": picked_unset,
        "picked_by_other": picked_other,
        "ambiguous": ambiguous_count,
        "per_set": per_set,
    }


def build_conclusion(analysis: Mapping[str, Any]) -> dict[str, Any]:
    """依 analyze_d2 結果建立事實性的一句話結論結構（無形容詞）。"""
    verdict = str(analysis.get("verdict") or "UNRESOLVED")
    boot = analysis.get("bootstrap") or {}
    comp = analysis.get("completeness") or {}
    cov = analysis.get("coverage") or {}
    prim = analysis.get("primary") or {}
    miss = prim.get("miss_diff_c_b") or {}
    tok = prim.get("token_ratio_b_c") or {}

    if cov.get("available") and cov.get("claims"):
        cov_text = (
            f"{cov['correct_page']}/{cov['claims']} = {_fmt_pct(cov.get('rate'))}"
            f"（門檻 ≥ {_fmt_pct(cov.get('threshold'), 0)}，{cov.get('verdict')}）"
        )
    else:
        cov_text = f"無資料（門檻 ≥ {_fmt_pct(cov.get('threshold'), 0)}，{cov.get('verdict')}）"

    miss_text = (
        f"點估計 {_fmt_float(miss.get('point'), 4, signed=True)}、"
        f"單尾 95% 上界 {_fmt_float(miss.get('upper_95'), 4)}"
        f"（門檻 < {_fmt_float(miss.get('margin'), 2)}，{miss.get('verdict')}）"
    )

    tok_text = (
        f"點估計 {_fmt_ratio(tok.get('point'), 2)}、"
        f"95% CI {_fmt_ci(tok.get('ci_95'), 2)}"
        f"（門檻下界 ≥ {_fmt_float(tok.get('threshold'), 2)}，{tok.get('verdict')}）"
    )

    n_sets = boot.get("n_sets", comp.get("n_sets", 0))
    n_boot = boot.get("n_boot")
    seed = boot.get("seed")
    missing_n = len(comp.get("missing") or [])

    if verdict == "INCOMPLETE":
        scope = f"缺少 {missing_n} 個 set×arm×cycle；n={n_sets} 組，bootstrap B={n_boot}，seed={seed}"
    else:
        scope = f"n={n_sets} 組，bootstrap B={n_boot}，seed={seed}"

    sentence = (
        f"裁決：`{verdict}`（{scope}）；"
        f"三項門檻：出處正確頁率 {cov_text}；"
        f"漏抓率差 c−b {miss_text}；"
        f"token 比值 b/c {tok_text}。"
    )

    return {
        "verdict": verdict,
        "complete": bool(comp.get("complete")),
        "missing_count": missing_n,
        "n_sets": n_sets,
        "n_boot": n_boot,
        "seed": seed,
        "gates": {
            "coverage": {
                "verdict": cov.get("verdict"),
                "correct_page": cov.get("correct_page"),
                "claims": cov.get("claims"),
                "rate": cov.get("rate"),
                "threshold": cov.get("threshold"),
            },
            "miss_diff_c_b": {
                "verdict": miss.get("verdict"),
                "point": miss.get("point"),
                "upper_95": miss.get("upper_95"),
                "margin": miss.get("margin"),
            },
            "token_ratio_b_c": {
                "verdict": tok.get("verdict"),
                "point": tok.get("point"),
                "ci_95": list(tok.get("ci_95") or [None, None]),
                "threshold": tok.get("threshold"),
            },
        },
        "sentence": sentence,
    }


def _stale_by_cycle(raw: Mapping[Any, Any] | None, cycles: Sequence[int] = DEFAULT_CYCLES) -> dict[str, int]:
    out: dict[str, int] = {}
    src = raw or {}
    for k in cycles:
        val = src.get(k, src.get(str(k), 0))
        out[str(k)] = int(val)
    return out


def build_arm_rows(
    score_summary: Mapping[str, Any],
    arms: Sequence[str] = DEFAULT_ARMS,
    cycles: Sequence[int] = DEFAULT_CYCLES,
) -> list[dict[str, Any]]:
    """建立第 2 節每臂表資料列（a, b, c, d）。"""
    arms_map = score_summary.get("arms") or {}
    ordered = _ordered_arms(list(arms_map.keys()), preferred=arms)
    rows: list[dict[str, Any]] = []
    for arm in ordered:
        info = arms_map.get(arm)
        if not isinstance(info, Mapping):
            rows.append({
                "arm": arm,
                "present": False,
                "changed_claims": None,
                "missed": None,
                "miss_rate": None,
                "false_mod": None,
                "unchanged_correct_claims": None,
                "stale_residual_by_cycle": {str(k): None for k in cycles},
                "agent_runs": None,
                "calls": None,
                "tokens_in": None,
                "tokens_out": None,
                "wall_s": None,
                "tool_wall_s": None,
                "usage_unknown": None,
                "source_requests_agent": None,
                "source_requests_vacant": None,
            })
            continue
        changed = int(info.get("changed_claims", 0))
        missed = int(info.get("missed", 0))
        miss_rate = (missed / changed) if changed > 0 else None
        cost = info.get("cost") if isinstance(info.get("cost"), Mapping) else {}
        rows.append({
            "arm": arm,
            "present": True,
            "changed_claims": changed,
            "missed": missed,
            "miss_rate": miss_rate,
            "false_mod": int(info.get("false_mod", 0)),
            "unchanged_correct_claims": int(info.get("unchanged_correct_claims", 0)),
            "stale_residual_by_cycle": _stale_by_cycle(info.get("stale_residual_by_cycle"), cycles),
            "agent_runs": cost.get("agent_runs"),
            "calls": cost.get("calls"),
            "tokens_in": cost.get("tokens_in"),
            "tokens_out": cost.get("tokens_out"),
            "wall_s": cost.get("wall_s"),
            "tool_wall_s": cost.get("tool_wall_s"),
            "usage_unknown": cost.get("usage_unknown", 0),
            "source_requests_agent": cost.get("source_requests_agent"),
            "source_requests_vacant": cost.get("source_requests_vacant"),
        })
    return rows


def build_pairwise_rows(analysis: Mapping[str, Any]) -> list[dict[str, Any]]:
    """建立第 3 節配對比較資料列：c vs b、c vs d、d vs b。"""
    prim = analysis.get("primary") or {}
    sec = analysis.get("secondary") or {}
    c_vs_d = sec.get("c_vs_d") or {}
    d_vs_b = sec.get("d_vs_b") or {}

    specs = [
        (
            "c vs b",
            "primary",
            prim.get("miss_diff_c_b") or {},
            prim.get("token_ratio_b_c") or {},
            prim.get("calls_ratio_b_c") or {},
            prim.get("wall_ratio_b_c") or {},
        ),
        (
            "c vs d",
            "secondary",
            c_vs_d.get("miss_diff") or {},
            c_vs_d.get("token_ratio") or {},
            c_vs_d.get("calls_ratio") or {},
            c_vs_d.get("wall_ratio") or {},
        ),
        (
            "d vs b",
            "secondary",
            d_vs_b.get("miss_diff") or {},
            d_vs_b.get("token_ratio") or {},
            d_vs_b.get("calls_ratio") or {},
            d_vs_b.get("wall_ratio") or {},
        ),
    ]

    out: list[dict[str, Any]] = []
    for pair_label, tier, md, tr, cr, wr in specs:
        out.append({
            "pair": pair_label,
            "tier": tier,
            "miss_diff": {
                "label": md.get("label"),
                "n_pairs": md.get("n_pairs"),
                "point": md.get("point"),
                "ci_95": list(md.get("ci_95") or [None, None]),
                "upper_95": md.get("upper_95"),
                "verdict": md.get("verdict"),
            },
            "token_ratio": {
                "label": tr.get("label"),
                "point": tr.get("point"),
                "ci_95": list(tr.get("ci_95") or [None, None]),
                "n_paired_used": tr.get("n_paired_used"),
                "n_paired_total": tr.get("n_paired_total"),
                "excluded_unknown_count": tr.get("excluded_unknown_count", 0),
                "verdict": tr.get("verdict"),
            },
            "calls_ratio": {
                "label": cr.get("label"),
                "point": cr.get("point"),
                "ci_95": list(cr.get("ci_95") or [None, None]),
                "n_paired_used": cr.get("n_paired_used"),
                "n_paired_total": cr.get("n_paired_total"),
                "excluded_unknown_count": cr.get("excluded_unknown_count", 0),
            },
            "wall_ratio": {
                "label": wr.get("label"),
                "point": wr.get("point"),
                "ci_95": list(wr.get("ci_95") or [None, None]),
                "n_paired_used": wr.get("n_paired_used"),
                "n_paired_total": wr.get("n_paired_total"),
                "excluded_unknown_count": wr.get("excluded_unknown_count", 0),
            },
        })
    return out


def build_provenance_quality(
    analysis: Mapping[str, Any],
    sources_check_summary: Mapping[str, Any],
    materials: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """建立第 4 節出處品質資料。"""
    cov = analysis.get("coverage") or {}
    mat = materials or {}
    return {
        "coverage": {
            "available": bool(cov.get("available")),
            "claims": cov.get("claims"),
            "with_source": cov.get("with_source"),
            "with_source_rate": cov.get("with_source_rate"),
            "correct_page": cov.get("correct_page"),
            "correct_page_rate": cov.get("rate"),
            "threshold": cov.get("threshold"),
            "verdict": cov.get("verdict"),
        },
        "sources_check_c1": dict(sources_check_summary),
        "materials": {
            "claims": mat.get("claims"),
            "value_with_unit_on_another_page": mat.get("value_with_unit_on_another_page"),
            "rate_with_unit": mat.get("rate_with_unit"),
            "bare_number_on_another_page": mat.get("bare_number_on_another_page"),
            "rate_bare_number": mat.get("rate_bare_number"),
        },
    }


def build_audit_section_data(
    audit_data: Mapping[str, Any],
    harness_match: Mapping[str, Any],
    arms: Sequence[str] = DEFAULT_ARMS,
) -> dict[str, Any]:
    """建立第 5 節稽核資料：逐列比對、病歷問題、各臂來歷摘要、錯誤歸因表。"""
    prov_sum = audit_data.get("provenance_summary") or {}
    ordered_prov_arms = _ordered_arms(list(prov_sum.keys()), preferred=arms)
    provenance_rows: list[dict[str, Any]] = []
    for arm in ordered_prov_arms:
        d = prov_sum.get(arm)
        if isinstance(d, Mapping):
            provenance_rows.append({"arm": arm, **{k: int(d.get(k, 0)) for k in PROV_FIELDS}})
        else:
            provenance_rows.append({"arm": arm, **{k: None for k in PROV_FIELDS}})

    attr_tbl = audit_data.get("attribution_table") or {}
    attr_order = _ordered_arms(list(attr_tbl.keys()), preferred=("c0", *arms))
    attribution_rows: list[dict[str, Any]] = []
    for arm in attr_order:
        kinds = attr_tbl.get(arm)
        if not isinstance(kinds, Mapping):
            continue
        for kind in sorted(kinds):
            segs = kinds[kind]
            if not isinstance(segs, Mapping):
                continue
            for seg in sorted(segs):
                attribution_rows.append({
                    "arm": arm,
                    "kind": str(kind),
                    "segment": str(seg),
                    "count": int(segs[seg]),
                })

    problems = list(audit_data.get("record_problems") or [])
    return {
        "harness_match": {
            "rows": int(harness_match.get("rows", 0)),
            "audit_rows": int(harness_match.get("audit_rows", harness_match.get("rows", 0))),
            "mismatches": int(harness_match.get("mismatches", 0)),
            "examples": list(harness_match.get("examples") or []),
        },
        "record_problems": problems,
        "provenance_rows": provenance_rows,
        "attribution_rows": attribution_rows,
    }


def build_latency_table_data(
    score_summary: Mapping[str, Any],
    arms: Sequence[str] = DEFAULT_ARMS,
) -> dict[str, Any]:
    """建立第 6 節偵測延遲直方圖表（各臂）。"""
    arms_map = score_summary.get("arms") or {}
    ordered = _ordered_arms(list(arms_map.keys()), preferred=arms)
    numeric_buckets: set[int] = {0, 1, 2}
    for arm in ordered:
        info = arms_map.get(arm)
        if not isinstance(info, Mapping):
            continue
        hist = info.get("latency_hist") or {}
        for k in hist:
            if k != "None":
                try:
                    numeric_buckets.add(int(k))
                except (TypeError, ValueError):
                    pass
    buckets = [str(b) for b in sorted(numeric_buckets)] + ["None"]

    rows: list[dict[str, Any]] = []
    for arm in ordered:
        info = arms_map.get(arm)
        if not isinstance(info, Mapping):
            rows.append({"arm": arm, "present": False, "counts": {b: None for b in buckets}, "total": None})
            continue
        hist = info.get("latency_hist") or {}
        counts = {b: int(hist.get(b, 0)) for b in buckets}
        rows.append({
            "arm": arm,
            "present": True,
            "counts": counts,
            "total": sum(counts.values()),
        })
    return {"buckets": buckets, "rows": rows}


def build_report_data(
    *,
    score_res: Mapping[str, Any],
    audit_res: Mapping[str, Any],
    harness_match: Mapping[str, Any],
    analysis: Mapping[str, Any],
    sources_check_summary: Mapping[str, Any],
    materials: Mapping[str, Any] | None,
    data_sources: Mapping[str, Sequence[str]],
    meta: Mapping[str, Any] | None = None,
    arms: Sequence[str] = DEFAULT_ARMS,
) -> dict[str, Any]:
    """將各模組輸出組裝為完整結構化報告資料（供 Markdown 渲染與 JSON sidecar 輸出）。"""
    summary = score_res.get("summary") or {}
    return {
        "schema": "vacant.d2.report/1",
        "meta": dict(meta or {}),
        "conclusion": build_conclusion(analysis),
        "c0": dict(summary.get("c0") or {}),
        "arms_table": build_arm_rows(summary, arms=arms),
        "pairwise_table": build_pairwise_rows(analysis),
        "provenance_quality": build_provenance_quality(analysis, sources_check_summary, materials),
        "audit": build_audit_section_data(audit_res, harness_match, arms=arms),
        "latency": build_latency_table_data(summary, arms=arms),
        "data_sources": {k: list(v) for k, v in data_sources.items()},
        "analysis": dict(analysis),
    }


# ---------------------------------------------------------------------------
# Pure Markdown renderers (Traditional Chinese headings & factual prose)
# ---------------------------------------------------------------------------

def render_conclusion(conclusion: Mapping[str, Any]) -> str:
    return "\n".join([
        "## 1. 一句話結論",
        "",
        str(conclusion["sentence"]),
    ])


def render_arm_table(
    arm_rows: Sequence[Mapping[str, Any]],
    c0_summary: Mapping[str, Any] | None = None,
) -> str:
    headers = [
        "臂",
        "異動宣稱數",
        "漏抓數",
        "漏抓率",
        "誤改／可誤改",
        "各週期殘留過時",
        "agent 次數",
        "模型呼叫",
        "輸入 tokens",
        "輸出 tokens",
        "牆鐘 (s)",
        "來源請求（agent）",
        "來源請求（Vacant）",
    ]
    tbl_rows: list[list[str]] = []
    tool_notes: list[str] = []
    unk_notes: list[str] = []

    for r in arm_rows:
        if not r.get("present"):
            tbl_rows.append([str(r["arm"])] + ["n/a"] * (len(headers) - 1))
            continue
        mr = r["miss_rate"]
        mr_s = "n/a" if mr is None else f"{mr:.4f} ({mr * 100:.2f}%)"
        fm_s = f"{r['false_mod']} / {r['unchanged_correct_claims']}"
        st = r["stale_residual_by_cycle"]
        st_s = ", ".join(f"c{k}: {st[k]}" for k in sorted(st, key=int))
        calls = r["calls"]
        unk = r.get("usage_unknown") or 0
        calls_s = "n/a" if calls is None else (f"{calls}（未知 {unk}）" if unk else str(calls))
        tin_s = "n/a" if r["tokens_in"] is None else f"{int(r['tokens_in']):,}"
        tout_s = "n/a" if r["tokens_out"] is None else f"{int(r['tokens_out']):,}"
        wall_s = "n/a" if r["wall_s"] is None else f"{float(r['wall_s']):.1f}"
        req_a = "n/a" if r["source_requests_agent"] is None else str(r["source_requests_agent"])
        req_v = "n/a" if r["source_requests_vacant"] is None else str(r["source_requests_vacant"])
        aruns = "n/a" if r["agent_runs"] is None else str(r["agent_runs"])
        tbl_rows.append([
            str(r["arm"]),
            str(r["changed_claims"]),
            str(r["missed"]),
            mr_s,
            fm_s,
            st_s,
            aruns,
            calls_s,
            tin_s,
            tout_s,
            wall_s,
            req_a,
            req_v,
        ])
        if r.get("tool_wall_s"):
            tool_notes.append(f"{r['arm']} 臂 {float(r['tool_wall_s']):.1f} s")
        if unk:
            unk_notes.append(f"{r['arm']} 臂 {unk} 個 set×cycle")

    parts = ["## 2. 每臂彙總", ""]
    if c0_summary and c0_summary.get("claims") is not None:
        parts.append(
            f"初稿（c0）正確數：{_fmt_frac(c0_summary.get('correct'), c0_summary.get('claims'))}。"
        )
        parts.append("")
    parts.append(_md_table(headers, tbl_rows))
    if tool_notes:
        parts.append("")
        parts.append(f"註：Vacant 工具牆鐘（未計入上表 agent 牆鐘）：{'、'.join(tool_notes)}。")
    if unk_notes:
        parts.append("")
        parts.append(f"註：用量未知之執行：{'、'.join(unk_notes)}。")
    return "\n".join(parts)


def render_pairwise_table(pairwise_rows: Sequence[Mapping[str, Any]]) -> str:
    headers = [
        "比較",
        "配對宣稱數",
        "漏抓率差（95% CI；單尾 95% 上界）",
        "token 比值（95% CI）",
        "呼叫比值（95% CI）",
        "牆鐘比值（95% CI）",
    ]
    tbl_rows: list[list[str]] = []
    notes: list[str] = []

    for r in pairwise_rows:
        tier_zh = "主要" if r["tier"] == "primary" else "次要"
        md = r["miss_diff"]
        tr = r["token_ratio"]
        cr = r["calls_ratio"]
        wr = r["wall_ratio"]

        md_lbl = md.get("label") or ""
        md_cell = (
            f"{md_lbl}: {_fmt_float(md.get('point'), 4, signed=True)}"
            f"（{_fmt_ci(md.get('ci_95'), 4, signed=True)}；"
            f"上界 {_fmt_float(md.get('upper_95'), 4)}）"
        )
        if md.get("verdict"):
            md_cell += f" [{md['verdict']}]"

        def _ratio_cell(blk: Mapping[str, Any], *, show_verdict: bool = False) -> str:
            lbl = blk.get("label") or ""
            txt = f"{lbl}: {_fmt_ratio(blk.get('point'), 2)} {_fmt_ci(blk.get('ci_95'), 2)}"
            if show_verdict and blk.get("verdict"):
                txt += f" [{blk['verdict']}]"
            excl = blk.get("excluded_unknown_count") or 0
            if excl:
                txt += f"（排除未知 {excl}）"
            return txt

        tbl_rows.append([
            f"{r['pair']}（{tier_zh}）",
            str(md.get("n_pairs", "n/a")),
            md_cell,
            _ratio_cell(tr, show_verdict=True),
            _ratio_cell(cr),
            _ratio_cell(wr),
        ])
        if tr.get("n_paired_total") is not None:
            notes.append(
                f"{r['pair']} 成本配對 {tr.get('n_paired_used')}/{tr.get('n_paired_total')} 個 set×cycle"
                + (f"（token 排除未知 {tr['excluded_unknown_count']}）" if tr.get("excluded_unknown_count") else "")
            )

    parts = ["## 3. 配對比較", "", _md_table(headers, tbl_rows)]
    if notes:
        parts.append("")
        parts.append("註：" + "；".join(notes) + "。")
    return "\n".join(parts)


def render_provenance_quality(pq: Mapping[str, Any]) -> str:
    cov = pq.get("coverage") or {}
    sc = pq.get("sources_check_c1") or {}
    mat = pq.get("materials") or {}

    parts = ["## 4. 出處品質", ""]

    # 4.1 覆蓋率
    parts.append("### 4.1 出處覆蓋率（c 臂第 1 週期稽核）")
    parts.append("")
    if cov.get("available") and cov.get("claims"):
        cov_rows = [
            ["有出處（with_source / claims）", _fmt_frac(cov.get("with_source"), cov.get("claims"))],
            ["正確頁面（correct_page / claims）", _fmt_frac(cov.get("correct_page"), cov.get("claims"))],
            ["門檻與判定", f"≥ {_fmt_pct(cov.get('threshold'), 0)} → `{cov.get('verdict')}`"],
        ]
    else:
        cov_rows = [["出處覆蓋率", f"無稽核資料 → `{cov.get('verdict')}`"]]
    parts.append(_md_table(["指標", "數值"], cov_rows))
    parts.append("")

    # 4.2 sources_check.json picked_by / ambiguous
    parts.append("### 4.2 出處挑選方式（`cells/<set>/c/cycle_1/sources_check.json`）")
    parts.append("")
    sc_claims = sc.get("claims", 0)
    sc_ws = sc.get("with_source", 0)
    sc_rows = [
        ["掃描組數", str(sc.get("sets", 0))],
        ["宣稱總筆數", str(sc_claims)],
        ["有出處（source 非空）", _fmt_frac(sc_ws, sc_claims) if sc_claims else "0"],
        ["由 context 挑選（picked_by = context）", _fmt_frac(sc.get("picked_by_context", 0), sc_ws) if sc_ws else "0"],
        ["由 blame 挑選（picked_by = blame）", _fmt_frac(sc.get("picked_by_blame", 0), sc_ws) if sc_ws else "0"],
        ["picked_by 未標記", _fmt_frac(sc.get("picked_by_unset", 0), sc_ws) if sc_ws else "0"],
        ["多候選（ambiguous 非空）", _fmt_frac(sc.get("ambiguous", 0), sc_ws) if sc_ws else "0"],
        ["無出處（source 為空）", _fmt_frac(sc.get("no_source", 0), sc_claims) if sc_claims else "0"],
    ]
    for k, v in sorted((sc.get("picked_by_other") or {}).items()):
        sc_rows.append([f"picked_by = {k}", _fmt_frac(v, sc_ws) if sc_ws else str(v)])
    parts.append(_md_table(["項目", "數值"], sc_rows))
    if sc.get("picked_by_unset", 0) > 0:
        parts.append("")
        parts.append(
            f"註：有 {sc['picked_by_unset']} 筆出處紀錄不含 `picked_by` 欄位"
            "（於 `sources.py` 加入 `picked_by`／`ambiguous` 欄位前產生）。"
        )
    parts.append("")

    # 4.3 教材碰撞率
    parts.append("### 4.3 教材數值碰撞率（第 0 週期，`score_d2.materials_stats`）")
    parts.append("")
    m_claims = mat.get("claims")
    if m_claims:
        mat_rows = [
            ["評估宣稱數", str(m_claims)],
            [
                "帶單位值出現於同組他頁",
                f"{mat.get('value_with_unit_on_another_page')}/{m_claims} "
                f"（{_fmt_float(mat.get('rate_with_unit'), 4)} / {_fmt_pct(mat.get('rate_with_unit'))}）",
            ],
            [
                "僅數字出現於同組他頁",
                f"{mat.get('bare_number_on_another_page')}/{m_claims} "
                f"（{_fmt_float(mat.get('rate_bare_number'), 4)} / {_fmt_pct(mat.get('rate_bare_number'))}）",
            ],
        ]
    else:
        mat_rows = [["教材數值碰撞率", "n/a"]]
    parts.append(_md_table(["項目", "數值"], mat_rows))
    return "\n".join(parts)


def render_audit_section(audit_sec: Mapping[str, Any]) -> str:
    hm = audit_sec.get("harness_match") or {}
    probs = audit_sec.get("record_problems") or []
    prov_rows = audit_sec.get("provenance_rows") or []
    attr_rows = audit_sec.get("attribution_rows") or []

    parts = ["## 5. 稽核", ""]

    # 5.1 一致性與病歷問題
    parts.append("### 5.1 稽核重算與執行器比對、病歷鏈檢查")
    parts.append("")
    chk_rows = [
        ["執行器評分列數", str(hm.get("rows", 0))],
        ["稽核重建列數", str(hm.get("audit_rows", 0))],
        ["不一致列數（audit vs harness）", str(hm.get("mismatches", 0))],
        ["病歷鏈問題數（record_problems）", str(len(probs))],
    ]
    parts.append(_md_table(["項目", "數值"], chk_rows))

    examples = hm.get("examples") or []
    if examples:
        parts.append("")
        parts.append("不一致列範例（最多 20 筆）：")
        parts.append("")
        ex_rows = [
            [
                "/".join(str(x) for x in ex.get("row", [])),
                str(ex.get("audit")),
                str(ex.get("harness")),
            ]
            for ex in examples
        ]
        parts.append(_md_table(["列（set/arm/cycle/claim）", "audit", "harness"], ex_rows))

    if probs:
        parts.append("")
        parts.append("病歷鏈問題清單：")
        parts.append("")
        for p in probs:
            parts.append(f"- `{p}`")
    parts.append("")

    # 5.2 各臂來歷摘要
    parts.append("### 5.2 各臂最終宣稱來歷摘要")
    parts.append("")
    p_tbl = [[str(r["arm"])] + ["n/a" if r[k] is None else str(r[k]) for k in PROV_FIELDS] for r in prov_rows]
    parts.append(_md_table(
        ["臂", "宣稱數", "找到寫入步", "有產品出處（source_check）", "產品出處指到正確頁", "只有候選網址（產品沒有出處）", "伺服器紀錄有那次抓取"],
        p_tbl,
    ))
    parts.append("")

    # 5.3 錯誤歸因表
    parts.append("### 5.3 錯誤歸因表（arm × kind × segment）")
    parts.append("")
    if attr_rows:
        a_tbl = [[r["arm"], r["kind"], r["segment"], str(r["count"])] for r in attr_rows]
        parts.append(_md_table(["臂 (arm)", "類型 (kind)", "歸因區段 (segment)", "筆數"], a_tbl))
    else:
        parts.append("無錯誤紀錄（0 筆）。")
    return "\n".join(parts)


def render_latency_table(lat_data: Mapping[str, Any]) -> str:
    buckets = list(lat_data.get("buckets") or ["0", "1", "2", "None"])
    rows = lat_data.get("rows") or []
    headers = ["臂"] + [
        "未修正 (None)" if b == "None" else f"延遲 {b} 週期"
        for b in buckets
    ] + ["合計"]

    tbl_rows: list[list[str]] = []
    for r in rows:
        if not r.get("present"):
            tbl_rows.append([str(r["arm"])] + ["n/a"] * (len(headers) - 1))
            continue
        counts = r.get("counts") or {}
        tbl_rows.append(
            [str(r["arm"])]
            + [str(counts.get(b, 0)) for b in buckets]
            + [str(r.get("total", 0))]
        )
    return "\n".join(["## 6. 偵測延遲分布", "", _md_table(headers, tbl_rows)])


def render_data_sources(data_sources: Mapping[str, Sequence[str]]) -> str:
    labels = {
        "config_and_manifest": "清單與執行設定",
        "server_access_log": "來源伺服器存取紀錄",
        "materials_pages": "教材第 0 週期頁面",
        "harness_outputs": "執行器報告與週期紀錄",
        "sources_check": "c 臂第 1 週期出處檢查檔",
        "audit_chains": "病歷鏈檔",
        "audit_object_stores": "病歷內容定址物件目錄",
    }
    total = sum(len(v) for v in data_sources.values())
    parts = ["## 7. 資料來源", "", f"共列出 {total} 個檔案／目錄路徑：", ""]
    order = list(labels.keys()) + [k for k in sorted(data_sources) if k not in labels]
    for key in order:
        paths = list(data_sources.get(key) or [])
        if not paths:
            continue
        title = labels.get(key, key)
        parts.append(f"### {title}（{len(paths)}）")
        parts.append("")
        for p in paths:
            parts.append(f"- `{p}`")
        parts.append("")
    return "\n".join(parts).rstrip()


def render_markdown(report_data: Mapping[str, Any]) -> str:
    """由結構化報告資料渲染完整繁體中文 Markdown 報告（純函式）。"""
    meta = report_data.get("meta") or {}
    title_suffix = f" — {meta['plan_id']}" if meta.get("plan_id") else ""
    header_lines = [f"# D2′ 實驗報告{title_suffix}", ""]
    meta_items: list[str] = []
    if meta.get("root"):
        meta_items.append(f"執行目錄：`{meta['root']}`")
    if meta.get("manifest"):
        meta_items.append(f"清單：`{meta['manifest']}`")
    if meta.get("plan"):
        meta_items.append(f"計畫：`{meta['plan']}`")
    if meta.get("model"):
        meta_items.append(f"模型：`{meta['model']}`")
    if meta.get("sets"):
        sets = meta["sets"]
        meta_items.append(f"組別（{len(sets)}）：`{', '.join(sets)}`")
    if meta_items:
        for item in meta_items:
            header_lines.append(f"- {item}")
        header_lines.append("")

    sections = [
        "\n".join(header_lines).rstrip(),
        render_conclusion(report_data["conclusion"]),
        render_arm_table(report_data["arms_table"], report_data.get("c0")),
        render_pairwise_table(report_data["pairwise_table"]),
        render_provenance_quality(report_data["provenance_quality"]),
        render_audit_section(report_data["audit"]),
        render_latency_table(report_data["latency"]),
        render_data_sources(report_data["data_sources"]),
    ]
    return "\n\n".join(sections) + "\n"


# ---------------------------------------------------------------------------
# I/O orchestration (calls score_d2 / audit_d2 / analyze_d2 as libraries)
# ---------------------------------------------------------------------------

def load_sources_checks(
    root: pathlib.Path,
    sets: Sequence[str] | None = None,
) -> tuple[dict[str, dict[str, Any]], list[pathlib.Path]]:
    """讀取每個 set 的 `cells/<set>/c/cycle_1/sources_check.json`。"""
    cells_dir = root / "cells"
    if sets is not None:
        sids = sorted(sets)
    elif cells_dir.is_dir():
        sids = sorted(p.name for p in cells_dir.iterdir() if p.is_dir())
    else:
        sids = []

    by_set: dict[str, dict[str, Any]] = {}
    paths: list[pathlib.Path] = []
    for sid in sids:
        p = cells_dir / sid / "c" / "cycle_1" / "sources_check.json"
        if p.is_file():
            by_set[sid] = json.loads(p.read_text(encoding="utf-8"))
            paths.append(p.resolve())
    return by_set, paths


def _chain_files_in_vh(vh: pathlib.Path) -> tuple[list[str], list[str]]:
    chains: list[str] = []
    obj_dirs: list[str] = []
    projs = vh / "trace" / "projects"
    if projs.is_dir():
        for pdir in sorted(projs.iterdir()):
            if not pdir.is_dir():
                continue
            for v in sorted(pdir.glob("chain-*.ndjson*")):
                if v.is_file():
                    chains.append(str(v.resolve()))
            main_chain = pdir / "chain.ndjson"
            if main_chain.is_file():
                chains.append(str(main_chain.resolve()))
    objs = vh / "trace" / "objects"
    if objs.is_dir():
        obj_dirs.append(str(objs.resolve()))
    return chains, obj_dirs


def collect_data_sources(
    root: pathlib.Path,
    manifest_path: pathlib.Path,
    sets: Sequence[str],
    *,
    plan_path: pathlib.Path | None = None,
    sources_check_paths: Sequence[pathlib.Path] = (),
) -> dict[str, list[str]]:
    """列出所有提供數字的檔案與目錄路徑（已正規化與排序）。"""
    root_r = root.resolve()
    manifest_r = manifest_path.resolve()
    mat_dir = manifest_r.parent

    config_files = [str(manifest_r)]
    if plan_path is not None:
        config_files.append(str(plan_path.resolve()))
    runj = root_r / "RUN.json"
    if runj.is_file():
        config_files.append(str(runj))

    access_files: list[str] = []
    acc = root_r / "access.jsonl"
    if acc.is_file():
        access_files.append(str(acc))

    mat_pages: list[str] = []
    harness_files: list[str] = []
    audit_chains: list[str] = []
    audit_obj_dirs: list[str] = []

    for sid in sorted(sets):
        site = mat_dir / "sets" / sid / "cycle_0" / "site"
        for i in range(1, 6):
            pg = site / f"p{i}.html"
            if pg.is_file():
                mat_pages.append(str(pg))

        sdir = root_r / "cells" / sid
        for cand in (sdir / "c0" / "report.md", sdir / "c0" / "done.json"):
            if cand.is_file():
                harness_files.append(str(cand))

        c0_ch, c0_obj = _chain_files_in_vh(sdir / "c0" / "snapshot" / "vh")
        audit_chains.extend(c0_ch)
        audit_obj_dirs.extend(c0_obj)

        if sdir.is_dir():
            for adir in sorted(p for p in sdir.iterdir() if p.is_dir() and p.name != "c0"):
                done_p = adir / "done.json"
                if not done_p.is_file():
                    continue
                harness_files.append(str(done_p))
                for k in DEFAULT_CYCLES:
                    for fname in ("report.md", "cycle.json"):
                        fp = adir / f"cycle_{k}" / fname
                        if fp.is_file():
                            harness_files.append(str(fp))
                a_ch, a_obj = _chain_files_in_vh(adir / "final" / "vh")
                audit_chains.extend(a_ch)
                audit_obj_dirs.extend(a_obj)

    return {
        "config_and_manifest": sorted(dict.fromkeys(config_files)),
        "server_access_log": sorted(dict.fromkeys(access_files)),
        "materials_pages": sorted(dict.fromkeys(mat_pages)),
        "harness_outputs": sorted(dict.fromkeys(harness_files)),
        "sources_check": sorted(dict.fromkeys(str(p.resolve()) for p in sources_check_paths)),
        "audit_chains": sorted(dict.fromkeys(audit_chains)),
        "audit_object_stores": sorted(dict.fromkeys(audit_obj_dirs)),
    }


def _load_plan_info(
    root: pathlib.Path,
    plan_path: pathlib.Path | None,
) -> tuple[dict[str, Any] | None, list[str] | None, list[str] | None]:
    plan_obj: dict[str, Any] | None = None
    if plan_path is not None:
        plan_obj = json.loads(plan_path.read_text(encoding="utf-8"))
    else:
        runj = root / "RUN.json"
        if runj.is_file():
            try:
                body = json.loads(runj.read_text(encoding="utf-8")).get("plan_body")
                if isinstance(body, dict):
                    plan_obj = body
            except (OSError, ValueError):
                plan_obj = None
    if not isinstance(plan_obj, dict):
        return None, None, None
    arms = plan_obj.get("arms")
    sets = (plan_obj.get("materials") or {}).get("sets")
    exp_arms = list(arms) if isinstance(arms, list) and arms else None
    exp_sets = list(sets) if isinstance(sets, list) and sets else None
    return plan_obj, exp_arms, exp_sets


def generate_report(
    root: pathlib.Path,
    manifest_path: pathlib.Path,
    *,
    plan_path: pathlib.Path | None = None,
    n_boot: int = analyze_d2.DEFAULT_N_BOOT,
    seed: int = analyze_d2.DEFAULT_SEED,
) -> tuple[str, dict[str, Any]]:
    """呼叫 score_d2／audit_d2／analyze_d2 產出 Markdown 文字與 JSON 報告資料。"""
    root_p = root.expanduser().resolve()
    manifest_p = manifest_path.expanduser().resolve()
    plan_p = plan_path.expanduser().resolve() if plan_path is not None else None

    manifest = json.loads(manifest_p.read_text(encoding="utf-8"))
    plan_obj, exp_arms, exp_sets = _load_plan_info(root_p, plan_p)

    reports, costs = score_d2.load_harness(root_p)
    scored_sets = sorted(reports)
    score_res = score_d2.score(manifest, reports, costs)
    mat_dir = pathlib.Path(score_d2.manifest_dir(str(manifest_p)))
    materials = score_d2.materials_stats(manifest, mat_dir, scored_sets)
    score_res["summary"]["materials"] = materials

    audit_res = audit_d2.audit(root_p, manifest)
    harness_match = compare_audit_harness(audit_res["scores"]["rows"], score_res["rows"])

    target_arms = tuple(exp_arms) if exp_arms else DEFAULT_ARMS
    analysis = analyze_d2.analyze(
        score_res,
        costs,
        audit_res,
        n_boot=n_boot,
        seed=seed,
        expected_arms=target_arms,
        expected_sets=exp_sets,
    )

    checks_by_set, sc_paths = load_sources_checks(root_p, scored_sets)
    sc_summary = summarize_sources_check(checks_by_set)
    data_sources = collect_data_sources(
        root_p,
        manifest_p,
        scored_sets,
        plan_path=plan_p,
        sources_check_paths=sc_paths,
    )

    model_info = (plan_obj or {}).get("model") if isinstance(plan_obj, Mapping) else None
    model_str = None
    if isinstance(model_info, Mapping) and model_info.get("model"):
        prov = model_info.get("provider")
        model_str = f"{prov}/{model_info['model']}" if prov else str(model_info["model"])

    meta = {
        "root": str(root_p),
        "manifest": str(manifest_p),
        "plan": str(plan_p) if plan_p is not None else None,
        "plan_id": (plan_obj or {}).get("id") if isinstance(plan_obj, Mapping) else None,
        "model": model_str,
        "sets": scored_sets,
        "expected_sets": exp_sets,
        "expected_arms": list(target_arms),
    }

    report_data = build_report_data(
        score_res=score_res,
        audit_res=audit_res,
        harness_match=harness_match,
        analysis=analysis,
        sources_check_summary=sc_summary,
        materials=materials,
        data_sources=data_sources,
        meta=meta,
        arms=target_arms,
    )
    markdown = render_markdown(report_data)
    return markdown, report_data


def _default_sidecar_path(md_out: pathlib.Path) -> pathlib.Path:
    if md_out.suffix.lower() == ".md":
        return md_out.with_suffix(".json")
    return pathlib.Path(str(md_out) + ".json")


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Produce a D2' Traditional Chinese Markdown report and JSON sidecar."
    )
    ap.add_argument("--root", required=True, help="D2' run root directory")
    ap.add_argument("--manifest", required=True, help="Path to materials manifest.json")
    ap.add_argument("--plan", help="Optional path to plan JSON (defaults to <root>/RUN.json if present)")
    ap.add_argument("--out", help="Write Markdown report to this path (JSON sidecar defaults to sibling .json)")
    ap.add_argument("--json-out", help="Explicit path for JSON sidecar (overrides default sidecar path)")
    ap.add_argument("-B", "--bootstrap", type=int, default=analyze_d2.DEFAULT_N_BOOT,
                    help=f"Bootstrap replicates (default {analyze_d2.DEFAULT_N_BOOT})")
    ap.add_argument("--seed", type=int, default=analyze_d2.DEFAULT_SEED,
                    help=f"Bootstrap random seed (default {analyze_d2.DEFAULT_SEED})")
    a = ap.parse_args(argv)

    md, data = generate_report(
        pathlib.Path(a.root),
        pathlib.Path(a.manifest),
        plan_path=pathlib.Path(a.plan) if a.plan else None,
        n_boot=a.bootstrap,
        seed=a.seed,
    )

    json_body = json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    md_out = pathlib.Path(a.out).expanduser() if a.out else None
    json_out = (
        pathlib.Path(a.json_out).expanduser()
        if a.json_out
        else (_default_sidecar_path(md_out) if md_out is not None else None)
    )

    if md_out is not None:
        md_out.parent.mkdir(parents=True, exist_ok=True)
        md_out.write_text(md, encoding="utf-8")
    if json_out is not None:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json_body, encoding="utf-8")
    if md_out is None:
        print(md, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
