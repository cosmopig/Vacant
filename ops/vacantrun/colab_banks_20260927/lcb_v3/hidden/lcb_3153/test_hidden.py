"""Scoring checks for lcb_3153 -- NOT part of any workspace.

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
    args = [[2, 6, 5, 8], 2]
    want = 261
    got = solution.maxSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[4, 5, 4, 7], 3]
    want = 90
    got = solution.maxSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[24], 1]
    want = 576
    got = solution.maxSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[67, 58, 37, 3], 4]
    want = 17363
    got = solution.maxSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[52, 9, 63, 28, 32, 90, 55], 7]
    want = 27923
    got = solution.maxSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[78, 11, 80, 19, 35, 39, 34], 3]
    want = 33483
    got = solution.maxSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[62, 17, 8, 29, 68, 55, 28, 9, 19, 49], 2]
    want = 20098
    got = solution.maxSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[1, 81, 38, 17, 84, 20, 30, 18, 81, 4], 4]
    want = 31708
    got = solution.maxSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[93, 73, 47, 53, 24, 93, 46, 85, 4, 78], 4]
    want = 57036
    got = solution.maxSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[7237, 6994, 3465, 2168, 3526, 5331, 4278, 425, 4025, 1891], 5]
    want = 272935109
    got = solution.maxSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[78029, 29071, 43907, 72660, 19825, 30037, 81795, 75150, 98095, 82269], 10]
    want = 900017517
    got = solution.maxSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

