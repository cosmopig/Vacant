"""Visible check 2: the later copy wins when asked for."""


def run(solution):
    records = [{"id": "x", "v": 1, "w": "old"}, {"id": "x", "v": 2, "w": "new"}]
    got = solution.dedupe(records, "id", "last")
    want = [{"id": "x", "v": 2, "w": "new"}]
    assert got == want, "args=%r got=%r want=%r" % (records, got, want)

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v02_keep_the_last")
