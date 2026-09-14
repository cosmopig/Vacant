# anchor_kind: contract
# anchor: `"last"` -- the latest copy's values are kept
# derivation: the later copy replaces the earlier one entirely, so a field only the
# earlier copy had does not survive.


def run(solution):
    records = [{"k": 1, "a": "keep?", "b": 2}, {"k": 1, "b": 3}]
    got = solution.dedupe(records, "k", "last")
    want = [{"k": 1, "b": 3}]
    assert got == want, "args=%r got=%r want=%r" % (records, got, want)
