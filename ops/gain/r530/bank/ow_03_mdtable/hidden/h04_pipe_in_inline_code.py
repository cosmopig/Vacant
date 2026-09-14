# anchor_kind: goal
# anchor: some sit inside inline code
# derivation: a pipe between backticks belongs to the code span, so the row keeps
# two cells and the backticks stay where they were.


def run(solution):
    text = "| what | how |\n| --- | --- |\n| alternation | `a|b` |\n"
    got = solution.realign(text)
    body = got.split("\n")[2]
    assert "`a|b`" in body, "args=%r got=%r want=%r" % (text, body, "`a|b` kept intact")
    assert body.count("|") == 4, "args=%r got=%r want=%r" % (text, body.count("|"), 4)
