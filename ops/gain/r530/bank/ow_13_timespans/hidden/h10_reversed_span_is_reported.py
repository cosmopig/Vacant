# anchor_kind: goal
# anchor: A period that ends before it starts is a bug in whoever sent it and has to
# be reported rather than quietly reversed.
# derivation: the reversed span raises from every entry point rather than being
# swapped into a plausible booking.


def run(solution):
    bad = [("2026-09-02T10:00:00", "2026-09-02T09:00:00")]
    for call in (lambda: solution.merge(bad),
                 lambda: solution.total_seconds(bad),
                 lambda: solution.subtract(bad, []),
                 lambda: solution.subtract([("2026-09-02", "2026-09-03")], bad)):
        try:
            call()
        except ValueError:
            continue
        raise AssertionError("args=%r got=%r want=%r" % (bad, "accepted", "ValueError"))
