"""Quote-level check: cited span must appear on page text."""
from __future__ import annotations

from typing import Any, Mapping


def quote_check(answer: Mapping[str, Any], page_text: str) -> tuple[bool, str]:
    ans = answer.get("answer") if isinstance(answer.get("answer"), dict) else answer
    if not isinstance(ans, dict):
        return False, "bad_answer"
    status = str(ans.get("status", "")).lower()
    if status == "not_found":
        return True, "abstain"
    span = str(ans.get("span", "")).strip()
    if not span:
        return False, "missing_span"
    if span in page_text:
        return True, "ok"
    return False, "span_not_in_page"