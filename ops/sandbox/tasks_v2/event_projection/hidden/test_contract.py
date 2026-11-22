import pytest
from service import Projection
from codec import loads, dumps

def event(id, sku="A", version=1, kind="set", quantity=3):
    return dict(id=id, sku=sku, version=version, kind=kind, quantity=quantity)

def test_projection_tombstones_cache_and_stale_events():
    # SPEC §1
    # SPEC §3
    # SPEC §4
    p = loads('[{"sku":"A","quantity":9}]')
    assert p.items()[0]["quantity"] == 9
    p.apply([event("del", version=3, kind="delete")])
    p = loads(dumps(p))
    p.apply([event("old", version=2), event("same", version=3)])
    assert p.items() == []
    p.apply([event("new", sku="Z", version=1), event("revive", version=4)])
    assert [row["sku"] for row in p.items()] == ["A", "Z"]
    view = p.items()
    view[0]["quantity"] = 999
    assert p.quantity("A") == 3

def test_projection_atomic_batch_and_reserved_stale_ids():
    # SPEC §2
    # SPEC §3
    p = Projection()
    p.apply([event("new", version=2), event("old", version=1)])
    before = dumps(p)
    p.items()
    with pytest.raises(ValueError, match="^unknown kind$"):
        p.apply([event("fresh", version=3), event("bad", kind="wat")])
    assert dumps(p) == before
    with pytest.raises(ValueError, match="^event conflict$"):
        p.apply([event("old", version=4)])
    p.apply([event("new", version=2)])
    assert dumps(p) == before
    with pytest.raises(ValueError, match="^quantity must be an integer >= 0$"):
        p.apply([event("bad", quantity=True)])
    p.apply([])
    assert dumps(p) == before

def test_projection_seen_ids_survive_wire():
    # SPEC §2
    # SPEC §4
    p = Projection()
    p.apply([event("a")])
    p = loads(dumps(p))
    with pytest.raises(ValueError, match="^event conflict$"):
        p.apply([event("a", version=2)])
