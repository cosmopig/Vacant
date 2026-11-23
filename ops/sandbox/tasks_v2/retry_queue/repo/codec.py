"""Retry queue persistence including outstanding claims."""
import json
from pathlib import Path
from checks import objects, required
from service import Queue


def dumps(queue):
    return json.dumps(queue.export(), sort_keys=True)


def loads(raw):
    value = json.loads(raw)
    queue = Queue()
    if isinstance(value, list):
        for row in objects(value):
            required(row, ("id", "payload", "due"))
            queue.push(row["id"], row["payload"], row["due"])
    else:
        queue.pending = value["pending"]
        queue.claimed = {}
        queue.sequence = value["sequence"]
    return queue


def load(path):
    return loads(Path(path).read_text(encoding="utf-8"))


def save(queue, path):
    Path(path).write_text(dumps(queue), encoding="utf-8")
