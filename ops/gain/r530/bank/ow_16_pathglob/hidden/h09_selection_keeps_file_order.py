# anchor_kind: goal
# anchor: The answer comes back in the order the files were listed, with nothing
# listed twice.
# derivation: two patterns that pick overlapping sets, written in the opposite order
# to the file list, still answer in file-list order and list nothing twice.


def run(solution):
    paths = ["a.py", "b.txt", "c.py", "d.md", "e.py"]
    got = solution.select(["*.py", "*.py", "*.md"], paths)
    want = ["a.py", "c.py", "d.md", "e.py"]
    assert got == want, "args=%r got=%r want=%r" % (paths, got, want)
