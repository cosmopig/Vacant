# anchor_kind: goal
# anchor: A field that is present but empty of meaning counts as not filled in.
# derivation: a later copy carrying None for a field must leave the real value that
# came before it alone.


def run(solution):
    records = [{"k": "u", "email": "bo@example.com", "note": None},
               {"k": "u", "email": None, "note": None}]
    got = solution.dedupe(records, "k", "merge")
    want = [{"k": "u", "email": "bo@example.com", "note": None}]
    assert got == want, "args=%r got=%r want=%r" % (records, got, want)
