# anchor_kind: goal
# anchor: some are escaped
# derivation: a backslash-escaped pipe is content, so the row still has two cells
# and the escape sequence survives into the output.


def _separators(line):
    return sum(1 for i, ch in enumerate(line)
               if ch == "|" and (i == 0 or line[i - 1] != "\\"))


def run(solution):
    text = "| key | value |\n| --- | --- |\n| or | a \\| b |\n"
    got = solution.realign(text)
    body = got.split("\n")[2]
    assert "a \\| b" in body, "args=%r got=%r want=%r" % (text, body, "a \\| b kept as one cell")
    got_n = _separators(body)
    assert got_n == 3, "args=%r got=%r want=%r" % (text, got_n, 3)
