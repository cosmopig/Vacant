"""Legacy-array and JSONL work-log reader."""
import json
from pathlib import Path
from checks import objects


def loads(raw):
    if raw.lstrip().startswith("["):
        return [json.loads(raw)]
    return objects([json.loads(line) for line in raw.splitlines() if line.strip()])


def dumps(rows):
    return "".join(json.dumps(row, ensure_ascii=False, sort_keys=True)+"\n" for row in objects(rows))


def load(path):
    return loads(Path(path).read_text(encoding="utf-8"))


def save(rows, path):
    Path(path).write_text(dumps(rows), encoding="utf-8")


def iter_rows(path):
    yield from load(path)
