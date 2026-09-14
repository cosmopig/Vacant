"""Known-bad A: counts four-hundreds as failures and sorts by name.

It also trusts the line to have five fields, so a truncated line takes the run
down with it.
"""


def summarize(lines):
    buckets = {}
    total = 0
    for raw in lines:
        line = raw.strip()
        total += 1
        stamp, method, path, status, ms = line.split(" ")
        bucket = buckets.setdefault(path, {"n": 0, "errors": 0, "latencies": []})
        bucket["n"] += 1
        if int(status) >= 400:
            bucket["errors"] += 1
        bucket["latencies"].append(int(ms))

    endpoints = []
    for path in sorted(buckets):
        bucket = buckets[path]
        ordered = sorted(bucket["latencies"])
        endpoints.append({"path": path, "n": bucket["n"],
                          "error_rate": bucket["errors"] / bucket["n"],
                          "p50_ms": ordered[len(ordered) // 2],
                          "p95_ms": ordered[-1]})
    return {"endpoints": endpoints, "bad_lines": 0, "total": total}
