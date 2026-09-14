# anchor_kind: goal
# anchor: People write the unit in whatever case they feel like
# derivation: every casing of a unit reads as the same unit.


def run(solution):
    for text in ("1 kib", "1 KIB", "1 KiB", "1 kIb"):
        got = solution.to_bytes(text)
        assert got == 1024, "args=%r got=%r want=%r" % (text, got, 1024)
    for text in ("2 mb", "2 MB", "2 Mb"):
        got = solution.to_bytes(text)
        assert got == 2000000, "args=%r got=%r want=%r" % (text, got, 2000000)
