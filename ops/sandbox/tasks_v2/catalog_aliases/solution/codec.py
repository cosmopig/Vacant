"""Versioned catalog snapshots and file adapter."""
import json
from pathlib import Path
from checks import objects, required
from service import Catalog


def loads(raw):
    data = json.loads(raw)
    rows = data["items"] if isinstance(data, dict) else data
    catalog = Catalog()
    for row in objects(rows):
        required(row, ("name", "price"))
        catalog.add(row["name"], row["price"], row.get("aliases", ()))
    return catalog


def dumps(catalog):
    return json.dumps({"version": 2, "items": catalog.export()}, ensure_ascii=False, sort_keys=True)


def load(path):
    return loads(Path(path).read_text(encoding="utf-8"))


def save(catalog, path):
    Path(path).write_text(dumps(catalog), encoding="utf-8")
