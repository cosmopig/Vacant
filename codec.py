"""Versioned busy-window import/export."""
import json
from pathlib import Path
from checks import instant


def _row(row):
    if isinstance(row, dict):
        if "start" not in row or "end" not in row:
            raise ValueError("invalid busy interval")
        row = [row["start"], row["end"]]
    if not isinstance(row, list) or len(row) != 2:
        raise ValueError("invalid busy interval")
    start, end = row
    if instant(end) < instant(start):
        raise ValueError("invalid busy interval")
    return [start, end]


def loads(raw):
    value = json.loads(raw)
    if isinstance(value, dict):
        if value.get("version") != 2 or isinstance(value.get("version"), bool):
            raise ValueError("unsupported busy version")
        rows = value.get("busy")
    else:
        rows = value
    if not isinstance(rows, list):
        raise ValueError("busy must be a list")
    return [_row(row) for row in rows]


def dumps(busy):
    rows = []
    for row in busy:
        start, end = _row(list(row) if isinstance(row, tuple) else row)
        rows.append({"start": instant(start).isoformat(), "end": instant(end).isoformat()})
    return json.dumps({"version": 2, "busy": rows}, sort_keys=True)


def load(path):
    return loads(Path(path).read_text(encoding="utf-8"))


def save(busy, path):
    Path(path).write_text(dumps(busy), encoding="utf-8")
