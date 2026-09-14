# anchor_kind: goal
# anchor: including the negative form
# derivation: a leading exclamation mark inside the brackets flips the class, and it
# still stands for exactly one character.


def run(solution):
    cases = [("x[!0-9]", "xa", True), ("x[!0-9]", "x5", False),
             ("[!a]bc", "zbc", True), ("[!a]bc", "abc", False),
             ("x[!0-9]", "x", False)]
    for pattern, path, want in cases:
        got = solution.matches(pattern, path)
        assert got is want, "args=%r got=%r want=%r" % ((pattern, path), got, want)
