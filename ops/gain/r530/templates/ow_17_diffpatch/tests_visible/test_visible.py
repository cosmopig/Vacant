"""Checks that ship with this task. You can run them yourself: `sh run_tests.sh`.

Each `check_*` function is one check. A check passes when it returns
normally. These are the same checks the client runs before accepting
the work.
"""
import solution


def check_v01_out_and_back():
    """Visible check 1: the pieces put back onto the old version give the new one."""


    def _bank_entry(solution):
        old = ["one", "two", "three", "four"]
        new = ["one", "TWO", "three", "four"]
        pieces = solution.diff(old, new)
        got = solution.apply(old, pieces)
        assert got == new, "args=%r got=%r want=%r" % ((old, new), got, new)
    _bank_entry(solution)


def check_v02_shape_of_a_piece():
    """Visible check 2: one changed line gives one piece holding just that line."""


    def _bank_entry(solution):
        old = ["a", "b", "c", "d", "e"]
        new = ["a", "b", "CHANGED", "d", "e"]
        pieces = solution.diff(old, new)
        assert len(pieces) == 1, "args=%r got=%r want=%r" % ((old, new), pieces, "one piece")
        piece = pieces[0]
        assert sorted(piece) == ["new", "old", "start"], (
            "args=%r got=%r want=%r" % ((old, new), sorted(piece), ["new", "old", "start"]))
        want = {"start": 2, "old": ["c"], "new": ["CHANGED"]}
        assert piece == want, "args=%r got=%r want=%r" % ((old, new), piece, want)
    _bank_entry(solution)


def check_v03_refuses_a_piece_that_does_not_fit():
    """Visible check 3: pieces made for another version are refused."""


    def _bank_entry(solution):
        old = ["a", "b", "c"]
        new = ["a", "B", "c"]
        pieces = solution.diff(old, new)
        someone_else_edited = ["a", "x", "c"]
        try:
            solution.apply(someone_else_edited, pieces)
        except ValueError:
            return
        raise AssertionError("args=%r got=%r want=%r"
                             % (someone_else_edited, "patched anyway", "ValueError"))
    _bank_entry(solution)
