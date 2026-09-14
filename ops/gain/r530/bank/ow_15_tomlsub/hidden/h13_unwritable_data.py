# anchor_kind: contract
# anchor: `dumps` raises `ValueError` for data it cannot write
# derivation: each of the four named cases raises rather than producing text that
# would not read back.


def run(solution):
    cases = [{"a": None}, {"a": {"b": set()}}, {"a": [1, "two"]}, {"a": [[1], [2]]},
             {"has space": 1}, {"a": object()}]
    for data in cases:
        try:
            solution.dumps(data)
        except ValueError:
            continue
        raise AssertionError("args=%r got=%r want=%r" % (data, "written", "ValueError"))
