# anchor_kind: goal
# anchor: A list that mixes kinds is a mistake.
# derivation: a list holding two different kinds raises, and the message says which
# line it was on.


def run(solution):
    text = 'a = 1\nb = [1, "two"]\n'
    try:
        solution.parse(text)
    except ValueError as exc:
        assert str(exc).startswith("line 2: "), (
            "args=%r got=%r want=%r" % (text, str(exc), "line 2: ..."))
        return
    raise AssertionError("args=%r got=%r want=%r" % (text, "parsed", "ValueError"))
