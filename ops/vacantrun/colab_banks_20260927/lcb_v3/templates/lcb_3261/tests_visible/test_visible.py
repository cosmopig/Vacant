"""Visible checks for lcb_3261 -- these ship with the task and can be run.

Rendered from ops/gain/data/lcb_bank_v3.jsonl (sha256 bd3dffebb1b1...) by
ops/vacantrun/colab_banks_20260927/build_banks.py. The literal (args, expected) pairs are the bank's
`visible_tests` field, byte for byte.
"""

import solution

def _aeq(a, b):
    """與 vacant_network/codebench.py::_lcb_check_code 的 __aeq 同一套判等（逐行對應）。"""
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
    args = [[3, 5, 3, 2, 7], 2]
    want = 3
    got = solution.minOrAfterOperations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_visible_02():
    args = [[7, 3, 15, 14, 2, 8], 4]
    want = 2
    got = solution.minOrAfterOperations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_visible_03():
    args = [[10, 7, 10, 3, 9, 14, 9, 4], 1]
    want = 15
    got = solution.minOrAfterOperations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

