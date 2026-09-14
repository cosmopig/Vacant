"""Visible check 3: character classes, and a pattern that was typed wrongly."""


def run(solution):
    cases = [("log[0-9].txt", "log7.txt", True),
             ("log[0-9].txt", "logx.txt", False),
             ("file[abc]", "fileb", True)]
    for pattern, path, want in cases:
        got = solution.matches(pattern, path)
        assert got is want, "args=%r got=%r want=%r" % ((pattern, path), got, want)

    for pattern in ("src/[abc.py", "src/[].py"):
        try:
            solution.matches(pattern, "src/a.py")
        except ValueError:
            continue
        raise AssertionError("args=%r got=%r want=%r" % (pattern, "answered", "ValueError"))

if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    import solution
    run(solution)
    print("PASS v03_classes_and_bad_patterns")
