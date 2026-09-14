# anchor_kind: goal
# anchor: Sizes larger than the biggest unit they use should still print, rather
# than falling back to a bare byte count.
# derivation: beyond a terabyte the unit stops changing and the number grows past
# the step instead.


def run(solution):
    got = solution.humanize(2048 * 1024 ** 4)
    assert got == "2048.0 TiB", "args=%r got=%r want=%r" % (2048 * 1024 ** 4, got, "2048.0 TiB")
    got = solution.humanize(5000 * 1000 ** 4, binary=False)
    assert got == "5000.0 TB", "args=%r got=%r want=%r" % (5000 * 1000 ** 4, got, "5000.0 TB")
