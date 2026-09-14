"""Known-bad B: correct quoting, but the records are cut into lines first.

Uses the csv module one line at a time, which is the usual way people lose
newlines embedded in quoted fields, and builds the object with setdefault, which
silently makes the *first* of two identical header names win.
"""

import csv
import json
import sys


def csv_to_jsonl(text):
    lines = text.splitlines()
    if not lines:
        return ""
    header = next(csv.reader([lines[0]]))
    out = []
    for number, raw in enumerate(lines[1:], start=2):
        if not raw:
            continue
        values = next(csv.reader([raw]))
        if len(values) != len(header):
            raise ValueError("line %d: expected %d fields, got %d"
                             % (number, len(header), len(values)))
        obj = {}
        for name, value in zip(header, values):
            obj.setdefault(name, value)
        out.append(json.dumps(obj, ensure_ascii=False))
    return "".join(s + "\n" for s in out)


def main(argv):
    try:
        with open(argv[1], encoding="utf-8") as handle:
            out = csv_to_jsonl(handle.read())
    except ValueError as exc:
        sys.stderr.write("%s\n" % exc)
        return 2
    sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
