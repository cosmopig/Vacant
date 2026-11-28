"""Runtime acceptance checks for invoice extraction (no gold labels)."""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Mapping

from typed_value import typed_equal

FIELDS = (
    "vendor",
    "invoice_date",
    "due_date",
    "currency",
    "subtotal",
    "tax",
    "total",
    "order_id",
)

ISO4217 = re.compile(r"^[A-Z]{3}$")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ORDER_ID = re.compile(r"^[A-Z0-9-]{6,16}$")


def parse_json_delivery(raw: str) -> dict[str, str]:
    s = raw.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```\s*$", "", s)
    try:
        obj = json.loads(s)
    except json.JSONDecodeError:
        return {}
    if not isinstance(obj, dict):
        return {}
    return {str(k): ("" if v is None else str(v).strip()) for k, v in obj.items()}


def _float(s: str) -> float | None:
    s = s.replace(",", "").replace("$", "").strip()
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def _date(s: str) -> datetime | None:
    if not ISO_DATE.match(s):
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        return None


def allowed_currencies(task: Mapping[str, Any]) -> set[str]:
    return {c.upper() for c in task.get("allowed_currencies", ["USD", "EUR", "GBP"])}


def provenance_ok(value: str, source: str, field: str) -> bool:
    v = value.strip()
    if not v:
        return False
    src = source
    if field in ("vendor", "order_id"):
        return v.lower() in src.lower()
    if field == "currency":
        return v.upper() in src.upper()
    if field in ("invoice_date", "due_date"):
        return v in src
    if field in ("subtotal", "tax", "total"):
        num = _float(v)
        if num is None:
            return False
        # require integer or .xx representation in source
        plain = f"{num:.2f}".rstrip("0").rstrip(".")
        alt = f"{num:,.2f}"
        return plain in src.replace(",", "") or alt.replace(",", "") in src.replace(",", "") or str(int(num)) in src
    return v in src


def check_field(field: str, value: str | None, task: Mapping[str, Any], doc: Mapping[str, str]) -> tuple[bool, str]:
    if value is None or not str(value).strip():
        return False, "missing"
    v = str(value).strip()
    src = task["source_text"]
    if field == "vendor":
        if len(v) < 2:
            return False, "vendor_short"
        if not provenance_ok(v, src, field):
            return False, "provenance"
        return True, "ok"
    if field == "currency":
        if not ISO4217.match(v.upper()):
            return False, "bad_currency"
        if v.upper() not in allowed_currencies(task):
            return False, "currency_not_in_doc"
        if not provenance_ok(v, src, field):
            return False, "provenance"
        return True, "ok"
    if field in ("invoice_date", "due_date"):
        if not _date(v):
            return False, "bad_date"
        if not provenance_ok(v, src, field):
            return False, "provenance"
        return True, "ok"
    if field in ("subtotal", "tax", "total"):
        if _float(v) is None:
            return False, "bad_amount"
        if not provenance_ok(v, src, field):
            return False, "provenance"
        return True, "ok"
    if field == "order_id":
        if not ORDER_ID.match(v.upper()):
            return False, "bad_order_id"
        if not provenance_ok(v, src, field):
            return False, "provenance"
        return True, "ok"
    return False, "unknown_field"


def check_global(doc: Mapping[str, str], task: Mapping[str, Any]) -> tuple[bool, str]:
    inv, due = _date(doc.get("invoice_date", "")), _date(doc.get("due_date", ""))
    if inv and due and due < inv:
        return False, "due_before_invoice"
    st, tx, tot = _float(doc.get("subtotal", "")), _float(doc.get("tax", "")), _float(doc.get("total", ""))
    if st is not None and tx is not None and tot is not None:
        if abs(st + tx - tot) > 0.01:
            return False, "arith_mismatch"
    return True, "ok"


def visible_all_pass(doc: Mapping[str, str], task: Mapping[str, Any]) -> tuple[bool, dict[str, tuple[bool, str]]]:
    per: dict[str, tuple[bool, str]] = {}
    ok = True
    for f in FIELDS:
        passed, reason = check_field(f, doc.get(f), task, doc)
        per[f] = (passed, reason)
        ok = ok and passed
    if ok:
        gok, gre = check_global(doc, task)
        per["__global__"] = (gok, gre)
        ok = ok and gok
    return ok, per


def oracle_whole(doc: Mapping[str, str], task: Mapping[str, Any]) -> bool:
    if not task.get("answerable", True):
        return False  # never "correct" to hallucinate a full invoice
    gold = task["gold"]
    for f in FIELDS:
        if f not in gold:
            return False
        gv, dv = str(gold[f]).strip(), str(doc.get(f, "")).strip()
        if f == "currency":
            if not typed_equal("currency", dv, gv):
                return False
        elif f in ("subtotal", "tax", "total"):
            cur = str(doc.get("currency") or gold.get("currency", "USD"))
            got_m = f"{cur} {dv}" if cur else dv
            exp_m = f"{cur} {gv}" if cur else gv
            if not typed_equal("money", got_m, exp_m) and _float(gv) != _float(dv):
                return False
        elif gv != dv:
            return False
    return True