# anchor_kind: goal
# anchor: some of the cells contain Chinese and Japanese text
# derivation: when a column holds wide characters the rows only line up if width is
# measured in columns rather than in characters.

import unicodedata


def _width(text):
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def run(solution):
    text = "| 品目 | qty |\n| --- | --- |\n| 鉛筆と消しゴム | 3 |\n| pen | 11 |\n"
    got = solution.realign(text)
    widths = [_width(line) for line in got.rstrip("\n").split("\n")]
    assert len(set(widths)) == 1, "args=%r got=%r want=%r" % (text, widths, "one common width")
