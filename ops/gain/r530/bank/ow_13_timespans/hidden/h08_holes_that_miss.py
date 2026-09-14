# anchor_kind: contract
# anchor: `subtract` returns the union of `spans`
# derivation: holes that fall entirely outside a stretch, or that only touch its
# edge, take nothing away from it.


def run(solution):
    spans = [("2026-07-01T10:00:00", "2026-07-01T12:00:00")]
    holes = [("2026-07-01T08:00:00", "2026-07-01T10:00:00"),
             ("2026-07-01T12:00:00", "2026-07-01T14:00:00"),
             ("2026-07-02", "2026-07-03")]
    got = solution.subtract(spans, holes)
    want = [("2026-07-01T10:00:00", "2026-07-01T12:00:00")]
    assert got == want, "args=%r got=%r want=%r" % ((spans, holes), got, want)
