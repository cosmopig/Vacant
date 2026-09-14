# anchor_kind: contract
# anchor: Any trailing newline is not part of the line.
# derivation: lines read straight from a file keep their newline, which must not
# turn the last field into something non-numeric.


def run(solution):
    lines = ["2026-01-01T00:00:00Z GET /f 200 12\n",
             "2026-01-01T00:00:01Z GET /f 500 34\r\n"]
    got = solution.summarize(lines)
    assert got["bad_lines"] == 0, "args=%r got=%r want=%r" % (lines, got["bad_lines"], 0)
    endpoint = got["endpoints"][0]
    assert (endpoint["n"], endpoint["error_rate"]) == (2, 0.5), (
        "args=%r got=%r want=%r" % (lines, (endpoint["n"], endpoint["error_rate"]), (2, 0.5)))
