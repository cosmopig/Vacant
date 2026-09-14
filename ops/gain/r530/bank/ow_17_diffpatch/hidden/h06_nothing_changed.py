# anchor_kind: goal
# anchor: A file that did not change at all produces no pieces.
# derivation: two equal versions give an empty list, and applying an empty list
# gives back an equal but separate list.


def run(solution):
    old = ["a", "b", "c"]
    pieces = solution.diff(old, list(old))
    assert pieces == [], "args=%r got=%r want=%r" % (old, pieces, [])
    got = solution.apply(old, [])
    assert got == old, "args=%r got=%r want=%r" % (old, got, old)
    assert got is not old, "args=%r got=%r want=%r" % (old, "the same list", "a new list")
