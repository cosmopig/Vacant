# anchor_kind: contract
# anchor: Every state the machine can be in appears as a key of `spec`, even when it
# has no events of its own.
# derivation: a state with an empty mapping is a legitimate end of the line: it
# builds, it can be reached, and everything is refused from there.


def run(solution):
    spec = {"open": {"close": "closed"}, "closed": {}}
    machine = solution.Machine(spec, "open")
    machine.fire("close")
    assert machine.can("close") is False, (
        "args=%r got=%r want=%r" % ("can('close') in closed", machine.can("close"), False))
    try:
        machine.fire("close")
    except ValueError:
        assert machine.state == "closed", (
            "args=%r got=%r want=%r" % ("state after refusal", machine.state, "closed"))
        return
    raise AssertionError("args=%r got=%r want=%r" % ("fire('close') in closed", "moved", "ValueError"))
