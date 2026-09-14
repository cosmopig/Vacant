"""Visible check 3: the total of the tidy list, in whole seconds."""


def run(solution):
    spans = [("2026-03-02T09:00:00", "2026-03-02T10:00:00"),
             ("2026-03-02T09:30:00", "2026-03-02T11:00:00")]
    got = solution.total_seconds(spans)
    assert got == 7200, "args=%r got=%r want=%r" % (spans, got, 7200)
    assert isinstance(got, int), "args=%r got=%r want=%r" % (spans, type(got).__name__, "int")

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v03_total")
