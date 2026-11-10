"""組裝受限上下文。

這支在架構裡承重什麼：模型看得到的個人資料只有校準案例或已凍結的
表示。保留題只以不含標籤的題幹進入預測提示。檢索不看答案；
同家族優先，再用中文二字組與英數詞的 Jaccard，同分按 case_id。

沒有 tokenizer 時用字元上限先擋，這個數字不是 usage。放不下就刪掉
整筆最低排名的案例或規則，不抽一句偏向某選項的碎片。
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from .profiles import RETRIEVAL_METHOD, ContextLeakError, assert_calibration_sources
from .prompts import render
from .schemas import DEFAULT_CONTEXT_CHAR_LIMIT, GATE_OFF_FEEDBACK, plan_json_schema

_CJK = re.compile(r"[\u4e00-\u9fff]")
_TOKEN = re.compile(r"[a-z0-9]+")


def normalize(text: str) -> str:
    return re.sub(r"[^\u4e00-\u9fffa-z0-9]+", " ", text.lower())


def features(text: str) -> set[str]:
    norm = normalize(text)
    chars = "".join(_CJK.findall(norm))
    bigrams = {f"b:{chars[i:i + 2]}" for i in range(len(chars) - 1)}
    tokens = {f"t:{tok}" for tok in _TOKEN.findall(norm)}
    return bigrams | tokens


def jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def _case_text(case: dict[str, Any]) -> str:
    options = case.get("options") or []
    body = " ".join(opt.get("text", "") if isinstance(opt, dict) else str(opt) for opt in options)
    return f"{case.get('title', '')}\n{case.get('stem', '')}\n{body}"


def _strip_label(case: dict[str, Any]) -> dict[str, Any]:
    """預測題只留題幹與選項。choice／reason 一律拿掉。"""
    return {
        "case_id": case["case_id"],
        "family": case["family"],
        "title": case["title"],
        "stem": case["stem"],
        "options": [{"id": opt["id"], "text": opt["text"]} for opt in case["options"]],
    }


def render_joined_case(case: dict[str, Any]) -> str:
    lines = [
        f"case_id: {case['case_id']}",
        f"family: {case['family']}",
        f"title: {case['title']}",
        f"stem: {case['stem']}",
    ]
    for opt in case["options"]:
        lines.append(f"option {opt['id']}: {opt['text']}")
    if "choice" in case:
        lines.append(f"presented_order: {case.get('presented_order')}")
        lines.append(f"choice: {case.get('choice')}")
        lines.append(f"choice_option_id: {case.get('choice_option_id')}")
        lines.append(f"reason: {case.get('reason') or ''}")
        lines.append(f"switch_condition: {case.get('switch_condition') or ''}")
    return "\n".join(lines)


def fit_blocks(ranked: list[dict[str, Any]], render_one, *, char_limit: int) -> tuple[list[dict[str, Any]], list[str]]:
    """從最低排名整筆刪，直到個人資料區塊放得下。不切半筆。"""
    kept = list(ranked)
    dropped: list[str] = []
    while kept and sum(len(render_one(item)) for item in kept) > char_limit:
        removed = kept.pop()
        dropped.append(str(removed.get("case_id") or removed.get("rule_id") or removed.get("id")))
    return kept, dropped


def retrieve(query: dict[str, Any], pool: list[dict[str, Any]], *, limit: int = 4, char_limit: int = DEFAULT_CONTEXT_CHAR_LIMIT) -> dict[str, Any]:
    if any(key in query for key in ("choice", "choice_option_id", "reason", "human_acceptance")):
        raise ContextLeakError("holdout query carries a label; retrieval refuses it")
    if any(str(case.get("case_id", "")).startswith(("H", "T")) for case in pool):
        raise ContextLeakError("retrieval pool must be calibration cases only")
    query_features = features(_case_text(query))
    family = query["family"]
    scored = []
    for case in pool:
        score = jaccard(query_features, features(_case_text(case)))
        same = 0 if case.get("family") == family else 1
        scored.append((same, -score, case["case_id"], score, case))
    scored.sort()
    ranked = [row[4] for row in scored]
    same_family = [row for row in scored if row[0] == 0]
    textual = [row for row in scored if row[3] > 0]
    if not same_family and textual:
        note = "cross_family_only"
    elif not textual:
        note = "no_textual_overlap"
    elif not any(row[3] > 0 for row in same_family):
        note = "same_family_no_textual_overlap"
    else:
        note = "same_family"
    capped = ranked[:limit]
    kept, dropped = fit_blocks(capped, render_joined_case, char_limit=char_limit)
    return {
        "method": RETRIEVAL_METHOD,
        "note": note,
        "cases": kept,
        "dropped_case_ids": dropped,
        "scores": [{"case_id": row[2], "same_family": row[0] == 0, "jaccard": row[3]} for row in scored],
        "char_limit": char_limit,
        "char_limit_is_usage": False,
    }


def _personal_block(representation: str, profiles: dict[str, Any], retrieval: dict[str, Any] | None, *, char_limit: int) -> tuple[str, list[str]]:
    if representation == "RAW":
        if retrieval is None:
            raise ContextLeakError("RAW requires a retrieval result")
        cases = retrieval["cases"]
        kept, dropped = fit_blocks(cases, render_joined_case, char_limit=char_limit)
        return "\n\n".join(render_joined_case(case) for case in kept), dropped
    if representation == "SUMMARY":
        lines = list(profiles["SUMMARY"].get("lines") or [])
        kept, dropped = fit_blocks(lines, lambda line: line["text"], char_limit=char_limit)
        return "\n".join(line["text"] for line in kept), dropped
    if representation == "STRUCTURED":
        rules = list(profiles["STRUCTURED"].get("rules") or [])
        kept, dropped = fit_blocks(rules, lambda rule: _render_rule(rule), char_limit=char_limit)
        unresolved = profiles["STRUCTURED"].get("unresolved_questions") or []
        body = "\n\n".join(_render_rule(rule) for rule in kept)
        if unresolved:
            body += "\n\nunresolved:\n" + "\n".join(unresolved)
        if len(body) > char_limit:
            body = "\n\n".join(_render_rule(rule) for rule in kept)
            dropped = dropped + ["unresolved_questions"]
        return body, dropped
    raise ContextLeakError(f"unknown representation {representation}")


def _render_rule(rule: dict[str, Any]) -> str:
    return "\n".join([
        f"rule_id: {rule['rule_id']}",
        f"scope: {rule['scope']}",
        f"condition: {rule['condition']}",
        f"preference: {rule['preference']}",
        f"exceptions: {rule['exceptions']}",
        f"evidence_case_ids: {rule['evidence_case_ids']}",
        f"counterevidence_case_ids: {rule['counterevidence_case_ids']}",
        f"status: {rule['status']}",
        f"evidence_strength: {rule['evidence_strength']}",
    ])


def _guard(profiles: dict[str, Any], allowed: set[str]) -> None:
    for profile in profiles.values():
        assert_calibration_sources(profile, allowed)


def prediction_prompt(query: dict[str, Any], profiles: dict[str, Any], pool: list[dict[str, Any]], representation: str, *, allowed_ids: set[str], char_limit: int = DEFAULT_CONTEXT_CHAR_LIMIT) -> dict[str, Any]:
    _guard(profiles, allowed_ids)
    public = _strip_label(query)
    retrieval = retrieve(public, pool, char_limit=char_limit) if representation == "RAW" else None
    block, dropped = _personal_block(representation, profiles, retrieval, char_limit=char_limit)
    user = render(
        "predict",
        profile_or_retrieved_cases=block,
        heldout_case_without_owner_label=render_joined_case(public),
    )
    from .prompts import SYSTEM
    return _pack(SYSTEM, user, block, dropped, retrieval)


def draft_prompt(task: dict[str, Any], profiles: dict[str, Any], representation: str, *, allowed_ids: set[str], char_limit: int = DEFAULT_CONTEXT_CHAR_LIMIT) -> dict[str, Any]:
    _guard(profiles, allowed_ids)
    block, dropped = _personal_block(representation, profiles, None, char_limit=char_limit)
    import json
    user = render(
        "draft",
        profile=block,
        task=json.dumps(task, ensure_ascii=False),
        schema=json.dumps(plan_json_schema(), ensure_ascii=False),
    )
    from .prompts import SYSTEM
    return _pack(SYSTEM, user, block, dropped, None)


def revision_prompt(task: dict[str, Any], profiles: dict[str, Any], representation: str, draft_text: str, *, arm: str, check_lines: list[str] | None, allowed_ids: set[str], char_limit: int = DEFAULT_CONTEXT_CHAR_LIMIT) -> dict[str, Any]:
    """gate-off 不放檢查結果。gate-on 才附逐條結果。兩邊都還會離線重跑同一 checker。"""
    from .schemas import GATE_ON_ARMS
    _guard(profiles, allowed_ids)
    block, dropped = _personal_block(representation, profiles, None, char_limit=char_limit)
    if arm in GATE_ON_ARMS:
        feedback = "\n".join(check_lines or []) or "checker returned no lines"
    else:
        feedback = GATE_OFF_FEEDBACK
        if check_lines and any(line in feedback for line in check_lines):
            raise ContextLeakError("gate-off feedback collided with a checker line")
    import json
    user = render(
        "revise",
        task=json.dumps(task, ensure_ascii=False),
        profile=block,
        draft=draft_text,
        gate_on_results_or_fixed_no_checker_feedback=feedback,
    )
    from .prompts import SYSTEM
    packed = _pack(SYSTEM, user, block, dropped, None)
    packed["gate"] = "on" if arm in GATE_ON_ARMS else "off"
    packed["feedback"] = feedback
    return packed


def _pack(system: str, user: str, block: str, dropped: list[str], retrieval: dict[str, Any] | None) -> dict[str, Any]:
    blob = system + "\n---\n" + user
    return {
        "system": system,
        "user": user,
        "personal_block": block,
        "personal_chars": len(block),
        "dropped": dropped,
        "retrieval": None if retrieval is None else {key: retrieval[key] for key in ("method", "note", "dropped_case_ids", "char_limit", "char_limit_is_usage")},
        "prompt_hash": hashlib.sha256(blob.encode("utf-8")).hexdigest(),
        "usage_note": "personal_chars is a pre-limit, not provider usage",
    }


def check_lines_from_decision(decision: dict[str, Any], report: dict[str, Any] | None) -> list[str]:
    lines = []
    for row in decision.get("results") or []:
        lines.append(f"{row.get('claim_id')}: {row.get('status')} — {row.get('detail')}")
    if report:
        for row in report.get("checks") or []:
            lines.append(
                f"{row.get('check_id')}: {row.get('status')} observed={row.get('observed')!s} expected={row.get('expected_or_constraint')!s}"
            )
    return lines
