# anchor_kind: goal
# anchor: every condition has to hold
# derivation: a three-condition requirement is only satisfied when all three are
# true; one failure is enough to answer no.


def run(solution):
    spec = ">=1.0.0,<2.0.0,!=1.5.0"
    assert solution.satisfies("1.4.0", spec) is True, (
        "args=%r got=%r want=%r" % (("1.4.0", spec), solution.satisfies("1.4.0", spec), True))
    assert solution.satisfies("1.5.0", spec) is False, (
        "args=%r got=%r want=%r" % (("1.5.0", spec), solution.satisfies("1.5.0", spec), False))
    assert solution.satisfies("0.9.0", spec) is False, (
        "args=%r got=%r want=%r" % (("0.9.0", spec), solution.satisfies("0.9.0", spec), False))
