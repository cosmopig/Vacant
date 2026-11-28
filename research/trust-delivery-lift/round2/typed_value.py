"""Typed value equality for extraction (GAP_MAP §破口 5).

Separates scale, sign, currency, period, units, and required sets —
not naive numeric strip-and-compare.
"""
from __future__ import annotations

import re
from typing import Any

_CURRENCY = re.compile(r"^[A-Z]{3}$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _parse_amount(s: str) -> tuple[float | None, str | None, float]:
    """Return (value, currency, scale_multiplier)."""
    s = s.strip()
    cur_m = re.search(r"\b(USD|EUR|GBP|JPY|CHF|CAD|AUD)\b", s, re.I)
    currency = cur_m.group(1).upper() if cur_m else None
    if "us$" in s.lower():
        currency = currency or "USD"
    sign = -1.0 if re.search(r"^\s*-|loss|\(\d", s, re.I) else 1.0
    num_m = re.search(r"(\d[\d,]*(?:\.\d+)?)", s.replace(",", ""))
    if not num_m:
        return None, currency, 1.0
    val = float(num_m.group(1)) * sign
    sl = s.lower()
    mult = 1.0
    if re.search(r"\b(billion|bn)\b", sl):
        mult = 1e9
    elif re.search(r"million|\bmm\b|\b3m\b|\$3m|us\$3m", sl) or re.search(r"\d+\s*m\b", sl):
        mult = 1e6
    elif re.search(r"\bthousand\b|\bk\b", sl):
        mult = 1e3
    if "us$" in sl and mult == 1.0 and "m" in sl:
        mult = 1e6
    return val, currency, mult


def typed_equal(field_kind: str, got: str, exp: str) -> bool:
  # field_kind: money | percent | date | currency | text | set | int
    if field_kind == "currency":
        return got.strip().upper() == exp.strip().upper()
    if field_kind == "date":
        return _DATE.match(got.strip()) and got.strip() == exp.strip()
    if field_kind == "text":
        return got.strip().lower() == exp.strip().lower()
    if field_kind == "set":
        gt = {x.strip().lower() for x in re.split(r"[,;|]", got) if x.strip()}
        et = {x.strip().lower() for x in re.split(r"[,;|]", exp) if x.strip()}
        return gt == et
    if field_kind == "percent":
        def p(x: str) -> float | None:
            m = re.search(r"(-?\d+(?:\.\d+)?)", x)
            if not m:
                return None
            v = float(m.group(1))
            if "%" not in x and "percent" not in x.lower() and abs(v) <= 1.0:
                v *= 100
            return v

        g, e = p(got), p(exp)
        bare_num = ("%" not in got and "percent" not in got.lower()) or (
            "%" not in exp and "percent" not in exp.lower()
        )
        if bare_num and ("%" in got or "percent" in got.lower()) != ("%" in exp or "percent" in exp.lower()):
            return False
        return g is not None and e is not None and abs(g - e) < 0.05
    if field_kind in ("money", "int"):
        if field_kind == "int":
            gm = re.search(r"-?\d+", got.replace(",", ""))
            em = re.search(r"-?\d+", exp.replace(",", ""))
            return gm and em and int(gm.group()) == int(em.group())
        gv, gc, gs = _parse_amount(got)
        ev, ec, es = _parse_amount(exp)
        if gv is None or ev is None:
            return False
        if gc and ec and gc != ec:
            return False
        return abs(gv * gs - ev * es) < 0.01 * max(1.0, abs(ev * es))
    return got.strip() == exp.strip()


def typed_differ(field_kind: str, a: str, b: str) -> bool:
    return not typed_equal(field_kind, a, b)


def control_suite() -> list[dict[str, Any]]:
    must_equal = [
        ("money", "USD 3 million", "US$3m"),
        ("money", "EUR 1.2 million", "€1,200,000.00"),
        ("date", "2024-06-30", "2024-06-30"),
        ("currency", "USD", "usd"),
        ("percent", "10%", "10 percent"),
        ("int", "1,250", "1250"),
    ]
    must_differ = [
        ("money", "USD 3 million", "USD 3 billion"),
        ("money", "USD 5 bn", "USD 5 m"),
        ("int", "-3", "3"),
        ("percent", "10%", "10"),
        ("money", "USD 10", "JPY 10"),
        ("money", "USD 120 million", "USD 120 thousand"),
        ("date", "2024-06-30", "2023-06-30"),
        ("set", "AAPL, MSFT", "AAPL"),
        ("currency", "USD", "EUR"),
    ]
    rows = []
    for cat, kind, a, b in [("must_equal", *x) for x in must_equal] + [("must_differ", *x) for x in must_differ]:
        eq = typed_equal(kind, a, b)
        rows.append({"cat": cat, "field_kind": kind, "a": a, "b": b, "equal": eq, "differ": typed_differ(kind, a, b)})
    return rows


def assert_controls() -> None:
    for row in control_suite():
        if row["cat"] == "must_equal":
            assert row["equal"], row
        else:
            assert row["differ"], row