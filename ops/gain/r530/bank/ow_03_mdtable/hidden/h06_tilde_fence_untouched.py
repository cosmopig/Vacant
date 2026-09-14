# anchor_kind: contract
# anchor: every line inside a fenced code block opened by three backticks or three
# tildes
# derivation: the tilde fence is the other spelling of the same thing and must be
# honoured identically.


def run(solution):
    text = "~~~\n|x|y|\n|--|--|\n|9|8|\n~~~\n"
    got = solution.realign(text)
    assert got == text, "args=%r got=%r want=%r" % (text, got, text)
