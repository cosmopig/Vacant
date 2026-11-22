import json
import pytest
from service import Projection
from codec import dumps, loads
from cli import dispatch


def ev(i, sku, v, kind="set", q=None):
    e = {"id": i, "sku": sku, "version": v, "kind": kind}
    if q is not None:
        e["quantity"] = q
    return e


def test_versions_and_tombstones():
    p = Projection()
    p.apply([ev("1", "B", 2, q=5), ev("2", "A", 1, q=1), ev("3", "B", 1, q=9),
             ev("4", "A", 2, "delete"), ev("5", "A", 2, q=7)])
    assert p.items() == [{"sku": "B", "quantity": 5, "version": 2}]
    p.apply([ev("6", "A", 3, q=4)])
    assert p.quantity("A") == 4


def test_ids_global_and_reserved():
    p = Projection()
    p.apply([ev("1", "A", 2, q=1), ev("2", "A", 1, q=3)])
    p.apply([ev("2", "A", 1, q=3)])
    with pytest.raises(ValueError, match="event conflict"):
        p.apply([ev("2", "B", 1, q=3)])
    with pytest.raises(ValueError, match="event conflict"):
        p.apply([ev("9", "A", 5, q=1), ev("9", "A", 6, q=1)])


@pytest.mark.parametrize("bad, msg", [
    (ev("x", "A", 9, "bump"), "unknown kind"),
    (ev("x", "A", 9, q=-1), "quantity must be an integer >= 0"),
    (ev("x", "A", 9), "quantity must be an integer >= 0"),
    (ev("x", "A", 9, q=True), "quantity must be an integer >= 0"),
    (ev("1", "A", 9, q=2), "event conflict"),
])
def test_batch_atomic(bad, msg):
    p = Projection()
    p.apply([ev("1", "A", 1, q=1)])
    view = p.items()
    before = dumps(p)
    with pytest.raises(ValueError, match=msg):
        p.apply([ev("2", "A", 5, q=8), ev("3", "C", 1, q=1), bad])
    assert dumps(p) == before
    assert p.items() == view
    p.apply([ev("2", "A", 5, q=8)])
    assert p.quantity("A") == 8


def test_detached():
    p = Projection()
    batch = [ev("1", "A", 1, q=1)]
    p.apply(batch)
    batch[0]["quantity"] = 99
    p.items()[0]["quantity"] = 50
    assert p.quantity("A") == 1
    p.apply([ev("1", "A", 1, q=1)])


def test_snapshot_roundtrip():
    p = Projection()
    p.apply([ev("1", "A", 3, q=2), ev("2", "B", 2, "delete")])
    raw = dumps(p)
    data = json.loads(raw)
    assert data["version"] == 2 and data["state"]["B"] == {"version": 2, "quantity": None}
    q = loads(raw)
    assert dumps(q) == raw
    q.apply([ev("3", "B", 1, q=5)])
    assert q.items() == [{"sku": "A", "quantity": 2, "version": 3}]
    with pytest.raises(ValueError, match="event conflict"):
        q.apply([ev("1", "A", 9, q=1)])


def test_legacy_and_empty():
    p = loads(json.dumps([{"sku": "A", "quantity": 4}]))
    assert p.items() == [{"sku": "A", "quantity": 4, "version": 0}] and p.seen == {}
    p.apply([ev("1", "A", 1, q=2)])
    assert p.quantity("A") == 2
    assert loads("").items() == [] and loads("[]").items() == []
    view = p.items()
    p.apply([])
    assert p.items() == view


def test_cli_dispatch():
    out = dispatch({"inventory": [{"sku": "A", "quantity": 1}],
                    "events": [ev("1", "A", 1, q=3)]})
    assert out["items"] == [{"sku": "A", "quantity": 3, "version": 1}]
    assert loads(json.dumps(out["snapshot"])).quantity("A") == 3
