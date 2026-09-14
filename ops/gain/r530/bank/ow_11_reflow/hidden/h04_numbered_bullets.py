# anchor_kind: contract
# anchor: or digits followed by `. `
# derivation: a numbered item hangs under its text, so the continuation indent is
# as wide as the number, the dot and the space together.


def run(solution):
    text = "10. alpha beta gamma delta epsilon zeta eta theta iota\n"
    got = solution.reflow(text, 20)
    lines = got.rstrip("\n").split("\n")
    assert lines[0].startswith("10. "), "args=%r got=%r want=%r" % (text, lines[0], "10. ...")
    for line in lines[1:]:
        assert line.startswith("    ") and line[4] != " ", (
            "args=%r got=%r want=%r" % (text, line, "four spaces of hanging indent"))
