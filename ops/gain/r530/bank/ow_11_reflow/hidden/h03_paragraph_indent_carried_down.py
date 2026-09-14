# anchor_kind: goal
# anchor: Their notes have indented blocks
# derivation: a paragraph that started indented keeps that indentation on every one
# of its lines.


def run(solution):
    text = "    one two three four five six seven eight nine ten eleven twelve\n"
    got = solution.reflow(text, 24)
    lines = got.rstrip("\n").split("\n")
    assert len(lines) > 1, "args=%r got=%r want=%r" % (24, lines, "more than one line")
    for line in lines:
        assert line.startswith("    ") and line[4] != " ", (
            "args=%r got=%r want=%r" % (text, line, "four spaces of indent"))
