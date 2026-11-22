"""Legacy-array and JSONL work-log reader."""
import json
from pathlib import Path
from checks import objects


def _defaults(rows):
    for row in rows:
        row.setdefault("status", "open")
        row.setdefault("seconds", 0)
    return rows


def loads(raw):
    if raw.startswith("\ufeff"):
        raw = raw[1:]
    if raw.lstrip().startswith("["):
        return _defaults(objects(json.loads(raw)))
    records = [line[:-1] if line.endswith("\r") else line for line in raw.split("\n")]
    return _defaults(objects([json.loads(line) for line in records if line.strip()]))


def dumps(rows):
    return "".join(json.dumps(row, ensure_ascii=False, sort_keys=True)+"\n" for row in objects(rows))


def load(path):
    return loads(Path(path).read_text(encoding="utf-8"))


def save(rows, path):
    Path(path).write_text(dumps(rows), encoding="utf-8")


def iter_rows(path):
    yield from load(path)
