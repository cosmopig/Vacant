# anchor_kind: goal
# anchor: Blank lines are just noise from the rotation script and should not count
# as anything at all.
# derivation: an empty or whitespace-only line is neither a request nor a bad line,
# so neither total nor bad_lines moves.


def run(solution):
    lines = ["", "   ", "\t", "2026-01-01T00:00:00Z GET /z 200 1", "", "\n"]
    got = solution.summarize(lines)
    assert got["total"] == 1, "args=%r got=%r want=%r" % (lines, got["total"], 1)
    assert got["bad_lines"] == 0, "args=%r got=%r want=%r" % (lines, got["bad_lines"], 0)
