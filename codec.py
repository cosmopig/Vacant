"""Projection persistence and legacy inventory import."""
import json
from pathlib import Path
from checks import objects, required, integer, text, snapshot
from service import Projection, normalize


def _load_legacy(rows, projection):
    for row in objects(rows):
        required(row, ("sku", "quantity"))
        sku = text(row["sku"], "sku")
        if sku in projection.state:
            raise ValueError("duplicate sku: " + sku)
        projection.state[sku] = {"version": 0,
                                 "quantity": integer(row["quantity"], "quantity")}


def _load_snapshot(value, projection):
    if value.get("version") != 2:
        raise ValueError("unsupported snapshot version")
    state = value.get("state", {})
    seen = value.get("seen", {})
    if not isinstance(state, dict) or not isinstance(seen, dict):
        raise ValueError("snapshot state and seen must be objects")
    for sku, item in state.items():
        sku = text(sku, "sku")
        if not isinstance(item, dict):
            raise ValueError("state entries must be objects")
        required(item, ("version", "quantity"))
        quantity = item["quantity"]
        if quantity is not None:
            quantity = integer(quantity, "quantity")
        projection.state[sku] = {"version": integer(item["version"], "version"),
                                 "quantity": quantity}
    for event_id, event in seen.items():
        if not isinstance(event, dict) or normalize(event)[0] != event_id:
            raise ValueError("invalid event history")
        projection.seen[event_id] = snapshot(event)


def loads(raw):
    projection = Projection()
    if raw is None or not str(raw).strip():
        return projection
    value = json.loads(raw)
    if value is None:
        return projection
    if isinstance(value, list):
        _load_legacy(value, projection)
    elif isinstance(value, dict):
        _load_snapshot(value, projection)
    else:
        raise ValueError("snapshot must be a list or an object")
    return projection


def dumps(projection):
    return json.dumps(projection.export(), sort_keys=True)


def load(path):
    return loads(Path(path).read_text(encoding="utf-8"))


def save(projection, path):
    Path(path).write_text(dumps(projection), encoding="utf-8")
