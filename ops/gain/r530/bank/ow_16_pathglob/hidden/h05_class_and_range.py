# anchor_kind: goal
# anchor: a way to say "one of these characters" or "any character in this range"
# derivation: a listed set and a range each match exactly one character, and a
# class matches nothing outside itself.


def run(solution):
    cases = [("v[123]", "v2", True), ("v[123]", "v4", False), ("v[123]", "v23", False),
             ("[a-f]og", "cog", True), ("[a-f]og", "log", False),
             ("[a-cx-z]1", "y1", True)]
    for pattern, path, want in cases:
        got = solution.matches(pattern, path)
        assert got is want, "args=%r got=%r want=%r" % ((pattern, path), got, want)
