import copy
import pytest
from service import merge, resolve, effective
from codec import dumps, loads

def test_config_deletion_lists_and_isolation():
    # SPEC §1
    base = {"db":{"host":"a","port":1},"tags":[1],"drop":0}
    patch = {"db":{"host":None},"tags":[None,2],"drop":None,"absent":None}
    original = copy.deepcopy((base, patch))
    result = merge(base, patch)
    assert result == {"db":{"port":1},"tags":[None,2]}
    result["tags"].append(3)
    assert (base, patch) == original
    clone = merge(base, {})
    clone["db"]["host"] = "other"
    assert base["db"]["host"] == "a"

def test_config_diamond_cycle_and_environment():
    # SPEC §2
    # SPEC §3
    docs = {"root":{"config":{"x":1}},
            "a":{"include":["root"],"config":{"x":2}},
            "b":{"include":["root"],"config":{"y":3}},
            "app":{"include":["a","b"],"config":{"z":4}}}
    assert resolve("app", docs) == {"x":1,"y":3,"z":4}
    assert effective("app", docs, {"x":None}) == {"y":3,"z":4}
    assert effective("app", docs)["x"] == 1
    docs["root"]["include"] = ["app"]
    with pytest.raises(ValueError, match="^include cycle: app$"):
        resolve("app", docs)
    with pytest.raises(KeyError) as exc:
        resolve("missing", docs)
    assert exc.value.args == ("missing",)

def test_config_legacy_and_include_validation():
    # SPEC §4
    assert loads('{"x":1}') == {"include":[],"config":{"x":1}}
    assert loads(dumps({"config":{}})) == {"include":[],"config":{}}
    document = {"include":["z", "a"], "config":{}}
    assert loads(dumps(document)) == document
    with pytest.raises(ValueError, match="^include must be a list$"):
        loads('{"include":"x","config":{}}')
