"""Visible check 1: a paragraph comes back with no line over the width."""

import unicodedata


def _width(text):
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def run(solution):
    text = ("the quick brown fox jumps over the lazy dog and then goes back "
            "to sleep under the table\n")
    got = solution.reflow(text, 20)
    lines = got.rstrip("\n").split("\n")
    for line in lines:
        assert _width(line) <= 20, "args=%r got=%r want=%r" % (20, line, "<= 20 columns")
    assert " ".join(got.split()) == " ".join(text.split()), (
        "args=%r got=%r want=%r" % (text, " ".join(got.split()), " ".join(text.split())))

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v01_wraps_to_width")
