# anchor_kind: goal
# anchor: two records that agree on only one of them are not the same thing
# derivation: two records whose key parts would glue into the same text are still
# different records, because the parts are compared separately.


def run(solution):
    records = [{"first": "ab", "second": "c", "v": 1},
               {"first": "a", "second": "bc", "v": 2}]
    got = solution.dedupe(records, ["first", "second"])
    assert len(got) == 2, "args=%r got=%r want=%r" % (records, len(got), 2)
    assert [record["v"] for record in got] == [1, 2], (
        "args=%r got=%r want=%r" % (records, [record["v"] for record in got], [1, 2]))
