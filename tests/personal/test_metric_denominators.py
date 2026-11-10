"""失敗與未評留在分母裡。沒有成功時不把每成功成本填成 0。"""

from __future__ import annotations

from vacant_network.personal.metrics import (
    objective_pass,
    regressions,
    score_predictions,
    stage1_screen,
    stage2_metrics,
    wilson_interval,
)
from vacant_network.personal.schemas import ARM_REPRESENTATION


def _grid():
    rows = []
    for index, task_id in enumerate(["T01", "T02", "T03", "T04", "T05", "T06"]):
        for arm in ("A", "B", "C", "D"):
            for pass_index in (1, 2):
                status = "parse_failed" if task_id == "T01" and arm == "D" and pass_index == 2 else "completed"
                rows.append({
                    "task_id": task_id,
                    "arm": arm,
                    "pass_index": pass_index,
                    "status": status,
                    "call_id": f"c-{task_id}-{arm}-{pass_index}",
                    "shared_first_draft_group": f"{task_id}:{ARM_REPRESENTATION[arm]}" if pass_index == 1 else None,
                    "contract_status": "accept" if status == "completed" else None,
                    "check_results": [{"status": "PASS"}] if status == "completed" else [],
                    "report_integrity": "ok",
                    "usage": None,
                    "cost_usd": None,
                    "blind_id": None,
                    "representation": ARM_REPRESENTATION[arm],
                })
    return rows


def test_failed_and_unreviewed_cells_stay_in_the_denominator():
    metrics = stage2_metrics(_grid(), [], [])
    assert metrics["observed_rows"] == 48
    assert metrics["planned_arm_pass_rows"] == 48
    assert metrics["per_arm_final"]["D"]["final_denominator"] == 6
    assert metrics["per_arm_final"]["A"]["adopt_as_is"] is None
    assert metrics["per_representation_first_draft"]["SUMMARY"]["unique_first_drafts_denominator"] == 6
    assert "T01:D:p2" in metrics["failed_rows_kept"]
    assert metrics["cost_per_joint_adoption"] is None
    assert "not zero" in metrics["cost_per_joint_adoption_note"]


def test_regression_is_counted_when_the_second_pass_breaks():
    rows = [
        {"task_id": "T02", "arm": "B", "pass_index": 1, "status": "completed", "contract_status": "accept",
         "check_results": [{"status": "PASS"}], "report_integrity": "ok"},
        {"task_id": "T02", "arm": "B", "pass_index": 2, "status": "completed", "contract_status": "reject",
         "check_results": [{"status": "FAIL"}], "report_integrity": "ok"},
    ]
    assert objective_pass(rows[0]) is True
    assert objective_pass(rows[1]) is False
    assert regressions(rows) == [{"task_id": "T02", "arm": "B"}]


def test_unknown_prediction_is_not_a_hit_and_missing_labels_do_not_go():
    cases = {f"H{i:02d}": {"case_id": f"H{i:02d}", "family": "F1" if i <= 8 else "F2"} for i in range(1, 17)}
    labels = [{"case_id": case_id, "choice": "A"} for case_id in list(cases)[:4]]
    labels.append({"case_id": "H05", "choice": "tie"})
    predictions = []
    for case_id in cases:
        for rep in ("RAW", "SUMMARY", "STRUCTURED"):
            predictions.append({
                "case_id": case_id,
                "representation": rep,
                "status": "completed",
                "prediction": "A" if rep == "STRUCTURED" and case_id == "H01" else "unsure",
            })
    scored = score_predictions(predictions, labels, cases)
    assert scored["missing_labels"]
    screen = stage1_screen(scored, complete_main_cells=False, usage_unknown=0)
    assert screen["decision"] == "inconclusive"
    structured = scored["representations"]["STRUCTURED"]["F1F2"]
    assert structured["definite_hits"] == 1
    assert structured["human_definite_n"] == 4
    interval = wilson_interval(1, 4)
    assert interval is not None
    assert 0 <= interval[0] <= interval[1] <= 1
