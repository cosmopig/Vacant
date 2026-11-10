"""三種個人表示。

這支在架構裡承重什麼：RAW／SUMMARY／STRUCTURED 來自同一批已 join 的
校準案例。確定性建造器只複寫本人寫過的選擇與理由，不補造人格，
也不讀 H／T。模型路徑另用凍結提示，每次一支請求；本模組的確定性
結果會標 builder，不能說成模型已經理解本人。

沒有來源的內容進 unresolved_questions。規則上限 6，摘要上限 10。
"""

from __future__ import annotations

from typing import Any

from .schemas import (
    PROFILE_SCHEMA,
    RAW_CASE_CAP,
    STRUCTURED_RULE_CAP,
    SUMMARY_LINE_CAP,
    validate_profile,
)

RETRIEVAL_METHOD = "family_then_jaccard_cjk_bigram_alnum_v1"


class ProfileError(ValueError):
    pass


class ContextLeakError(ProfileError):
    """保留標籤或未見來源進了個人資料。發生時不准發模型請求。"""


def calibration_ids(cases: list[dict[str, Any]]) -> set[str]:
    return {case["case_id"] for case in cases}


def assert_calibration_sources(profile: dict[str, Any], allowed: set[str]) -> None:
    found: list[str] = []
    found.extend(profile.get("source_case_ids") or [])
    for rule in profile.get("rules") or []:
        found.extend(rule.get("evidence_case_ids") or [])
        found.extend(rule.get("counterevidence_case_ids") or [])
    for line in profile.get("lines") or []:
        if isinstance(line, dict) and line.get("case_id"):
            found.append(line["case_id"])
    bad = []
    for case_id in found:
        if case_id not in allowed or not str(case_id).startswith("C"):
            bad.append(case_id)
    if bad:
        raise ContextLeakError(
            "profile cites sources outside the calibration answers: " + ", ".join(sorted(set(bad)))
        )


def build_raw_index(joined: list[dict[str, Any]], *, updated_at: str, user_id: str) -> dict[str, Any]:
    return {
        "schema_version": "vacant.personal.raw.v1",
        "representation": "RAW",
        "user_id": user_id,
        "updated_at": updated_at,
        "builder": "deterministic_retrieval",
        "retrieval_method": RETRIEVAL_METHOD,
        "case_cap": RAW_CASE_CAP,
        "source_case_ids": [case["case_id"] for case in joined],
        "rules": [],
        "lines": [],
    }


def build_summary(joined: list[dict[str, Any]], *, updated_at: str, user_id: str, profile_version: str) -> dict[str, Any]:
    """逐題複寫，不濃縮成資料裡沒有的人格句。超過 10 條時整筆排除並留下 id。"""
    ordered = sorted(joined, key=lambda case: case["case_id"])
    kept = ordered[:SUMMARY_LINE_CAP]
    dropped = [case["case_id"] for case in ordered[SUMMARY_LINE_CAP:]]
    lines = []
    for case in kept:
        reason = case["reason"] or "未寫"
        switch = case["switch_condition"] or "未寫"
        stable = case["choice_option_id"] or "無對應選項"
        lines.append({
            "case_id": case["case_id"],
            "text": (
                f"{case['case_id']}（{case['family']}）展示選擇 {case['choice']}，"
                f"對應穩定 id {stable}。本人理由：{reason}。改選條件：{switch}。"
            ),
        })
    return {
        "schema_version": "vacant.personal.summary.v1",
        "representation": "SUMMARY",
        "user_id": user_id,
        "profile_version": profile_version,
        "updated_at": updated_at,
        "builder": "deterministic_transcript",
        "source_case_ids": [line["case_id"] for line in lines],
        "excluded_case_ids": dropped,
        "lines": lines,
        "rules": [],
        "unresolved_questions": [
            f"{case_id} 因摘要上限 {SUMMARY_LINE_CAP} 整筆未放入"
            for case_id in dropped
        ],
    }


def build_structured(joined: list[dict[str, Any]], *, updated_at: str, user_id: str, profile_version: str) -> dict[str, Any]:
    """一題至多一條規則。偏好文字只用本人選到的選項原文；沒有口語理由就記在 unresolved。"""
    ordered = sorted(joined, key=lambda case: case["case_id"])
    rules = []
    unresolved: list[str] = []
    for case in ordered:
        if len(rules) >= STRUCTURED_RULE_CAP:
            unresolved.append(f"{case['case_id']} 超過 {STRUCTURED_RULE_CAP} 條上限，整筆留在 unresolved")
            continue
        if case["choice"] in ("A", "B") and case.get("choice_text"):
            preference = case["choice_text"]
        else:
            preference = f"本人選擇 {case['choice']}，沒有單一選項。"
        if not case["reason"] and not case["switch_condition"] and case["choice"] not in ("A", "B"):
            unresolved.append(f"{case['case_id']} 沒有選項也沒有理由，不補造規則")
            continue
        exceptions = [case["switch_condition"]] if case["switch_condition"] else []
        if not case["reason"]:
            unresolved.append(f"{case['case_id']} 沒有口語理由；規則只複寫選項原文")
        rules.append({
            "rule_id": f"r{len(rules) + 1:03d}",
            "scope": [case["family"]],
            "condition": case["stem"],
            "preference": preference,
            "exceptions": exceptions,
            "evidence_case_ids": [case["case_id"]],
            "counterevidence_case_ids": [],
            "status": "inferred",
            "evidence_strength": "limited",
        })
    profile = {
        "schema_version": PROFILE_SCHEMA,
        "representation": "STRUCTURED",
        "user_id": user_id,
        "profile_version": profile_version,
        "updated_at": updated_at,
        "builder": "deterministic_transcript",
        "source_case_ids": [case["case_id"] for case in ordered if case["case_id"] in {cid for rule in rules for cid in rule["evidence_case_ids"]}],
        "rules": rules,
        "unresolved_questions": unresolved,
        "excluded_case_ids": [case["case_id"] for case in ordered if case["case_id"] not in {cid for rule in rules for cid in rule["evidence_case_ids"]}],
    }
    problems = validate_profile(profile)
    if problems:
        raise ProfileError("; ".join(problems))
    assert_calibration_sources(profile, calibration_ids(joined))
    return profile


def build_all(joined: list[dict[str, Any]], *, updated_at: str, user_id: str, profile_version: str) -> dict[str, dict[str, Any]]:
    if not updated_at:
        raise ProfileError("updated_at is required; a profile is not built from a blank form")
    raw = build_raw_index(joined, updated_at=updated_at, user_id=user_id)
    summary = build_summary(joined, updated_at=updated_at, user_id=user_id, profile_version=profile_version)
    structured = build_structured(joined, updated_at=updated_at, user_id=user_id, profile_version=profile_version)
    allowed = calibration_ids(joined)
    for profile in (raw, summary, structured):
        assert_calibration_sources(profile, allowed)
    return {"RAW": raw, "SUMMARY": summary, "STRUCTURED": structured}
