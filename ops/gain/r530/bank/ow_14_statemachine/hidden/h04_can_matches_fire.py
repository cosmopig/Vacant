# anchor_kind: contract
# anchor: `.can(event)` is True exactly when the current state's mapping has that
# event.
# derivation: for every state and every event name in play, can() and whether fire()
# succeeds must agree.

SPEC = {"a": {"x": "b", "y": "a"}, "b": {"x": "a"}}


def run(solution):
    for state in ("a", "b"):
        for event in ("x", "y", "z"):
            machine = solution.Machine(SPEC, state)
            allowed = machine.can(event)
            try:
                machine.fire(event)
                happened = True
            except ValueError:
                happened = False
            assert allowed is happened, (
                "args=%r got=%r want=%r" % ((state, event), (allowed, happened), "they agree"))
