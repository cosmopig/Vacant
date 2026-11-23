"""Configuration document wire adapter."""
import json
from pathlib import Path
from checks import snapshot, text


def loads(raw):
    value = json.loads(raw)
    if "config" not in value:
        value = {"include": [], "config": value}
    includes = value.get("include", [])
    if not isinstance(includes, list):
        raise ValueError("include must be a list")
    return {"include": [text(name, "include") for name in includes],
            "config": snapshot(value["config"])}


def dumps(document):
    return json.dumps({"include": document.get("include", []),
                       "config": document["config"]}, sort_keys=True)


def load(path):
    return loads(Path(path).read_text(encoding="utf-8"))


def save(document, path):
    Path(path).write_text(dumps(document), encoding="utf-8")
