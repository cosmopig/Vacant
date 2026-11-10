"""個人試驗的資料形狀。

這支在架構裡承重什麼：把計畫 §5 的答案、profile、預測、產物與 run row
收成可拒絕未知欄位的檢查。正式答案檔不接受 null choice；空白收集表
與正式檔是兩種形狀，不能混用。

未知欄位一律拒絕。布林值不是整數。
"""

from __future__ import annotations

import json
from typing import Any

ANSWER_SCHEMA = "vacant.personal.answer.v1"
PROFILE_SCHEMA = "vacant.personal.profile.v1"
PREDICTION_SCHEMA = "vacant.personal.prediction.v1"
ENVELOPE_KEYS = (
    "memo_markdown",
    "plan",
)
PLAN_KEYS = (
    "task_id",
    "selected_option_ids",
    "sequence",
    "total_cost_units",
    "total_person_hours",
    "validation",
    "stop_condition",
    "assumptions",
    "tradeoff",
)
VALIDATION_KEYS = ("metric", "method", "decision_rule")
CHOICES = ("A", "B", "tie", "neither", "unsure")
REVIEW_VERDICTS = (
    "adopt_as_is",
    "minor_revision",
    "major_revision",
    "reject",
    "unable_to_judge",
)
ROW_STATUSES = (
    "planned",
    "completed",
    "parse_failed",
    "model_failed",
    "timeout",
    "budget_stopped",
    "usage_unknown",
    "checker_unknown",
    "report_integrity_unknown",
)
RULE_STATUSES = ("inferred", "confirmed", "retracted")
EVIDENCE_STRENGTHS = ("limited", "moderate", "strong")
ARMS = ("A", "B", "C", "D")
REPRESENTATIONS = ("RAW", "SUMMARY", "STRUCTURED")
ARM_REPRESENTATION = {"A": "SUMMARY", "B": "STRUCTURED", "C": "SUMMARY", "D": "STRUCTURED"}
GATE_ON_ARMS = frozenset({"C", "D"})

# 沒有 tokenizer 時的保守字元上限。這不是 usage，不能拿去報 token。
DEFAULT_CONTEXT_CHAR_LIMIT = 2400
STRUCTURED_RULE_CAP = 6
SUMMARY_LINE_CAP = 10
RAW_CASE_CAP = 4

GATE_OFF_FEEDBACK = "此組不提供檢查器回饋，請自行檢視已給任務與原稿。"


class SchemaError(ValueError):
    def __init__(self, problems: list[str]):
        self.problems = list(problems)
        super().__init__("; ".join(self.problems))


def _unknown(obj: dict, allowed: set[str], where: str) -> list[str]:
    return [f"{where}: unknown key {k!r}" for k in sorted(set(obj) - allowed)]


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def plan_json_schema() -> dict[str, Any]:
    """Draft 2020-12。整數不含布林；額外鍵拒絕。任務邊界由 checker 依 facts 重算。"""
    text = {"type": "string", "minLength": 1}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "additionalProperties": False,
        "required": list(PLAN_KEYS),
        "properties": {
            "task_id": {"type": "string", "minLength": 1},
            "selected_option_ids": {
                "type": "array",
                "items": {"type": "string", "minLength": 1},
                "uniqueItems": True,
            },
            "sequence": {
                "type": "array",
                "items": {"type": "string", "minLength": 1},
                "uniqueItems": True,
            },
            "total_cost_units": {"type": "integer", "minimum": 0},
            "total_person_hours": {"type": "integer", "minimum": 0},
            "validation": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": list(VALIDATION_KEYS),
                    "properties": {
                        "metric": text,
                        "method": text,
                        "decision_rule": text,
                    },
                },
            },
            "stop_condition": text,
            "assumptions": {"type": "array", "items": text},
            "tradeoff": text,
        },
    }


def _require_str(obj: dict, key: str, where: str, problems: list[str]) -> None:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        problems.append(f"{where}.{key} must be a non-empty string")


def validate_formal_answer(obj: Any) -> list[str]:
    """正式答案。null choice／空 answered_at 不合法；未作答應根本沒有這一筆。"""
    problems: list[str] = []
    if not isinstance(obj, dict):
        return ["answer must be an object"]
    allowed = {
        "schema_version", "user_id", "case_id", "choice", "reason",
        "switch_condition", "seconds_spent", "presented_order", "answered_at",
    }
    problems += _unknown(obj, allowed, "answer")
    if obj.get("schema_version") != ANSWER_SCHEMA:
        problems.append(f"schema_version must be {ANSWER_SCHEMA!r}")
    _require_str(obj, "user_id", "answer", problems)
    _require_str(obj, "case_id", "answer", problems)
    if obj.get("choice") not in CHOICES:
        problems.append(f"choice must be one of {CHOICES}; null is only for a blank form")
    if not isinstance(obj.get("reason", ""), str):
        problems.append("reason must be a string")
    if not isinstance(obj.get("switch_condition", ""), str):
        problems.append("switch_condition must be a string")
    spent = obj.get("seconds_spent")
    if spent is not None and (not _is_int(spent) or spent < 0):
        problems.append("seconds_spent must be a non-negative integer or omitted")
    order = obj.get("presented_order")
    if order != ["option_1", "option_2"] and order != ["option_2", "option_1"]:
        problems.append("presented_order must be a permutation of option_1 and option_2")
    answered = obj.get("answered_at")
    if not isinstance(answered, str) or not answered.strip():
        problems.append("answered_at must be the actual timestamp; null is only for a blank form")
    return problems


def blank_answer_template(*, user_id: str, case_id: str) -> dict[str, Any]:
    """空白收集表。不能匯入正式答案檔。"""
    return {
        "schema_version": ANSWER_SCHEMA,
        "user_id": user_id,
        "case_id": case_id,
        "choice": None,
        "reason": "",
        "switch_condition": "",
        "seconds_spent": None,
        "presented_order": ["option_1", "option_2"],
        "answered_at": None,
        "_blank_form": True,
    }


def map_choice(choice: str, presented_order: list[str]) -> str | None:
    """A/B 是展示位置。tie／neither／unsure 沒有穩定選項 ID。"""
    if choice in ("tie", "neither", "unsure"):
        return None
    if choice == "A":
        return presented_order[0]
    if choice == "B":
        return presented_order[1]
    raise SchemaError([f"choice {choice!r} cannot be mapped"])


def validate_profile(obj: Any) -> list[str]:
    problems: list[str] = []
    if not isinstance(obj, dict):
        return ["profile must be an object"]
    allowed = {
        "schema_version", "user_id", "profile_version", "updated_at",
        "source_case_ids", "rules", "unresolved_questions", "builder",
        "excluded_case_ids", "representation",
    }
    problems += _unknown(obj, allowed, "profile")
    if obj.get("schema_version") != PROFILE_SCHEMA:
        problems.append(f"schema_version must be {PROFILE_SCHEMA!r}")
    _require_str(obj, "user_id", "profile", problems)
    _require_str(obj, "profile_version", "profile", problems)
    updated = obj.get("updated_at")
    if not isinstance(updated, str) or not updated.strip():
        problems.append("updated_at must be an actual timestamp")
    sources = obj.get("source_case_ids")
    if not isinstance(sources, list) or not all(isinstance(x, str) for x in sources):
        problems.append("source_case_ids must be a list of strings")
    rules = obj.get("rules")
    if not isinstance(rules, list):
        problems.append("rules must be a list")
        rules = []
    rule_ids: set[str] = set()
    rule_keys = {
        "rule_id", "scope", "condition", "preference", "exceptions",
        "evidence_case_ids", "counterevidence_case_ids", "status", "evidence_strength",
    }
    for i, rule in enumerate(rules):
        where = f"rules[{i}]"
        if not isinstance(rule, dict):
            problems.append(f"{where} must be an object")
            continue
        problems += _unknown(rule, rule_keys, where)
        rid = rule.get("rule_id")
        if not isinstance(rid, str) or not rid:
            problems.append(f"{where}.rule_id must be a non-empty string")
        elif rid in rule_ids:
            problems.append(f"duplicate rule_id {rid!r}")
        else:
            rule_ids.add(rid)
        if not isinstance(rule.get("scope"), list) or not all(isinstance(x, str) for x in rule.get("scope", [])):
            problems.append(f"{where}.scope must be a list of strings")
        for key in ("condition", "preference"):
            if not isinstance(rule.get(key), str) or not rule.get(key, "").strip():
                problems.append(f"{where}.{key} must be a non-empty string")
        for key in ("exceptions", "evidence_case_ids", "counterevidence_case_ids"):
            value = rule.get(key)
            if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
                problems.append(f"{where}.{key} must be a list of strings")
        if rule.get("status") not in RULE_STATUSES:
            problems.append(f"{where}.status must be one of {RULE_STATUSES}")
        if rule.get("evidence_strength") not in EVIDENCE_STRENGTHS:
            problems.append(f"{where}.evidence_strength must be one of {EVIDENCE_STRENGTHS}")
        if not rule.get("evidence_case_ids"):
            problems.append(f"{where} has no evidence_case_ids; move it to unresolved_questions")
    unresolved = obj.get("unresolved_questions")
    if not isinstance(unresolved, list) or not all(isinstance(x, str) for x in unresolved):
        problems.append("unresolved_questions must be a list of strings")
    return problems


def validate_prediction(obj: Any) -> list[str]:
    problems: list[str] = []
    if not isinstance(obj, dict):
        return ["prediction must be an object"]
    allowed = {
        "case_id", "prediction", "evidence_case_ids", "applicable_rule_ids", "uncertainty",
    }
    problems += _unknown(obj, allowed, "prediction")
    _require_str(obj, "case_id", "prediction", problems)
    if obj.get("prediction") not in CHOICES:
        problems.append(f"prediction must be one of {CHOICES}")
    for key in ("evidence_case_ids", "applicable_rule_ids"):
        value = obj.get(key)
        if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
            problems.append(f"{key} must be a list of strings")
    if obj.get("uncertainty") not in ("low", "medium", "high"):
        problems.append("uncertainty must be low, medium, or high")
    return problems


def parse_envelope(text: str) -> tuple[dict[str, Any] | None, str | None]:
    """只接受一個 JSON object。解析失敗不重試；呼叫端把該輪記成 parse_failed。"""
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, f"json: {exc.msg}"
    if not isinstance(obj, dict):
        return None, "envelope must be one JSON object"
    extra = sorted(set(obj) - set(ENVELOPE_KEYS))
    if extra or any(k not in obj for k in ENVELOPE_KEYS):
        return None, f"envelope keys must be exactly {list(ENVELOPE_KEYS)}"
    if not isinstance(obj["memo_markdown"], str) or not obj["memo_markdown"].strip():
        return None, "memo_markdown must be a non-empty string"
    plan = obj["plan"]
    if not isinstance(plan, dict):
        return None, "plan must be an object"
    return obj, None


ROW_REQUIRED = {
    "run_id", "task_id", "arm", "pass_index", "status", "call_id",
    "shared_first_draft_group", "model_id", "base_commit", "profile_hash",
    "prompt_hash", "artifact_hashes", "contract_status", "check_results",
    "usage", "cost_usd", "wall_ms", "human_acceptance", "error",
}
ROW_OPTIONAL = {
    "representation", "blind_id", "report_integrity", "backend",
    "fixture_plumbing", "objective_pass",
}


def validate_run_row(obj: Any) -> list[str]:
    problems: list[str] = []
    if not isinstance(obj, dict):
        return ["run row must be an object"]
    allowed = ROW_REQUIRED | ROW_OPTIONAL
    problems += _unknown(obj, allowed, "row")
    for key in ROW_REQUIRED:
        if key not in obj:
            problems.append(f"row missing {key}")
    if obj.get("arm") not in ARMS:
        problems.append(f"arm must be one of {ARMS}")
    if obj.get("pass_index") not in (1, 2):
        problems.append("pass_index must be 1 or 2")
    if obj.get("status") not in ROW_STATUSES:
        problems.append(f"status must be one of {ROW_STATUSES}")
    if obj.get("human_acceptance") is not None:
        problems.append("human_acceptance must stay null until a person reviews the blind bundle")
    return problems
