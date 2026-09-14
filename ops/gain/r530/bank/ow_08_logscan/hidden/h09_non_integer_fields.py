# anchor_kind: contract
# anchor: when `STATUS` or `MS` is not a run of digits with an optional leading `-`
# derivation: a status or a duration that is not an integer makes the line
# unusable, and a negative one does not.


def run(solution):
    lines = ["2026-01-01T00:00:00Z GET /n 20x 5",
             "2026-01-01T00:00:01Z GET /n 200 5.5",
             "2026-01-01T00:00:02Z GET /n 200 -3"]
    got = solution.summarize(lines)
    assert got["bad_lines"] == 2, "args=%r got=%r want=%r" % (lines, got["bad_lines"], 2)
    assert got["endpoints"][0]["n"] == 1, (
        "args=%r got=%r want=%r" % (lines, got["endpoints"][0]["n"], 1))
