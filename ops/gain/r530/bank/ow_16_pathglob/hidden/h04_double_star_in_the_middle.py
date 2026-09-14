# anchor_kind: contract
# anchor: A segment that is exactly `**` matches zero or more whole segments.
# derivation: with a literal segment on each side the double star has to stretch to
# whatever lies between them, and stop where the literal does not fit.


def run(solution):
    cases = [("a/**/z", "a/b/c/d/z", True), ("a/**/z", "a/z", True),
             ("a/**/z", "a/b/c", False), ("a/**/z", "b/c/z", False)]
    for pattern, path, want in cases:
        got = solution.matches(pattern, path)
        assert got is want, "args=%r got=%r want=%r" % ((pattern, path), got, want)
