"""Scoring checks for lcb_3265 -- NOT part of any workspace.

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
    args = [[1, 2, 3, 4, 5, 6], 1]
    want = 11
    got = solution.maximumSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[-1, 3, 2, 4, 5], 3]
    want = 11
    got = solution.maximumSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[-1, -2, -3, -4], 2]
    want = -6
    got = solution.maximumSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[-1, 0], 1]
    want = -1
    got = solution.maximumSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[0, -9], 10]
    want = 0
    got = solution.maximumSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[457, 627], 10]
    want = 0
    got = solution.maximumSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[5, -1, -5, -3, 7], 8]
    want = -2
    got = solution.maximumSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[52, -352], 1000000000]
    want = 0
    got = solution.maximumSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[270645956, -790693743], 10]
    want = 0
    got = solution.maximumSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[-104965022, 933472124], 1000]
    want = 0
    got = solution.maximumSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[-96, -96, -9, 43, -85, -53], 18]
    want = 0
    got = solution.maximumSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[9, 7, -8, 6, 6, 1, 2, 6, -8], 10]
    want = 7
    got = solution.maximumSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

