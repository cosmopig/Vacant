"""Visible check 2: taking a period out of the front of a busy stretch."""


def run(solution):
    spans = [("2026-03-02T09:00:00", "2026-03-02T12:00:00")]
    holes = [("2026-03-02T08:00:00", "2026-03-02T10:00:00")]
    got = solution.subtract(spans, holes)
    want = [("2026-03-02T10:00:00", "2026-03-02T12:00:00")]
    assert got == want, "args=%r got=%r want=%r" % ((spans, holes), got, want)

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v02_subtract_from_an_end")
