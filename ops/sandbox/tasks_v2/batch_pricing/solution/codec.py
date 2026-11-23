"""Legacy tier object and modern ordered-pair adapter."""
import json
from pathlib import Path
from service import validate_tiers


def loads(raw):
    value = json.loads(raw)
    if isinstance(value, dict):
        value = sorted(((int(k), v) for k, v in value.items() if k != "*"), key=lambda pair: pair[0]) + (
            [(None, value["*"])] if "*" in value else [])
    return [(upper, str(rate)) for upper, rate in validate_tiers(value)]


def dumps(tiers):
    return json.dumps([[upper, str(rate)] for upper, rate in validate_tiers(tiers)])


def load(path):
    return loads(Path(path).read_text(encoding="utf-8"))


def save(tiers, path):
    Path(path).write_text(dumps(tiers), encoding="utf-8")
