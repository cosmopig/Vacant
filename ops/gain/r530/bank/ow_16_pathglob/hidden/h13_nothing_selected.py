# anchor_kind: contract
# anchor: A plain pattern adds every path that matches it
# derivation: patterns that match nothing give an empty answer, and an empty list of
# patterns selects nothing at all.


def run(solution):
    paths = ["a.py", "b.py"]
    assert solution.select([], paths) == [], (
        "args=%r got=%r want=%r" % (paths, solution.select([], paths), []))
    assert solution.select(["*.md"], paths) == [], (
        "args=%r got=%r want=%r" % (paths, solution.select(["*.md"], paths), []))
    assert solution.select(["!*.py"], paths) == [], (
        "args=%r got=%r want=%r" % (paths, solution.select(["!*.py"], paths), []))
