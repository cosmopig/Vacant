"""Visible check 2: an ordinary line is untouched, and a second pass does nothing."""


def run(solution):
    clean = "2026-09-13 INFO served GET /health in 3ms"
    got = solution.redact(clean)
    assert got == clean, "args=%r got=%r want=%r" % (clean, got, clean)
    assert solution.findings(clean) == [], (
        "args=%r got=%r want=%r" % (clean, solution.findings(clean), []))

    dirty = "connecting to postgres://svc:hunter2@db.internal:5432/app now"
    once = solution.redact(dirty)
    twice = solution.redact(once)
    assert once == twice, "args=%r got=%r want=%r" % (dirty, twice, once)

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v02_clean_lines_and_second_passes")
