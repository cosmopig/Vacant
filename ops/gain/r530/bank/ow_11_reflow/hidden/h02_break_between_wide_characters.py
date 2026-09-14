# anchor_kind: goal
# anchor: it can be broken between any two characters without a space appearing at
# the break
# derivation: a Chinese run with no spaces in it still wraps, and putting the lines
# back together with nothing between them gives the original text.


def run(solution):
    text = "甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥"
    got = solution.reflow(text, 8)
    lines = got.split("\n")
    assert len(lines) >= 5, "args=%r got=%r want=%r" % (8, len(lines), ">= 5 lines")
    assert "".join(lines) == text, "args=%r got=%r want=%r" % (text, "".join(lines), text)
    for line in lines:
        assert " " not in line, "args=%r got=%r want=%r" % (text, line, "no spaces introduced")
