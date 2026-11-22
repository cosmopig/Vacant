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
        if not isinstance(value, dict):
            raise ValueError("queue must be an object or a list of jobs")
        required(value, ("pending",))
        pending = objects(value["pending"], "pending")
        claimed = value.get("claimed", {})
        if not isinstance(claimed, dict):
            raise ValueError("claimed must be an object")
        claimed = objects(list(claimed.values()), "claimed")
        seen = set()
        for job in pending + claimed:
            required(job, ("id", "payload", "due", "attempts", "sequence"))
            if job["id"] in seen:
                raise ValueError("duplicate job")
            seen.add(job["id"])
        jobs = pending + claimed
        sequence = value.get("sequence", 0)
        if jobs:
            sequence = max(sequence, max(job["sequence"] for job in jobs) + 1)
        queue.pending = pending
        queue.claimed = {job["id"]: job for job in claimed}
        queue.sequence = sequence
    return queue


def load(path):
    return loads(Path(path).read_text(encoding="utf-8"))


def save(queue, path):
    Path(path).write_text(dumps(queue), encoding="utf-8")
