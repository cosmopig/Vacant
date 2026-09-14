# anchor_kind: goal
# anchor: in the order things first appeared
# derivation: the position of a key in the result is decided by its first
# occurrence, not by its last one and not by sorting.


def run(solution):
    records = [{"k": "z"}, {"k": "m"}, {"k": "a"}, {"k": "m"}, {"k": "z"}]
    got = [record["k"] for record in solution.dedupe(records, "k")]
    want = ["z", "m", "a"]
    assert got == want, "args=%r got=%r want=%r" % (records, got, want)
