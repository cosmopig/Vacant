import json
import pytest
from service import Catalog
from codec import dumps, loads
from cli import dispatch


def make():
    c = Catalog()
    c.add("Tea", 250, ["Chai"])
    c.add("Café", 300)
    return c


def test_rename_warm_cache_and_aliases():
    c = make()
    assert c.lookup("chai")["name"] == "Tea"
    c.rename("Tea", "Green Tea")
    for n in ("tea", "chai", "GREEN TEA"):
        got = c.lookup(n)
        assert got == {"name": "Green Tea", "price": 250, "aliases": ["Chai", "Tea"]}


def test_rename_same_normalized_only_spelling():
    c = make()
    c.rename("tea", " TEA ")
    assert c.lookup("tea") == {"name": "TEA", "price": 250, "aliases": ["Chai"]}


def test_rename_to_own_alias():
    c = make()
    c.rename("Tea", "chai")
    assert c.lookup("tea") == {"name": "chai", "price": 250, "aliases": ["Tea"]}


def test_nfc_and_collision_atomic():
    c = make()
    c.lookup("cafe\u0301")
    with pytest.raises(ValueError, match="name collision"):
        c.rename("Tea", "CAFE\u0301")
    with pytest.raises(ValueError, match="name collision"):
        c.add("x", 1, ["chai"])
    assert c.lookup("chai")["name"] == "Tea"
    with pytest.raises(KeyError):
        c.lookup("x")
    assert c.lookup("café")["aliases"] == []


def test_errors():
    c = make()
    with pytest.raises(KeyError) as e:
        c.lookup(" MISSING ")
    assert e.value.args == ("missing",)
    with pytest.raises(KeyError):
        c.rename("nope", "x")
    with pytest.raises(ValueError, match="name must be nonempty text"):
        c.add("  ", 1)
    with pytest.raises(ValueError, match="name must be nonempty text"):
        c.rename("Tea", "")


def test_isolation():
    c = Catalog()
    aliases = ["A"]
    c.add("N", 1, aliases)
    aliases.append("B")
    snap = c.lookup("n")
    snap["aliases"].append("Z")
    assert c.lookup("n")["aliases"] == ["A"]


def test_codec_roundtrip_and_legacy():
    c = make()
    c.rename("Tea", "Green Tea")
    raw = dumps(c)
    again = loads(raw)
    assert dumps(again) == raw
    assert again.lookup("tea")["name"] == "Green Tea"
    assert [i["name"] for i in json.loads(raw)["items"]] == ["Green Tea", "Café"]
    legacy = loads(json.dumps([{"name": "Tea", "price": 1}]))
    assert legacy.lookup("tea")["aliases"] == []
    assert dumps(loads(dumps(Catalog()))) == dumps(Catalog())
    assert dumps(loads("[]")) == dumps(Catalog())


def test_cli_dispatch():
    out = dispatch({"items": [{"name": "Tea", "price": 1, "aliases": ["Chai"]}],
                    "renames": [{"old": "chai", "new": "Black Tea"}]})
    assert out["items"] == [{"name": "Black Tea", "price": 1, "aliases": ["Chai", "Tea"]}]
