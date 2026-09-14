# anchor_kind: goal
# anchor: They run the same rules for the next order
# derivation: two machines built from the same rules keep their own state and their
# own path, so moving one does not move the other.

SPEC = {"a": {"go": "b"}, "b": {"go": "c"}, "c": {}}


def run(solution):
    first = solution.Machine(SPEC, "a")
    second = solution.Machine(SPEC, "a")
    first.fire("go")
    first.fire("go")
    assert second.state == "a", "args=%r got=%r want=%r" % ("the second machine", second.state, "a")
    assert second.history() == ["a"], (
        "args=%r got=%r want=%r" % ("the second machine", second.history(), ["a"]))
