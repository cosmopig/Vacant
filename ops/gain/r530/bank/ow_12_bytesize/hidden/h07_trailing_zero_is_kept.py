# anchor_kind: goal
# anchor: keep one decimal place even when it is a round number
# derivation: a size that lands on a whole number of units still shows the decimal
# point and the zero after it.


def run(solution):
    cases = [(1024, "1.0 KiB"), (2 * 1024 ** 2, "2.0 MiB"), (10 * 1024 ** 3, "10.0 GiB")]
    for number, want in cases:
        got = solution.humanize(number)
        assert got == want, "args=%r got=%r want=%r" % (number, got, want)
