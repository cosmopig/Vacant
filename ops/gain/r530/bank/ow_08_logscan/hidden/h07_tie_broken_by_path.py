# anchor_kind: goal
# anchor: when two are equally busy they want the order to be the same every time
# they run it
# derivation: equal counts are separated by the path in ordinary string order, so
# the answer does not depend on which path appeared first in the file.


def run(solution):
    first = ["2026-01-01T00:00:00Z GET /zebra 200 1", "2026-01-01T00:00:01Z GET /apple 200 1"]
    second = list(reversed(first))
    got_first = [row["path"] for row in solution.summarize(first)["endpoints"]]
    got_second = [row["path"] for row in solution.summarize(second)["endpoints"]]
    want = ["/apple", "/zebra"]
    assert got_first == want, "args=%r got=%r want=%r" % (first, got_first, want)
    assert got_second == want, "args=%r got=%r want=%r" % (second, got_second, want)
