"""Reference solution for ow_08_logscan (gauge only; never enters a workspace)."""

import datetime
import math
import re
import sys

INTEGER = re.compile(r"^-?\d+$")


def is_timestamp(text):
    candidate = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        datetime.datetime.fromisoformat(candidate)
    except ValueError:
        return False
    return True


def parse_line(line):
    """(path, status, ms) for a good line, or None for a bad one."""
    fields = line.split(" ")
    if len(fields) != 5:
        return None
    stamp, _method, path, status, milliseconds = fields
    if not is_timestamp(stamp):
        return None
    if not INTEGER.match(status) or not INTEGER.match(milliseconds):
        return None
    return path, int(status), int(milliseconds)


def percentile(values, p):
    """Nearest-rank: the value at 1-based position ceil(p/100 * n)."""
    ordered = sorted(values)
    rank = math.ceil(p / 100 * len(ordered))
    return ordered[max(1, rank) - 1]


def summarize(lines):
    buckets = {}
    bad_lines = 0
    total = 0
    for raw in lines:
        line = raw.rstrip("\r\n")
        if not line.strip():
            continue
        total += 1
        parsed = parse_line(line)
        if parsed is None:
            bad_lines += 1
            continue
        path, status, milliseconds = parsed
        bucket = buckets.setdefault(path, {"n": 0, "errors": 0, "latencies": []})
        bucket["n"] += 1
        bucket["errors"] += 1 if status >= 500 else 0
        bucket["latencies"].append(milliseconds)

    endpoints = [{"path": path,
                  "n": bucket["n"],
                  "error_rate": round(bucket["errors"] / bucket["n"], 4),
                  "p50_ms": percentile(bucket["latencies"], 50),
                  "p95_ms": percentile(bucket["latencies"], 95)}
                 for path, bucket in buckets.items()]
    endpoints.sort(key=lambda row: (-row["n"], row["path"]))
    return {"endpoints": endpoints, "bad_lines": bad_lines, "total": total}


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("usage: python -m solution FILE\n")
        return 2
    with open(argv[1], encoding="utf-8") as handle:
        report = summarize(handle)
    width = max([len("path")] + [len(row["path"]) for row in report["endpoints"]])
    print("%-*s %6s %10s %8s %8s" % (width, "path", "n", "error_rate", "p50_ms", "p95_ms"))
    for row in report["endpoints"]:
        print("%-*s %6d %10.4f %8d %8d"
              % (width, row["path"], row["n"], row["error_rate"], row["p50_ms"], row["p95_ms"]))
    print("total=%d bad_lines=%d" % (report["total"], report["bad_lines"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
