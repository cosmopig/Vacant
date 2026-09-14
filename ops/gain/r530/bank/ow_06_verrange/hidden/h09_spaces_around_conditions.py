# anchor_kind: goal
# anchor: sometimes with spaces around them
# derivation: padding around a condition is not part of the version, so the spaced
# requirement answers exactly like the tight one.


def run(solution):
    tight = ">=1.2.0,<1.9.0"
    spaced = " >=1.2.0 ,  <1.9.0 "
    for version in ("1.2.0", "1.5.5", "1.9.0", "1.1.9"):
        got = solution.satisfies(version, spaced)
        want = solution.satisfies(version, tight)
        assert got == want, "args=%r got=%r want=%r" % ((version, spaced), got, want)
    assert solution.satisfies("1.5.5", spaced) is True, (
        "args=%r got=%r want=%r" % (("1.5.5", spaced), solution.satisfies("1.5.5", spaced), True))
