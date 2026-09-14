# anchor_kind: goal
# anchor: Applying must not touch what it was given, because they keep the old
# version around.
# derivation: after a successful apply the old list and the pieces hold exactly what
# they held before, and the answer is a different object.


def run(solution):
    old = ["a", "b", "c", "d"]
    new = ["a", "B", "c", "D"]
    pieces = solution.diff(old, new)
    old_before = list(old)
    pieces_before = [dict(piece) for piece in pieces]
    got = solution.apply(old, pieces)
    assert old == old_before, "args=%r got=%r want=%r" % ("apply", old, old_before)
    assert pieces == pieces_before, "args=%r got=%r want=%r" % ("apply", pieces, pieces_before)
    assert got is not old, "args=%r got=%r want=%r" % ("apply", "the same list", "a new list")
    assert got == new, "args=%r got=%r want=%r" % ((old, new), got, new)
