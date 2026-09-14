# anchor_kind: contract
# anchor: The unit chosen is the largest one that leaves the number below the step
# derivation: each size lands in the unit whose number is at least 1 and less than
# the step, on both sides of every boundary.


def run(solution):
    cases = [(1023, "1023 B"), (1024, "1.0 KiB"), (1024 ** 2 - 1, "1024.0 KiB"),
             (1024 ** 2, "1.0 MiB"), (1024 ** 3, "1.0 GiB")]
    for number, want in cases:
        got = solution.humanize(number)
        assert got == want, "args=%r got=%r want=%r" % (number, got, want)
