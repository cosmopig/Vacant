# anchor_kind: goal
# anchor: and a later pattern can put something back
# derivation: patterns are read left to right, so an add after a removal wins, and
# the same pair in the other order does not.


def run(solution):
    paths = ["a/x.py", "a/y.py", "b/x.py"]
    got = solution.select(["**/*.py", "!a/*.py", "a/y.py"], paths)
    want = ["a/y.py", "b/x.py"]
    assert got == want, "args=%r got=%r want=%r" % (paths, got, want)

    got = solution.select(["**/*.py", "a/y.py", "!a/*.py"], paths)
    want = ["b/x.py"]
    assert got == want, "args=%r got=%r want=%r" % (paths, got, want)
