"""Visible check 3: merging takes whichever fields are actually filled in."""


def run(solution):
    records = [{"id": "p", "name": "Ann", "email": None},
               {"id": "p", "name": "Ann", "email": "ann@example.com"}]
    got = solution.dedupe(records, "id", "merge")
    want = [{"id": "p", "name": "Ann", "email": "ann@example.com"}]
    assert got == want, "args=%r got=%r want=%r" % (records, got, want)

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v03_merge_filled_fields")
