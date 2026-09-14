# anchor_kind: goal
# anchor: Rules that point at a state nobody defined
# derivation: an event leading somewhere that is not a state is caught at hand-over,
# even when no order would ever reach it.


def run(solution):
    spec = {"a": {"go": "b"}, "b": {"onward": "nowhere"}}
    try:
        solution.Machine(spec, "a")
    except ValueError:
        return
    raise AssertionError("args=%r got=%r want=%r" % (spec, "constructed", "ValueError"))
