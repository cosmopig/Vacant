# anchor_kind: goal
# anchor: there has to be a way to start over
# derivation: after reset the machine is in the starting state and its path is just
# that state, and it still works afterwards.

SPEC = {"new": {"pay": "paid"}, "paid": {"ship": "done"}, "done": {}}


def run(solution):
    machine = solution.Machine(SPEC, "new")
    machine.fire("pay")
    machine.fire("ship")
    machine.reset()
    assert machine.state == "new", "args=%r got=%r want=%r" % ("after reset", machine.state, "new")
    assert machine.history() == ["new"], (
        "args=%r got=%r want=%r" % ("after reset", machine.history(), ["new"]))
    got = machine.fire("pay")
    assert got == "paid", "args=%r got=%r want=%r" % ("fire after reset", got, "paid")
