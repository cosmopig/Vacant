"""Versioned busy-window import/export."""
import json
from pathlib import Path
from checks import instant


def loads(raw):
    value = json.loads(raw)
    rows = value["busy"] if isinstance(value, dict) else value
    result = []
    for row in rows:
        if isinstance(row, dict):
            row = [row["start"], row["end"]]
        start, end = row
        if instant(end) < instant(start):
            raise ValueError("invalid busy interval")
        result.append([start, end])
    return result


def dumps(busy):
    return json.dumps({"version": 2, "busy": [
        {"start": instant(start).replace(tzinfo=None).isoformat(), "end": instant(end).replace(tzinfo=None).isoformat()}
        for start, end in busy]}, sort_keys=True)


def load(path):
    return loads(Path(path).read_text(encoding="utf-8"))


def save(busy, path):
    Path(path).write_text(dumps(busy), encoding="utf-8")
