"""Equal-budget intervention arms (one follow-up call each)."""
from __future__ import annotations

import json
import random
import re
from typing import Any, Mapping

from scorer import load_fields, parse_delivery

SYSTEM = (
    "You extract structured facts into a single JSON object. "
    "Use only the provided source paragraphs. Output JSON only, no prose."
)

ARMS = ("KEEP", "BLIND", "BLANKS", "EVR", "RAND", "UPFRONT")


def _source_block(task: Mapping[str, Any]) -> str:
    lines = [f"[{p['id']}] {p['text']}" for p in task["source_paragraphs"]]
    return "\n".join(lines)


def _field_list(task: Mapping[str, Any]) -> str:
    return ", ".join(f["id"] for f in task["fields"])


def _evidence_for_field(task: Mapping[str, Any], field_id: str) -> list[str]:
    cues = {
        "founded_year": r"found|start|establish|creat|incorporat|form|date|began|launch",
        "hq_city": r"headquarter|based|office|hub|in [A-Z][a-z]+",
        "employees": r"employ|staff|headcount|workforce|people|mariner",
        "revenue": r"revenue|sales|premium|ARR|freight",
        "margin": r"margin|ratio|churn|utilization|factor|intensity|yield|take rate",
        "income": r"income|profit|loss|EBITDA",
    }
    pat = cues.get(field_id)
    if not pat:
        for k, rx in cues.items():
            if k in field_id:
                pat = rx
                break
    pat = pat or field_id.replace("_", " ")
    rx = re.compile(pat, re.I)
    out = []
    for p in task["source_paragraphs"]:
        if rx.search(p["text"]):
            out.append(f"[{p['id']}] {p['text']}")
    return out or [f"[{task['source_paragraphs'][0]['id']}] {task['source_paragraphs'][0]['text']}"]


def build_call1_user(task: Mapping[str, Any], *, upfront: bool = False) -> str:
    spec = ""
    if upfront:
        spec = (
            "Field contract: each value must copy exact units/currency from the source; "
            "percent fields must include %; money fields must include currency code.\n"
        )
    return (
        f"TASK_ID: {task['task_id']}\n"
        f"Fill fields: {_field_list(task)}\n"
        f"{spec}"
        f"Sources:\n{_source_block(task)}\n"
        "Return one JSON object with those keys."
    )


def build_call2_user(
    task: Mapping[str, Any],
    arm: str,
    draft_json: str,
    *,
    rng: random.Random,
    visible_grade: dict[str, Any],
) -> str:
    delivery = parse_delivery(draft_json)
    base = (
        f"TASK_ID: {task['task_id']}\n"
        f"Sources:\n{_source_block(task)}\n"
        f"Previous JSON:\n{json.dumps(delivery, ensure_ascii=False)}\n"
    )
    if arm == "KEEP":
        return base + "Re-output the same JSON values unless a visible format error is obvious. JSON only."
    if arm == "BLIND":
        return base + "Rewrite the full JSON from sources. JSON only."
    if arm == "BLANKS":
        missing = [f["id"] for f in task["fields"] if not str(delivery.get(f["id"], "")).strip()]
        return base + f"Fill ONLY these empty fields: {missing or ['(none)']}. Keep other keys unchanged. JSON only."
    if arm == "RAND":
        fields = load_fields(task)
        wrong = [fr["id"] for fr in visible_grade["fields"] if not fr["visible_ok"]]
        if not wrong:
            wrong = [f.id for f in fields]
        k = max(1, min(2, len(wrong)))
        pick = rng.sample(wrong, k=min(k, len(wrong)))
        return base + f"Revise ONLY these fields (others frozen): {pick}. JSON only."
    if arm == "EVR":
        issues = []
        for fr in visible_grade["fields"]:
            if fr["visible_ok"]:
                continue
            ev = _evidence_for_field(task, fr["id"])
            issues.append(
                {
                    "field": fr["id"],
                    "problem": fr["detail"],
                    "current": fr.get("got"),
                    "evidence": ev,
                }
            )
        return (
            base
            + "Visible check failed for:\n"
            + json.dumps(issues, ensure_ascii=False, indent=2)
            + "\nFix ONLY listed fields using cited evidence. Keep correct fields unchanged. JSON only."
        )
    raise ValueError(f"unknown arm {arm}")


def merge_delivery(draft: dict[str, str], new: dict[str, str], frozen_ok: Mapping[str, bool]) -> dict[str, str]:
    out = dict(draft)
    for k, v in new.items():
        if k in frozen_ok and frozen_ok[k] and k in out and str(out[k]).strip():
            continue
        out[k] = v
    return out


def frozen_correct_fields(visible_grade: dict[str, Any]) -> dict[str, bool]:
    return {
        fr["id"]: bool(fr["hidden_ok"] and fr["visible_ok"]) for fr in visible_grade["fields"]
    }