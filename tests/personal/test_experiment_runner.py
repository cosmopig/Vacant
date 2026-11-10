"""格子、共用首稿與盲包。管線答案不是本人偏好。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vacant_network.personal.backend import FixtureBackend
from vacant_network.personal.budget import BudgetLedger
from vacant_network.personal.dataset import load_bank
from vacant_network.personal.fixtures import _plumbing_profiles
from vacant_network.personal.runner import (
    ResumeError,
    execute_screen,
    export_blind,
    prediction_plan,
    structural_handler,
)

ROOT = Path(__file__).resolve().parents[2]
BANK = ROOT / "ops" / "personal_pilot" / "task_bank"


def _config():
    return {
        "bank_dir": str(BANK),
        "checker": str(ROOT / "ops" / "personal_pilot" / "trusted_checks" / "check_plan.py"),
        "seed": 7,
        "run_id": "unit",
        "budget": {"stage2_output_tokens": 1800},
        "model": {"model_id": "not-called"},
    }


def test_screen_grid_shares_drafts_and_keeps_48_rows(tmp_path):
    banks = {
        "calibration": load_bank(BANK / "calibration.json", kind="calibration"),
        "tasks": load_bank(BANK / "tasks.json", kind="tasks"),
    }
    profiles = _plumbing_profiles(banks)
    tasks = {task["task_id"]: task for task in banks["tasks"]["tasks"]}
    backend = FixtureBackend(handler=structural_handler(tasks), ledger=BudgetLedger(pricing="unset"))
    summary = execute_screen(_config(), backend, tmp_path, profiles, fixture_plumbing=True, resume=False)
    rows = [json.loads(line) for line in (tmp_path / "arm_pass_rows.jsonl").read_text(encoding="utf-8").splitlines()]
    calls = [json.loads(line) for line in (tmp_path / "calls.jsonl").read_text(encoding="utf-8").splitlines()]
    assert summary["rows"] == 48
    assert len(calls) == 36
    assert len({call["call_id"] for call in calls}) == 36
    groups = {}
    for row in rows:
        assert row["human_acceptance"] is None
        assert row["model_id"] is None
        if row["pass_index"] == 1:
            groups.setdefault(row["shared_first_draft_group"], set()).add(row["call_id"])
    assert len([key for key in groups if key.endswith(":SUMMARY")]) == 6
    assert len([key for key in groups if key.endswith(":STRUCTURED")]) == 6
    assert all(len(ids) == 1 for ids in groups.values())
    blind = export_blind(tmp_path, tmp_path / "blind", seed=7)
    text = (tmp_path / "blind" / "bundle.md").read_text(encoding="utf-8")
    assert "arm A" not in text
    assert "contract_status" not in text
    assert blind["row_identities"] == 48
    assert blind["display_items"] < 48


def test_resume_does_not_resend_an_unknown_call(tmp_path):
    banks = {
        "calibration": load_bank(BANK / "calibration.json", kind="calibration"),
        "tasks": load_bank(BANK / "tasks.json", kind="tasks"),
    }
    profiles = _plumbing_profiles(banks)
    (tmp_path / "arm_pass_rows.jsonl").write_text(json.dumps({
        "task_id": "T01", "arm": "A", "pass_index": 1, "status": "usage_unknown", "call_id": "sent-already",
    }) + "\n", encoding="utf-8")
    tasks = {task["task_id"]: task for task in banks["tasks"]["tasks"]}
    backend = FixtureBackend(handler=structural_handler(tasks), ledger=BudgetLedger(pricing="unset"))
    with pytest.raises(ResumeError):
        execute_screen(_config(), backend, tmp_path, profiles, fixture_plumbing=True, resume=True)
    assert backend.invocations == []


def test_prediction_plan_is_72_cells_and_not_filled():
    holdout = load_bank(BANK / "holdout.json", kind="holdout")
    plan = prediction_plan(holdout["cases"])
    assert len(plan) == 72
    assert {row["representation"] for row in plan} == {"RAW", "SUMMARY", "STRUCTURED"}
    assert all(row["status"] == "planned" for row in plan)
