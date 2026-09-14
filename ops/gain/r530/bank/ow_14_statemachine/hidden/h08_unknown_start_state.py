# anchor_kind: goal
# anchor: a starting state that is not on the whiteboard at all
# derivation: the mistake is reported when the rules are handed over, so building
# the machine raises rather than the first event failing.

SPEC = {"a": {"go": "b"}, "b": {}}


def run(solution):
    for start in ("c", "", "A"):
        try:
            solution.Machine(SPEC, start)
        except ValueError:
            continue
        raise AssertionError("args=%r got=%r want=%r" % (start, "constructed", "ValueError"))
