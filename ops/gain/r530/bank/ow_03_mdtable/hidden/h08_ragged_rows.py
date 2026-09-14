# anchor_kind: goal
# anchor: some rows have more cells than the header
# derivation: the table grows to the widest row and the short rows are filled with
# empty cells, so every output row has the same number of separators.


def run(solution):
    text = "| a | b |\n| --- | --- |\n| 1 | 2 | 3 |\n| 4 |\n"
    got = solution.realign(text)
    lines = got.rstrip("\n").split("\n")
    counts = [line.count("|") for line in lines]
    assert counts == [4, 4, 4, 4], "args=%r got=%r want=%r" % (text, counts, [4, 4, 4, 4])
    assert "3" in lines[2], "args=%r got=%r want=%r" % (text, lines[2], "the third cell survives")
