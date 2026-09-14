# anchor_kind: contract
# anchor: `apply(old, diff(old, new))` equals `new`, for any two lists.
# derivation: a pure deletion has an empty new side, and removing a run of lines
# still goes out and back.


def run(solution):
    cases = [(["a", "b", "c"], ["a", "c"]),
             (["a", "b", "c", "d", "e"], ["a", "e"]),
             (["a", "b"], ["a"]),
             (["a", "b"], ["b"])]
    for old, new in cases:
        pieces = solution.diff(old, new)
        assert any(piece["new"] == [] for piece in pieces), (
            "args=%r got=%r want=%r" % ((old, new), pieces, "a piece with an empty new side"))
        got = solution.apply(old, pieces)
        assert got == new, "args=%r got=%r want=%r" % ((old, new), got, new)
