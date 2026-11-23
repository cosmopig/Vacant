import json
import pytest
from service import Manifest, normalize
from codec import loads, dumps

def test_manifest_normalization_idempotency_and_cache():
    # SPEC §1
    # SPEC §2
    m = Manifest()
    assert m.total_size() == 0
    m.add("a/./x/../b", 3, "A"*64)
    m.add("a"+chr(92)+"b", 3, "a"*64)
    assert m.count() == 1 and m.total_size() == 3
    rows = m.entries()
    rows[0]["size"] = 999
    assert m.entries()[0]["size"] == 3
    m.remove("a//b")
    assert m.total_size() == 0
    with pytest.raises(KeyError) as exc:
        m.remove("a/./b")
    assert exc.value.args == ("a/b",)
    for path in ("../x", "/x", "C:/x", "a/..", ""):
        with pytest.raises(ValueError, match="^unsafe path$"):
            normalize(path)

def test_manifest_wire_and_conflicts():
    # SPEC §2
    # SPEC §4
    legacy = {"a/./b":{"size":2,"sha256":"F"*64}}
    m = loads(json.dumps(legacy))
    assert loads(dumps(m)).entries() == [{"path":"a/b","size":2,"digest":"f"*64}]
    with pytest.raises(ValueError, match="^path conflict$"):
        m.add("a/b", 3, "f"*64)
    bad = {"version":2,"entries":[{"path":"../escape","size":1,"digest":"a"*64}]}
    with pytest.raises(ValueError, match="^unsafe path$"):
        loads(json.dumps(bad))

def test_manifest_failed_addition_is_atomic():
    # SPEC §3
    m = Manifest()
    with pytest.raises(ValueError, match="^invalid digest$"):
        m.add("a", 2, "bad")
    with pytest.raises(ValueError, match="^size must be an integer >= 0$"):
        m.add("a", True, "a"*64)
    assert m.total_size() == 0 and m.entries() == []
