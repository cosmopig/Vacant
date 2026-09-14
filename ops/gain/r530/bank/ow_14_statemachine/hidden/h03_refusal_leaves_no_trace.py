# anchor_kind: goal
# anchor: has to leave the order exactly where it was, in state and in record
# derivation: after several refused events the state and the path are exactly what
# they were before them.

SPEC = {"one": {"next": "two"}, "two": {}}


def run(solution):
    machine = solution.Machine(SPEC, "one")
    machine.fire("next")
    before_state, before_history = machine.state, machine.history()
    for event in ("next", "back", "explode"):
        try:
            machine.fire(event)
        except ValueError:
            pass
    assert machine.state == before_state, (
        "args=%r got=%r want=%r" % ("three refusals", machine.state, before_state))
    assert machine.history() == before_history, (
        "args=%r got=%r want=%r" % ("three refusals", machine.history(), before_history))
