# anchor_kind: goal
# anchor: starting from where it began
# derivation: before anything has happened the path already holds the starting
# state, so support staff can see where the order came from.

SPEC = {"queued": {"start": "running"}, "running": {}}


def run(solution):
    machine = solution.Machine(SPEC, "queued")
    got = machine.history()
    assert got == ["queued"], "args=%r got=%r want=%r" % ("a fresh machine", got, ["queued"])
