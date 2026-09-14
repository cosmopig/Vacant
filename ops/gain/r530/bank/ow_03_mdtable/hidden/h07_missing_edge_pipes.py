# anchor_kind: goal
# anchor: some rows are missing the pipes at the start and end
# derivation: a table written without edge pipes is still a table, and the output
# gets the edge pipes the contract requires.


def run(solution):
    text = "a | b\n--- | ---\n1 | 2\n"
    got = solution.realign(text)
    for line in got.rstrip("\n").split("\n"):
        assert line.startswith("| ") and line.endswith(" |"), (
            "args=%r got=%r want=%r" % (text, line, "| ... |"))
    assert "1" in got and "2" in got, "args=%r got=%r want=%r" % (text, got, "cells preserved")
