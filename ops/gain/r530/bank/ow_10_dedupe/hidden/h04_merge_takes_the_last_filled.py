# anchor_kind: contract
# anchor: field by field, the value of the last copy that both has the field and
# whose value is not `None`
# derivation: across three copies each field independently takes the latest real
# value it was given.


def run(solution):
    records = [{"k": 1, "a": "a1", "b": "b1"},
               {"k": 1, "a": "a2"},
               {"k": 1, "b": "b3"}]
    got = solution.dedupe(records, "k", "merge")
    want = [{"k": 1, "a": "a2", "b": "b3"}]
    assert got == want, "args=%r got=%r want=%r" % (records, got, want)
