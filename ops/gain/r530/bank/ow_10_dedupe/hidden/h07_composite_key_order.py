# anchor_kind: contract
# anchor: a list of field names making a composite key whose parts are compared in
# the order given
# derivation: two records are the same only when every named part agrees, so
# swapping the values between the two fields makes a different record.


def run(solution):
    records = [{"a": 1, "b": 2, "v": "x"},
               {"a": 2, "b": 1, "v": "y"},
               {"a": 1, "b": 2, "v": "z"}]
    got = solution.dedupe(records, ["a", "b"])
    want = [{"a": 1, "b": 2, "v": "x"}, {"a": 2, "b": 1, "v": "y"}]
    assert got == want, "args=%r got=%r want=%r" % (records, got, want)
