"""Manifest snapshots with normalization at both wire entry points."""
import json
from pathlib import Path
from checks import objects, required
from service import Manifest


def loads(raw):
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("manifest must be an object")
    if value.get("version") == 2 and not isinstance(value["version"], bool):
        rows = objects(value.get("entries"), "entries")
        rows = [(row["path"], row["size"], row["digest"])
                for row in (required(row, ("path", "size", "digest")) for row in rows)]
    else:
        rows = []
        for path, item in value.items():
            item = required(item, ("size", "sha256"))
            rows.append((path, item["size"], item["sha256"]))
    manifest = Manifest()
    for path, size, digest in rows:
        manifest.add(path, size, digest)
    return manifest


def dumps(manifest):
    return json.dumps({"version": 2, "entries": manifest.entries()}, sort_keys=True)


def load(path):
    return loads(Path(path).read_text(encoding="utf-8"))


def save(manifest, path):
    Path(path).write_text(dumps(manifest), encoding="utf-8")
