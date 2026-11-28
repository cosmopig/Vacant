"""Typed deliverable scorer with visible/hidden separation (P0).

Visible checks may inform repair feedback during the run. Hidden checks grade only
after collection. Includes synthetic must-equal / must-differ controls.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class FieldSpec:
    id: str
    ftype: str  # year | int | money | percent | text | set
    required: bool = True
    aliases: tuple[str, ...] = ()


_MONEY_RE = re.compile(
    r"(?P<sign>−|-)?\s*(?P<cur>USD|EUR|US\$|€|JPY|¥)?\s*"
    r"(?P<num>\d[\d,]*(?:\.\d+)?)\s*(?P<scale>m|million|bn|billion|k|thousand|trillion|t)?",
    re.I,
)
_PERCENT_RE = re.compile(r"(?P<num>-?\d+(?:\.\d+)?)\s*%?")
_YEAR_RE = re.compile(r"\b(1[89]\d{2}|20\d{2})\b")


def _norm_text(s: str) -> str:
    return " ".join(s.strip().lower().split())


def parse_money(s: str) -> dict[str, Any] | None:
    m = _MONEY_RE.search(s.replace("US$", "USD "))
    if not m:
        return None
    num = float(m.group("num").replace(",", ""))
    sign = -1.0 if m.group("sign") else 1.0
    raw_cur = (m.group("cur") or "").upper()
    cur = raw_cur or "USD"
    for tok, code in (("US$", "USD"), ("€", "EUR"), ("¥", "JPY"), ("CAD", "CAD"), ("CHF", "CHF"),
                      ("GBP", "GBP"), ("AUD", "AUD"), ("NOK", "NOK")):
        if tok in s.upper():
            cur = code
            break
    cur = cur.replace("US$", "USD")
    scale = (m.group("scale") or "").lower()
    mult = {
        "k": 1e3,
        "thousand": 1e3,
        "m": 1e6,
        "million": 1e6,
        "bn": 1e9,
        "b": 1e9,
        "billion": 1e9,
        "t": 1e12,
        "trillion": 1e12,
    }.get(scale, 1.0)
    return {"currency": cur, "amount": sign * num * mult}


def parse_percent(s: str) -> float | None:
    m = _PERCENT_RE.fullmatch(s.strip())
    if not m:
        m = _PERCENT_RE.search(s.strip())
    if not m:
        return None
    v = float(m.group("num"))
    if "%" not in s and abs(v) <= 1.0:
        return v * 100.0
    return v


def parse_year(s: str) -> int | None:
    m = _YEAR_RE.search(s)
    return int(m.group(1)) if m else None


def parse_int(s: str) -> int | None:
    m = re.search(r"-?\d[\d,]*", s.replace(",", ""))
    return int(m.group(0)) if m else None


def values_equal(ftype: str, got: str, exp: str) -> bool:
    if ftype == "text":
        return _norm_text(got) == _norm_text(exp)
    if ftype == "set":
        def tok(x: str) -> set[str]:
            return {_norm_text(t) for t in re.split(r"[,;|/]", x) if t.strip()}

        return tok(got) == tok(exp)
    if ftype == "year":
        return parse_year(got) == parse_year(exp)
    if ftype == "int":
        return parse_int(got) == parse_int(exp)
    if ftype == "percent":
        gh, eh = "%" in got or "percent" in got.lower(), "%" in exp or "percent" in exp.lower()
        if gh != eh:
            return False
        g, e = parse_percent(got), parse_percent(exp)
        return g is not None and e is not None and abs(g - e) < 0.05
    if ftype == "money":
        g, e = parse_money(got), parse_money(exp)
        if not g or not e:
            return False
        return g["currency"] == e["currency"] and abs(g["amount"] - e["amount"]) < 1e-6 * max(1.0, abs(e["amount"]))
    return _norm_text(got) == _norm_text(exp)


def values_differ(ftype: str, a: str, b: str) -> bool:
    return not values_equal(ftype, a, b)


def load_fields(task: Mapping[str, Any]) -> list[FieldSpec]:
    out: list[FieldSpec] = []
    for f in task["fields"]:
        out.append(
            FieldSpec(
                id=f["id"],
                ftype=f["type"],
                required=bool(f.get("required", True)),
                aliases=tuple(f.get("aliases", ())),
            )
        )
    return out


def parse_delivery(raw: str) -> dict[str, str]:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```\s*$", "", raw)
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(obj, dict):
        return {}
    return {str(k): ("" if v is None else str(v)) for k, v in obj.items()}


@dataclass
class FieldVerdict:
    field_id: str
    visible_ok: bool
    hidden_ok: bool
    got: str | None
    detail: str


def visible_check(got: str | None, spec: FieldSpec) -> tuple[bool, str]:
    if got is None or not str(got).strip():
        if spec.required:
            return False, "missing_or_empty"
        return True, "optional_empty"
    s = str(got).strip()
    if spec.ftype == "year" and parse_year(s) is None:
        return False, "bad_year_format"
    if spec.ftype == "int" and parse_int(s) is None:
        return False, "bad_int_format"
    if spec.ftype == "money" and parse_money(s) is None:
        return False, "bad_money_format"
    if spec.ftype == "percent" and parse_percent(s) is None:
        return False, "bad_percent_format"
    return True, "ok"


def grade_task(task: Mapping[str, Any], delivery: Mapping[str, str]) -> dict[str, Any]:
    fields = load_fields(task)
    gold = task["gold"]
    field_rows: list[FieldVerdict] = []
    for spec in fields:
        got = delivery.get(spec.id)
        vis_ok, vis_detail = visible_check(got, spec)
        hid_ok = False
        if got is not None and spec.id in gold:
            hid_ok = values_equal(spec.ftype, got, str(gold[spec.id]))
        elif not spec.required and (got is None or not str(got).strip()):
            hid_ok = spec.id not in gold or gold[spec.id] in (None, "")
        field_rows.append(FieldVerdict(spec.id, vis_ok, hid_ok, got, vis_detail))

    required = [f for f in fields if f.required]
    whole_success = all(
        fr.hidden_ok for fr in field_rows if any(r.id == fr.field_id for r in required)
    )
    all_required_present = all(
        fr.visible_ok for fr in field_rows if any(r.id == fr.field_id and r.required for r in required)
    )

    return {
        "whole_success": whole_success,
        "all_required_present": all_required_present,
        "fields": [
            {
                "id": fr.field_id,
                "visible_ok": fr.visible_ok,
                "hidden_ok": fr.hidden_ok,
                "got": fr.got,
                "detail": fr.detail,
            }
            for fr in field_rows
        ],
    }


def synthetic_control_suite() -> list[dict[str, Any]]:
    """Must-equal and must-differ cases for scorer regression."""
    rows = []
    must_equal = [
        ("year", "1976", "Founded in 1976"),
        ("year", "2020", "est. 2020"),
        ("money", "USD 3 million", "US$3m"),
        ("percent", "10%", "10 percent"),
        ("text", "Acme Corp", "acme corp"),
    ]
    must_differ = [
        ("money", "USD 3 million", "USD 3 billion"),
        ("money", "USD 5 bn", "USD 5 m"),
        ("int", "-3", "3"),
        ("percent", "10%", "10"),  # 10% vs 10 (parsed as different when strict)
        ("money", "USD 10", "JPY 10"),
    ]
    for ftype, a, b in must_equal:
        rows.append(
            {
                "cat": "must_equal",
                "ftype": ftype if ftype != "sign" else "int",
                "a": a,
                "b": b,
                "equal": values_equal(ftype if ftype != "sign" else "int", a, b),
            }
        )
    for ftype, a, b in must_differ:
        rows.append(
            {
                "cat": "must_differ",
                "ftype": ftype,
                "a": a,
                "b": b,
                "differ": values_differ(ftype, a, b),
            }
        )
    return rows


def assert_scorer_controls() -> None:
    suite = synthetic_control_suite()
    for row in suite:
        if row["cat"] == "must_equal":
            assert row["equal"], f"expected equal: {row}"
        else:
            assert row["differ"], f"expected differ: {row}"