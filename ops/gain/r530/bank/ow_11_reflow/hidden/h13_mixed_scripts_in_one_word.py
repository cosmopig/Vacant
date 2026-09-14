# anchor_kind: contract
# anchor: A break may fall between any two characters when at least one of them is
# wide, and no space is inserted at such a break.
# derivation: a run that mixes Latin letters and Chinese may break where the two
# meet, and the Latin part is not broken inside itself.


def run(solution):
    text = "版本abcdefgh版本"
    got = solution.reflow(text, 6)
    lines = got.split("\n")
    assert "".join(lines) == text, "args=%r got=%r want=%r" % (text, "".join(lines), text)
    assert any("abcdefgh" in line for line in lines), (
        "args=%r got=%r want=%r" % (text, lines, "abcdefgh kept whole"))
