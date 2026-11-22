"""Versioned catalog snapshots and file adapter."""
import json
from pathlib import Path
from checks import objects, required
from service import Catalog


def loads(raw):
    data = json.loads(raw)
    if isinstance(data, dict):
        if data.get("version") != 2:
            raise ValueError("unsupported snapshot version")
        required(data, ("items",))
        rows = data["items"]
    else:
        rows = data
    catalog = Catalog()
    for row in objects(rows):
        required(row, ("name", "price"))
        aliases = row.get("aliases", [])
        if not isinstance(aliases, list):
            raise ValueError("aliases must be a list")
        catalog.add(row["name"], row["price"], aliases)
    return catalog


def dumps(catalog):
    return json.dumps({"version": 2, "items": catalog.export()}, ensure_ascii=False, sort_keys=True)


def load(path):
    return loads(Path(path).read_text(encoding="utf-8"))


def save(catalog, path):
    Path(path).write_text(dumps(catalog), encoding="utf-8")
