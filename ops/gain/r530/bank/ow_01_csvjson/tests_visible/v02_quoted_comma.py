"""Visible check 2: a comma inside a quoted field is data, not a separator."""

import json


def run(solution):
    text = 'sku,colours\nA1,"red, blue"\nB2,green\n'
    got = solution.csv_to_jsonl(text)
    lines = got.splitlines()
    assert len(lines) == 2, "args=%r got=%r want=%r" % (text, len(lines), 2)
    row = json.loads(lines[0])
    want = {"sku": "A1", "colours": "red, blue"}
    assert row == want, "args=%r got=%r want=%r" % (text, row, want)
    assert json.loads(lines[1]) == {"sku": "B2", "colours": "green"}, (
        "args=%r got=%r want=%r" % (text, lines[1], {"sku": "B2", "colours": "green"}))

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v02_quoted_comma")
