# anchor_kind: contract
# anchor: a bullet marker -- `- `, `* `, or digits followed by `. `
# derivation: the star spelling behaves like the dash, and an indented bullet hangs
# under its own text rather than under the left margin.


def run(solution):
    text = "  * alpha beta gamma delta epsilon zeta eta theta iota kappa\n"
    got = solution.reflow(text, 20)
    lines = got.rstrip("\n").split("\n")
    assert lines[0].startswith("  * "), "args=%r got=%r want=%r" % (text, lines[0], "  * ...")
    for line in lines[1:]:
        assert line.startswith("    ") and line[4] != " ", (
            "args=%r got=%r want=%r" % (text, line, "four spaces of hanging indent"))
