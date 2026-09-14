# anchor_kind: contract
# anchor: The presence or absence of a final newline is unchanged.
# derivation: a note without a final newline must not gain one, and one with a
# final newline must keep exactly one.


def run(solution):
    without = "alpha beta gamma delta"
    got = solution.reflow(without, 10)
    assert not got.endswith("\n"), "args=%r got=%r want=%r" % (without, got[-3:], "no final newline")

    got = solution.reflow(without + "\n", 10)
    assert got.endswith("\n") and not got.endswith("\n\n"), (
        "args=%r got=%r want=%r" % (without + "\n", got[-3:], "exactly one final newline"))
