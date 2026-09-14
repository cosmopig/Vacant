# anchor_kind: goal
# anchor: Characters that mean something to a regular expression -- a dot, a plus, a
# bracket sitting in a file name -- are ordinary characters in a path.
# derivation: a dot in a pattern matches only a dot, and a plus or a parenthesis in
# a file name is matched by writing it out.


def run(solution):
    cases = [("a.py", "axpy", False), ("a.py", "a.py", True),
             ("c++/main.cc", "c++/main.cc", True), ("c++/main.cc", "cxx/main.cc", False),
             ("re(1).txt", "re(1).txt", True), ("a|b", "a|b", True), ("a|b", "a", False)]
    for pattern, path, want in cases:
        got = solution.matches(pattern, path)
        assert got is want, "args=%r got=%r want=%r" % ((pattern, path), got, want)
