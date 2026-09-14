# anchor_kind: contract
# anchor: `merge` returns the union of the spans as the shortest list that covers it
# derivation: no spans means no stretches and a total of zero, and subtracting from
# nothing is still nothing.


def run(solution):
    assert solution.merge([]) == [], "args=%r got=%r want=%r" % ([], solution.merge([]), [])
    assert solution.total_seconds([]) == 0, (
        "args=%r got=%r want=%r" % ([], solution.total_seconds([]), 0))
    assert solution.subtract([], [("2026-01-01", "2026-01-02")]) == [], (
        "args=%r got=%r want=%r" % ("empty spans", solution.subtract([], [("2026-01-01", "2026-01-02")]), []))
