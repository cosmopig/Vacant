"""Legacy-compatible usage log serialization."""
import json
from checks import objects, required
from service import Usage


def loads(raw):
    usage = Usage()
    for row in objects(json.loads(raw)):
        required(row, ("tenant", "time", "units"))
        usage.add(row["tenant"], row["time"], row["units"], row.get("id"))
    return usage


def dumps(usage):
    return json.dumps(usage.export(), sort_keys=True, separators=(",", ":"))


def load(path):
    from pathlib import Path
    return loads(Path(path).read_text(encoding="utf-8"))


def save(usage, path):
    from pathlib import Path
    Path(path).write_text(dumps(usage), encoding="utf-8")
