# anchor_kind: goal
# anchor: one per place that changed, so that a reviewer sees the two lines that
# moved rather than one block covering everything between them
# derivation: two edits far apart give two pieces, each holding only its own changed
# line, not one piece spanning the untouched middle.


def run(solution):
    old = ["l%d" % index for index in range(10)]
    new = list(old)
    new[2] = "TWO"
    new[7] = "SEVEN"
    pieces = solution.diff(old, new)
    assert len(pieces) == 2, "args=%r got=%r want=%r" % ((old, new), pieces, "two pieces")
    want = [{"start": 2, "old": ["l2"], "new": ["TWO"]},
            {"start": 7, "old": ["l7"], "new": ["SEVEN"]}]
    assert pieces == want, "args=%r got=%r want=%r" % ((old, new), pieces, want)
