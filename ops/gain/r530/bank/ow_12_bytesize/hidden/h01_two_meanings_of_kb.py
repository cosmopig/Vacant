# anchor_kind: goal
# anchor: the two meanings of "KB"
# derivation: the i spelling steps by 1024 and the plain spelling by 1000, so the
# same number with the two spellings gives two different byte counts.


def run(solution):
    pairs = [("1 KiB", 1024, "1 KB", 1000),
             ("1 MiB", 1024 ** 2, "1 MB", 1000 ** 2),
             ("2 GiB", 2 * 1024 ** 3, "2 GB", 2 * 1000 ** 3),
             ("1 TiB", 1024 ** 4, "1 TB", 1000 ** 4)]
    for binary_text, binary_want, decimal_text, decimal_want in pairs:
        got = solution.to_bytes(binary_text)
        assert got == binary_want, "args=%r got=%r want=%r" % (binary_text, got, binary_want)
        got = solution.to_bytes(decimal_text)
        assert got == decimal_want, "args=%r got=%r want=%r" % (decimal_text, got, decimal_want)
