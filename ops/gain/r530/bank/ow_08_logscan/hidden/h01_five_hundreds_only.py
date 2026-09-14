# anchor_kind: goal
# anchor: Failed means the server's own fault, the five-hundreds; a client sending
# a bad request is not a failure of theirs.
# derivation: a run of four-hundreds contributes nothing to the error share, while
# a single five-hundred does.


def run(solution):
    lines = ["2026-01-01T00:00:00Z GET /q 400 1",
             "2026-01-01T00:00:01Z GET /q 401 1",
             "2026-01-01T00:00:02Z GET /q 404 1",
             "2026-01-01T00:00:03Z GET /q 499 1"]
    got = solution.summarize(lines)["endpoints"][0]["error_rate"]
    assert got == 0.0, "args=%r got=%r want=%r" % ("four four-hundreds", got, 0.0)

    lines.append("2026-01-01T00:00:04Z GET /q 500 1")
    got = solution.summarize(lines)["endpoints"][0]["error_rate"]
    assert got == 0.2, "args=%r got=%r want=%r" % ("one five-hundred in five", got, 0.2)
