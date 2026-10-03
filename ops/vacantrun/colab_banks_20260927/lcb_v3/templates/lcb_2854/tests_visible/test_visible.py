"""Visible checks for lcb_2854 -- these ship with the task and can be run.

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
    args = [['aa', 'ab', 'bc']]
    want = 4
    got = solution.minimizeConcatenatedLength(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_visible_02():
    args = [['ab', 'b']]
    want = 2
    got = solution.minimizeConcatenatedLength(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_visible_03():
    args = [['aaa', 'c', 'aba']]
    want = 6
    got = solution.minimizeConcatenatedLength(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

