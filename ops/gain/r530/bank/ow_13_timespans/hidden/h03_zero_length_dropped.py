# anchor_kind: goal
# anchor: A period with no length is not a period at all.
# derivation: a span whose start and end are the same covers nothing, so it neither
# appears in the tidy list nor joins its neighbours together.


def run(solution):
    spans = [("2026-02-01T00:00:00", "2026-02-01T00:00:00"),
             ("2026-02-01T05:00:00", "2026-02-01T06:00:00")]
    got = solution.merge(spans)
    want = [("2026-02-01T05:00:00", "2026-02-01T06:00:00")]
    assert got == want, "args=%r got=%r want=%r" % (spans, got, want)

    got = solution.merge([("2026-02-01", "2026-02-01")])
    assert got == [], "args=%r got=%r want=%r" % ([("2026-02-01", "2026-02-01")], got, [])
