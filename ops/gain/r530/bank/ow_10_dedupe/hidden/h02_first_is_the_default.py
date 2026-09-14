# anchor_kind: contract
# anchor: The default is `"first"`.
# derivation: calling without a policy behaves exactly like asking for the first
# copy.


def run(solution):
    records = [{"k": 1, "v": "early"}, {"k": 1, "v": "late"}]
    implicit = solution.dedupe(records, "k")
    explicit = solution.dedupe(records, "k", "first")
    assert implicit == explicit == [{"k": 1, "v": "early"}], (
        "args=%r got=%r want=%r" % (records, implicit, [{"k": 1, "v": "early"}]))
