"""Shared boundary validation for the public service and wire adapter."""
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation


def text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(field + " must be nonempty text")
    return value.strip()


def integer(value, field, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(field + " must be an integer >= " + str(minimum))
    return value


def number(value, field):
    if isinstance(value, bool):
        raise ValueError(field + " must be finite")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(field + " must be finite") from None
    if not result.is_finite():
        raise ValueError(field + " must be finite")
    return result


def instant(value, field="time"):
    try:
        result = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError(field + " must include an offset") from None
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError(field + " must include an offset")
    return result.astimezone(timezone.utc)


def objects(value, field="rows"):
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise ValueError(field + " must be a list of objects")
    return deepcopy(value)


def required(row, names):
    if not isinstance(row, dict):
        raise ValueError("row must be an object")
    missing = [name for name in names if name not in row]
    if missing:
        raise ValueError("missing fields: " + ", ".join(missing))
    return row


def unique(values, field):
    result = list(values)
    if len(result) != len(set(result)):
        raise ValueError(field + " must be unique")
    return result


def choice(value, allowed, field):
    if value not in allowed:
        raise ValueError(field + " must be one of " + ", ".join(sorted(allowed)))
    return value


def snapshot(value):
    return deepcopy(value)
