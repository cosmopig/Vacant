"""把一個或多個 twin2k-run 目錄寫成 P5 形狀的報告。

決定規則寫在數字前面。unsure 同時當棄權比例，也算進嚴格準確率的錯誤。
這支不呼叫模型，也不讀本人自填的 C/H。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ARMS = ("MAJORITY", "DEMOGRAPHICS", "NONE", "RAW", "SUMMARY", "STRUCTURED")
PROFILE_ARMS = ("DEMOGRAPHICS", "RAW", "SUMMARY", "STRUCTURED")
LLM_ARMS = ("DEMOGRAPHICS", "NONE", "RAW", "SUMMARY", "STRUCTURED")

DECISION_RULE = """\
Decision rule, fixed before the numbers in this file are read:

1. A directory is inconclusive when predictions are missing, an arm is missing rows for a person-item that another arm has, or fewer than 95% of its LLM cells have status completed.
2. Otherwise let S be STRUCTURED strict accuracy, U be SUMMARY strict accuracy, M be leave-one-out MAJORITY, and C be the mean of the per-person test-retest rates recomputed for this sample. Unsure counts as incorrect in S, U, and M. It is also shown as its own rate.
3. If S−U is at least 0.03 and the paired bootstrap 95% interval of S−U is entirely above 0: continue. That is an exploratory screen, not a population result.
4. Otherwise if S−U is at most 0: simplify. Keep the summary.
5. Otherwise if every profile arm is at most M+0.02 and C is known and S is below C−0.15: stop.
6. Otherwise: inconclusive.

If the directories disagree, the headline is inconclusive and each directory keeps its own decision.
The 83% test-retest and 56% majority figures from a 294-person pilot are a reference printed next to the recomputed ceiling and floor. They are not this run.
"""


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _latest(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        latest[(str(row.get("pid")), str(row.get("arm")), str(row.get("case_id")))] = row
    return list(latest.values())


def load_run(path: Path, *, model_id: str | None = None) -> dict[str, Any]:
    root = Path(path)
    meta_path = root / "run_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
    scores_path = root / "scores.json"
    scores = json.loads(scores_path.read_text(encoding="utf-8")) if scores_path.is_file() else {}
    predictions = _latest(_read_jsonl(root / "predictions.jsonl"))
    calls = _read_jsonl(root / "calls.jsonl")
    return {
        "path": str(root),
        "model_id": model_id or meta.get("model_id") or root.name,
        "meta": meta,
        "scores": scores,
        "predictions": predictions,
        "calls": calls,
    }


def _acc(scores: dict[str, Any], arm: str) -> float | None:
    block = (scores.get("arms") or {}).get(arm) or {}
    value = block.get("strict_accuracy", block.get("micro_accuracy"))
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _wilson(scores: dict[str, Any], arm: str) -> list[float] | None:
    value = ((scores.get("arms") or {}).get(arm) or {}).get("micro_wilson95")
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return [float(value[0]), float(value[1])]
    return None


def unsure_table(predictions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    found = {}
    for arm in ARMS:
        rows = [row for row in predictions if row.get("arm") == arm]
        unsure = [row for row in rows if row.get("prediction") == "unsure" and row.get("status") == "completed"]
        found[arm] = {
            "n": len(rows),
            "unsure_n": len(unsure),
            "unsure_rate": (len(unsure) / len(rows)) if rows else None,
        }
    return found


def _coverage(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    cases = {(str(row.get("pid")), str(row.get("case_id"))) for row in predictions if row.get("arm") in LLM_ARMS}
    per_arm = {}
    incomplete = not predictions or not cases
    for arm in LLM_ARMS:
        rows = [row for row in predictions if row.get("arm") == arm]
        keys = {(str(row.get("pid")), str(row.get("case_id"))) for row in rows}
        done = sum(1 for row in rows if row.get("status") == "completed")
        frac = (done / len(cases)) if cases else 0.0
        per_arm[arm] = {"rows": len(rows), "completed": done, "completed_fraction": frac}
        if keys != cases or frac < 0.95:
            incomplete = True
    return {"cases": len(cases), "per_arm": per_arm, "incomplete": incomplete}


def _ceiling(scores: dict[str, Any]) -> float | None:
    rates = []
    for row in (scores.get("retests") or {}).values():
        if isinstance(row, dict) and isinstance(row.get("rate"), (int, float)) and not isinstance(row.get("rate"), bool):
            rates.append(float(row["rate"]))
    if not rates:
        return None
    return sum(rates) / len(rates)


def _oriented_pair(scores: dict[str, Any], left: str, right: str) -> dict[str, Any] | None:
    """回 right−left 的差與區間。McNemar 的 b 是只有 right 對。"""
    for pair in scores.get("pairs") or []:
        if pair.get("left") == left and pair.get("right") == right:
            return {
                "diff": pair.get("accuracy_diff_right_minus_left"),
                "bootstrap95": pair.get("bootstrap95"),
                "mcnemar_p": pair.get("mcnemar_p"),
                "b_right_only": pair.get("mcnemar_b_right_only"),
                "c_left_only": pair.get("mcnemar_c_left_only"),
                "n": pair.get("n"),
            }
        if pair.get("left") == right and pair.get("right") == left:
            diff = pair.get("accuracy_diff_right_minus_left")
            boot = pair.get("bootstrap95")
            flipped = None if not isinstance(boot, (list, tuple)) else [-float(boot[1]), -float(boot[0])]
            return {
                "diff": None if diff is None else -float(diff),
                "bootstrap95": flipped,
                "mcnemar_p": pair.get("mcnemar_p"),
                "b_right_only": pair.get("mcnemar_c_left_only"),
                "c_left_only": pair.get("mcnemar_b_right_only"),
                "n": pair.get("n"),
            }
    return None


def _ci_above_zero(boot: Any) -> bool:
    return isinstance(boot, (list, tuple)) and len(boot) == 2 and float(boot[0]) > 0


def decide_one(run: dict[str, Any]) -> dict[str, Any]:
    coverage = _coverage(run["predictions"])
    if coverage["incomplete"] or not run["scores"]:
        return {"decision": "inconclusive", "reason": "cells are incomplete or scores.json is missing", "coverage": coverage}
    scores = run["scores"]
    structured = _acc(scores, "STRUCTURED")
    summary = _acc(scores, "SUMMARY")
    majority = _acc(scores, "MAJORITY")
    ceiling = _ceiling(scores)
    pair = _oriented_pair(scores, "SUMMARY", "STRUCTURED")
    diff = None if pair is None else pair.get("diff")
    if structured is None or summary is None or diff is None:
        return {"decision": "inconclusive", "reason": "SUMMARY or STRUCTURED accuracy is missing", "coverage": coverage}
    if diff >= 0.03 and _ci_above_zero(pair.get("bootstrap95") if pair else None):
        return {"decision": "continue", "reason": "STRUCTURED beats SUMMARY by at least 0.03 and the bootstrap interval is above 0", "coverage": coverage, "diff_structured_minus_summary": diff}
    if diff <= 0:
        return {"decision": "simplify", "reason": "SUMMARY is at least as accurate as STRUCTURED", "coverage": coverage, "diff_structured_minus_summary": diff}
    profile_vals = [_acc(scores, arm) for arm in PROFILE_ARMS]
    if majority is not None and ceiling is not None and all(value is not None and value <= majority + 0.02 for value in profile_vals) and structured < ceiling - 0.15:
        return {"decision": "stop", "reason": "profile arms sit on the majority floor and well below the recomputed test-retest ceiling", "coverage": coverage}
    return {"decision": "inconclusive", "reason": "the screen margins were not met", "coverage": coverage, "diff_structured_minus_summary": diff}


def _cost(calls: list[dict[str, Any]]) -> dict[str, Any]:
    known = 0.0
    priced = False
    unknown = 0
    walls = []
    for row in calls:
        if row.get("budget_request") is False:
            continue
        if row.get("sent") is False:
            continue
        usage = row.get("usage")
        if not usage:
            unknown += 1
        if isinstance(row.get("cost_usd"), (int, float)) and not isinstance(row.get("cost_usd"), bool):
            known += float(row["cost_usd"])
            priced = True
        if isinstance(row.get("wall_ms"), int):
            walls.append(row["wall_ms"])
    return {
        "known_cost_usd": known if priced else None,
        "unknown_usage_calls": unknown,
        "wall_ms_sum": sum(walls),
        "wall_ms_mean": (sum(walls) / len(walls)) if walls else None,
        "calls": len(calls),
    }


def decide_all(runs: list[dict[str, Any]]) -> dict[str, Any]:
    per = [{"model_id": run["model_id"], **decide_one(run)} for run in runs]
    names = {item["decision"] for item in per}
    if len(names) == 1:
        return {"decision": per[0]["decision"], "reason": per[0]["reason"], "per_model": per}
    detail = ", ".join(f"{item['model_id']}={item['decision']}" for item in per)
    return {"decision": "inconclusive", "reason": f"models disagree: {detail}", "per_model": per}


def _fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def render_report(runs: list[dict[str, Any]]) -> str:
    if not runs:
        raise ValueError("no runs")
    headline = decide_all(runs)
    lines = [
        "# Twin-2K-500 result",
        "",
        DECISION_RULE.strip(),
        "",
        f"**Headline decision: {headline['decision']}.** {headline['reason']}",
        "",
        "## 1. Decision",
        "",
        headline["decision"],
        "",
        headline["reason"],
        "",
        "## 2. Experiment identity",
        "",
    ]
    for run in runs:
        meta = run["meta"]
        lines.append(f"- `{run['model_id']}` from `{run['path']}`"
                     + (f", seed {meta.get('seed')}" if meta.get("seed") is not None else "")
                     + (f", participants {meta.get('participants')}" if meta.get("participants") is not None else ""))
    lines.extend([
        "",
        "Preliminary reference, not this sample: test-retest ceiling 0.83 and majority floor 0.56 on 294 people.",
        "",
        "## 3. Cells",
        "",
    ])
    for run in runs:
        coverage = _coverage(run["predictions"])
        lines.append(f"- `{run['model_id']}`: {coverage['cases']} person-items; incomplete={coverage['incomplete']}.")
        for arm, block in coverage["per_arm"].items():
            lines.append(f"  - {arm}: completed {block['completed']}/{coverage['cases']} ({_fmt(block['completed_fraction'])})")
    lines.extend(["", "## 4. Stage 1 preference predictions", ""])
    for run in runs:
        scores = run["scores"]
        ceiling = _ceiling(scores)
        unsure = unsure_table(run["predictions"])
        lines.append(f"### {run['model_id']}")
        lines.append("")
        lines.append(f"Recomputed test-retest ceiling (mean of per-person rates): {_fmt(ceiling)}.")
        lines.append(f"Leave-one-out majority floor: {_fmt(_acc(scores, 'MAJORITY'))}.")
        lines.append("")
        lines.append("| Arm | Strict accuracy | Wilson 95% | Unsure rate | Unsure n |")
        lines.append("|---|---:|---|---:|---:|")
        for arm in ARMS:
            interval = _wilson(scores, arm)
            interval_text = "—" if interval is None else f"{interval[0]:.3f}–{interval[1]:.3f}"
            rate = unsure[arm]["unsure_rate"]
            lines.append(f"| {arm} | {_fmt(_acc(scores, arm))} | {interval_text} | {_fmt(rate)} | {unsure[arm]['unsure_n']} |")
        lines.append("")
        lines.append("Unsure is an abstention in the rate column and an incorrect answer in strict accuracy. It stays in the denominator.")
        lines.append("")
        for label, left, right in (
            ("versus no profile", "NONE", "STRUCTURED"),
            ("versus no profile", "NONE", "SUMMARY"),
            ("versus no profile", "NONE", "RAW"),
            ("STRUCTURED versus SUMMARY", "SUMMARY", "STRUCTURED"),
        ):
            pair = _oriented_pair(scores, left, right)
            if pair is None:
                lines.append(f"- {right} {label}: pair missing.")
                continue
            boot = pair.get("bootstrap95")
            boot_text = "—" if not isinstance(boot, (list, tuple)) else f"{float(boot[0]):.3f}–{float(boot[1]):.3f}"
            lines.append(
                f"- {right} minus {left}: diff {_fmt(pair.get('diff'))}, bootstrap 95% {boot_text}, "
                f"McNemar p {_fmt(pair.get('mcnemar_p'), 4)} "
                f"(b only-{right} {pair.get('b_right_only')}, c only-{left} {pair.get('c_left_only')}, n {pair.get('n')})."
            )
        lines.append("")
        order = ((scores.get("arms") or {}).get("STRUCTURED") or {}).get("option_order") or {}
        lines.append("Option order, STRUCTURED strict accuracy:")
        for name in ("identity", "swapped"):
            block = order.get(name) or {}
            lines.append(f"- {name}: n {block.get('n', '—')}, accuracy {_fmt(block.get('accuracy'))}")
        lines.append("")
        negatives = []
        none_acc = _acc(scores, "NONE")
        maj_acc = _acc(scores, "MAJORITY")
        for arm in PROFILE_ARMS:
            value = _acc(scores, arm)
            if value is None or none_acc is None or maj_acc is None:
                continue
            if value < none_acc and value < maj_acc:
                negatives.append(f"{arm} {_fmt(value)} is below both NONE {_fmt(none_acc)} and MAJORITY {_fmt(maj_acc)}")
        lines.append("Negative results: " + ("; ".join(negatives) if negatives else "none of the profile arms are below both NONE and MAJORITY."))
        lines.append("")
    lines.extend(["## 5. Stage 2 memos", "", "Not run. This report is the preference-prediction screen only.", ""])
    lines.extend(["## 6. Cost and latency", ""])
    lines.append("| Model | Calls | Known USD | Unknown usage calls | Mean wall ms |")
    lines.append("|---|---:|---:|---:|---:|")
    for run in runs:
        cost = _cost(run["calls"])
        lines.append(f"| {run['model_id']} | {cost['calls']} | {_fmt(cost['known_cost_usd'])} | {cost['unknown_usage_calls']} | {_fmt(cost['wall_ms_mean'], 1)} |")
    lines.extend([
        "",
        "Known USD sums `cost_usd` on sent calls. A call with `budget_request: false` is a superseded retry and is not added. Missing usage stays missing; it is not filled with zero.",
        "",
        "## 7. Cross-model table",
        "",
        "| Model | MAJORITY | NONE | RAW | SUMMARY | STRUCTURED | Unsure STRUCTURED | Decision |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ])
    by_model = {item["model_id"]: item for item in headline["per_model"]}
    for run in runs:
        unsure = unsure_table(run["predictions"])["STRUCTURED"]["unsure_rate"]
        scores = run["scores"]
        lines.append(
            "| {model} | {maj} | {none} | {raw} | {summary} | {structured} | {unsure} | {decision} |".format(
                model=run["model_id"],
                maj=_fmt(_acc(scores, "MAJORITY")),
                none=_fmt(_acc(scores, "NONE")),
                raw=_fmt(_acc(scores, "RAW")),
                summary=_fmt(_acc(scores, "SUMMARY")),
                structured=_fmt(_acc(scores, "STRUCTURED")),
                unsure=_fmt(unsure),
                decision=by_model[run["model_id"]]["decision"],
            )
        )
    lines.extend([
        "",
        "## 8. Limitations",
        "",
        "- The sample is the people in these directories, not a population estimate. 24 items are not 24 people, and here the items are also repeated inside each person.",
        "- Wave 4 two-option survey items are not the original memo tasks. Stage 2 was not run.",
        "- Unsure is both an abstention rate and a strict miss. Dropping unsure would shrink the denominator; this report does not.",
        "- The 0.83 / 0.56 reference is a preliminary 294-person pilot. The ceiling and floor above are recomputed from this sample.",
        "- Local endpoints record API USD as 0 or leave it null. That is not a measured dollar cost.",
        "- No self-filled C/H answers are in this report. `persona_summary` is not a profile.",
        "",
        "## 9. Next step",
        "",
        "Only the smallest step supported by the headline. continue means keep this freeze and look at the paired items. simplify means stop spending profile-build calls on STRUCTURED. stop means do not add a larger model. inconclusive means do not add tasks until the missing cells or the interval are resolved.",
        "",
        "## 10. Recompute",
        "",
        "```bash",
        "python3 -m vacant_network.personal twin2k-report \\",
        "  --run <model-a-run> --run <model-b-run> \\",
        "  --out result.md",
        "```",
        "",
        "This command reads the saved jsonl and scores.json. It does not call a model.",
        "",
    ])
    return "\n".join(lines)


def write_report(paths: list[Path], out: Path, *, model_ids: list[str] | None = None) -> dict[str, Any]:
    runs = []
    for index, path in enumerate(paths):
        model_id = None if not model_ids or index >= len(model_ids) else model_ids[index]
        runs.append(load_run(path, model_id=model_id))
    text = render_report(runs)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    headline = decide_all(runs)
    return {"decision": headline["decision"], "out": str(out), "models": [run["model_id"] for run in runs]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write a Twin-2K-500 result.md from one or more twin2k-run directories.")
    parser.add_argument("--run", action="append", required=True, dest="runs")
    parser.add_argument("--model", action="append", dest="models", help="optional model id, in the same order as --run")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        result = write_report([Path(path) for path in args.runs], Path(args.out), model_ids=args.models)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(str(exc))
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0
