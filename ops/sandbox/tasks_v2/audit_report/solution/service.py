"""Deduplicated work-log aggregation and atomic Markdown delivery."""
import os
from pathlib import Path
import tempfile
import unicodedata
from checks import objects, integer, text


def summarize(rows):
    seen = {}
    totals = {}
    for row in objects(rows):
        id = text(row["id"], "id")
        if id in seen:
            if seen[id] != row:
                raise ValueError("event conflict")
            continue
        seen[id] = row
        owner = unicodedata.normalize("NFC", text(row["owner"], "owner"))
        seconds = integer(row.get("seconds", 0), "seconds")
        status = row.get("status", "open")
        if status not in ("open", "done"):
            raise ValueError("invalid status")
        value, done = totals.get(owner, (0, 0))
        totals[owner] = (value + seconds, done + (status == "done"))
    result = [dict(owner=owner, seconds=value, done=done) for owner, (value, done) in totals.items()]
    return sorted(result, key=lambda row: (-row["seconds"], row["owner"].casefold(), row["owner"]))


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
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="", dir=output.parent, delete=False) as stream:
        temp = stream.name
        stream.write(render(rows))
    os.replace(temp, output)
    return rows


if __name__ == "__main__":
    build()
