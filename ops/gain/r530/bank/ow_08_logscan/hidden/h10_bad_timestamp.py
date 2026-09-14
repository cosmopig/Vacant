# anchor_kind: contract
# anchor: or when the timestamp is not ISO8601
# derivation: a timestamp that is not a real date-time makes the line unusable even
# though the other four fields are fine.


def run(solution):
    lines = ["yesterday GET /s 200 1",
             "2026-13-45T99:99:99Z GET /s 200 1",
             "2026-01-01T00:00:00Z GET /s 200 1"]
    got = solution.summarize(lines)
    assert got["bad_lines"] == 2, "args=%r got=%r want=%r" % (lines, got["bad_lines"], 2)
    assert got["total"] == 3, "args=%r got=%r want=%r" % (lines, got["total"], 3)
