# anchor_kind: goal
# anchor: bullet lists whose continuation lines should line up under the text and
# not under the bullet
# derivation: a bullet that follows a plain paragraph with no blank line between
# them starts its own paragraph and hangs its own continuation.


def run(solution):
    text = "intro words here\n- item one two three four five six seven eight\n"
    got = solution.reflow(text, 20)
    lines = got.rstrip("\n").split("\n")
    assert lines[0] == "intro words here", (
        "args=%r got=%r want=%r" % (text, lines[0], "intro words here"))
    assert lines[1].startswith("- item"), "args=%r got=%r want=%r" % (text, lines[1], "- item ...")
    for line in lines[2:]:
        assert line.startswith("  ") and line[2] != " ", (
            "args=%r got=%r want=%r" % (text, line, "two spaces of hanging indent"))
