"""Visible check 2: a bullet's continuation lines sit under the text."""


def run(solution):
    text = "- alpha beta gamma delta epsilon zeta eta theta\n"
    got = solution.reflow(text, 18)
    lines = got.rstrip("\n").split("\n")
    assert len(lines) > 1, "args=%r got=%r want=%r" % (text, lines, "more than one line")
    assert lines[0].startswith("- "), "args=%r got=%r want=%r" % (text, lines[0], "- ...")
    for line in lines[1:]:
        assert line.startswith("  ") and not line.startswith("- "), (
            "args=%r got=%r want=%r" % (text, line, "two spaces of hanging indent"))

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v02_bullet_hanging_indent")
