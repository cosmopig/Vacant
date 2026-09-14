# anchor_kind: goal
# anchor: nothing they handed in may come back changed
# derivation: after every policy the original dictionaries hold exactly what they
# held before, and no dictionary in the result is one of them.


def run(solution):
    for policy in ("first", "last", "merge"):
        records = [{"k": "u", "a": 1, "b": None}, {"k": "u", "b": 2, "c": 3}]
        snapshot = [dict(record) for record in records]
        result = solution.dedupe(records, "k", policy)
        assert records == snapshot, "args=%r got=%r want=%r" % (policy, records, snapshot)
        for produced in result:
            for original in records:
                assert produced is not original, (
                    "args=%r got=%r want=%r" % (policy, "an input dict", "a new dict"))
