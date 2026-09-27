"""Scoring checks for lcb_3171 -- NOT part of any workspace.

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
    args = [[3, 2, 0, 1, 0], [6, 5, 0]]
    want = 12
    got = solution.minSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[2, 0, 2, 0], [1, 4]]
    want = -1
    got = solution.minSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[1], [0]]
    want = 1
    got = solution.minSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[7098], [4050]]
    want = -1
    got = solution.minSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[97868], [29855]]
    want = -1
    got = solution.minSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[5, 8, 2, 6, 0], [5, 6]]
    want = -1
    got = solution.minSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[0, 3, 2, 0], [7, 4, 0, 9]]
    want = 21
    got = solution.minSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[6, 0, 4, 1, 3], [2, 3, 0, 0, 0]]
    want = 15
    got = solution.minSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[10, 0, 7, 8, 9], [8, 2, 7, 5, 4]]
    want = -1
    got = solution.minSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[4, 0, 1, 9], [9, 9, 10, 1, 0, 8, 9]]
    want = 47
    got = solution.minSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

