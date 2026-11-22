"""CSV roster interchange, independent from caller-owned rows."""
import csv
import io
from pathlib import Path
from service import merge_roster

HEADER = ["email", "name", "roles", "active"]
LEGACY_HEADER = ["email", "name"]


def loads(raw):
    if raw.startswith("\ufeff"):
        raw = raw[1:]
    reader = csv.reader(io.StringIO(raw, newline=""))
    header = next(reader, None)
    if header is None:
        return []
    if header not in (HEADER, LEGACY_HEADER):
        raise ValueError("invalid header")
    rows = []
    for fields in reader:
        if not fields:
            continue
        if len(fields) > len(header):
            raise ValueError("invalid row")
        row = dict(zip(header, fields))
        if "active" in row:
            if row["active"] not in ("true", "false"):
                raise ValueError("invalid active")
            row["active"] = row["active"] == "true"
        rows.append(row)
    return merge_roster(rows, [])


def dumps(rows):
    out = io.StringIO(newline="")
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(HEADER)
    for row in merge_roster(rows, []):
        writer.writerow([row["email"], row["name"], "|".join(row["roles"]),
                         "true" if row["active"] else "false"])
    return out.getvalue()


def load(path):
    with Path(path).open(encoding="utf-8", newline="") as stream:
        return loads(stream.read())


def save(rows, path):
    with Path(path).open("w", encoding="utf-8", newline="") as stream:
        stream.write(dumps(rows))
