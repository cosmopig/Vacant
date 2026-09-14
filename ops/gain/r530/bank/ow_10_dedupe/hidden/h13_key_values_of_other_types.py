# anchor_kind: contract
# anchor: `key` is a field name
# derivation: the key value is whatever the field holds, so numbers and None are
# key values in their own right and do not collide with their text form.


def run(solution):
    records = [{"k": 1, "v": "int"}, {"k": "1", "v": "str"}, {"k": None, "v": "none"},
               {"k": 1, "v": "int again"}]
    got = solution.dedupe(records, "k")
    want = [{"k": 1, "v": "int"}, {"k": "1", "v": "str"}, {"k": None, "v": "none"}]
    assert got == want, "args=%r got=%r want=%r" % (records, got, want)
