"""Checks that ship with this task. You can run them yourself: `sh run_tests.sh`.

Each `check_*` function is one check. A check passes when it returns
normally. These are the same checks the client runs before accepting
the work.
"""
import solution


def check_v01_first_appearance_order():
    """Visible check 1: one record per key, in the order the keys first showed up."""


    def _bank_entry(solution):
        records = [{"id": "b", "v": 1}, {"id": "a", "v": 2}, {"id": "b", "v": 3}]
        got = solution.dedupe(records, "id")
        want = [{"id": "b", "v": 1}, {"id": "a", "v": 2}]
        assert got == want, "args=%r got=%r want=%r" % (records, got, want)
    _bank_entry(solution)


def check_v02_keep_the_last():
    """Visible check 2: the later copy wins when asked for."""


    def _bank_entry(solution):
        records = [{"id": "x", "v": 1, "w": "old"}, {"id": "x", "v": 2, "w": "new"}]
        got = solution.dedupe(records, "id", "last")
        want = [{"id": "x", "v": 2, "w": "new"}]
        assert got == want, "args=%r got=%r want=%r" % (records, got, want)
    _bank_entry(solution)


def check_v03_merge_filled_fields():
    """Visible check 3: merging takes whichever fields are actually filled in."""


    def _bank_entry(solution):
        records = [{"id": "p", "name": "Ann", "email": None},
                   {"id": "p", "name": "Ann", "email": "ann@example.com"}]
        got = solution.dedupe(records, "id", "merge")
        want = [{"id": "p", "name": "Ann", "email": "ann@example.com"}]
        assert got == want, "args=%r got=%r want=%r" % (records, got, want)
    _bank_entry(solution)
