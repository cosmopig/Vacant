# anchor_kind: contract
# anchor: A `bool` accepts `true`, `false`, `1`, `0`, `yes` and `no` without regard
# to case.
# derivation: all six words, in mixed case, have to land on the right boolean.


def run(solution):
    defaults = {"flag": False}
    truthy = ("true", "TRUE", "1", "yes", "Yes")
    falsy = ("false", "False", "0", "no", "NO")
    for word in truthy:
        got = solution.load(defaults, "flag = %s\n" % word, {}).get("flag")
        assert got is True, "args=%r got=%r want=%r" % (word, got, True)
    for word in falsy:
        got = solution.load(defaults, "flag = %s\n" % word, {}).get("flag")
        assert got is False, "args=%r got=%r want=%r" % (word, got, False)
