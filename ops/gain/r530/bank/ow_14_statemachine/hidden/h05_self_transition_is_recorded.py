# anchor_kind: goal
# anchor: Something that puts an order back into the state it was already in still
# happened and belongs in that path.
# derivation: an event whose target is the state it started from still appends to
# the path, so the path grows by one each time.

SPEC = {"idle": {"poke": "idle", "go": "busy"}, "busy": {}}


def run(solution):
    machine = solution.Machine(SPEC, "idle")
    for _ in range(3):
        got = machine.fire("poke")
        assert got == "idle", "args=%r got=%r want=%r" % ("fire('poke')", got, "idle")
    want = ["idle", "idle", "idle", "idle"]
    assert machine.history() == want, (
        "args=%r got=%r want=%r" % ("three pokes", machine.history(), want))
