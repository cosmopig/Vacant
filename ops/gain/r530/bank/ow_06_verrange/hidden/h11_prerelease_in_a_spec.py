# anchor_kind: contract
# anchor: Every condition has to hold for `satisfies` to return True.
# derivation: the comparison used inside a condition is the same one `compare`
# implements, so a pre-release bound behaves the same way there.


def run(solution):
    assert solution.satisfies("1.0.0-rc.2", ">=1.0.0-rc.1") is True, (
        "args=%r got=%r want=%r" % (("1.0.0-rc.2", ">=1.0.0-rc.1"), False, True))
    assert solution.satisfies("1.0.0-rc.2", ">=1.0.0") is False, (
        "args=%r got=%r want=%r" % (("1.0.0-rc.2", ">=1.0.0"), True, False))
    assert solution.satisfies("1.0.0", ">1.0.0-rc.9") is True, (
        "args=%r got=%r want=%r" % (("1.0.0", ">1.0.0-rc.9"), False, True))
