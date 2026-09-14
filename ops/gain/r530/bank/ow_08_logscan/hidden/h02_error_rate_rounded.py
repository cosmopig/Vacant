# anchor_kind: contract
# anchor: rounded to four decimal places
# derivation: one failure in three is 0.3333 exactly, not the full repeating float.


def run(solution):
    lines = ["2026-01-01T00:00:00Z GET /r 500 1",
             "2026-01-01T00:00:01Z GET /r 200 1",
             "2026-01-01T00:00:02Z GET /r 200 1"]
    got = solution.summarize(lines)["endpoints"][0]["error_rate"]
    assert got == 0.3333, "args=%r got=%r want=%r" % ("one in three", got, 0.3333)

    lines = ["2026-01-01T00:00:0%d GET /r %d 1" % (i, 500 if i == 0 else 200) for i in range(7)]
    got = solution.summarize(lines)["endpoints"][0]["error_rate"]
    assert got == 0.1429, "args=%r got=%r want=%r" % ("one in seven", got, 0.1429)
