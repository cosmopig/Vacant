"""Visible check 1: per-endpoint counts, busiest first, five-hundreds only."""


def run(solution):
    lines = [
        "2026-09-13T10:00:00Z GET /a 200 10",
        "2026-09-13T10:00:01Z GET /a 500 20",
        "2026-09-13T10:00:02Z GET /a 404 30",
        "2026-09-13T10:00:03Z GET /a 503 40",
        "2026-09-13T10:00:04Z GET /b 200 50",
    ]
    got = solution.summarize(lines)
    paths = [row["path"] for row in got["endpoints"]]
    assert paths == ["/a", "/b"], "args=%r got=%r want=%r" % (lines, paths, ["/a", "/b"])
    first = got["endpoints"][0]
    assert first["n"] == 4, "args=%r got=%r want=%r" % (lines, first["n"], 4)
    assert first["error_rate"] == 0.5, "args=%r got=%r want=%r" % (lines, first["error_rate"], 0.5)
    assert got["total"] == 5, "args=%r got=%r want=%r" % (lines, got["total"], 5)

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v01_counts_and_error_share")
