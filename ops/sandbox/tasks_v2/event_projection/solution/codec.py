"""Projection persistence and legacy inventory import."""
import json
from pathlib import Path
from checks import objects, required, integer
from service import Projection


def loads(raw):
    value = json.loads(raw)
    projection = Projection()
    if isinstance(value, list):
        for row in objects(value):
            required(row, ("sku", "quantity"))
            projection.state[row["sku"]] = {"quantity": integer(row["quantity"], "quantity"), "version": 0}
    else:
        projection.state = value["state"]
        projection.seen = value["seen"]
    return projection


def dumps(projection):
    return json.dumps(projection.export(), sort_keys=True)


def load(path):
    return loads(Path(path).read_text(encoding="utf-8"))


def save(projection, path):
    Path(path).write_text(dumps(projection), encoding="utf-8")
