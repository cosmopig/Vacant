"""Visible check 1: overlapping periods fold into one, in order."""


def run(solution):
    spans = [("2026-03-02T09:00:00", "2026-03-02T10:30:00"),
             ("2026-03-02T10:00:00", "2026-03-02T11:00:00"),
             ("2026-03-02T14:00:00", "2026-03-02T15:00:00")]
    got = solution.merge(spans)
    want = [("2026-03-02T09:00:00", "2026-03-02T11:00:00"),
            ("2026-03-02T14:00:00", "2026-03-02T15:00:00")]
    assert got == want, "args=%r got=%r want=%r" % (spans, got, want)

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v01_merge_overlaps")
