"""Visible check 1: one record per key, in the order the keys first showed up."""


def run(solution):
    records = [{"id": "b", "v": 1}, {"id": "a", "v": 2}, {"id": "b", "v": 3}]
    got = solution.dedupe(records, "id")
    want = [{"id": "b", "v": 1}, {"id": "a", "v": 2}]
    assert got == want, "args=%r got=%r want=%r" % (records, got, want)

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v01_first_appearance_order")
