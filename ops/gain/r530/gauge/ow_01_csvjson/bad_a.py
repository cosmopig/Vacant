"""Known-bad A: splits on commas and newlines with str.split.

The single most common way this task is got wrong: no quote handling at all, and
no field-count validation, so a quoted comma silently creates an extra column.
"""

import json
import sys


def csv_to_jsonl(text):
    lines = [ln for ln in text.split("\n") if ln]
    if not lines:
        return ""
    header = lines[0].split(",")
    out = []
    for line in lines[1:]:
        values = line.split(",")
        out.append(json.dumps(dict(zip(header, values))))
    return "".join(s + "\n" for s in out)


def main(argv):
    with open(argv[1], encoding="utf-8") as handle:
        sys.stdout.write(csv_to_jsonl(handle.read()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
