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


def _csv_line(fields):
    out = io.StringIO(newline="")
    csv.writer(out, lineterminator="\r\n").writerow(fields)
    return out.getvalue()[:-2] + "\n"


def dumps(rows):
    header = _csv_line(["email", "name", "roles", "active"])
    return header + "".join(_csv_line([row["email"], row["name"], "|".join(row["roles"]),
                                      str(row["active"]).lower()])
                            for row in merge_roster(rows, []))


def load(path):
    with Path(path).open(encoding="utf-8", newline="") as stream:
        return loads(stream.read())


def save(rows, path):
    with Path(path).open("w", encoding="utf-8", newline="") as stream:
        stream.write(dumps(rows))
