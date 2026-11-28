"""Compile requester contracts from task spec only (no model outputs)."""
from __future__ import annotations

from typing import Any, Mapping

from contract.canonical import sha256_obj

FROZEN_AT = "2026-11-28T13:37:00Z"


def _period_instant(question: Mapping[str, Any]) -> str | None:
    gold = question.get("gold") or {}
    period = gold.get("period") or {}
    return period.get("instant") or period.get("end")


def _unit_from_question_text(question: Mapping[str, Any]) -> str:
    q = str(question.get("question", ""))
    if "EUR" in q:
        return "EUR"
    if "GBP" in q:
        return "GBP"
    return "USD"


def compile_contract_primary(question: Mapping[str, Any], *, profile: str = "primary") -> dict[str, Any]:
    """Requester contract (primary line). Uses pinned task metadata shipped with the question."""
    gold = question.get("gold") or {}
    unit = str(gold.get("unit", "USD"))
    clauses: list[dict[str, Any]] = [
        {
            "id": "C1_status",
            "op": "status_found_fields",
            "required_fields": ["value", "span", "scale"],
            "allow_not_found": False,
        },
        {
            "id": "C2_provenance",
            "op": "provenance_span_substr",
        },
        {
            "id": "C3_value_in_span",
            "op": "value_in_span_numbers",
            "tolerance_relative": 0.001,
            "tolerance_floor": 0.5,
        },
        {
            "id": "C4_scale_header",
            "op": "scale_header_consistency",
        },
        {
            "id": "C5_unit",
            "op": "unit_if_declared",
            "unit": unit,
        },
    ]
    if profile == "primary":
        # Known incompleteness (documented): no period/column pin — multi-number spans ESCALATE only in independent profile.
        pass
    body = {
        "v": 1,
        "task_id": question["id"],
        "requester": "benchmark_operator",
        "owner_escalate": "contract_owner@requester",
        "field_type": "money",
        "declared_unit": unit,
        "declared_scale_exponent": gold.get("scale"),
        "declared_period_instant": _period_instant(question),
        "frozen_at": FROZEN_AT,
        "profile": profile,
        "clauses": clauses,
    }
    body["sha256"] = sha256_obj({k: v for k, v in body.items() if k != "sha256"})
    return body


def compile_contract_question_only(question: Mapping[str, Any]) -> dict[str, Any]:
    """Third blind author: question + form only, minimal clauses, always ESCALATE multi-column."""
    unit = _unit_from_question_text(question)
    clauses: list[dict[str, Any]] = [
        {"id": "Q1_provenance", "op": "provenance_span_substr"},
        {"id": "Q2_value_in_span", "op": "value_in_span_numbers", "tolerance_relative": 0.001, "tolerance_floor": 0.5},
        {"id": "Q3_multi", "op": "multi_column_escalate", "distinct_numbers_escalate_above": 2},
    ]
    body = {
        "v": 1,
        "task_id": question["id"],
        "requester": "question_only_compiler",
        "owner_escalate": "contract_owner@requester",
        "field_type": "money",
        "declared_unit": unit,
        "declared_scale_exponent": None,
        "declared_period_instant": None,
        "frozen_at": FROZEN_AT,
        "profile": "question_only",
        "clauses": clauses,
    }
    body["sha256"] = sha256_obj({k: v for k, v in body.items() if k != "sha256"})
    return body


def compile_contract_independent(question: Mapping[str, Any]) -> dict[str, Any]:
    """Blind author: task text + form only; stricter ESCALATE on ambiguous tables (no gold JSON)."""
    unit = _unit_from_question_text(question)
    clauses: list[dict[str, Any]] = [
        {"id": "R1_span", "op": "provenance_span_substr"},
        {"id": "R2_fields", "op": "status_found_fields", "required_fields": ["value", "span"], "allow_not_found": False},
        {"id": "R3_value_in_span", "op": "value_in_span_numbers", "tolerance_relative": 0.001, "tolerance_floor": 0.5},
        {"id": "R4_scale", "op": "scale_header_consistency"},
        {"id": "R5_multi_column", "op": "multi_column_escalate", "distinct_numbers_escalate_above": 2},
        {"id": "R6_unit", "op": "unit_if_declared", "unit": unit},
    ]
    body = {
        "v": 1,
        "task_id": question["id"],
        "requester": "independent_compiler_script",
        "owner_escalate": "contract_owner@requester",
        "field_type": "money",
        "declared_unit": unit,
        "declared_scale_exponent": None,
        "declared_period_instant": None,
        "frozen_at": FROZEN_AT,
        "profile": "independent",
        "author_note": "Compiled from question string + form only; period/scale from gold intentionally omitted.",
        "clauses": clauses,
    }
    body["sha256"] = sha256_obj({k: v for k, v in body.items() if k != "sha256"})
    return body