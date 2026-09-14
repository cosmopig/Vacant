# anchor_kind: goal
# anchor: that has to work even when there is nothing underneath at all
# derivation: the double star standing for zero segments is the case an
# at-least-one implementation gets wrong.


def run(solution):
    cases = [("src/**/main.py", "src/main.py", True),
             ("**/main.py", "main.py", True),
             ("a/**/b/**/c", "a/b/c", True),
             ("**", "anything", True)]
    for pattern, path, want in cases:
        got = solution.matches(pattern, path)
        assert got is want, "args=%r got=%r want=%r" % ((pattern, path), got, want)
