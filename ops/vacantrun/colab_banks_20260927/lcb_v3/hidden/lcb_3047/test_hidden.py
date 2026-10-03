"""Scoring checks for lcb_3047 -- NOT part of any workspace.

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
    args = [[8, 7, 3, 5, 7, 2, 4, 9]]
    want = 16
    got = solution.maximumSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[5, 10, 3, 10, 1, 13, 7, 9, 4]]
    want = 19
    got = solution.maximumSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[43, 66, 2, 61, 71, 6]]
    want = 104
    got = solution.maximumSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[76, 56, 99, 36, 6, 24, 69]]
    want = 112
    got = solution.maximumSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[14, 6, 78, 2, 9, 10, 31, 52]]
    want = 78
    got = solution.maximumSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[100, 41, 39, 16, 86, 20, 96]]
    want = 116
    got = solution.maximumSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[1, 9, 2, 8, 4, 4, 2, 9, 3, 1]]
    want = 18
    got = solution.maximumSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[100, 3, 89, 6, 16, 47, 79, 29]]
    want = 106
    got = solution.maximumSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[3, 10, 7, 5, 4, 4, 10, 3, 6, 1]]
    want = 14
    got = solution.maximumSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[55, 80, 44, 24, 8, 65, 78, 43, 74]]
    want = 153
    got = solution.maximumSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[78, 26, 8, 81, 73, 18, 65, 35, 22, 79]]
    want = 181
    got = solution.maximumSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

