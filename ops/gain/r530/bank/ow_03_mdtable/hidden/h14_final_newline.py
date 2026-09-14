# anchor_kind: contract
# anchor: the presence or absence of a final newline is unchanged
# derivation: a document whose last line has no newline must not gain one, and one
# that has a newline must not lose it.


def run(solution):
    without = "|a|b|\n|---|---|\n|1|2|"
    got = solution.realign(without)
    assert not got.endswith("\n"), "args=%r got=%r want=%r" % (without, got[-3:], "no trailing newline")

    with_nl = without + "\n"
    got = solution.realign(with_nl)
    assert got.endswith("\n") and not got.endswith("\n\n"), (
        "args=%r got=%r want=%r" % (with_nl, got[-3:], "exactly one trailing newline"))
