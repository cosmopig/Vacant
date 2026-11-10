"""Twin-2K-500 轉換與指標。夾具是合成的，不連線、不放真資料。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vacant_network.personal.budget import BudgetLedger
from vacant_network.personal.backend import FixtureBackend
from vacant_network.personal.twin2k import (
    Twin2kError,
    assert_outside_repo,
    convert_participant,
    load_rows_json,
    prepare_rows,
    repo_root,
    sample_rows,
)
from vacant_network.personal.twin_runner import execute_twin, fixture_handler

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "twin2k_min.json"


def test_conversion_drops_wave4_and_ignores_persona_summary():
    rows = load_rows_json(FIXTURE)
    person = convert_participant(rows[0], seed=20261109)
    private = json.dumps({"calibration": person["calibration"], "profiles": person["profiles"]}, ensure_ascii=False)
    assert "PERSONA_SUMMARY_USES_WAVE4_SECRET" not in private
    assert "WAVE4_ONLY_STEM_SENTINEL" not in private
    assert "WAVE4_REPEAT_STEM_SENTINEL" not in private
    assert "WAVE4_ONLY_STEM_SENTINEL" in json.dumps(person["holdout_cases"])
    assert person["persona_summary_used"] is False
    assert all(not case["question_id"].startswith("Q_REPEAT") for case in person["calibration"])
    assert {case["case_id"] for case in person["holdout_cases"]} == {"W4:Q_REPEAT", "W4:Q_ONLY4"}
    assert person["test_retest"]["compared"] == 1
    assert person["test_retest"]["agreed"] == 0
    assert person["profiles"]["STRUCTURED"]["char_len"] <= person["profiles"]["SUMMARY"]["char_len"]
    assert person["profiles"]["DEMOGRAPHICS"]["source_case_ids"] == ["W13:Q_REGION"]
    for label in person["labels"]:
        shown = label["presented_order"][0 if label["choice"] == "A" else 1]
        assert shown == label["choice_option_id"]
        assert "label_private_marker" in label


def test_sample_is_deterministic_and_repo_writes_are_refused(tmp_path):
    rows = load_rows_json(FIXTURE)
    assert [row["pid"] for row in sample_rows(rows, 2, 1)] == [row["pid"] for row in sample_rows(rows, 2, 1)]
    assert len(sample_rows(rows, 2, 1)) == 2
    with pytest.raises(Twin2kError):
        assert_outside_repo(repo_root() / "ops" / "personal_pilot" / "reporting")
    manifest = prepare_rows(rows, tmp_path / "out", n=2, seed=1)
    assert manifest["persona_summary_used"] is False
    assert len(manifest["pids"]) == 2
    assert (tmp_path / "out" / "manifest.json").is_file()


def test_fixture_run_scores_without_leaking_labels_into_prompts(tmp_path):
    rows = load_rows_json(FIXTURE)
    people = [convert_participant(row, seed=3) for row in rows]
    backend = FixtureBackend(
        handler=fixture_handler,
        ledger=BudgetLedger({"max_requests": 1000}, pricing="local"),
    )
    summary = execute_twin(people, backend, tmp_path, max_output_tokens=64)
    prompts = (tmp_path / "prompts.jsonl").read_text(encoding="utf-8")
    assert "label_private_marker" not in prompts
    assert "sealed-label-" not in prompts
    assert "PERSONA_SUMMARY_USES_WAVE4_SECRET" not in prompts
    assert "WAVE4_ONLY_STEM_SENTINEL" not in json.dumps(people[0]["profiles"])
    majority = summary["scores"]["arms"]["MAJORITY"]
    assert majority["differs_from_majority"]["n"] > 0
    assert majority["differs_from_majority"]["accuracy"] == 0
    pair = next(item for item in summary["scores"]["pairs"] if item["left"] == "RAW" and item["right"] == "SUMMARY")
    assert pair["mcnemar_p"] == 1.0
    assert pair["bootstrap95"][0] == pair["bootstrap95"][1] == 0
    orders = majority["option_order"]
    assert orders["identity"]["n"] + orders["swapped"]["n"] == 3 * 2


def test_budget_stops_later_twin_calls(tmp_path):
    rows = load_rows_json(FIXTURE)
    people = [convert_participant(row, seed=3) for row in rows]
    backend = FixtureBackend(
        handler=fixture_handler,
        ledger=BudgetLedger({"max_requests": 1}, pricing="local"),
    )
    summary = execute_twin(people, backend, tmp_path, max_output_tokens=32)
    assert summary["stopped"] is True
    assert backend.invocations == [{"purpose": "twin|p1|DEMOGRAPHICS|W4:Q_REPEAT", "max_output_tokens": 32}] or len(backend.invocations) == 1
    stopped = [row for row in json.loads("[" + ",".join((tmp_path / "predictions.jsonl").read_text().splitlines()) + "]") if row["status"] == "budget_stopped"]
    assert stopped
    assert all(row["sent"] is False for row in stopped)


def test_cli_prepare_and_run_stay_outside_the_repo(tmp_path):
    from vacant_network.personal.cli import main
    out = tmp_path / "prepared"
    rc = main(["twin2k-prepare", "--fixture", str(FIXTURE), "--out", str(out), "--participants", "2", "--seed", "4"])
    assert rc == 0
    assert (out / "manifest.json").is_file()
    refused = main(["twin2k-prepare", "--fixture", str(FIXTURE), "--out", str(repo_root() / "ops" / "personal_pilot" / "reporting" / "nope"), "--participants", "1", "--seed", "1"])
    assert refused == 2
    run = tmp_path / "run"
    rc = main([
        "twin2k-run", "--config", str(repo_root() / "ops" / "personal_pilot" / "config.example.json"),
        "--prepared", str(out), "--out", str(run), "--backend", "fixture",
    ])
    assert rc == 0
    assert (run / "scores.json").is_file()
    assert (run / "calls.jsonl").is_file()
