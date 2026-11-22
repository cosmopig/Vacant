"""JSON-array and JSONL transaction reader."""
import json
from pathlib import Path
from checks import objects


def _defaults(rows):
    for row in rows:
        row.setdefault("kind", "sale")
        row.setdefault("status", "posted")
    return rows


def loads(raw):
    stripped = raw.lstrip()
    if stripped.startswith("["):
        return _defaults(objects(json.loads(stripped)))
    records = []
    for line in raw.split("\n"):
        if line.endswith("\r"):
            line = line[:-1]
        if line.strip():
            records.append(json.loads(line))
    return _defaults(objects(records))


def dumps(rows):
    return json.dumps(objects(rows), ensure_ascii=False, sort_keys=True)


def load(path):
    return loads(Path(path).read_text(encoding="utf-8"))


def save(rows, path):
    Path(path).write_text(dumps(rows), encoding="utf-8")


def iter_rows(path):
    yield from load(path)
