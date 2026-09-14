# anchor_kind: goal
# anchor: leaves everything that is not a table exactly as it was
# derivation: with no blank line above or below, the neighbouring prose lines must
# be returned untouched while the table between them is rewritten.


def run(solution):
    text = "Costs below:\n|item|cost|\n|---|---|\n|tea|4|\nThat is all.\n"
    got = solution.realign(text)
    lines = got.split("\n")
    assert lines[0] == "Costs below:", "args=%r got=%r want=%r" % (text, lines[0], "Costs below:")
    assert lines[4] == "That is all.", "args=%r got=%r want=%r" % (text, lines[4], "That is all.")
    assert lines[1].startswith("| item"), "args=%r got=%r want=%r" % (text, lines[1], "| item ... |")
