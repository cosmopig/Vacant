#!/usr/bin/env python3
"""D2′ 統計分析：以 set 為群集做 cluster bootstrap（純標準函式庫）。

輸入：
  --score <json>   `score_d2.py --out` 產生的分數 JSON（含 rows 與 summary）
  --root  <dir>    D2′ 執行根目錄（重用 `score_d2.load_harness` 取得每組×每臂×每週期用量）
  --audit <json>   （可選）`audit_d2.py --out` 產生的稽核 JSON（含 coverage）

主要判準（overall verdict）：
  (1) coverage = correct_page / claims（來自 audit）：< 0.80 ⇒ FAIL，≥ 0.80 ⇒ PASS
  (2) miss difference (c − b)：changed=True、以 (set, cycle, claim) 配對；
      單尾 95% 上界（bootstrap 第 95 百分位）< 0.10 ⇒ NONINFERIOR；
      點估計 ≥ 0.10 ⇒ FAIL；否則 UNRESOLVED
  (3) token ratio (b / c)：sum(tokens_in + tokens_out) 之比；
      雙尾 95% 百分位 CI 下界 ≥ 3 ⇒ EFFECTIVE；點估計 < 3 ⇒ FAIL；否則 UNRESOLVED
      （同法亦回報 calls ratio 與 wall ratio；任一臂 tokens 為 None 的 (set, cycle) 雙方成對排除並記數）
  (4) 次要指標（不進裁決）：c vs d、d vs b 的 miss diff 與 ratio；各臂誤改率（含 95% CI）；各臂各週期殘留 stale
  (5) 總裁決：缺臂／週期 ⇒ INCOMPLETE；任一主要項 FAIL ⇒ FAIL；
      coverage PASS 且 miss NONINFERIOR 且 token ratio EFFECTIVE ⇒ EFFECTIVE；否則 UNRESOLVED。
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import random
import sys
from collections.abc import Callable, Mapping, Sequence
from typing import Any

try:
    from .score_d2 import load_harness
except ImportError:
    _HERE = pathlib.Path(__file__).resolve().parent
    if str(_HERE) not in sys.path:
        sys.path.insert(0, str(_HERE))
    from score_d2 import load_harness  # type: ignore[no-redef]

DEFAULT_N_BOOT = 10000
DEFAULT_SEED = 20261125
DEFAULT_ARMS = ("a", "b", "c", "d")
DEFAULT_CYCLES = (1, 2, 3)

COVERAGE_THRESHOLD = 0.80
MISS_MARGIN = 0.10
RATIO_THRESHOLD = 3.0


def percentile(sorted_vals: Sequence[float], q: float) -> float | None:
    """線性插值百分位（q ∈ [0, 1]）；輸入須已遞增排序，安全處理 +inf。"""
    n = len(sorted_vals)
    if n == 0:
        return None
    if q <= 0.0:
        return sorted_vals[0]
    if q >= 1.0:
        return sorted_vals[-1]
    pos = q * (n - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    a, b = sorted_vals[lo], sorted_vals[hi]
    if lo == hi or a == b:
        return a
    if math.isinf(b):
        return b
    if math.isinf(a):
        return a
    return a + (pos - lo) * (b - a)


def draw_cluster_weights(n_sets: int, n_boot: int = DEFAULT_N_BOOT,
                         seed: int = DEFAULT_SEED) -> list[list[int]]:
    """對 n_sets 個群集有放回抽樣 n_boot 次，每次回傳長度 n_sets 的整數權重向量。"""
    if n_sets <= 0 or n_boot <= 0:
        return []
    rng = random.Random(seed)
    randrange = rng.randrange
    out: list[list[int]] = []
    for _ in range(n_boot):
        w = [0] * n_sets
        for _ in range(n_sets):
            w[randrange(n_sets)] += 1
        out.append(w)
    return out


def cluster_bootstrap(
    set_ids: Sequence[str],
    stat_fn: Callable[[Sequence[int]], float | None],
    *,
    n_boot: int = DEFAULT_N_BOOT,
    seed: int = DEFAULT_SEED,
    weights: Sequence[Sequence[int]] | None = None,
) -> list[float]:
    """對群集執行 bootstrap，回傳排序後的有效估計值列表。"""
    ws = weights if weights is not None else draw_cluster_weights(len(set_ids), n_boot, seed)
    vals: list[float] = []
    for w in ws:
        v = stat_fn(w)
        if v is not None and not math.isnan(v):
            vals.append(v)
    vals.sort()
    return vals


def check_completeness(
    rows: Sequence[dict[str, Any]],
    costs: Mapping[tuple[str, str, int], Mapping[str, Any]],
    *,
    expected_arms: Sequence[str] = DEFAULT_ARMS,
    expected_cycles: Sequence[int] = DEFAULT_CYCLES,
    expected_sets: Sequence[str] | None = None,
) -> dict[str, Any]:
    """檢查每個 set 是否具備全部預期的 arm × cycle（同時檢查 rows 與 costs）。"""
    row_keys = {(str(r["set"]), str(r["arm"]), int(r["cycle"]))
                for r in rows if str(r.get("arm")) != "c0"}
    cost_keys = {(str(sid), str(arm), int(k)) for sid, arm, k in costs}
    all_sets = sorted(
        set(expected_sets or ())
        | {str(r["set"]) for r in rows}
        | {str(sid) for sid, _, _ in costs}
    )
    missing: list[dict[str, Any]] = []
    for sid in all_sets:
        for arm in expected_arms:
            for cyc in expected_cycles:
                in_r = (sid, arm, cyc) in row_keys
                in_c = (sid, arm, cyc) in cost_keys
                if not in_r or not in_c:
                    where = "both" if (not in_r and not in_c) else ("rows" if not in_r else "costs")
                    missing.append({"set": sid, "arm": arm, "cycle": cyc, "missing_in": where})
    return {
        "complete": bool(all_sets) and len(missing) == 0,
        "n_sets": len(all_sets),
        "sets": all_sets,
        "expected_arms": list(expected_arms),
        "expected_cycles": [int(c) for c in expected_cycles],
        "missing": missing,
    }


def evaluate_coverage(audit_data: Mapping[str, Any] | None,
                      *, threshold: float = COVERAGE_THRESHOLD) -> dict[str, Any]:
    """(1) coverage = correct_page / claims；< threshold ⇒ FAIL，≥ threshold ⇒ PASS。"""
    if not isinstance(audit_data, Mapping) or not isinstance(audit_data.get("coverage"), Mapping):
        return {
            "available": False,
            "claims": None,
            "with_source": None,
            "correct_page": None,
            "rate": None,
            "with_source_rate": None,
            "threshold": threshold,
            "verdict": "UNRESOLVED",
        }
    cov = audit_data["coverage"]
    claims = int(cov.get("claims", 0))
    with_source = int(cov.get("with_source", 0))
    correct_page = int(cov.get("correct_page", 0))
    if claims <= 0:
        return {
            "available": True,
            "claims": claims,
            "with_source": with_source,
            "correct_page": correct_page,
            "rate": None,
            "with_source_rate": None,
            "threshold": threshold,
            "verdict": "UNRESOLVED",
        }
    rate = correct_page / claims
    return {
        "available": True,
        "claims": claims,
        "with_source": with_source,
        "correct_page": correct_page,
        "rate": rate,
        "with_source_rate": with_source / claims,
        "threshold": threshold,
        "verdict": "PASS" if rate >= threshold else "FAIL",
    }


def compute_miss_diff(
    rows: Sequence[dict[str, Any]],
    arm1: str,
    arm2: str,
    *,
    set_ids: Sequence[str] | None = None,
    weights: Sequence[Sequence[int]] | None = None,
    n_boot: int = DEFAULT_N_BOOT,
    seed: int = DEFAULT_SEED,
    margin: float | None = None,
) -> dict[str, Any]:
    """(2) 配對漏抓率差 (arm1 − arm2)：changed=True，以 (set, cycle, claim) 配對。"""
    m1: dict[tuple[str, int, str], int] = {}
    m2: dict[tuple[str, int, str], int] = {}
    for r in rows:
        if not r.get("changed"):
            continue
        arm = str(r.get("arm"))
        if arm != arm1 and arm != arm2:
            continue
        key = (str(r["set"]), int(r["cycle"]), str(r["claim"]))
        miss = 1 if r.get("status") != "correct" else 0
        if arm == arm1:
            m1[key] = miss
        if arm == arm2:
            m2[key] = miss
    paired = sorted(set(m1) & set(m2))
    per_set_diff: dict[str, int] = {}
    per_set_n: dict[str, int] = {}
    tot_m1 = 0
    tot_m2 = 0
    for key in paired:
        sid = key[0]
        v1, v2 = m1[key], m2[key]
        tot_m1 += v1
        tot_m2 += v2
        per_set_diff[sid] = per_set_diff.get(sid, 0) + (v1 - v2)
        per_set_n[sid] = per_set_n.get(sid, 0) + 1

    sets = list(set_ids) if set_ids is not None else sorted(per_set_n)
    n_pairs = len(paired)
    if n_pairs > 0:
        miss1: float | None = tot_m1 / n_pairs
        miss2: float | None = tot_m2 / n_pairs
        point: float | None = (tot_m1 - tot_m2) / n_pairs
    else:
        miss1 = miss2 = point = None

    diffs_arr = [per_set_diff.get(s, 0) for s in sets]
    ns_arr = [per_set_n.get(s, 0) for s in sets]
    idx_range = range(len(sets))

    def _stat(w: Sequence[int]) -> float | None:
        dn = 0
        dd = 0
        for i in idx_range:
            wi = w[i]
            if wi:
                dd += wi * diffs_arr[i]
                dn += wi * ns_arr[i]
        return dd / dn if dn > 0 else None

    reps = cluster_bootstrap(sets, _stat, n_boot=n_boot, seed=seed, weights=weights)
    upper_95 = percentile(reps, 0.95)
    ci_lo = percentile(reps, 0.025)
    ci_hi = percentile(reps, 0.975)

    res: dict[str, Any] = {
        "label": f"{arm1}-{arm2}",
        "arm1": arm1,
        "arm2": arm2,
        "n_pairs": n_pairs,
        "n_sets": len(per_set_n),
        "missed_arm1": tot_m1,
        "missed_arm2": tot_m2,
        "miss_rate_arm1": miss1,
        "miss_rate_arm2": miss2,
        "point": point,
        "upper_95": upper_95,
        "ci_95": [ci_lo, ci_hi],
    }
    if margin is not None:
        if point is None or upper_95 is None:
            verdict = "UNRESOLVED"
        elif point >= margin:
            verdict = "FAIL"
        elif upper_95 < margin:
            verdict = "NONINFERIOR"
        else:
            verdict = "UNRESOLVED"
        res["margin"] = margin
        res["verdict"] = verdict
    return res


def _extract_metric(entry: Mapping[str, Any], metric: str) -> float | None:
    if metric == "tokens":
        ti = entry.get("tokens_in")
        to = entry.get("tokens_out")
        if ti is None or to is None:
            return None
        return float(ti) + float(to)
    if metric == "calls":
        v = entry.get("calls")
        return None if v is None else float(v)
    if metric == "wall_s":
        v = entry.get("wall_s")
        return None if v is None else float(v)
    raise ValueError(f"unknown metric: {metric!r}")


def compute_cost_ratio(
    costs: Mapping[tuple[str, str, int], Mapping[str, Any]],
    num_arm: str,
    den_arm: str,
    metric: str,
    *,
    set_ids: Sequence[str] | None = None,
    weights: Sequence[Sequence[int]] | None = None,
    n_boot: int = DEFAULT_N_BOOT,
    seed: int = DEFAULT_SEED,
    threshold: float | None = None,
) -> dict[str, Any]:
    """(3) 成本比值 (num_arm / den_arm)：以 (set, cycle) 配對，任一臂未知（None）則雙方成對排除。"""
    num_map: dict[tuple[str, int], Mapping[str, Any]] = {}
    den_map: dict[tuple[str, int], Mapping[str, Any]] = {}
    for (sid, arm, cyc), entry in costs.items():
        key = (str(sid), int(cyc))
        if str(arm) == num_arm:
            num_map[key] = entry
        elif str(arm) == den_arm:
            den_map[key] = entry

    unknown_num = [list(k) for k in sorted(num_map) if _extract_metric(num_map[k], metric) is None]
    unknown_den = [list(k) for k in sorted(den_map) if _extract_metric(den_map[k], metric) is None]
    paired_sc = sorted(set(num_map) & set(den_map))

    excluded_unknown: list[list[Any]] = []
    num_by_set: dict[str, float] = {}
    den_by_set: dict[str, float] = {}
    n_used = 0
    for sid, cyc in paired_sc:
        nv = _extract_metric(num_map[(sid, cyc)], metric)
        dv = _extract_metric(den_map[(sid, cyc)], metric)
        if nv is None or dv is None:
            excluded_unknown.append([sid, cyc])
            continue
        num_by_set[sid] = num_by_set.get(sid, 0.0) + nv
        den_by_set[sid] = den_by_set.get(sid, 0.0) + dv
        n_used += 1

    sum_num = sum(num_by_set.values())
    sum_den = sum(den_by_set.values())
    if n_used == 0:
        point: float | None = None
    elif sum_den > 0.0:
        point = sum_num / sum_den
    elif sum_num > 0.0:
        point = math.inf
    else:
        point = None

    sets = list(set_ids) if set_ids is not None else sorted({sid for sid, _ in paired_sc})
    num_arr = [num_by_set.get(s, 0.0) for s in sets]
    den_arr = [den_by_set.get(s, 0.0) for s in sets]
    idx_range = range(len(sets))

    def _stat(w: Sequence[int]) -> float | None:
        bn = 0.0
        bd = 0.0
        for i in idx_range:
            wi = w[i]
            if wi:
                bn += wi * num_arr[i]
                bd += wi * den_arr[i]
        if bd > 0.0:
            return bn / bd
        if bn > 0.0:
            return math.inf
        return None

    reps = cluster_bootstrap(sets, _stat, n_boot=n_boot, seed=seed, weights=weights)
    ci_lo = percentile(reps, 0.025)
    ci_hi = percentile(reps, 0.975)

    res: dict[str, Any] = {
        "label": f"{num_arm}/{den_arm}",
        "metric": metric,
        "numerator": num_arm,
        "denominator": den_arm,
        "n_paired_total": len(paired_sc),
        "n_paired_used": n_used,
        "excluded_unknown_count": len(excluded_unknown),
        "excluded_unknown": excluded_unknown,
        "unknown_in_numerator": len(unknown_num),
        "unknown_in_denominator": len(unknown_den),
        "sum_numerator": sum_num,
        "sum_denominator": sum_den,
        "point": point,
        "ci_95": [ci_lo, ci_hi],
    }
    if threshold is not None:
        if point is None or ci_lo is None:
            verdict = "UNRESOLVED"
        elif point < threshold:
            verdict = "FAIL"
        elif ci_lo >= threshold:
            verdict = "EFFECTIVE"
        else:
            verdict = "UNRESOLVED"
        res["threshold"] = threshold
        res["verdict"] = verdict
    return res


def compute_false_mod(
    rows: Sequence[dict[str, Any]],
    arm: str,
    *,
    set_ids: Sequence[str] | None = None,
    weights: Sequence[Sequence[int]] | None = None,
    n_boot: int = DEFAULT_N_BOOT,
    seed: int = DEFAULT_SEED,
) -> dict[str, Any]:
    """單臂誤改率：changed=False 且 pre=='correct' 中，status != 'correct' 的比例與 95% CI。"""
    per_set_fm: dict[str, int] = {}
    per_set_n: dict[str, int] = {}
    tot_fm = 0
    tot_n = 0
    for r in rows:
        if str(r.get("arm")) != arm:
            continue
        if r.get("changed") or r.get("pre") != "correct":
            continue
        sid = str(r["set"])
        bad = 1 if r.get("status") != "correct" else 0
        tot_fm += bad
        tot_n += 1
        per_set_fm[sid] = per_set_fm.get(sid, 0) + bad
        per_set_n[sid] = per_set_n.get(sid, 0) + 1

    sets = list(set_ids) if set_ids is not None else sorted(per_set_n)
    point: float | None = tot_fm / tot_n if tot_n > 0 else None
    fm_arr = [per_set_fm.get(s, 0) for s in sets]
    n_arr = [per_set_n.get(s, 0) for s in sets]
    idx_range = range(len(sets))

    def _stat(w: Sequence[int]) -> float | None:
        num = 0
        den = 0
        for i in idx_range:
            wi = w[i]
            if wi:
                num += wi * fm_arr[i]
                den += wi * n_arr[i]
        return num / den if den > 0 else None

    reps = cluster_bootstrap(sets, _stat, n_boot=n_boot, seed=seed, weights=weights)
    return {
        "arm": arm,
        "n": tot_n,
        "false_mod": tot_fm,
        "point": point,
        "ci_95": [percentile(reps, 0.025), percentile(reps, 0.975)],
    }


def compute_residual_stale(
    rows: Sequence[dict[str, Any]],
    *,
    arms: Sequence[str] | None = None,
    cycles: Sequence[int] = DEFAULT_CYCLES,
) -> dict[str, dict[str, dict[str, Any]]]:
    """各臂各週期的殘留 stale 數與比例。"""
    found_arms = sorted({str(r["arm"]) for r in rows if str(r.get("arm")) != "c0"})
    target_arms = sorted(set(found_arms) | set(arms or ()))
    out: dict[str, dict[str, dict[str, Any]]] = {}
    for arm in target_arms:
        out[arm] = {}
        for k in cycles:
            sub = [r for r in rows if str(r.get("arm")) == arm and int(r["cycle"]) == k]
            stale = sum(1 for r in sub if r.get("status") == "stale")
            tot = len(sub)
            out[arm][str(k)] = {"stale": stale, "total": tot, "rate": (stale / tot if tot else None)}
    return out


def compute_usage_unknown_summary(
    costs: Mapping[tuple[str, str, int], Mapping[str, Any]],
) -> dict[str, Any]:
    """統計各臂未知用量（tokens / calls / wall_s 為 None）的 (set, cycle) 數。"""
    by_arm: dict[str, dict[str, Any]] = {}
    for (sid, arm, cyc), entry in sorted(costs.items()):
        a = str(arm)
        d = by_arm.setdefault(a, {"set_cycles": 0, "tokens_unknown": 0, "calls_unknown": 0,
                                  "wall_unknown": 0, "tokens_unknown_keys": []})
        d["set_cycles"] += 1
        if entry.get("tokens_in") is None or entry.get("tokens_out") is None:
            d["tokens_unknown"] += 1
            d["tokens_unknown_keys"].append([str(sid), int(cyc)])
        if entry.get("calls") is None:
            d["calls_unknown"] += 1
        if entry.get("wall_s") is None:
            d["wall_unknown"] += 1
    return {
        "total_tokens_unknown": sum(v["tokens_unknown"] for v in by_arm.values()),
        "total_calls_unknown": sum(v["calls_unknown"] for v in by_arm.values()),
        "by_arm": by_arm,
    }


def analyze(
    score_data: Mapping[str, Any],
    costs: Mapping[tuple[str, str, int], Mapping[str, Any]],
    audit_data: Mapping[str, Any] | None = None,
    *,
    n_boot: int = DEFAULT_N_BOOT,
    seed: int = DEFAULT_SEED,
    expected_arms: Sequence[str] = DEFAULT_ARMS,
    expected_cycles: Sequence[int] = DEFAULT_CYCLES,
    expected_sets: Sequence[str] | None = None,
) -> dict[str, Any]:
    """執行完整 D2′ 群集 bootstrap 分析並回傳結構化結果。"""
    rows: list[dict[str, Any]] = list(score_data.get("rows") or [])
    comp = check_completeness(rows, costs, expected_arms=expected_arms,
                              expected_cycles=expected_cycles, expected_sets=expected_sets)
    set_ids = comp["sets"]
    weights = draw_cluster_weights(len(set_ids), n_boot=n_boot, seed=seed)

    cov = evaluate_coverage(audit_data, threshold=COVERAGE_THRESHOLD)
    miss_cb = compute_miss_diff(rows, "c", "b", set_ids=set_ids, weights=weights, margin=MISS_MARGIN)
    tok_bc = compute_cost_ratio(costs, "b", "c", "tokens", set_ids=set_ids, weights=weights,
                                threshold=RATIO_THRESHOLD)
    calls_bc = compute_cost_ratio(costs, "b", "c", "calls", set_ids=set_ids, weights=weights)
    wall_bc = compute_cost_ratio(costs, "b", "c", "wall_s", set_ids=set_ids, weights=weights)

    arms_present = sorted({str(r["arm"]) for r in rows if str(r.get("arm")) != "c0"})
    secondary = {
        "c_vs_d": {
            "miss_diff": compute_miss_diff(rows, "c", "d", set_ids=set_ids, weights=weights),
            "token_ratio": compute_cost_ratio(costs, "d", "c", "tokens", set_ids=set_ids, weights=weights),
            "calls_ratio": compute_cost_ratio(costs, "d", "c", "calls", set_ids=set_ids, weights=weights),
            "wall_ratio": compute_cost_ratio(costs, "d", "c", "wall_s", set_ids=set_ids, weights=weights),
        },
        "d_vs_b": {
            "miss_diff": compute_miss_diff(rows, "d", "b", set_ids=set_ids, weights=weights),
            "token_ratio": compute_cost_ratio(costs, "b", "d", "tokens", set_ids=set_ids, weights=weights),
            "calls_ratio": compute_cost_ratio(costs, "b", "d", "calls", set_ids=set_ids, weights=weights),
            "wall_ratio": compute_cost_ratio(costs, "b", "d", "wall_s", set_ids=set_ids, weights=weights),
        },
        "false_mod": {
            arm: compute_false_mod(rows, arm, set_ids=set_ids, weights=weights)
            for arm in arms_present
        },
        "residual_stale": compute_residual_stale(rows, arms=arms_present, cycles=expected_cycles),
    }

    cov_v = cov["verdict"]
    miss_v = miss_cb["verdict"]
    ratio_v = tok_bc["verdict"]
    if not comp["complete"]:
        overall = "INCOMPLETE"
    elif "FAIL" in (cov_v, miss_v, ratio_v):
        overall = "FAIL"
    elif cov_v == "PASS" and miss_v == "NONINFERIOR" and ratio_v == "EFFECTIVE":
        overall = "EFFECTIVE"
    else:
        overall = "UNRESOLVED"

    return {
        "schema": "vacant.d2.analysis/1",
        "verdict": overall,
        "verdict_parts": {
            "complete": comp["complete"],
            "coverage": cov_v,
            "miss_diff_c_b": miss_v,
            "token_ratio_b_c": ratio_v,
        },
        "bootstrap": {"n_boot": n_boot, "seed": seed, "n_sets": len(set_ids)},
        "completeness": comp,
        "coverage": cov,
        "primary": {
            "miss_diff_c_b": miss_cb,
            "token_ratio_b_c": tok_bc,
            "calls_ratio_b_c": calls_bc,
            "wall_ratio_b_c": wall_bc,
        },
        "secondary": secondary,
        "usage_unknown": compute_usage_unknown_summary(costs),
    }


def _fmt_num(x: float | None, digits: int = 3, pct: bool = False) -> str:
    if x is None:
        return "n/a"
    if math.isinf(x):
        return "inf"
    if pct:
        return f"{x * 100:.1f}%"
    return f"{x:.{digits}f}"


def _fmt_ci(ci: Sequence[float | None], digits: int = 3, pct: bool = False) -> str:
    return f"[{_fmt_num(ci[0], digits, pct)}, {_fmt_num(ci[1], digits, pct)}]"


def format_text(res: Mapping[str, Any]) -> str:
    """產出精簡人讀報告。"""
    lines: list[str] = []
    boot = res["bootstrap"]
    comp = res["completeness"]
    lines.append(f"D2' Analysis Verdict: {res['verdict']} "
                 f"(sets={boot['n_sets']}, B={boot['n_boot']}, seed={boot['seed']})")
    if not comp["complete"]:
        miss_preview = ", ".join(
            f"{m['set']}/{m['arm']}/c{m['cycle']}({m['missing_in']})"
            for m in comp["missing"][:10]
        )
        more = f" (+{len(comp['missing']) - 10} more)" if len(comp["missing"]) > 10 else ""
        lines.append(f"  INCOMPLETE missing ({len(comp['missing'])}): {miss_preview}{more}")

    cov = res["coverage"]
    if cov["available"] and cov["claims"]:
        lines.append(f"  [1] Coverage: {cov['correct_page']}/{cov['claims']} "
                     f"= {_fmt_num(cov['rate'], pct=True)} "
                     f"(with_source={cov['with_source']}/{cov['claims']}, "
                     f"threshold>={cov['threshold']:.0%}) -> {cov['verdict']}")
    else:
        lines.append(f"  [1] Coverage: not available -> {cov['verdict']}")

    p = res["primary"]
    m = p["miss_diff_c_b"]
    lines.append(f"  [2] Miss diff (c-b): {_fmt_num(m['point'], 4)} "
                 f"(95% upper={_fmt_num(m['upper_95'], 4)}, margin<{m['margin']:.2f}; "
                 f"c={_fmt_num(m['miss_rate_arm1'], pct=True)}, "
                 f"b={_fmt_num(m['miss_rate_arm2'], pct=True)}, n={m['n_pairs']}) -> {m['verdict']}")

    for tag, key, show_v in (("Token", "token_ratio_b_c", True),
                             ("Calls", "calls_ratio_b_c", False),
                             ("Wall ", "wall_ratio_b_c", False)):
        r = p[key]
        vtxt = f" -> {r['verdict']}" if show_v else ""
        unk = f", excl_unk={r['excluded_unknown_count']}" if r["excluded_unknown_count"] else ""
        lines.append(f"  [3] {tag} ratio (b/c): {_fmt_num(r['point'], 2)}x "
                     f"95% CI {_fmt_ci(r['ci_95'], 2)} "
                     f"(n={r['n_paired_used']}/{r['n_paired_total']}{unk}){vtxt}")

    sec = res["secondary"]
    lines.append("  [4] Secondary:")
    for name, label_m, label_r in (("c_vs_d", "c-d", "d/c"), ("d_vs_b", "d-b", "b/d")):
        blk = sec[name]
        md = blk["miss_diff"]
        tr = blk["token_ratio"]
        lines.append(f"      {name}: miss({label_m})={_fmt_num(md['point'], 4)} "
                     f"(upper95={_fmt_num(md['upper_95'], 4)}), "
                     f"tok({label_r})={_fmt_num(tr['point'], 2)}x {_fmt_ci(tr['ci_95'], 2)}")
    if sec["false_mod"]:
        fm_parts = [
            f"{arm}={d['false_mod']}/{d['n']}({_fmt_num(d['point'], pct=True)} {_fmt_ci(d['ci_95'], pct=True)})"
            for arm, d in sorted(sec["false_mod"].items())
        ]
        lines.append("      false_mod: " + "; ".join(fm_parts))
    if sec["residual_stale"]:
        st_parts = []
        for arm, cycs in sorted(sec["residual_stale"].items()):
            cs = ",".join(f"c{k}={cycs[k]['stale']}" for k in sorted(cycs, key=int))
            st_parts.append(f"{arm}({cs})")
        lines.append("      residual_stale: " + " ".join(st_parts))
    unk_tot = res["usage_unknown"]["total_tokens_unknown"]
    if unk_tot:
        lines.append(f"      usage_unknown(tokens): {unk_tot}")
    return "\n".join(lines)


def _expected_from_root(root: pathlib.Path) -> tuple[list[str] | None, list[str] | None]:
    runj = root / "RUN.json"
    if not runj.exists():
        return None, None
    try:
        plan = json.loads(runj.read_text()).get("plan_body") or {}
    except (OSError, ValueError):
        return None, None
    arms = plan.get("arms")
    sets = (plan.get("materials") or {}).get("sets")
    return (list(arms) if isinstance(arms, list) and arms else None,
            list(sets) if isinstance(sets, list) and sets else None)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Cluster-bootstrap analysis for D2' experiment.")
    ap.add_argument("--score", required=True, help="JSON written by score_d2.py --out")
    ap.add_argument("--root", required=True, help="D2' run root directory (for costs via score_d2.load_harness)")
    ap.add_argument("--audit", help="Optional JSON written by audit_d2.py --out (for coverage)")
    ap.add_argument("-B", "--bootstrap", type=int, default=DEFAULT_N_BOOT,
                    help=f"Bootstrap replicates (default {DEFAULT_N_BOOT})")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED,
                    help=f"Random seed (default {DEFAULT_SEED})")
    ap.add_argument("--out", help="Write JSON result to this path")
    ap.add_argument("--text-out", help="Write human-readable text summary to this path")
    a = ap.parse_args(argv)

    score_data = json.loads(pathlib.Path(a.score).expanduser().read_text(encoding="utf-8"))
    root = pathlib.Path(a.root).expanduser()
    _reports, costs = load_harness(root)
    audit_data = (json.loads(pathlib.Path(a.audit).expanduser().read_text(encoding="utf-8"))
                  if a.audit else None)
    exp_arms, exp_sets = _expected_from_root(root)

    res = analyze(
        score_data,
        costs,
        audit_data,
        n_boot=a.bootstrap,
        seed=a.seed,
        expected_arms=exp_arms or DEFAULT_ARMS,
        expected_sets=exp_sets,
    )
    body = json.dumps(res, ensure_ascii=False, indent=1, sort_keys=True)
    text = format_text(res)
    if a.out:
        out_p = pathlib.Path(a.out).expanduser()
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(body + "\n", encoding="utf-8")
    if a.text_out:
        txt_p = pathlib.Path(a.text_out).expanduser()
        txt_p.parent.mkdir(parents=True, exist_ok=True)
        txt_p.write_text(text + "\n", encoding="utf-8")
    if a.out:
        print(text)
    else:
        print(body)
        print("\n" + text, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
