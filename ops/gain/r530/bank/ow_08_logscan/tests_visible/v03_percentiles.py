"""Visible check 3: the ordinary middle and the unlucky tail."""


def run(solution):
    lines = ["2026-09-13T12:00:0%d GET /p 200 %d" % (index, value)
             for index, value in enumerate([50, 10, 40, 20, 30])]
    got = solution.summarize(lines)["endpoints"][0]
    assert got["p50_ms"] == 30, "args=%r got=%r want=%r" % (lines, got["p50_ms"], 30)
    assert got["p95_ms"] == 50, "args=%r got=%r want=%r" % (lines, got["p95_ms"], 50)

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v03_percentiles")
