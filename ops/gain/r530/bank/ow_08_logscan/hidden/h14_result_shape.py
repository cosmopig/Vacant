# anchor_kind: contract
# anchor: The result has exactly this shape
# derivation: the three top-level keys and the five per-endpoint keys are fixed,
# the counts are ints and the percentiles are ints, and an empty log still has the
# shape.


def run(solution):
    empty = solution.summarize([])
    assert empty == {"endpoints": [], "bad_lines": 0, "total": 0}, (
        "args=%r got=%r want=%r" % ([], empty, {"endpoints": [], "bad_lines": 0, "total": 0}))

    lines = ["2026-01-01T00:00:00Z GET /k 500 8"]
    got = solution.summarize(lines)
    assert sorted(got) == ["bad_lines", "endpoints", "total"], (
        "args=%r got=%r want=%r" % (lines, sorted(got), ["bad_lines", "endpoints", "total"]))
    row = got["endpoints"][0]
    assert sorted(row) == ["error_rate", "n", "p50_ms", "p95_ms", "path"], (
        "args=%r got=%r want=%r" % (lines, sorted(row),
                                    ["error_rate", "n", "p50_ms", "p95_ms", "path"]))
    kinds = (type(row["n"]).__name__, type(row["p50_ms"]).__name__,
             type(row["error_rate"]).__name__, type(row["path"]).__name__)
    assert kinds == ("int", "int", "float", "str"), (
        "args=%r got=%r want=%r" % (lines, kinds, ("int", "int", "float", "str")))
