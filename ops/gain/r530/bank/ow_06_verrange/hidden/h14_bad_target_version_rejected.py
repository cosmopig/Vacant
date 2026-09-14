# anchor_kind: goal
# anchor: because a silent guess is how a bad build shipped last time
# derivation: the version written inside a condition goes through the same check as
# the version being tested, so a typo there is an error and not a False.


def run(solution):
    for spec in (">=1.0", "<2.0.0.0", "==one.two.three"):
        try:
            solution.satisfies("1.5.0", spec)
        except ValueError:
            continue
        raise AssertionError("args=%r got=%r want=%r" % (spec, "answered fine", "ValueError"))
