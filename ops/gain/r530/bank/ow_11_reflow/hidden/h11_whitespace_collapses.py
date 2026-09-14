# anchor_kind: contract
# anchor: runs of spaces and tabs separate words and are replaced by a single space
# derivation: doubled spaces and tabs between words become one space each, and no
# output line is left with trailing whitespace.


def run(solution):
    text = "alpha    beta\tgamma \t delta\n"
    got = solution.reflow(text, 40)
    assert got == "alpha beta gamma delta\n", (
        "args=%r got=%r want=%r" % (text, got, "alpha beta gamma delta\n"))
    for line in got.split("\n"):
        assert line == line.rstrip(), "args=%r got=%r want=%r" % (text, line, "no trailing space")
