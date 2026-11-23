"""JSON-array and JSONL transaction reader."""
import json
from pathlib import Path
from checks import objects


def loads(raw):
    stripped = raw.lstrip()
    if stripped.startswith("["):
        return objects(json.loads(stripped))
    return objects([json.loads(line) for line in raw.split("\n") if line.strip()])


def dumps(rows):
    return json.dumps(objects(rows), ensure_ascii=False, sort_keys=True)


def load(path):
    return loads(Path(path).read_text(encoding="utf-8"))


def save(rows, path):
    Path(path).write_text(dumps(rows), encoding="utf-8")


def iter_rows(path):
    yield from load(path)
