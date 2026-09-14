# anchor_kind: goal
# anchor: two bookings where one ends exactly when the next begins are one busy
# stretch, not two
# derivation: the end instant is not covered, so there is no gap between the two and
# they come back as a single span.


def run(solution):
    spans = [("2026-01-01T09:00:00", "2026-01-01T10:00:00"),
             ("2026-01-01T10:00:00", "2026-01-01T11:00:00")]
    got = solution.merge(spans)
    want = [("2026-01-01T09:00:00", "2026-01-01T11:00:00")]
    assert got == want, "args=%r got=%r want=%r" % (spans, got, want)
