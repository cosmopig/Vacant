"""Typed receipt checks for Filing-Evidence JSON answers (visible: quote, header scale, sign)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

_NUM = re.compile(r"(-?\d[\d,]*(?:\.\d+)?)")


def _scale_to_mult(scale: Any) -> float:
    if scale is None:
        return 1.0
    if isinstance(scale, (int, float)) and scale < 20:
        return float(10 ** int(scale))
    s = str(scale).lower()
    if "million" in s:
        return 1e6
    if "billion" in s:
        return 1e9
    if "thousand" in s:
        return 1e3
    return 1.0


def parse_header_scale(page_text: str) -> float:
    t = page_text.lower()
    if "in billions" in t or "(billions)" in t:
        return 1e9
    if "in millions" in t or "(millions)" in t:
        return 1e6
    if "in thousands" in t:
        return 1e3
    return 1.0


@dataclass
class TypedVerdict:
    ok: bool
    reason: str


def _answer_payload(ans: Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(ans.get("answer"), dict):
        return ans["answer"]
    return ans


def _numbers_in_line(line: str) -> list[float]:
    out = []
    for m in _NUM.findall(line):
        try:
            out.append(float(m.replace(",", "")))
        except ValueError:
            pass
    return out


def check_answer_typed(
    row: Mapping[str, Any],
    page_text: str,
    *,
    gold: Mapping[str, Any] | None = None,
    for_audit: bool = False,
) -> TypedVerdict:
    """Gold-free runtime check. `for_audit` enables optional gold-only diagnostics (not used in stop rule)."""
    _ = for_audit, gold
    ans = _answer_payload(row)
    status = str(ans.get("status", "found")).lower()
    if status in ("not_found", "none", ""):
        return TypedVerdict(False, "not_found")

    span = str(ans.get("span", ""))
    if not span or span not in page_text:
        return TypedVerdict(False, "provenance_fail")

    raw_val = ans.get("value")
    if raw_val is None:
        return TypedVerdict(False, "no_value")
    try:
        shown = float(raw_val)
    except (TypeError, ValueError):
        return TypedVerdict(False, "bad_value")

    header_scale = parse_header_scale(page_text)
    if ans.get("scale") is not None:
        ans_scale = _scale_to_mult(ans.get("scale"))
        if header_scale >= 1e6 and ans_scale >= 1e9:
            return TypedVerdict(False, "scale_mismatch")
        if header_scale >= 1e6 and ans_scale <= 1e3 and ans_scale > 1:
            return TypedVerdict(False, "scale_mismatch")
        if header_scale >= 1e9 and ans_scale <= 1e6 and ans_scale > 1:
            return TypedVerdict(False, "scale_mismatch")

    nums = _numbers_in_line(span)
    cmp_val = abs(shown)
    if nums and not any(abs(cmp_val - abs(n)) <= max(0.5, 0.001 * abs(n)) for n in nums):
        return TypedVerdict(False, "value_not_in_span")

    return TypedVerdict(True, "ok")