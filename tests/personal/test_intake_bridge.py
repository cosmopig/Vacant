"""橋接必須呼叫既有 intake，而且不把多餘參數塞進 claim。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from vacant_network.intake.verifiers import VERIFIERS
from vacant_network.personal.dataset import load_bank, structural_memo, structural_plan
from vacant_network.personal.intake_bridge import (
    build_control,
    check_artifacts,
    supported_param_problems,
    write_artifacts,
)

ROOT = Path(__file__).resolve().parents[2]
TASKS = load_bank(ROOT / "ops" / "personal_pilot" / "task_bank" / "tasks.json", kind="tasks")
CHECKER = ROOT / "ops" / "personal_pilot" / "trusted_checks" / "check_plan.py"


def test_supported_params_are_only_the_intake_ones(tmp_path):
    task = TASKS["tasks"][0]
    built = build_control(tmp_path / "control", task)
    assert supported_param_problems(built["raw"]) == []
    for claim in built["raw"]["claims"]:
        assert set(claim["params"]) <= set(VERIFIERS[claim["verifier"]].params)
        assert "quote" not in claim["params"]
        assert "confidence" not in claim["params"]


def test_legal_plan_is_accept_and_short_total_is_reject(tmp_path):
    task = TASKS["tasks"][0]
    plan = structural_plan(task)
    built = build_control(tmp_path / "ok", task)
    artifact = tmp_path / "ok-art"
    write_artifacts(artifact, structural_memo(task, plan), plan)
    result = check_artifacts(built["control_dir"], artifact)
    assert result["outcome"] == "accept"
    assert result["exit_code"] == 0
    assert result["human_acceptance"] is None
    assert result["integrity"]["ok"] is True

    short = json.loads(json.dumps(plan))
    short["total_cost_units"] = plan["total_cost_units"] - 1
    built = build_control(tmp_path / "bad", task)
    artifact = tmp_path / "bad-art"
    write_artifacts(artifact, structural_memo(task, plan), short)
    result = check_artifacts(built["control_dir"], artifact)
    assert result["outcome"] == "reject"
    assert result["exit_code"] == 40
    report = json.loads(Path(result["report_path"]).read_text(encoding="utf-8"))
    cost = next(item for item in report["checks"] if item["check_id"] == "total_cost_units")
    assert cost["observed"] == short["total_cost_units"]
    assert cost["expected_or_constraint"]["recomputed"] == plan["total_cost_units"]


def test_cli_exit_code_matches_the_bridge(tmp_path):
    task = TASKS["tasks"][0]
    plan = structural_plan(task)
    built = build_control(tmp_path / "control", task)
    artifact = tmp_path / "artifact"
    write_artifacts(artifact, structural_memo(task, plan), plan)
    proc = subprocess.run(
        [sys.executable, "-m", "vacant_network", "check", "--contract", str(built["contract_path"]),
         "--dir", str(artifact), "--json"],
        capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["outcome"] == "accept"


def test_bool_in_facts_is_unknown_not_a_candidate_fail(tmp_path):
    task = json.loads(json.dumps(TASKS["tasks"][0]))
    task["options"][0]["cost_units"] = True
    facts = tmp_path / "task_facts.json"
    schema = tmp_path / "plan.schema.json"
    report = tmp_path / "report.json"
    artifact = tmp_path / "artifact"
    artifact.mkdir()
    (artifact / "memo.md").write_text("備忘錄", encoding="utf-8")
    (artifact / "plan.json").write_text("{}", encoding="utf-8")
    facts.write_text(json.dumps(task), encoding="utf-8")
    schema.write_text("{}", encoding="utf-8")
    env = dict(os.environ)
    env.update({
        "VACANT_ARTIFACT_DIR": str(artifact),
        "VACANT_INPUT_TASK_FACTS": str(facts),
        "VACANT_INPUT_PLAN_SCHEMA": str(schema),
        "VACANT_INPUT_CHECKER": str(CHECKER),
        "VACANT_PERSONAL_CHECK_REPORT": str(report),
    })
    proc = subprocess.run([sys.executable, "-I", str(CHECKER)], capture_output=True, text=True, env=env, check=False)
    assert proc.returncode == 2
    body = json.loads(report.read_text(encoding="utf-8"))
    assert body["checks"][0]["status"] == "UNKNOWN"
    assert body["checks"][0]["error_type"] == "setup"
