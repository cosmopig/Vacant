# anchor_kind: contract
# anchor: The result holds one record per distinct key value
# derivation: an empty list gives an empty list, and a list with no repeats comes
# back in the same order with the same contents.


def run(solution):
    got = solution.dedupe([], "k")
    assert got == [], "args=%r got=%r want=%r" % ([], got, [])

    records = [{"k": 1, "v": "a"}, {"k": 2, "v": "b"}, {"k": 3, "v": "c"}]
    got = solution.dedupe(records, "k", "merge")
    assert got == records, "args=%r got=%r want=%r" % (records, got, records)
