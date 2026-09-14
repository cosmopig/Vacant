"""Checks that ship with this task. You can run them yourself: `sh run_tests.sh`.

Each `check_*` function is one check. A check passes when it returns
normally. These are the same checks the client runs before accepting
the work.
"""
import solution


def check_v01_the_secret_goes_the_rest_stays():
    """Visible check 1: the key is gone and the line is still readable."""


    def _bank_entry(solution):
        line = "2026-09-13 WARN starting upload with AKIAIOSFODNN7EXAMPLE to bucket logs"
        got = solution.redact(line)
        assert "AKIAIOSFODNN7EXAMPLE" not in got, (
            "args=%r got=%r want=%r" % (line, got, "the key removed"))
        for word in ("2026-09-13", "WARN", "starting", "upload", "bucket", "logs"):
            assert word in got, "args=%r got=%r want=%r" % (line, got, "the word %r kept" % word)
    _bank_entry(solution)


def check_v02_clean_lines_and_second_passes():
    """Visible check 2: an ordinary line is untouched, and a second pass does nothing."""


    def _bank_entry(solution):
        clean = "2026-09-13 INFO served GET /health in 3ms"
        got = solution.redact(clean)
        assert got == clean, "args=%r got=%r want=%r" % (clean, got, clean)
        assert solution.findings(clean) == [], (
            "args=%r got=%r want=%r" % (clean, solution.findings(clean), []))

        dirty = "connecting to postgres://svc:hunter2@db.internal:5432/app now"
        once = solution.redact(dirty)
        twice = solution.redact(once)
        assert once == twice, "args=%r got=%r want=%r" % (dirty, twice, once)
    _bank_entry(solution)
