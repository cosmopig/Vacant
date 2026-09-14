# anchor_kind: goal
# anchor: They have been burned by "1.10" sorting before "1.9"
# derivation: the minor and patch fields are numbers, so a two-digit field is
# larger than a one-digit field however the text sorts.


def run(solution):
    cases = [("0.10.0", "0.9.0", 1), ("0.0.10", "0.0.9", 1), ("1.11.0", "1.2.0", 1)]
    for a, b, want in cases:
        got = solution.compare(a, b)
        assert got == want, "args=%r got=%r want=%r" % ((a, b), got, want)
