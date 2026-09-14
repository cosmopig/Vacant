# anchor_kind: goal
# anchor: A record that does not carry the field they are keying on is a data
# problem they want to hear about, not something to skip quietly.
# derivation: the missing field raises, and the error names the field, for the
# single-field and the composite case alike.


def run(solution):
    records = [{"id": 1}, {"other": 2}]
    try:
        solution.dedupe(records, "id")
    except KeyError as exc:
        assert exc.args[0] == "id", "args=%r got=%r want=%r" % (records, exc.args[0], "id")
    else:
        raise AssertionError("args=%r got=%r want=%r" % (records, "returned", "KeyError"))

    records = [{"a": 1, "b": 2}, {"a": 1}]
    try:
        solution.dedupe(records, ["a", "b"])
    except KeyError as exc:
        assert exc.args[0] == "b", "args=%r got=%r want=%r" % (records, exc.args[0], "b")
        return
    raise AssertionError("args=%r got=%r want=%r" % (records, "returned", "KeyError"))
