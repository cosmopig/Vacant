"""CSV roster interchange, independent from caller-owned rows."""
import csv
import io
from pathlib import Path
from service import merge_roster


def loads(raw):
    rows = []
    for row in csv.DictReader(io.StringIO(raw)):
        if "active" in row:
            if row["active"] not in ("true", "false"):
                raise ValueError("invalid active")
            row["active"] = row["active"] == "true"
        rows.append(row)
    return merge_roster(rows, [])


def dumps(rows):
    out = io.StringIO(newline="")
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["email", "name", "roles", "active"])
    for row in merge_roster(rows, []):
        writer.writerow([row["email"], row["name"], "|".join(row["roles"]), str(row["active"]).lower()])
    return out.getvalue()


def load(path):
    return loads(Path(path).read_text(encoding="utf-8"))


def save(rows, path):
    Path(path).write_text(dumps(rows), encoding="utf-8")
