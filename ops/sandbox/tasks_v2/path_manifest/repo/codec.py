"""Manifest snapshots with normalization at both wire entry points."""
import json
from pathlib import Path
from checks import objects
from service import Manifest


def loads(raw):
    value = json.loads(raw)
    if value.get("version") == 2:
        rows = objects(value["entries"])
    else:
        rows = [{"path": path, "size": item["size"], "digest": item["sha256"]}
                for path, item in value.items()]
    manifest = Manifest()
    for row in rows:
        manifest._entries[row["path"]] = dict(row)
    return manifest


def dumps(manifest):
    return json.dumps({"version": 2, "entries": manifest.entries()}, sort_keys=True)


def load(path):
    return loads(Path(path).read_text(encoding="utf-8"))


def save(manifest, path):
    Path(path).write_text(dumps(manifest), encoding="utf-8")
