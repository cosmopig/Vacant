# anchor_kind: goal
# anchor: Asking for a way of resolving disagreements that does not exist is a
# programming mistake and should say so.
# derivation: anything outside the three names raises, including near misses and
# the empty string.


def run(solution):
    for policy in ("newest", "First", "", "merge ", None):
        try:
            solution.dedupe([{"k": 1}], "k", policy)
        except ValueError:
            continue
        raise AssertionError("args=%r got=%r want=%r" % (policy, "accepted", "ValueError"))
