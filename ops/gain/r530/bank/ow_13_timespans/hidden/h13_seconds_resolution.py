# anchor_kind: contract
# anchor: `total_seconds` returns the number of whole seconds covered by the union,
# as an `int`.
# derivation: a one-second stretch is one second, and a stretch across a day
# boundary is counted through it.


def run(solution):
    got = solution.total_seconds([("2026-01-01T00:00:00", "2026-01-01T00:00:01")])
    assert got == 1, "args=%r got=%r want=%r" % ("one second", got, 1)
    got = solution.total_seconds([("2026-01-01T23:59:00", "2026-01-02T00:01:00")])
    assert got == 120, "args=%r got=%r want=%r" % ("across midnight", got, 120)
