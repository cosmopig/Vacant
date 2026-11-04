"""Unit tests for reqloop G2 repair controller.

NOTE: All test fixtures herein are synthetic and used strictly for offline unit testing.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace as NS
import pytest

from vacant_network.intake.verifiers import ClaimResult
from vacant_network.reqloop.requirements import RequirementItem, RequirementSet
from vacant_network.reqloop.checks import check_tag_format, run_requirement_checks
from vacant_network.reqloop.repair import (
    parse_pi_metrics,
    generate_repair_prompt,
    run_repair_loop,
)


def _mk_claim_result(claim_id: str, status: str, detail: str, evidence: dict | None = None) -> ClaimResult:
    return ClaimResult(
        claim_id=claim_id,
        status=status,
        detail=detail,
        evidence=evidence or {},
        verifier="test_verifier",
        verifier_version="1.0",
        required=True,
        authority="client",
    )


def test_parse_pi_metrics_valid():
    sample = "\n".join([
        json.dumps({"type": "session", "id": "s1"}),
        json.dumps({
            "type": "message_end",
            "message": {
                "role": "assistant",
                "usage": {"input": 120, "output": 25, "reasoning": 10},
                "stopReason": "toolUse",
            },
        }),
        json.dumps({
            "type": "message_end",
            "message": {
                "role": "assistant",
                "usage": {"input": 180, "output": 40, "reasoning": 15},
                "stopReason": "stop",
            },
        }),
    ])
    metrics = parse_pi_metrics(sample)
    assert metrics["model_calls"] == 2
    assert metrics["input_tokens"] == 300
    assert metrics["output_tokens"] == 65
    assert metrics["reasoning_tokens"] == 25
    assert metrics["stop_reason"] == "stop"


def test_parse_pi_metrics_missing_usage():
    sample = "\n".join([
        json.dumps({
            "type": "message_end",
            "message": {"role": "assistant", "stopReason": "stop"},
        }),
    ])
    metrics = parse_pi_metrics(sample)
    assert metrics["model_calls"] == 1
    # Missing values must be UNKNOWN, never 0
    assert metrics["input_tokens"] == "UNKNOWN"
    assert metrics["output_tokens"] == "UNKNOWN"


def test_generate_repair_prompt_generic():
    failing = [
        _mk_claim_result("r1", "FAIL", "missing brackets", {"k": "v"}),
    ]
    prompt = generate_repair_prompt("task instructions", failing, "generic")
    assert "task instructions" in prompt
    assert "未通過" in prompt
    assert "missing brackets" not in prompt  # generic doesn't leak specifics


def test_generate_repair_prompt_localized():
    failing = [
        _mk_claim_result("r1", "FAIL", "missing brackets", {"k": "v"}),
    ]
    prompt = generate_repair_prompt("task instructions", failing, "localized")
    assert "task instructions" in prompt
    assert "[r1]" in prompt
    assert "missing brackets" in prompt
    assert '"k": "v"' in prompt


def test_tag_format_verifier(tmp_path: Path):
    item = RequirementItem(
        id="c1",
        quote="quote",
        deliverable="answer.txt",
        verifier="tag_format",
        kind="explicit",
        params={"file": "answer.txt", "tag": "mean_val", "value_type": "integer"},
    )

    # 1. missing file
    res = check_tag_format(tmp_path, item)
    assert res.status == "FAIL"
    assert "缺少指定檔案" in res.detail

    # 2. missing brackets: @mean_val1234
    (tmp_path / "answer.txt").write_text("@mean_val1234\n", encoding="utf-8")
    res = check_tag_format(tmp_path, item)
    assert res.status == "FAIL"
    assert "缺少方括號" in res.detail

    # 3. float with decimal when integer required: @mean_val[1234.56]
    (tmp_path / "answer.txt").write_text("@mean_val[1234.56]\n", encoding="utf-8")
    res = check_tag_format(tmp_path, item)
    assert res.status == "FAIL"
    assert "包含小數點" in res.detail

    # 4. correct positive integer: @mean_val[1234]
    (tmp_path / "answer.txt").write_text("@mean_val[1234]\n", encoding="utf-8")
    res = check_tag_format(tmp_path, item)
    assert res.status == "PASS"


# --- Synthetic Offline Unit Tests for Repair Loop ---

def test_repair_loop_already_passed(tmp_path: Path):
    # synthetic: offline unit test fixture
    (tmp_path / "answer.txt").write_text("@score[95]\n", encoding="utf-8")
    req_set = RequirementSet(
        task_id="synthetic_t1",
        items=[
            RequirementItem(
                id="req_score",
                quote="Format score as integer",
                deliverable="answer.txt",
                verifier="tag_format",
                kind="explicit",
                params={"file": "answer.txt", "tag": "score", "value_type": "integer"},
            ),
        ],
    )

    res = run_repair_loop(tmp_path, req_set, tmp_path, "prompt", feedback_mode="localized")
    assert res["completed"] is True
    assert res["stop_reason"] == "already_passed"
    assert len(res["attempts"]) == 0
    assert res["total_cost"]["model_calls"] == 0


def test_repair_loop_consecutive_no_progress_stops(tmp_path: Path):
    # synthetic: offline unit test fixture
    (tmp_path / "answer.txt").write_text("@score[95.5]\n", encoding="utf-8")  # bad float
    req_set = RequirementSet(
        task_id="synthetic_t2",
        items=[
            RequirementItem(
                id="req_score",
                quote="Format score as integer",
                deliverable="answer.txt",
                verifier="tag_format",
                kind="explicit",
                params={"file": "answer.txt", "tag": "score", "value_type": "integer"},
            ),
        ],
    )

    call_count = 0
    def dummy_turn(ws, prompt, **kwargs):
        nonlocal call_count
        call_count += 1
        # Model fails to fix the file
        return {
            "rc": 0,
            "timed_out": False,
            "wall_ms": 100,
            "metrics": {"model_calls": 1, "input_tokens": 50, "output_tokens": 10, "reasoning_tokens": 0, "stop_reason": "stop"},
            "error": None,
        }

    res = run_repair_loop(
        tmp_path,
        req_set,
        tmp_path,
        "prompt",
        feedback_mode="localized",
        max_attempts=3,
        turn_fn=dummy_turn,
    )

    assert res["completed"] is False
    assert res["stop_reason"] == "consecutive_no_progress"
    assert len(res["attempts"]) == 2  # stops after 2 attempts with no progress
    assert res["total_cost"]["model_calls"] == 2
    assert "req_score" in res["unresolved_claims"]


def test_repair_loop_fixes_shortfall(tmp_path: Path):
    # synthetic: offline unit test fixture
    (tmp_path / "answer.txt").write_text("@score[95.5]\n", encoding="utf-8")
    req_set = RequirementSet(
        task_id="synthetic_t3",
        items=[
            RequirementItem(
                id="req_score",
                quote="Format score as integer",
                deliverable="answer.txt",
                verifier="tag_format",
                kind="explicit",
                params={"file": "answer.txt", "tag": "score", "value_type": "integer"},
            ),
        ],
    )

    def fixing_turn(ws, prompt, **kwargs):
        # Model fixes the error
        (ws / "answer.txt").write_text("@score[96]\n", encoding="utf-8")
        return {
            "rc": 0,
            "timed_out": False,
            "wall_ms": 250,
            "metrics": {"model_calls": 1, "input_tokens": 80, "output_tokens": 15, "reasoning_tokens": 0, "stop_reason": "stop"},
            "error": None,
        }

    res = run_repair_loop(
        tmp_path,
        req_set,
        tmp_path,
        "prompt",
        feedback_mode="localized",
        max_attempts=2,
        turn_fn=fixing_turn,
    )

    assert res["completed"] is True
    assert res["stop_reason"] == "completed"
    assert len(res["attempts"]) == 1
    assert "req_score" in res["fixed_claims"]
    assert res["regressed_claims"] == []
    assert res["unresolved_claims"] == []
