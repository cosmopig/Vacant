# anchor_kind: goal
# anchor: numbers that come back out different from the way they went in
# derivation: for a size the printed form represents exactly, reading it back gives
# the number that was printed.


def run(solution):
    for number in (0, 512, 1024, 1536, 5 * 1024 ** 2, 3 * 1024 ** 3):
        printed = solution.humanize(number)
        got = solution.to_bytes(printed)
        assert got == number, "args=%r got=%r want=%r" % (printed, got, number)
    for number in (999, 1000, 1500, 2 * 1000 ** 3):
        printed = solution.humanize(number, binary=False)
        got = solution.to_bytes(printed)
        assert got == number, "args=%r got=%r want=%r" % (printed, got, number)
