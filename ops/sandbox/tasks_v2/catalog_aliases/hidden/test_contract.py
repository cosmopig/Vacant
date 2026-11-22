import pytest
from service import Catalog
from codec import dumps, loads

def test_alias_rename_warm_cache_unicode_and_wire():
    # SPEC §1
    # SPEC §2
    # SPEC §4
    c = Catalog()
    aliases = ["STRASSE"]
    c.add("Café", 200, aliases)
    c.lookup("strasse")
    c.rename("cafe\u0301", "Coffee")
    assert c.lookup("straße")["name"] == "Coffee"
    assert c.lookup("café")["aliases"] == ["STRASSE", "Café"]
    aliases.append("unrelated")
    c = loads(dumps(c))
    assert c.lookup("Café")["name"] == "Coffee"
    c.rename("Coffee", " COFFEE ")
    assert c.lookup("coffee")["aliases"] == ["STRASSE", "Café"]
    assert loads(dumps(Catalog())).export() == []

def test_alias_collision_is_atomic_and_snapshots_detached():
    # SPEC §3
    c = Catalog()
    c.add("A", 1, ["first"])
    c.add("B", 2)
    before = dumps(c)
    with pytest.raises(ValueError, match="^name collision$"):
        c.rename("first", "b")
    assert dumps(c) == before
    view = c.lookup("a")
    view["aliases"].append("intruder")
    with pytest.raises(KeyError) as exc:
        c.lookup(" INTRUDER ")
    assert exc.value.args == ("intruder",)
    with pytest.raises(ValueError, match="^name must be nonempty text$"):
        c.lookup(" ")

def test_alias_legacy_input():
    # SPEC §4
    assert loads('[{"name":"A","price":2}]').lookup("a") == {"name":"A","price":2,"aliases":[]}
