"""Checks that ship with this task. You can run them yourself: `sh run_tests.sh`.

Each `check_*` function is one check. A check passes when it returns
normally. These are the same checks the client runs before accepting
the work.
"""
import solution


def check_v01_star_stays_in_one_level():
    """Visible check 1: a star is one directory level, and the whole path must match."""


    def _bank_entry(solution):
        cases = [("src/*.py", "src/main.py", True),
                 ("src/*.py", "src/deep/main.py", False),
                 ("*.py", "main.py", True),
                 ("*.py", "a/main.py", False)]
        for pattern, path, want in cases:
            got = solution.matches(pattern, path)
            assert got is want, "args=%r got=%r want=%r" % ((pattern, path), got, want)
    _bank_entry(solution)


def check_v02_double_star_goes_deep():
    """Visible check 2: a double star reaches through directories."""


    def _bank_entry(solution):
        cases = [("src/**/*.py", "src/a/main.py", True),
                 ("src/**/*.py", "src/a/b/c/main.py", True),
                 ("src/**/*.py", "other/a/main.py", False)]
        for pattern, path, want in cases:
            got = solution.matches(pattern, path)
            assert got is want, "args=%r got=%r want=%r" % ((pattern, path), got, want)
    _bank_entry(solution)


def check_v03_classes_and_bad_patterns():
    """Visible check 3: character classes, and a pattern that was typed wrongly."""


    def _bank_entry(solution):
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
    _bank_entry(solution)
