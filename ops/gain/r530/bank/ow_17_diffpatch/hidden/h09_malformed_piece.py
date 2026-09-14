# anchor_kind: goal
# anchor: or that is simply malformed
# derivation: a missing key, an extra key, a piece empty on both sides, and a piece
# reaching past the end are each refused.


def run(solution):
    old = ["a", "b", "c"]
    for hunk in ({"start": 0, "old": ["a"]},
                 {"start": 0, "old": ["a"], "new": ["A"], "extra": 1},
                 {"start": 1, "old": [], "new": []},
                 {"start": 2, "old": ["c", "d"], "new": ["z"]},
                 {"start": 9, "old": ["a"], "new": ["b"]},
                 ["not", "a", "dict"]):
        try:
            solution.apply(old, [hunk])
        except ValueError:
            continue
        raise AssertionError("args=%r got=%r want=%r" % (hunk, "patched", "ValueError"))
