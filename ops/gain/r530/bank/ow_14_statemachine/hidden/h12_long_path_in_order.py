# anchor_kind: goal
# anchor: They want the path an order took, in order
# derivation: over a longer run through a cycle the path holds every state in the
# order it was entered, with repeats kept.

SPEC = {"a": {"go": "b"}, "b": {"go": "c", "back": "a"}, "c": {"back": "b"}}


def run(solution):
    machine = solution.Machine(SPEC, "a")
    for event in ("go", "go", "back", "back", "go"):
        machine.fire(event)
    want = ["a", "b", "c", "b", "a", "b"]
    assert machine.history() == want, (
        "args=%r got=%r want=%r" % ("go,go,back,back,go", machine.history(), want))
