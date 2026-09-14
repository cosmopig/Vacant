# anchor_kind: contract
# anchor: A condition is one of `>=`, `>`, `<=`, `<`, `==`, `!=` followed by a
# version.
# derivation: each operator is checked on both sides of its own boundary, which is
# also where a solution that matches ">" before ">=" goes wrong.


def run(solution):
    cases = [("1.0.0", ">0.9.9", True), ("1.0.0", ">1.0.0", False),
             ("1.0.0", ">=1.0.0", True), ("1.0.0", ">=1.0.1", False),
             ("1.0.0", "<1.0.1", True), ("1.0.0", "<1.0.0", False),
             ("1.0.0", "<=1.0.0", True), ("1.0.0", "<=0.9.9", False),
             ("1.0.0", "==1.0.0", True), ("1.0.0", "==1.0.1", False),
             ("1.0.0", "!=1.0.1", True), ("1.0.0", "!=1.0.0", False)]
    for version, spec, want in cases:
        got = solution.satisfies(version, spec)
        assert got is want, "args=%r got=%r want=%r" % ((version, spec), got, want)
