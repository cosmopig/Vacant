"""Known-bad B: close, with four ordinary slips.

Bad lines are survived and the five-hundreds rule is right, but the error share is
never rounded, the percentile index is a floor rather than a nearest rank, equally
busy endpoints come back in whatever order they were first seen, and blank lines
are counted as bad ones.
"""

import re

INTEGER = re.compile(r"^-?\d+$")


def _parse(line):
    fields = line.split(" ")
    if len(fields) != 5:
        return None
    stamp, _method, path, status, ms = fields
    if not re.match(r"^\d{4}-\d{2}-\d{2}T", stamp):
        return None
    if not INTEGER.match(status) or not INTEGER.match(ms):
        return None
    return path, int(status), int(ms)


def summarize(lines):
    order = []
    buckets = {}
    bad_lines = 0
    total = 0
    for raw in lines:
        line = raw.rstrip("\r\n")
        total += 1
        parsed = _parse(line)
        if parsed is None:
            bad_lines += 1
            continue
        path, status, ms = parsed
        if path not in buckets:
            buckets[path] = {"n": 0, "errors": 0, "latencies": []}
            order.append(path)
        buckets[path]["n"] += 1
        if status >= 500:
            buckets[path]["errors"] += 1
        buckets[path]["latencies"].append(ms)

    endpoints = []
    for path in order:
        bucket = buckets[path]
        ordered = sorted(bucket["latencies"])
        n = len(ordered)
        endpoints.append({"path": path, "n": bucket["n"],
                          "error_rate": bucket["errors"] / bucket["n"],
                          "p50_ms": ordered[int(n * 0.5)] if int(n * 0.5) < n else ordered[-1],
                          "p95_ms": ordered[int(n * 0.95)] if int(n * 0.95) < n else ordered[-1]})
    endpoints.sort(key=lambda row: -row["n"])
    return {"endpoints": endpoints, "bad_lines": bad_lines, "total": total}
