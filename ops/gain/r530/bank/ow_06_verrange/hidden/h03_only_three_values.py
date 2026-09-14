# anchor_kind: contract
# anchor: It returns exactly those three values.
# derivation: the result is -1, 0 or 1 and nothing else, so a caller may compare it
# against those literals.


def run(solution):
    pairs = [("1.0.0", "2.0.0"), ("2.0.0", "1.0.0"), ("1.0.0", "1.0.0"),
             ("1.0.0-a", "1.0.0-b"), ("3.4.5-rc.1", "3.4.5-rc.1")]
    for a, b in pairs:
        got = solution.compare(a, b)
        assert got in (-1, 0, 1), "args=%r got=%r want=%r" % ((a, b), got, "-1, 0 or 1")
        assert isinstance(got, int) and not isinstance(got, bool), (
            "args=%r got=%r want=%r" % ((a, b), type(got).__name__, "int"))
