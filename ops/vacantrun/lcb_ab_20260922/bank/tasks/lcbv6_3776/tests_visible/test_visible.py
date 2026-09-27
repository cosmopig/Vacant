"""Visible checks for lcbv6_3776 — LiveCodeBench v6 的 public_test_cases（題目頁面上看得到的那幾條）。"""

import solution

def _aeq(a, b):
    """與 vacant_network/codebench.py::_lcb_check_code 的 __aeq 同一套判等。"""
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
    args = [[6, 2, 8, 4]]
    want = 12
    got = solution.minCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

def check_visible_02():
    args = [[2, 1, 3, 3]]
    want = 5
    got = solution.minCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)
