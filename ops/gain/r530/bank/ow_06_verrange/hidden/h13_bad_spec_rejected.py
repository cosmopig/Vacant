# anchor_kind: contract
# anchor: a spec with an empty condition, and a condition with an unrecognised
# operator all raise `ValueError`
# derivation: a requirement whose operator is not one of the six, or that contains
# an empty piece, is rejected rather than silently answered.


def run(solution):
    for spec in ("~>1.0.0", "1.0.0", ">=1.0.0,", "", ">=1.0.0,,<2.0.0", "=>1.0.0"):
        try:
            solution.satisfies("1.5.0", spec)
        except ValueError:
            continue
        raise AssertionError("args=%r got=%r want=%r" % (spec, "answered fine", "ValueError"))
