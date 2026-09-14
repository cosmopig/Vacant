"""Visible check 1: a star is one directory level, and the whole path must match."""


def run(solution):
    cases = [("src/*.py", "src/main.py", True),
             ("src/*.py", "src/deep/main.py", False),
             ("*.py", "main.py", True),
             ("*.py", "a/main.py", False)]
    for pattern, path, want in cases:
        got = solution.matches(pattern, path)
        assert got is want, "args=%r got=%r want=%r" % ((pattern, path), got, want)

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v01_star_stays_in_one_level")
