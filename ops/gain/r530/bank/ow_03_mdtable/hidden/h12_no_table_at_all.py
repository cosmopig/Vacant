# anchor_kind: goal
# anchor: A document with no table in it at all must come back byte for byte.
# derivation: prose that happens to contain a pipe is not a table, because no
# separator row follows it.


def run(solution):
    text = "Run `grep x | wc -l` and read the count.\nNothing here is a table.\n"
    got = solution.realign(text)
    assert got == text, "args=%r got=%r want=%r" % (text, got, text)
