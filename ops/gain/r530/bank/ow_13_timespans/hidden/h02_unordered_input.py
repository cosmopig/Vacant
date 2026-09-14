# anchor_kind: goal
# anchor: The periods arrive in no particular order
# derivation: the same set of periods handed over in a different order gives the
# same tidy list, sorted by when each stretch starts.


def run(solution):
    spans = [("2026-01-05", "2026-01-06"), ("2026-01-01", "2026-01-02"),
             ("2026-01-03", "2026-01-04")]
    got = solution.merge(spans)
    want = [("2026-01-01T00:00:00", "2026-01-02T00:00:00"),
            ("2026-01-03T00:00:00", "2026-01-04T00:00:00"),
            ("2026-01-05T00:00:00", "2026-01-06T00:00:00")]
    assert got == want, "args=%r got=%r want=%r" % (spans, got, want)
    assert solution.merge(list(reversed(spans))) == want, (
        "args=%r got=%r want=%r" % (list(reversed(spans)), solution.merge(list(reversed(spans))), want))
