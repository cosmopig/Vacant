import json
import pytest
from service import Manifest
from codec import dumps, loads

A, B = "a" * 64, "B" * 64


@pytest.mark.parametrize("bad", ["", "/x", "C:/x", "c:x", "..", "a/../..", "./.", "\\\\srv\\x"])
def test_unsafe_paths(bad):
    with pytest.raises(ValueError, match="unsafe path"):
        Manifest().add(bad, 1, A)


def test_normalization_case_unicode_and_idempotence():
    m = Manifest()
    m.add("Dir\\.\\sub//../Ünï.TXT", 2, B)
    m.add("Dir/Ünï.TXT", 2, B.lower())
    assert m.entries() == [{"path": "Dir/Ünï.TXT", "size": 2, "digest": "b" * 64}]
    assert m.total_size() == 2
    with pytest.raises(ValueError, match="path conflict"):
        m.add("./Dir/Ünï.TXT", 3, B)
    assert m.total_size() == 2


def test_errors_are_atomic_and_cache_invalidated():
    m = Manifest()
    assert m.total_size() == 0 and m.entries() == []
    with pytest.raises(ValueError, match="invalid digest"):
        m.add("x", 1, "z" * 64)
    for size in (-1, True, 1.0):
        with pytest.raises(ValueError, match=r"size must be an integer >= 0"):
            m.add("x", size, A)
    assert m.entries() == [] and m.total_size() == 0
    m.add("x", 1, A)
    assert m.total_size() == 1
    m.add("y", 4, A)
    assert m.total_size() == 5
    m.remove("./y")
    assert m.total_size() == 1
    with pytest.raises(KeyError) as exc:
        m.remove("a\\..\\y")
    assert exc.value.args == ("y",)


def test_entries_detached_and_sorted():
    m = Manifest()
    m.add("b", 1, A)
    m.add("a", 2, A)
    rows = m.entries()
    assert [r["path"] for r in rows] == ["a", "b"]
    rows[0]["size"] = 99
    assert m.total_size() == 3


def test_codec_v2_and_legacy_route_through_add():
    legacy = loads(json.dumps({"x\\y": {"size": 1, "sha256": B}, "z": {"size": 2, "sha256": A}}))
    assert legacy.entries()[0] == {"path": "x/y", "size": 1, "digest": "b" * 64}
    raw = dumps(legacy)
    assert raw == json.dumps(json.loads(raw), sort_keys=True)
    again = loads(raw)
    assert again.entries() == legacy.entries() and again.total_size() == 3
    with pytest.raises(ValueError, match="path conflict"):
        loads(json.dumps({"version": 2, "entries": [
            {"path": "a", "size": 1, "digest": A}, {"path": "./a", "size": 2, "digest": A}]}))
    with pytest.raises(ValueError, match="unsafe path"):
        loads(json.dumps({"version": 2, "entries": [{"path": "../a", "size": 1, "digest": A}]}))
    with pytest.raises(ValueError, match="unsafe path"):
        loads(json.dumps({"/etc/x": {"size": 1, "sha256": A}}))
