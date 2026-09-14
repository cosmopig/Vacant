# anchor_kind: contract
# anchor: It uses the 1024 units when `binary` is true and the 1000 units otherwise.
# derivation: with the flag turned off the steps are thousands and the unit names
# lose the i.


def run(solution):
    cases = [(999, "999 B"), (1000, "1.0 KB"), (1500, "1.5 KB"),
             (2 * 1000 ** 3, "2.0 GB"), (1000 ** 4, "1.0 TB")]
    for number, want in cases:
        got = solution.humanize(number, binary=False)
        assert got == want, "args=%r got=%r want=%r" % ((number, False), got, want)
