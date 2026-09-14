# anchor_kind: goal
# anchor: a pattern beginning with an exclamation mark removes what the earlier ones
# picked up
# derivation: the removal applies to what has already been chosen, and leaves the
# rest in place and in order.


def run(solution):
    paths = ["src/a.py", "src/b.py", "src/test_a.py", "src/test_b.py"]
    got = solution.select(["src/*.py", "!src/test_*.py"], paths)
    want = ["src/a.py", "src/b.py"]
    assert got == want, "args=%r got=%r want=%r" % (paths, got, want)
