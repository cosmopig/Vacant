# anchor_kind: contract
# anchor: `.history()` hands back a copy: changing the returned list does not change
# the machine.
# derivation: a caller who clears or appends to what they were given must not be
# able to rewrite the order's past.

SPEC = {"a": {"go": "b"}, "b": {}}


def run(solution):
    machine = solution.Machine(SPEC, "a")
    machine.fire("go")
    borrowed = machine.history()
    borrowed.append("forged")
    borrowed.clear()
    got = machine.history()
    assert got == ["a", "b"], "args=%r got=%r want=%r" % ("after mangling the copy", got, ["a", "b"])
