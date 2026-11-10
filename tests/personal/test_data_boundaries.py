"""題庫邊界：校準與保留題分開，倉庫裡沒有本人答案。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vacant_network.personal.context import retrieve
from vacant_network.personal.dataset import (
    DataError,
    assert_banks_separated,
    join_answers,
    legal_subsets,
    load_answers,
    load_bank,
    refuse_label_path,
)
from vacant_network.personal.profiles import ContextLeakError, assert_calibration_sources, build_all
from vacant_network.personal.prompts import TEMPLATES
from vacant_network.personal.schemas import validate_formal_answer

ROOT = Path(__file__).resolve().parents[2]
BANK = ROOT / "ops" / "personal_pilot" / "task_bank"
PROMPTS = ROOT / "ops" / "personal_pilot" / "prompts"


def test_banks_match_the_appendix_counts():
    calibration = load_bank(BANK / "calibration.json", kind="calibration")
    holdout = load_bank(BANK / "holdout.json", kind="holdout")
    tasks = load_bank(BANK / "tasks.json", kind="tasks")
    assert assert_banks_separated(calibration, holdout, tasks) == []
    assert [case["case_id"] for case in calibration["cases"]] == [f"C{i:02d}" for i in range(1, 17)]
    assert [case["case_id"] for case in holdout["cases"]] == [f"H{i:02d}" for i in range(1, 25)]
    counts = {task["task_id"]: len(legal_subsets(task)) for task in tasks["tasks"]}
    assert counts == tasks["documented_legal_subset_counts"]
    assert all(task["task_instruction"].strip() for task in tasks["tasks"])
    assert all(task["required_option_ids"] and task["choice_groups"] for task in tasks["tasks"])
    blob = json.dumps({"calibration": calibration, "holdout": holdout}, ensure_ascii=False)
    assert '"choice":' not in blob


def test_prompt_files_match_the_frozen_templates():
    for name, text in TEMPLATES.items():
        assert (PROMPTS / f"{name}.txt").read_text(encoding="utf-8") == text


def test_blank_answers_are_rejected_and_labels_are_not_a_bank():
    with pytest.raises(DataError):
        refuse_label_path(Path("sealed/holdout_labels.jsonl"))
    problems = validate_formal_answer({
        "schema_version": "vacant.personal.answer.v1",
        "user_id": "pilot-owner",
        "case_id": "C01",
        "choice": None,
        "reason": "",
        "switch_condition": "",
        "seconds_spent": None,
        "presented_order": ["option_1", "option_2"],
        "answered_at": None,
    })
    assert problems


def test_join_keeps_the_stem_and_maps_display_order(tmp_path):
    calibration = load_bank(BANK / "calibration.json", kind="calibration")
    case = calibration["cases"][0]
    path = tmp_path / "answers.jsonl"
    path.write_text(json.dumps({
        "schema_version": "vacant.personal.answer.v1",
        "user_id": "fixture-not-a-person",
        "case_id": case["case_id"],
        "choice": "A",
        "reason": "管線用，不是本人回答。",
        "switch_condition": "",
        "seconds_spent": 3,
        "presented_order": ["option_2", "option_1"],
        "answered_at": "2026-11-10T00:00:00Z",
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    joined = join_answers({case["case_id"]: case}, load_answers(path))
    assert joined[0]["stem"] == case["stem"]
    assert joined[0]["choice_option_id"] == "option_2"
    assert "option_1" in joined[0]["options"][0]["text"] or joined[0]["options"][0]["id"] == "option_1"


def test_retrieval_refuses_a_labeled_query_and_holdout_pool():
    holdout = load_bank(BANK / "holdout.json", kind="holdout")
    calibration = load_bank(BANK / "calibration.json", kind="calibration")
    query = dict(holdout["cases"][0])
    pool = calibration["cases"]
    found = retrieve(query, pool)
    assert all(case["case_id"].startswith("C") for case in found["cases"])
    assert "choice" not in found["cases"][0]
    query["choice"] = "A"
    with pytest.raises(ContextLeakError):
        retrieve(query, pool)
    with pytest.raises(ContextLeakError):
        retrieve(holdout["cases"][1], holdout["cases"])


def test_profile_cannot_cite_a_holdout_or_unseen_case():
    calibration = load_bank(BANK / "calibration.json", kind="calibration")
    answer = {
        "schema_version": "vacant.personal.answer.v1",
        "user_id": "fixture-not-a-person",
        "case_id": "C01",
        "choice": "B",
        "reason": "",
        "switch_condition": "若明天要示範就改。",
        "seconds_spent": 1,
        "presented_order": ["option_1", "option_2"],
        "answered_at": "2026-11-10T00:00:00Z",
    }
    joined = join_answers({"C01": calibration["cases"][0]}, [answer])
    built = build_all(joined, updated_at="2026-11-10T00:00:00Z", user_id="fixture-not-a-person", profile_version="p001")
    assert built["STRUCTURED"]["rules"][0]["evidence_case_ids"] == ["C01"]
    assert "未寫" not in built["STRUCTURED"]["rules"][0]["preference"] or built["STRUCTURED"]["rules"][0]["preference"]
    leaked = json.loads(json.dumps(built["STRUCTURED"]))
    leaked["rules"][0]["evidence_case_ids"] = ["H01"]
    with pytest.raises(ContextLeakError):
        assert_calibration_sources(leaked, {"C01"})
