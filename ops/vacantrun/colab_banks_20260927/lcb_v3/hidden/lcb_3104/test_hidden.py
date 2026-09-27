"""Scoring checks for lcb_3104 -- NOT part of any workspace.

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
    args = [[1, 1]]
    want = 2
    got = solution.countWays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[6, 0, 3, 3, 6, 7, 2, 7]]
    want = 3
    got = solution.countWays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[0]]
    want = 1
    got = solution.countWays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[1, 1]]
    want = 2
    got = solution.countWays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[1, 1, 2]]
    want = 2
    got = solution.countWays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[2, 0, 2, 2, 4]]
    want = 2
    got = solution.countWays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[1, 2, 2, 0, 0]]
    want = 1
    got = solution.countWays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[6, 0, 3, 3, 6, 7, 2, 7]]
    want = 3
    got = solution.countWays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[0, 4, 7, 1, 8, 8, 2, 0, 2]]
    want = 2
    got = solution.countWays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[0, 1, 5, 4, 8, 8, 3, 4, 8, 3]]
    want = 3
    got = solution.countWays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[55, 31, 88, 21, 38, 33, 69, 80, 81, 14, 19, 63, 80, 87, 51, 49, 86, 62, 19, 74, 61, 46, 17, 23, 87, 0, 24, 0, 47, 99, 65, 95, 8, 60, 11, 74, 89, 98, 33, 11, 67, 27, 3, 89, 56, 42, 47, 59, 43, 99, 30, 52, 95, 63, 54, 20, 50, 54, 55, 44, 0, 87, 70, 99, 38, 53, 85, 70, 84, 51, 32, 67, 2, 64, 30, 11, 6, 26, 54, 99, 35, 18, 28, 14, 40, 51, 64, 25, 50, 69, 31, 21, 77, 47, 30, 5, 89, 0, 98, 0]]
    want = 10
    got = solution.countWays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

