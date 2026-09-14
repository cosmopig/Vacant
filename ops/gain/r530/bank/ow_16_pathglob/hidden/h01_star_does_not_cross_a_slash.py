# anchor_kind: goal
# anchor: A star should stay inside one directory level
# derivation: a star in the middle of a pattern cannot swallow a slash, so a deeper
# path does not match a shallower pattern.


def run(solution):
    cases = [("a/*/c", "a/b/c", True), ("a/*/c", "a/b/x/c", False),
             ("*", "one", True), ("*", "one/two", False),
             ("a*z", "abcz", True), ("a*z", "ab/cz", False)]
    for pattern, path, want in cases:
        got = solution.matches(pattern, path)
        assert got is want, "args=%r got=%r want=%r" % ((pattern, path), got, want)
