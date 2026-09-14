# anchor_kind: goal
# anchor: Some systems send a date only and some send a time of day as well
# derivation: a date on its own is the midnight that starts that day, so it joins
# with a timed span that runs up to that same midnight.


def run(solution):
    spans = [("2026-04-01", "2026-04-02"),
             ("2026-04-02T00:00:00", "2026-04-02T06:00:00")]
    got = solution.merge(spans)
    want = [("2026-04-01T00:00:00", "2026-04-02T06:00:00")]
    assert got == want, "args=%r got=%r want=%r" % (spans, got, want)
    assert solution.total_seconds([("2026-04-01", "2026-04-02")]) == 86400, (
        "args=%r got=%r want=%r" % ("one whole day", solution.total_seconds([("2026-04-01", "2026-04-02")]), 86400))
