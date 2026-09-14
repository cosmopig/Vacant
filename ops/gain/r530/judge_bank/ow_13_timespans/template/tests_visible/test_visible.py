"""Checks that ship with this task. You can run them yourself: `sh run_tests.sh`.

Each `check_*` function is one check. A check passes when it returns
normally. These are the same checks the client runs before accepting
the work.
"""
import solution


def check_v01_merge_overlaps():
    """Visible check 1: overlapping periods fold into one, in order."""


    def _bank_entry(solution):
        spans = [("2026-03-02T09:00:00", "2026-03-02T10:30:00"),
                 ("2026-03-02T10:00:00", "2026-03-02T11:00:00"),
                 ("2026-03-02T14:00:00", "2026-03-02T15:00:00")]
        got = solution.merge(spans)
        want = [("2026-03-02T09:00:00", "2026-03-02T11:00:00"),
                ("2026-03-02T14:00:00", "2026-03-02T15:00:00")]
        assert got == want, "args=%r got=%r want=%r" % (spans, got, want)
    _bank_entry(solution)


def check_v02_subtract_from_an_end():
    """Visible check 2: taking a period out of the front of a busy stretch."""


    def _bank_entry(solution):
        spans = [("2026-03-02T09:00:00", "2026-03-02T12:00:00")]
        holes = [("2026-03-02T08:00:00", "2026-03-02T10:00:00")]
        got = solution.subtract(spans, holes)
        want = [("2026-03-02T10:00:00", "2026-03-02T12:00:00")]
        assert got == want, "args=%r got=%r want=%r" % ((spans, holes), got, want)
    _bank_entry(solution)


def check_v03_total():
    """Visible check 3: the total of the tidy list, in whole seconds."""


    def _bank_entry(solution):
        spans = [("2026-03-02T09:00:00", "2026-03-02T10:00:00"),
                 ("2026-03-02T09:30:00", "2026-03-02T11:00:00")]
        got = solution.total_seconds(spans)
        assert got == 7200, "args=%r got=%r want=%r" % (spans, got, 7200)
        assert isinstance(got, int), "args=%r got=%r want=%r" % (spans, type(got).__name__, "int")
    _bank_entry(solution)
