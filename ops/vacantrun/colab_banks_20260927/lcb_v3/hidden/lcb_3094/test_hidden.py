"""Scoring checks for lcb_3094 -- NOT part of any workspace.

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
    args = [[2, 3, 3, 2, 2, 4, 2, 3, 4]]
    want = 4
    got = solution.minOperations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[2, 1, 2, 2, 3, 3]]
    want = -1
    got = solution.minOperations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[9, 10]]
    want = -1
    got = solution.minOperations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[3, 6, 6]]
    want = -1
    got = solution.minOperations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[669163, 704685]]
    want = -1
    got = solution.minOperations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[4047, 3627, 6536]]
    want = -1
    got = solution.minOperations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[7, 5, 1, 3, 8, 9]]
    want = -1
    got = solution.minOperations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[7, 5, 3, 5, 7, 8]]
    want = -1
    got = solution.minOperations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[1, 96, 85, 46, 98]]
    want = -1
    got = solution.minOperations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[15, 95, 28, 16, 22]]
    want = -1
    got = solution.minOperations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[4, 6, 8, 1, 9, 4, 3, 3, 3, 9, 10, 10, 8, 6, 5, 10, 4, 3, 1, 7, 6, 6, 10, 1, 2, 2, 2, 7, 10, 4, 1, 8, 7, 3, 10, 10, 1, 3, 8, 6, 7, 6, 2, 1, 1, 5, 6, 10, 4, 8, 5, 5, 4, 8, 7, 10, 6, 10, 7, 8, 4, 7, 1, 10, 3, 5, 8, 1, 5, 9, 5, 9, 3, 5, 3, 8, 8, 7, 4, 5, 5, 3, 9, 5, 4, 6, 5, 4, 3, 7, 5, 8, 5, 10, 8]]
    want = 34
    got = solution.minOperations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

