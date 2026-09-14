# anchor_kind: goal
# anchor: They also want to know how many lines were unusable
# derivation: the count of unusable lines is part of the answer and keeps rising
# through a file that is mostly rubbish, without the run stopping.


def run(solution):
    lines = ["rubbish %d" % index for index in range(20)]
    lines.insert(10, "2026-01-01T00:00:00Z GET /one 200 9")
    got = solution.summarize(lines)
    assert got["bad_lines"] == 20, "args=%r got=%r want=%r" % ("20 junk + 1 good", got["bad_lines"], 20)
    assert got["total"] == 21, "args=%r got=%r want=%r" % ("20 junk + 1 good", got["total"], 21)
    assert got["endpoints"][0]["path"] == "/one", (
        "args=%r got=%r want=%r" % ("20 junk + 1 good", got["endpoints"], "/one survives"))
