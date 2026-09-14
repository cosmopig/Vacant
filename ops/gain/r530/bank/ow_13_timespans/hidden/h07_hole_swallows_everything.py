# anchor_kind: contract
# anchor: `subtract` returns the union of `spans` with every instant covered by
# `holes` removed
# derivation: a hole that covers the whole stretch leaves nothing behind, and
# several holes together can do the same.


def run(solution):
    spans = [("2026-06-01T08:00:00", "2026-06-01T10:00:00")]
    got = solution.subtract(spans, [("2026-06-01T07:00:00", "2026-06-01T11:00:00")])
    assert got == [], "args=%r got=%r want=%r" % (spans, got, [])

    holes = [("2026-06-01T08:00:00", "2026-06-01T09:00:00"),
             ("2026-06-01T09:00:00", "2026-06-01T10:00:00")]
    got = solution.subtract(spans, holes)
    assert got == [], "args=%r got=%r want=%r" % ((spans, holes), got, [])
