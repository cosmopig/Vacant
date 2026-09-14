# anchor_kind: goal
# anchor: A pattern has to match the whole path: half a match is not a match.
# derivation: a pattern that fits the start, or the end, or the middle of a path is
# not a match unless it fits all of it.


def run(solution):
    cases = [("main", "main.py", False), ("main.py", "src/main.py", False),
             ("src", "src/main.py", False), ("ain.py", "main.py", False),
             ("main.py", "main.py", True)]
    for pattern, path, want in cases:
        got = solution.matches(pattern, path)
        assert got is want, "args=%r got=%r want=%r" % ((pattern, path), got, want)
