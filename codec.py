"""Legacy tier object and modern ordered-pair adapter."""
import json
from decimal import Decimal
from pathlib import Path
from service import validate_tiers


def loads(raw):
    value = json.loads(raw, parse_float=Decimal)
    if isinstance(value, dict):
        try:
            pairs = [(int(upper), rate) for upper, rate in value.items() if upper != "*"]
        except ValueError:
            raise ValueError("invalid tiers") from None
        pairs.sort(key=lambda pair: pair[0])
        if "*" in value:
            pairs.append((None, value["*"]))
        value = pairs
    return [(upper, str(rate)) for upper, rate in validate_tiers(value)]


def dumps(tiers):
    return json.dumps([[upper, str(rate)] for upper, rate in validate_tiers(tiers)])


def load(path):
    return loads(Path(path).read_text(encoding="utf-8"))


def save(tiers, path):
    Path(path).write_text(dumps(tiers), encoding="utf-8")
