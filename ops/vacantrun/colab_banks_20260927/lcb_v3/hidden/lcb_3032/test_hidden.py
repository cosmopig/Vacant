"""Scoring checks for lcb_3032 -- NOT part of any workspace.

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
    args = [[2, 0, 1], 4]
    want = 6
    got = solution.getMaxFunctionValue(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[1, 1, 1, 2, 3], 3]
    want = 10
    got = solution.getMaxFunctionValue(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[0, 0], 99]
    want = 1
    got = solution.getMaxFunctionValue(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[2, 0, 1], 1]
    want = 3
    got = solution.getMaxFunctionValue(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[0, 0, 1], 3]
    want = 3
    got = solution.getMaxFunctionValue(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[2, 0, 0], 5]
    want = 6
    got = solution.getMaxFunctionValue(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[4, 1, 5, 5, 9, 0, 4, 2, 9, 4], 1]
    want = 17
    got = solution.getMaxFunctionValue(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[6, 2, 3, 7, 1, 1, 2, 4, 4, 9], 10]
    want = 99
    got = solution.getMaxFunctionValue(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[8, 6, 0, 6, 4, 1, 5, 6, 0, 4], 10]
    want = 49
    got = solution.getMaxFunctionValue(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[2, 9, 3, 0, 4, 9, 4, 8, 4, 6], 10000000]
    want = 40000012
    got = solution.getMaxFunctionValue(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[8, 1, 9, 2, 0, 4, 4, 9, 1, 5], 10000000]
    want = 10000028
    got = solution.getMaxFunctionValue(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[7, 9, 7, 5, 3, 5, 2, 7, 9, 4], 100000000]
    want = 700000007
    got = solution.getMaxFunctionValue(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

