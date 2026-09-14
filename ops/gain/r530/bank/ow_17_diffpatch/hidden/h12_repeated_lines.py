# anchor_kind: goal
# anchor: Files with many identical lines are common in their data, and going out
# and back has to survive them.
# derivation: versions made almost entirely of one repeated line still go out and
# back exactly, whether a copy is added or removed.


def run(solution):
    cases = [(["x"] * 6, ["x"] * 7),
             (["x"] * 6, ["x"] * 5),
             (["x", "x", "y", "x", "x"], ["x", "x", "z", "x", "x"]),
             (["a", "a", "b", "a", "a", "b"], ["a", "b", "a", "a", "b", "b"])]
    for old, new in cases:
        pieces = solution.diff(old, new)
        got = solution.apply(old, pieces)
        assert got == new, "args=%r got=%r want=%r" % ((old, new), got, new)
