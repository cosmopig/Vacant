# anchor_kind: contract
# anchor: Either side may be empty, but not both.
# derivation: a pure insertion has an empty old side, and it works at the front, in
# the middle and at the end.


def run(solution):
    cases = [(["b", "c"], ["a", "b", "c"]),
             (["a", "c"], ["a", "b", "c"]),
             (["a", "b"], ["a", "b", "c"])]
    for old, new in cases:
        pieces = solution.diff(old, new)
        assert any(piece["old"] == [] for piece in pieces), (
            "args=%r got=%r want=%r" % ((old, new), pieces, "a piece with an empty old side"))
        got = solution.apply(old, pieces)
        assert got == new, "args=%r got=%r want=%r" % ((old, new), got, new)
