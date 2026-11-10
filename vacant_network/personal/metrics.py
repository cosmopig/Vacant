"""分母固定的指標。

這支在架構裡承重什麼：失敗、未評、UNKNOWN 都留在預定格數裡。
明確選擇準確率只除以本人實際選了 A/B 的題數。tie／neither／unsure
不折成半分。沒有成功交付時，每成功成本是算不出來，不是 0。

N=1 的使用者不是人群效益。F3 不拿來補 F1/F2。
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any

from .schemas import ARMS, ARM_REPRESENTATION, CHOICES

CLASSES = ("A", "B", "tie", "neither", "unsure")
ADOPTION_RANK = {
    "adopt_as_is": 4,
    "minor_revision": 3,
    "major_revision": 2,
    "reject": 1,
}


def wilson_interval(successes: int, total: int, *, z: float = 1.96) -> tuple[float, float] | None:
    if total <= 0:
        return None
    p = successes / total
    z2 = z * z
    denom = 1 + z2 / total
    centre = (p + z2 / (2 * total)) / denom
    margin = z * math.sqrt((p * (1 - p) + z2 / (4 * total)) / total) / denom
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def _index(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    out = {}
    for row in rows:
        out[row[key]] = row
    return out


def score_predictions(predictions: list[dict[str, Any]], labels: list[dict[str, Any]], cases: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """predictions 是模型輸出；labels 只在這裡讀。未出現的標籤是 missing，不是 unsure。"""
    label_by = {row["case_id"]: row for row in labels}
    by_rep: dict[str, list[dict[str, Any]]] = {}
    missing_labels = []
    for case_id, case in cases.items():
        if case_id not in label_by:
            missing_labels.append(case_id)
    graded = []
    for pred in predictions:
        case = cases.get(pred.get("case_id"))
        if case is None:
            continue
        label = label_by.get(pred["case_id"])
        human = None if label is None else label.get("choice")
        if human not in CLASSES:
            human = None
        model = pred.get("prediction") if pred.get("status", "completed") == "completed" else None
        if model not in CHOICES:
            model = None
        graded.append({
            "case_id": pred["case_id"],
            "family": case["family"],
            "representation": pred["representation"],
            "human": human,
            "model": model,
            "legal": model in CHOICES,
        })
        by_rep.setdefault(pred["representation"], []).append(graded[-1])

    def pack(rows: list[dict[str, Any]], *, family: str | None = None) -> dict[str, Any]:
        chosen = [row for row in rows if family is None or row["family"] == family]
        definite = [row for row in chosen if row["human"] in ("A", "B")]
        hits = [row for row in definite if row["model"] == row["human"]]
        non_ab = [row for row in chosen if row["human"] in ("tie", "neither", "unsure")]
        matrix = Counter((row["human"], row["model"] or "missing") for row in chosen if row["human"] is not None)
        exact = [row for row in chosen if row["human"] is not None and row["model"] == row["human"]]
        return {
            "cells": len(chosen),
            "legal_cells": sum(1 for row in chosen if row["legal"]),
            "prediction_coverage": (sum(1 for row in chosen if row["legal"]) / len(chosen)) if chosen else None,
            "human_definite_n": len(definite),
            "definite_hits": len(hits),
            "definite_accuracy": (len(hits) / len(definite)) if definite else None,
            "wilson95": wilson_interval(len(hits), len(definite)) if definite else None,
            "non_ab": {
                "n": len(non_ab),
                "by_human": dict(Counter(row["human"] for row in non_ab)),
                "model_match": dict(Counter(row["model"] for row in non_ab if row["model"] == row["human"])),
            },
            "exact_match_filled": len(exact),
            "filled_n": sum(1 for row in chosen if row["human"] is not None),
            "confusion": {f"{human}->{model}": count for (human, model), count in sorted(matrix.items())},
            "hit_ids": [row["case_id"] for row in hits],
        }

    representations = {}
    for name in ("RAW", "SUMMARY", "STRUCTURED"):
        rows = [row for row in graded if row["representation"] == name]
        representations[name] = {
            "all": pack(rows),
            "F1F2": pack([row for row in rows if row["family"] in ("F1", "F2")]),
            "F3": pack([row for row in rows if row["family"] == "F3"]),
        }
    main_hits = {name: set(representations[name]["F1F2"]["hit_ids"]) for name in representations}
    baseline_name = max(("RAW", "SUMMARY"), key=lambda name: (len(main_hits[name]), name))
    net = len(main_hits["STRUCTURED"] - main_hits[baseline_name]) - len(main_hits[baseline_name] - main_hits["STRUCTURED"])
    definite_n = representations["STRUCTURED"]["F1F2"]["human_definite_n"]
    return {
        "missing_labels": sorted(missing_labels),
        "representations": representations,
        "baseline_for_net_gain": baseline_name,
        "net_gain_structured_vs_baseline_f1f2": net,
        "human_definite_n_f1f2": definite_n,
        "note": "one user; 24 items are not 24 people. F3 is not pooled into the main screen.",
    }


def stage1_screen(scored: dict[str, Any], *, complete_main_cells: bool, usage_unknown: int) -> dict[str, Any]:
    """§7.3 的探索門檻。資料不齊時不發 worth_stage2。"""
    if scored.get("missing_labels") or not complete_main_cells or usage_unknown:
        return {"decision": "inconclusive", "reason": "labels, main cells, or usage are incomplete; an incomplete baseline cannot trigger a go"}
    structured = scored["representations"]["STRUCTURED"]["F1F2"]
    accuracy = structured["definite_accuracy"]
    if structured["human_definite_n"] < 12 or accuracy is None:
        return {"decision": "inconclusive", "reason": "fewer than 12 definite A/B labels"}
    if accuracy < 0.70 or scored["net_gain_structured_vs_baseline_f1f2"] < 3:
        if accuracy is not None and scored["net_gain_structured_vs_baseline_f1f2"] < 0:
            return {"decision": "simplify", "reason": "structured representation is behind the stronger baseline on definite choices"}
        return {"decision": "inconclusive", "reason": "accuracy or net gain is below the exploratory screen"}
    return {
        "decision": "continue",
        "reason": "exploratory screen only: F1/F2 structured accuracy and net gain cleared the pre-set bar. This is not a population result.",
    }


def objective_pass(row: dict[str, Any]) -> bool:
    if row.get("contract_status") != "accept":
        return False
    if row.get("report_integrity") not in (None, "ok"):
        return False
    for result in row.get("check_results") or []:
        if result.get("status") != "PASS":
            return False
    return row.get("status") == "completed"


def regressions(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    by = {}
    for row in rows:
        by.setdefault((row["task_id"], row["arm"]), {})[row["pass_index"]] = row
    found = []
    for (task_id, arm), passes in sorted(by.items()):
        first, second = passes.get(1), passes.get(2)
        if first and second and objective_pass(first) and not objective_pass(second):
            found.append({"task_id": task_id, "arm": arm})
    return found


def stage2_metrics(rows: list[dict[str, Any]], reviews: list[dict[str, Any]] | None, calls: list[dict[str, Any]]) -> dict[str, Any]:
    reviews = reviews or []
    review_by = {}
    for review in reviews:
        review_by[review["bundle_item_id"]] = review
    planned_final = [row for row in rows if row["pass_index"] == 2]
    planned_draft_groups = {}
    for row in rows:
        if row["pass_index"] == 1 and row.get("shared_first_draft_group"):
            planned_draft_groups.setdefault(row["shared_first_draft_group"], row)
    per_arm = {}
    for arm in ARMS:
        finals = [row for row in planned_final if row["arm"] == arm]
        adopted = []
        missing = []
        joint = []
        for row in finals:
            review = review_by.get(row.get("blind_id") or "")
            if review is None or review.get("verdict") is None:
                missing.append(row["task_id"])
                continue
            if review["verdict"] == "adopt_as_is":
                adopted.append(row["task_id"])
                if objective_pass(row):
                    joint.append(row["task_id"])
        per_arm[arm] = {
            "final_denominator": 6,
            "final_rows": len(finals),
            "adopt_as_is": None if missing else len(adopted) / 6,
            "joint_adopt": None if missing else len(joint) / 6,
            "missing_reviews": missing,
            "objective_pass": sum(1 for row in finals if objective_pass(row)),
        }
    per_rep = {}
    for rep in ("SUMMARY", "STRUCTURED"):
        groups = [row for key, row in planned_draft_groups.items() if key.endswith(":" + rep)]
        adopted = []
        missing = []
        joint = []
        for row in groups:
            review = review_by.get(row.get("blind_id") or "")
            if review is None:
                missing.append(row["task_id"])
                continue
            if review.get("verdict") == "adopt_as_is":
                adopted.append(row["task_id"])
                if objective_pass(row):
                    joint.append(row["task_id"])
        per_rep[rep] = {
            "unique_first_drafts_denominator": 6,
            "unique_first_drafts": len(groups),
            "adopt_as_is": None if missing else len(adopted) / 6,
            "joint_adopt": None if missing else len(joint) / 6,
            "missing_reviews": missing,
        }
    unique_calls = {}
    for call in calls:
        if call.get("sent") and call.get("call_id"):
            unique_calls[call["call_id"]] = call
    known_cost = 0.0
    unknown_usage = 0
    gross_out = 0
    wall = 0
    priced = False
    for call in unique_calls.values():
        if call.get("usage") is None:
            unknown_usage += 1
        mapped_out = ((call.get("usage") or {}).get("completion_tokens")) if isinstance(call.get("usage"), dict) else None
        if isinstance(mapped_out, int):
            gross_out += mapped_out
        if isinstance(call.get("wall_ms"), int):
            wall += call["wall_ms"]
        if isinstance(call.get("cost_usd"), (int, float)) and not isinstance(call.get("cost_usd"), bool):
            known_cost += float(call["cost_usd"])
            priced = True
    successes = []
    for row in planned_final:
        review = review_by.get(row.get("blind_id") or "")
        if review and review.get("verdict") == "adopt_as_is" and objective_pass(row):
            successes.append(row)
    if not successes:
        per_success = None
        per_success_note = "no adopted delivery that also passed the objective check; per-success cost is not computable and is not zero"
    elif not priced:
        per_success = None
        per_success_note = "usage or price is incomplete"
    else:
        per_success = known_cost / len(successes)
        per_success_note = "known call cost divided by joint adoptions; shared calls are counted once"
    equivalent = {}
    for arm in ARMS:
        ids = []
        for row in rows:
            if row["arm"] == arm and row.get("call_id"):
                ids.append(row["call_id"])
        cost = 0.0
        for call_id in dict.fromkeys(ids):
            call = unique_calls.get(call_id) or {}
            if isinstance(call.get("cost_usd"), (int, float)) and not isinstance(call.get("cost_usd"), bool):
                cost += float(call["cost_usd"])
        equivalent[arm] = cost
    return {
        "planned_arm_pass_rows": 48,
        "observed_rows": len(rows),
        "planned_independent_requests": 36,
        "independent_requests": len(unique_calls),
        "per_arm_final": per_arm,
        "per_representation_first_draft": per_rep,
        "regressions": regressions(rows),
        "status_counts": dict(Counter(row["status"] for row in rows)),
        "actual_known_cost_usd": known_cost if priced else None,
        "unknown_usage_calls": unknown_usage,
        "gross_completion_tokens": gross_out,
        "wall_ms": wall,
        "cost_per_joint_adoption": per_success,
        "cost_per_joint_adoption_note": per_success_note,
        "equivalent_arm_cost_usd": equivalent,
        "equivalent_cost_note": "each arm includes a full copy of the shared first draft; do not add the four figures into the bill",
        "failed_rows_kept": [row["task_id"] + ":" + row["arm"] + ":p" + str(row["pass_index"]) for row in rows if row["status"] != "completed"],
    }


def pairwise(rows: list[dict[str, Any]], reviews: list[dict[str, Any]]) -> list[dict[str, Any]]:
    review_by = {review["bundle_item_id"]: review for review in reviews}
    out = []
    by_task = {}
    for row in rows:
        if row["pass_index"] != 2:
            continue
        by_task.setdefault(row["task_id"], {})[row["arm"]] = row
    for task_id, arms in sorted(by_task.items()):
        for left, right in (("B", "A"), ("C", "A"), ("D", "B")):
            a, b = arms.get(left), arms.get(right)
            if not a or not b:
                continue
            va = (review_by.get(a.get("blind_id") or "") or {}).get("verdict")
            vb = (review_by.get(b.get("blind_id") or "") or {}).get("verdict")
            if va not in ADOPTION_RANK or vb not in ADOPTION_RANK:
                winner = "unranked"
            elif ADOPTION_RANK[va] == ADOPTION_RANK[vb]:
                winner = "tie"
            elif ADOPTION_RANK[va] > ADOPTION_RANK[vb]:
                winner = left
            else:
                winner = right
            out.append({"task_id": task_id, "left": left, "right": right, "winner": winner})
    return out


# --- Twin-2K-500 比較 -------------------------------------------------------
# 分母是每個人的二選項保留題。沒答、解析失敗、預算停掉都算未命中，不從分母拿掉。

TWIN_PRELIMINARY = {
    "n_people": 294,
    "test_retest_ceiling": 0.83,
    "majority_floor": 0.56,
    "status": "preliminary reference from a 294-person pilot; recompute with score_twin on the sample actually drawn",
}


def _twin_hit(prediction: str | None, human: str | None) -> bool:
    return prediction in ("A", "B") and human in ("A", "B") and prediction == human


def leave_one_out_majority(labels: list[dict[str, Any]]) -> dict[tuple[str, str], str | None]:
    """每個 (pid, case) 的多數選項，不算本人。平手回 None，不當成猜對。"""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in labels:
        grouped.setdefault(row["case_id"], []).append(row)
    found: dict[tuple[str, str], str | None] = {}
    for case_id, rows in grouped.items():
        for row in rows:
            counts: Counter[str] = Counter(
                other["choice_option_id"] for other in rows
                if other["pid"] != row["pid"] and other.get("choice_option_id")
            )
            if not counts:
                found[(str(row["pid"]), case_id)] = None
                continue
            ranking = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
            if len(ranking) > 1 and ranking[0][1] == ranking[1][1]:
                found[(str(row["pid"]), case_id)] = None
            else:
                found[(str(row["pid"]), case_id)] = ranking[0][0]
    return found


def _letter(option_id: str | None, presented_order: list[str]) -> str | None:
    if option_id == presented_order[0]:
        return "A"
    if option_id == presented_order[1]:
        return "B"
    return None


def latest_prediction_rows(predictions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """同一 (pid, arm, case_id) 以最後一筆為準，resume 補寫不會把舊失敗算進分母兩次。"""
    latest: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in predictions:
        latest[(str(row.get("pid")), str(row.get("arm")), str(row.get("case_id")))] = row
    return list(latest.values())


def score_twin(predictions: list[dict[str, Any]], labels: list[dict[str, Any]], retests: dict[str, dict[str, Any]], *, n_boot: int = 2000, seed: int = 0) -> dict[str, Any]:
    """每人準確率、Wilson、重測正規化、偏離多數的題、配對 McNemar 與 bootstrap、選項順序分拆。"""
    from vacant_network.research import boot_ci, mcnemar_exact

    predictions = latest_prediction_rows(predictions)
    label_by = {(str(row["pid"]), row["case_id"]): row for row in labels}
    majority = leave_one_out_majority(labels)
    arms = sorted({row["arm"] for row in predictions})
    graded = []
    for row in predictions:
        key = (str(row["pid"]), row["case_id"])
        label = label_by.get(key)
        human = None if label is None else label.get("choice")
        order = (label or row).get("presented_order") or ["option_1", "option_2"]
        pred = row.get("prediction") if row.get("status") == "completed" else None
        if row["arm"] == "MAJORITY" and row.get("status") == "completed":
            pred = _letter(majority.get(key), order)
        hit = _twin_hit(pred, human)
        maj = majority.get(key)
        human_option = None if label is None else label.get("choice_option_id")
        differs = maj is not None and human_option is not None and human_option != maj
        graded.append({
            "pid": str(row["pid"]),
            "case_id": row["case_id"],
            "arm": row["arm"],
            "human": human,
            "prediction": pred,
            "hit": hit,
            "answered": pred in ("A", "B", "tie", "neither", "unsure"),
            "presented_order": order,
            "swapped": order == ["option_2", "option_1"],
            "differs_from_majority": differs,
            "in_denominator": human in ("A", "B"),
        })
    per_person = []
    pids = sorted({row["pid"] for row in graded})
    by_arm: dict[str, dict[str, Any]] = {}
    for arm in arms:
        arm_rows = [row for row in graded if row["arm"] == arm and row["in_denominator"]]
        people = []
        for pid in pids:
            mine = [row for row in arm_rows if row["pid"] == pid]
            hits = sum(1 for row in mine if row["hit"])
            total = len(mine)
            rate = retests.get(pid, {}).get("rate")
            accuracy = (hits / total) if total else None
            people.append({
                "pid": pid,
                "hits": hits,
                "n": total,
                "accuracy": accuracy,
                "wilson95": wilson_interval(hits, total) if total else None,
                "test_retest_rate": rate,
                "accuracy_over_retest": (accuracy / rate) if accuracy is not None and rate else None,
            })
        differs = [row for row in arm_rows if row["differs_from_majority"]]
        same_order = [row for row in arm_rows if not row["swapped"]]
        swapped = [row for row in arm_rows if row["swapped"]]

        def _acc(rows: list[dict[str, Any]]) -> float | None:
            if not rows:
                return None
            return sum(1 for row in rows if row["hit"]) / len(rows)

        unsure_rows = [row for row in arm_rows if row["prediction"] == "unsure"]
        strict = _acc(arm_rows)
        by_arm[arm] = {
            "per_person": people,
            "micro_accuracy": strict,
            "strict_accuracy": strict,
            "micro_wilson95": wilson_interval(sum(1 for row in arm_rows if row["hit"]), len(arm_rows)) if arm_rows else None,
            "macro_accuracy": _mean_defined([person["accuracy"] for person in people]),
            "macro_accuracy_over_retest": _mean_defined([person["accuracy_over_retest"] for person in people]),
            "unsure_n": len(unsure_rows),
            "unsure_rate": (len(unsure_rows) / len(arm_rows)) if arm_rows else None,
            "unsure_note": "unsure is reported as abstention and counts as incorrect in strict_accuracy; it is not dropped from the denominator",
            "differs_from_majority": {"n": len(differs), "accuracy": _acc(differs)},
            "option_order": {
                "identity": {"n": len(same_order), "accuracy": _acc(same_order)},
                "swapped": {"n": len(swapped), "accuracy": _acc(swapped)},
            },
            "denominator_note": "unanswered, unsure, parse_failed, and budget_stopped count as misses in strict_accuracy",
        }
        per_person.extend(people)
    pairs = []
    arm_list = [arm for arm in ("MAJORITY", "DEMOGRAPHICS", "NONE", "RAW", "SUMMARY", "STRUCTURED") if arm in by_arm]
    for i, left in enumerate(arm_list):
        for right in arm_list[i + 1:]:
            left_rows = {(row["pid"], row["case_id"]): row for row in graded if row["arm"] == left and row["in_denominator"]}
            right_rows = {(row["pid"], row["case_id"]): row for row in graded if row["arm"] == right and row["in_denominator"]}
            keys = sorted(set(left_rows) & set(right_rows))
            paired = []
            b = c = 0
            for key in keys:
                hit_l = bool(left_rows[key]["hit"])
                hit_r = bool(right_rows[key]["hit"])
                paired.append({"hit_left": hit_l, "hit_right": hit_r})
                if (not hit_l) and hit_r:
                    b += 1
                elif hit_l and (not hit_r):
                    c += 1

            def _diff(sample: list[dict[str, Any]], _b=b) -> float:
                if not sample:
                    return 0.0
                return (
                    sum(1.0 if row["hit_right"] else 0.0 for row in sample)
                    - sum(1.0 if row["hit_left"] else 0.0 for row in sample)
                ) / len(sample)

            low, high = boot_ci(paired, _diff, n_boot=n_boot, seed=seed) if paired else (None, None)
            pairs.append({
                "left": left,
                "right": right,
                "n": len(paired),
                "mcnemar_b_right_only": b,
                "mcnemar_c_left_only": c,
                "mcnemar_p": mcnemar_exact(b, c),
                "accuracy_diff_right_minus_left": _diff(paired) if paired else None,
                "bootstrap95": None if low is None else [low, high],
            })
    return {
        "arms": by_arm,
        "pairs": pairs,
        "preliminary_reference": TWIN_PRELIMINARY,
        "retests": retests,
        "note": "N people are not independent items. Majority is leave-one-out. The 0.83/0.56 figures are a preliminary reference, not this sample.",
    }


def _mean_defined(values: list[float | None]) -> float | None:
    usable = [value for value in values if isinstance(value, (int, float)) and not isinstance(value, bool)]
    if not usable:
        return None
    return sum(usable) / len(usable)
