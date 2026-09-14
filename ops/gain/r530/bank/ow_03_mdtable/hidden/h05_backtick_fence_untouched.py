# anchor_kind: goal
# anchor: some are inside fenced code blocks that happen to show a table
# derivation: a table drawn inside a backtick fence is sample text, not structure,
# so those lines come back byte for byte.


def run(solution):
    text = "intro\n\n```\n|a|b|\n|---|---|\n|1|2|\n```\n\nend\n"
    got = solution.realign(text)
    assert got == text, "args=%r got=%r want=%r" % (text, got, text)
