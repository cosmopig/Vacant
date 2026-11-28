"""No-model baseline: header scale + rightmost/largest date column heuristic."""
from __future__ import annotations

import re
from typing import Any, Mapping

from typed_filing_check import _numbers_in_line, parse_header_scale

_DATE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")


def rule_answer(question: Mapping[str, Any], page_text: str) -> dict[str, Any]:
    gold = question.get("gold") or {}
    label = str(gold.get("label") or "").lower()
    lines = page_text.splitlines()
    best_line = ""
    for line in lines:
        if label and label.split()[-1] in line.lower():
            best_line = line
    if not best_line:
        for line in lines:
            if any(tok in line.lower() for tok in label.split()[:2] if tok):
                best_line = line
                break
    nums = _numbers_in_line(best_line)
    if not nums:
        return {"status": "not_found"}
    val = nums[-1]  # latest column heuristic
    scale = parse_header_scale(page_text)
    scale_s = "in millions" if scale >= 1e6 else "in billions" if scale >= 1e9 else "units"
    return {
        "status": "found",
        "value": val,
        "scale": scale_s,
        "span": best_line.strip(),
        "page": (question.get("page_labels") or [0])[0],
    }