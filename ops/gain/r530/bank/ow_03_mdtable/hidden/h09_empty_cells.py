# anchor_kind: goal
# anchor: some cells are empty
# derivation: an empty cell is still a column, padded to the column width and never
# collapsed away.

import unicodedata


def _width(text):
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def run(solution):
    text = "| p | q |\n| --- | --- |\n| |longish|\n"
    got = solution.realign(text)
    lines = got.rstrip("\n").split("\n")
    assert all(line.count("|") == 3 for line in lines), (
        "args=%r got=%r want=%r" % (text, [l.count("|") for l in lines], [3, 3, 3]))
    widths = [_width(line) for line in lines]
    assert len(set(widths)) == 1, "args=%r got=%r want=%r" % (text, widths, "one common width")
