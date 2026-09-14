# anchor_kind: contract
# anchor: `"merge"` -- field by field
# derivation: a field that only the later copy carries is added to the merged
# record rather than dropped.


def run(solution):
    records = [{"k": "u", "name": "Bo"}, {"k": "u", "phone": "555"}]
    got = solution.dedupe(records, "k", "merge")
    want = [{"k": "u", "name": "Bo", "phone": "555"}]
    assert got == want, "args=%r got=%r want=%r" % (records, got, want)
