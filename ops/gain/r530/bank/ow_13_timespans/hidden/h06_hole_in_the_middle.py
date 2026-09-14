# anchor_kind: goal
# anchor: a way to work out what is left once certain periods are taken out of it
# derivation: a hole strictly inside a busy stretch leaves two stretches, one on
# each side of it.


def run(solution):
    spans = [("2026-06-01T08:00:00", "2026-06-01T18:00:00")]
    holes = [("2026-06-01T12:00:00", "2026-06-01T13:00:00")]
    got = solution.subtract(spans, holes)
    want = [("2026-06-01T08:00:00", "2026-06-01T12:00:00"),
            ("2026-06-01T13:00:00", "2026-06-01T18:00:00")]
    assert got == want, "args=%r got=%r want=%r" % ((spans, holes), got, want)
