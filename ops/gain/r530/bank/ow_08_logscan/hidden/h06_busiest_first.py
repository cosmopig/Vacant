# anchor_kind: goal
# anchor: They want the busiest endpoints at the top
# derivation: the ordering is by request count from large to small, whatever order
# the paths were first seen in.


def run(solution):
    lines = (["2026-01-01T00:00:00Z GET /rare 200 1"]
             + ["2026-01-01T00:00:0%d GET /busy 200 1" % (i % 10) for i in range(5)]
             + ["2026-01-01T00:00:0%d GET /mid 200 1" % (i % 10) for i in range(3)])
    got = [row["path"] for row in solution.summarize(lines)["endpoints"]]
    want = ["/busy", "/mid", "/rare"]
    assert got == want, "args=%r got=%r want=%r" % ("1 rare, 5 busy, 3 mid", got, want)
