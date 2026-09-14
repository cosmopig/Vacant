# anchor_kind: goal
# anchor: Applying a list of pieces to a version they do not fit is the dangerous
# case
# derivation: a piece whose old side is not what the text holds at that index is
# refused, and nothing partial is returned.


def run(solution):
    old = ["a", "b", "c"]
    for piece in ({"start": 1, "old": ["x"], "new": ["y"]},
                  {"start": 0, "old": ["a", "x"], "new": ["z"]},
                  {"start": 2, "old": ["b"], "new": ["q"]}):
        try:
            solution.apply(old, [piece])
        except ValueError:
            continue
        raise AssertionError("args=%r got=%r want=%r" % (piece, "patched", "ValueError"))
