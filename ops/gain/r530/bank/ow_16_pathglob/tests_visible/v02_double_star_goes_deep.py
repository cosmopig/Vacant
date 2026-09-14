"""Visible check 2: a double star reaches through directories."""


def run(solution):
    cases = [("src/**/*.py", "src/a/main.py", True),
             ("src/**/*.py", "src/a/b/c/main.py", True),
             ("src/**/*.py", "other/a/main.py", False)]
    for pattern, path, want in cases:
        got = solution.matches(pattern, path)
        assert got is want, "args=%r got=%r want=%r" % ((pattern, path), got, want)

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v02_double_star_goes_deep")
