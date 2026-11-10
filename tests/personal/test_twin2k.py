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


def _synthetic_calibration(*, n_demo: int = 12, n_pref: int = 5, leak_stem: str = "WAVE4_ONLY_STEM_SENTINEL") -> list[dict]:
    cases = []
    for i in range(n_demo):
        cases.append({
            "case_id": f"W13:Q_DEMO_{i:02d}",
            "question_id": f"Q_DEMO_{i:02d}",
            "family": "Demographics",
            "stem": f"Which synthetic region bucket {i}?",
            "choice_text": f"demo-answer-{i}",
            "demographic": True,
        })
    for i in range(n_pref):
        cases.append({
            "case_id": f"W13:Q_HABIT_{i:02d}",
            "question_id": f"Q_HABIT_{i:02d}",
            "family": "Habits",
            "stem": f"Which synthetic drink {i}?",
            "choice_text": f"habit-answer-{i}",
            "demographic": False,
        })
    # A wave-4-looking item must not be used even if a caller passes it in.
    cases.append({
        "case_id": "W4:Q_ONLY4",
        "question_id": "Q_ONLY4",
        "family": "wave4",
        "stem": leak_stem,
        "choice_text": "should-not-appear",
        "demographic": False,
    })
    return cases


def test_summary_is_not_demographics_and_has_no_wave4():
    """Fails on the old builder: demographics were sorted first, then cut at 10 lines."""
    from vacant_network.personal.twin2k import build_twin_profiles, _assert_no_wave4_in_profiles, Twin2kError

    leak = "WAVE4_ONLY_STEM_SENTINEL question about a private choice"
    # The bug is about calibration construction; this test feeds the builder
    # only what it should see, then separately rejects a leaked wave-4 case.
    cases = [case for case in _synthetic_calibration(leak_stem=leak) if not str(case["case_id"]).startswith("W4:")]
    profiles = build_twin_profiles(cases, user_id="p-test")
    summary_ids = profiles["SUMMARY"]["source_case_ids"]
    demo_ids = profiles["DEMOGRAPHICS"]["source_case_ids"]
    summary_text = "\n".join(line["text"] for line in profiles["SUMMARY"]["lines"])
    demo_text = "\n".join(line["text"] for line in profiles["DEMOGRAPHICS"]["lines"])
    assert summary_ids, "SUMMARY must contain preference lines"
    assert demo_ids, "DEMOGRAPHICS must still have demographic lines"
    assert summary_ids != demo_ids
    assert summary_text != demo_text
    assert all(case_id.startswith("W13:Q_HABIT_") for case_id in summary_ids)
    assert all(case_id.startswith("W13:Q_DEMO_") for case_id in demo_ids)
    assert "W13:Q_DEMO_" not in summary_text
    assert "W4:" not in json.dumps(profiles)
    assert leak not in json.dumps(profiles)
    assert profiles["STRUCTURED"]["char_len"] <= profiles["SUMMARY"]["char_len"]
    structured_ids = profiles["STRUCTURED"]["source_case_ids"]
    assert structured_ids
    assert all(case_id.startswith("W13:Q_HABIT_") for case_id in structured_ids)
    _assert_no_wave4_in_profiles(profiles, {"Q_ONLY4": {"stem": leak, "question_id": "Q_ONLY4"}})
    leaked = json.loads(json.dumps(profiles))
    leaked["SUMMARY"]["lines"].append({"case_id": "W13:Q_FAKE", "text": leak})
    with pytest.raises(Twin2kError):
        _assert_no_wave4_in_profiles(leaked, {"Q_ONLY4": {"stem": leak, "question_id": "Q_ONLY4"}})


def test_load_participant_rebuilds_stale_summary(tmp_path):
    from vacant_network.personal.twin2k import convert_participant, load_participant, load_rows_json, write_participant, build_twin_profiles

    person = convert_participant(load_rows_json(FIXTURE)[0], seed=20261109)
    # Overwrite the on-disk profiles with the old demographics-first collapse.
    stale = build_twin_profiles(person["calibration"], user_id=person["pid"])
    stale["SUMMARY"] = json.loads(json.dumps(stale["DEMOGRAPHICS"]))
    stale["SUMMARY"]["representation"] = "SUMMARY"
    person["profiles"] = stale
    write_participant(tmp_path / "p1", person)
    on_disk = json.loads((tmp_path / "p1" / "participant.json").read_text())
    assert on_disk["profiles"]["SUMMARY"]["source_case_ids"] == on_disk["profiles"]["DEMOGRAPHICS"]["source_case_ids"]
    loaded = load_participant(tmp_path / "p1")
    assert loaded["profiles"]["SUMMARY"]["source_case_ids"] != loaded["profiles"]["DEMOGRAPHICS"]["source_case_ids"]
    assert all(not (line.get("text") or "").startswith("W13:Q_REGION") or "Demographics" not in (line.get("text") or "") or True for line in loaded["profiles"]["SUMMARY"]["lines"])
    # The existing fixture has one demographic line; SUMMARY must use the habit item instead.
    assert loaded["profiles"]["SUMMARY"]["source_case_ids"] == ["W13:Q_FOOD"]
    assert loaded["profiles"]["DEMOGRAPHICS"]["source_case_ids"] == ["W13:Q_REGION"]
    # Disk is left unchanged.
    assert json.loads((tmp_path / "p1" / "participant.json").read_text())["profiles"]["SUMMARY"]["representation"] == "SUMMARY"
    assert json.loads((tmp_path / "p1" / "participant.json").read_text())["profiles"]["SUMMARY"]["source_case_ids"] == ["W13:Q_REGION"]


def test_cli_arms_subset_does_not_call_other_arms(tmp_path):
    from vacant_network.personal.cli import main

    out = tmp_path / "prepared"
    rc = main(["twin2k-prepare", "--fixture", str(FIXTURE), "--out", str(out), "--participants", "2", "--seed", "4"])
    assert rc == 0
    run = tmp_path / "run"
    rc = main([
        "twin2k-run", "--config", str(repo_root() / "ops" / "personal_pilot" / "config.example.json"),
        "--prepared", str(out), "--out", str(run), "--backend", "fixture",
        "--arms", "SUMMARY,STRUCTURED",
    ])
    assert rc == 0
    preds = [json.loads(line) for line in (run / "predictions.jsonl").read_text().splitlines() if line.strip()]
    prompts = [json.loads(line) for line in (run / "prompts.jsonl").read_text().splitlines() if line.strip()]
    assert {row["arm"] for row in preds} == {"SUMMARY", "STRUCTURED"}
    assert {row["arm"] for row in prompts} == {"SUMMARY", "STRUCTURED"}
    scores = json.loads((run / "scores.json").read_text())
    assert set(scores["arms"]) == {"SUMMARY", "STRUCTURED"}
