"""Deduplicated work-log aggregation and atomic Markdown delivery."""
import os
from pathlib import Path
import tempfile
import unicodedata
from checks import objects, integer, text


def summarize(rows):
    totals = {}
    for row in objects(rows):
        owner = text(row["owner"], "owner")
        seconds, done = totals.get(owner, (0,0))
        totals[owner] = (seconds+row.get("seconds",0), done+(row.get("status")=="done"))
    return [dict(owner=owner, seconds=value, done=done)
            for owner, (value,done) in sorted(totals.items())]


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
