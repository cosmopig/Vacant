# anchor_kind: contract
# anchor: for any two lists
# derivation: an empty old version and an empty new version are both ordinary
# cases, and the round trip holds for them too.


def run(solution):
    cases = [([], ["a", "b"]), (["a", "b"], []), ([], [])]
    for old, new in cases:
        pieces = solution.diff(old, new)
        got = solution.apply(old, pieces)
        assert got == new, "args=%r got=%r want=%r" % ((old, new), got, new)
