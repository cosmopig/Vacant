"""Scoring checks for lcb_3329 -- NOT part of any workspace.

⚠ 計分用的 GT。住在 hidden/ 這棵**另外的樹**，永遠不複製進 agent 的工作區；
  任何把它的內容（含失敗訊息）回饋給模型的路徑都作廢那一批資料。

case 組成 ＝ 題庫的 `visible_tests` ＋ `hidden_tests`（超集），與
vacant_network/codebench.py::LiveCodeBenchLoader 的 `hidden_check` 同一組（ops/gain/data/lcb_bank_v3.jsonl）。
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


def check_case_01():
    args = [[1, 10, 100], [1000]]
    want = 3
    got = solution.longestCommonPrefix(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[1, 2, 3], [4, 4, 4]]
    want = 0
    got = solution.longestCommonPrefix(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[1], [99999999]]
    want = 0
    got = solution.longestCommonPrefix(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[25, 26], [65, 22]]
    want = 1
    got = solution.longestCommonPrefix(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[10000000], [10000000]]
    want = 8
    got = solution.longestCommonPrefix(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[23, 100, 11, 96], [20]]
    want = 1
    got = solution.longestCommonPrefix(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[81, 23, 98, 52], [5, 42]]
    want = 1
    got = solution.longestCommonPrefix(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[67, 41, 18], [41, 10, 53]]
    want = 2
    got = solution.longestCommonPrefix(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[123456, 12345678], [123456]]
    want = 6
    got = solution.longestCommonPrefix(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[83, 37, 14, 44, 51], [4, 95, 88, 31]]
    want = 1
    got = solution.longestCommonPrefix(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

