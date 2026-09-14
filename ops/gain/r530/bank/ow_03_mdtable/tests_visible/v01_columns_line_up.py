"""Visible check 1: ragged columns come back aligned, including wide characters."""

import unicodedata


def _width(text):
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def run(solution):
    text = "|name|city|\n|---|---|\n|Bo|台北|\n|Alexandra|Oslo|\n"
    got = solution.realign(text)
    lines = got.split("\n")[:4]
    widths = [_width(line) for line in lines]
    assert len(set(widths)) == 1, "args=%r got=%r want=%r" % (text, widths, "all rows the same width")
    for line in lines:
        assert line.startswith("| ") and line.endswith(" |"), (
            "args=%r got=%r want=%r" % (text, line, "| ... |"))
    assert "Alexandra" in got and "台北" in got, (
        "args=%r got=%r want=%r" % (text, got, "cell text preserved"))

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v01_columns_line_up")
