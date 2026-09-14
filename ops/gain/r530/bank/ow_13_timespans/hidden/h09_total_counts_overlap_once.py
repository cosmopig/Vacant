# anchor_kind: goal
# anchor: counting time that two systems both reported only once
# derivation: three heavily overlapping reports of the same hour total one hour,
# not three.


def run(solution):
    spans = [("2026-08-01T09:00:00", "2026-08-01T10:00:00"),
             ("2026-08-01T09:15:00", "2026-08-01T09:45:00"),
             ("2026-08-01T09:00:00", "2026-08-01T10:00:00")]
    got = solution.total_seconds(spans)
    assert got == 3600, "args=%r got=%r want=%r" % (spans, got, 3600)
