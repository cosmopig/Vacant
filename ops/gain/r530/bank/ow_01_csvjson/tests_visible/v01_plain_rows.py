"""Visible check 1: the plain path -- rows in, JSON Lines out."""

import json


def run(solution):
    text = "name,qty,note\npen,3,\nmug,12,chipped\n"
    got = solution.csv_to_jsonl(text)
    assert got.endswith("\n"), "args=%r got=%r want=%r" % (text, got, "a string ending in a newline")
    lines = got.splitlines()
    assert len(lines) == 2, "args=%r got=%r want=%r" % (text, len(lines), 2)
    first = json.loads(lines[0])
    want_first = {"name": "pen", "qty": "3", "note": ""}
    assert first == want_first, "args=%r got=%r want=%r" % (text, first, want_first)
    second = json.loads(lines[1])
    want_second = {"name": "mug", "qty": "12", "note": "chipped"}
    assert second == want_second, "args=%r got=%r want=%r" % (text, second, want_second)
    for value in first.values():
        assert isinstance(value, str), "args=%r got=%r want=%r" % (text, type(value).__name__, "str")

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v01_plain_rows")
