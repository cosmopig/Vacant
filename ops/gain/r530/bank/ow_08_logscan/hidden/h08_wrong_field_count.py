# anchor_kind: contract
# anchor: A line is bad when it does not have exactly five fields
# derivation: too few fields and too many fields are both bad, and neither adds a
# request to any endpoint.


def run(solution):
    lines = ["2026-01-01T00:00:00Z GET /ok 200 1",
             "2026-01-01T00:00:01Z GET /short 200",
             "2026-01-01T00:00:02Z GET /long 200 1 extra"]
    got = solution.summarize(lines)
    assert got["bad_lines"] == 2, "args=%r got=%r want=%r" % (lines, got["bad_lines"], 2)
    assert len(got["endpoints"]) == 1, (
        "args=%r got=%r want=%r" % (lines, len(got["endpoints"]), 1))
