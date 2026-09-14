# anchor_kind: goal
# anchor: Chinese takes two columns per character in their terminal
# derivation: a line of Chinese is only within the width when each character is
# counted as two columns.

import unicodedata


def _width(text):
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def run(solution):
    text = "這是一段中文筆記用來測試換行寬度是否以顯示寬度計算\n"
    got = solution.reflow(text, 10)
    for line in got.rstrip("\n").split("\n"):
        assert _width(line) <= 10, "args=%r got=%r want=%r" % (10, line, "<= 10 columns")
    assert "".join(got.split()) == "".join(text.split()), (
        "args=%r got=%r want=%r" % (text, "".join(got.split()), "".join(text.split())))
