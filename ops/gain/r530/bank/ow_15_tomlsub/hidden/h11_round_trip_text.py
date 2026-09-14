# anchor_kind: goal
# anchor: writing out what was just read has to give the same text
# derivation: written form is canonical, so a second pass through parse and dumps
# changes nothing at all.


def run(solution):
    data = {"z": 1, "a": 2, "m": {"q": "x\"y", "b": [1, 2], "deep": {"k": True}}}
    once = solution.dumps(data)
    twice = solution.dumps(solution.parse(once))
    assert once == twice, "args=%r got=%r want=%r" % (data, twice, once)
    thrice = solution.dumps(solution.parse(twice))
    assert twice == thrice, "args=%r got=%r want=%r" % (data, thrice, twice)
