"""Scoring checks for lcb_2954 -- NOT part of any workspace.

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
    args = [[2, 6, 7, 3, 1, 7], 3, 4]
    want = 18
    got = solution.maxSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[5, 9, 9, 2, 4, 5, 4], 1, 3]
    want = 23
    got = solution.maxSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[1, 2, 1, 2, 1, 2, 1], 3, 3]
    want = 0
    got = solution.maxSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[21, 100], 1, 1]
    want = 100
    got = solution.maxSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[41, 37, 91, 3], 2, 1]
    want = 0
    got = solution.maxSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[2, 5, 5, 5, 1, 9, 4, 8, 8, 4], 6, 6]
    want = 0
    got = solution.maxSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[8, 3, 9, 4, 6, 5, 3, 9, 8, 5], 1, 2]
    want = 17
    got = solution.maxSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[8, 3, 9, 4, 6, 5, 3, 9, 8, 5], 1, 6]
    want = 36
    got = solution.maxSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[8, 3, 9, 4, 6, 5, 3, 9, 8, 5], 9, 10]
    want = 0
    got = solution.maxSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[2, 3, 5, 2, 1, 2, 5, 7, 3, 7], 4, 10]
    want = 37
    got = solution.maxSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[8, 3, 9, 4, 6, 5, 3, 9, 8, 5], 1, 10]
    want = 60
    got = solution.maxSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

