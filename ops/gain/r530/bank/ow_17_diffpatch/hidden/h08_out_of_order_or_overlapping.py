# anchor_kind: goal
# anchor: a list of pieces that is out of order, that overlaps itself
# derivation: pieces given back to front, and pieces whose ranges run into each
# other, are both refused even though each one on its own would fit.


def run(solution):
    old = ["a", "b", "c", "d", "e"]
    backwards = [{"start": 3, "old": ["d"], "new": ["D"]},
                 {"start": 1, "old": ["b"], "new": ["B"]}]
    overlapping = [{"start": 1, "old": ["b", "c"], "new": ["X"]},
                   {"start": 2, "old": ["c"], "new": ["Y"]}]
    for hunks in (backwards, overlapping):
        try:
            solution.apply(old, hunks)
        except ValueError:
            continue
        raise AssertionError("args=%r got=%r want=%r" % (hunks, "patched", "ValueError"))
