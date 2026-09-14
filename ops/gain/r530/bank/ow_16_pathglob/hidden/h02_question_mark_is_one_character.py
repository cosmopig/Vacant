# anchor_kind: goal
# anchor: They also need a single-character wildcard
# derivation: exactly one character, no more and no fewer, and never the separator.


def run(solution):
    cases = [("a?c", "abc", True), ("a?c", "ac", False), ("a?c", "abbc", False),
             ("a?c", "a/c", False)]
    for pattern, path, want in cases:
        got = solution.matches(pattern, path)
        assert got is want, "args=%r got=%r want=%r" % ((pattern, path), got, want)
