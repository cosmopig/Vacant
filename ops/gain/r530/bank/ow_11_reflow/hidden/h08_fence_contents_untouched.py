# anchor_kind: goal
# anchor: code fenced off with backticks that must not be touched
# derivation: every line between the fences comes back byte for byte, including
# leading spaces, long lines and lines that look like bullets.


def run(solution):
    inner = ["    indented   spacing   kept", "- looks like a bullet but is code",
             "a" * 80]
    text = "intro\n\n```\n" + "\n".join(inner) + "\n```\n\nafter\n"
    got = solution.reflow(text, 15)
    for line in inner:
        assert "\n" + line + "\n" in got, (
            "args=%r got=%r want=%r" % (15, line, "the fenced line unchanged"))
