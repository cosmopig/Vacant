"""Visible checks for lcb_3627 -- these ship with the task and can be run.

Rendered from ops/gain/data/lcb_bank_v2.jsonl (sha256 b98f027213e2...) by
ops/gain/r534/build_bank.py. The literal (args, expected) pairs are the bank's
`visible_tests` field, byte for byte.
"""

import solution

def _aeq(a, b):
    """與 vacant/codebench.py::_lcb_check_code 的 __aeq 同一套判等（逐行對應）。"""
    try:
        if a == b:
            return True
    except (TypeError, ValueError):
        pass
    if isinstance(a, bool) != isinstance(b, bool):
        return False
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= 1e-6
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_aeq(x, y) for x, y in zip(a, b))
    return a == b


def check_visible_01():
    args = [[[0, 4], [4, 4]]]
    want = 6
    got = solution.minTimeToReach(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_visible_02():
    args = [[[0, 0, 0], [0, 0, 0]]]
    want = 3
    got = solution.minTimeToReach(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_visible_03():
    args = [[[0, 1], [1, 2]]]
    want = 3
    got = solution.minTimeToReach(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

