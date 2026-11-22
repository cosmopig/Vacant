"""Deduplicated work-log aggregation and atomic Markdown delivery."""
import json
import os
from pathlib import Path
import tempfile
import unicodedata
from checks import objects, integer, required, text


STATUSES = ("open", "done")


def _owner(value):
    if not isinstance(value, str):
        raise ValueError("owner must be nonempty text")
    return text(unicodedata.normalize("NFC", value), "owner")


def _event(row):
    required(row, ["id", "owner"])
    status = row.get("status", "open")
    if not isinstance(status, str) or status not in STATUSES:
        raise ValueError("invalid status")
    seconds = integer(row.get("seconds", 0), "seconds")
    return json.dumps(row["id"], sort_keys=True), (_owner(row["owner"]), status, seconds)


def summarize(rows):
    seen = {}
    totals = {}
    for row in objects(rows):
        key, event = _event(row)
        if key in seen:
            if seen[key] != event:
                raise ValueError("event conflict")
            continue
        seen[key] = event
        owner, status, seconds = event
        total, done = totals.get(owner, (0, 0))
        totals[owner] = (total + seconds, done + (status == "done"))
    ordered = sorted(totals.items(), key=lambda item: (-item[1][0], item[0].casefold(), item[0]))
    return [dict(owner=owner, seconds=value, done=done) for owner, (value, done) in ordered]


def escape(value):
    value = value.replace(chr(92), chr(92)*2).replace("|", chr(92)+"|")
    return value.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")


def render(rows):
    lines = ["# Work log", "", "| Owner | Seconds | Done |", "|---|---:|---:|"]
    lines.extend(f"| {escape(row['owner'])} | {row['seconds']} | {row['done']} |" for row in rows)
    return "\n".join(lines) + "\n"


def build(input_path="events.jsonl", output_path="REPORT.md"):
    from codec import load
    rows = summarize(load(input_path))
    output = Path(output_path)
    content = render(rows).encode("utf-8")
    fd, temp = tempfile.mkstemp(dir=output.parent or ".", prefix=".report-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
        os.replace(temp, output)
    except BaseException:
        if os.path.exists(temp):
            os.unlink(temp)
        raise
    return rows


if __name__ == "__main__":
    build()
