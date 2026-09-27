"""Scoring checks for lcb_2728 -- NOT part of any workspace.

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
    args = [[[7, 2, 1], [6, 4, 2], [6, 5, 3], [3, 2, 1]]]
    want = 15
    got = solution.matrixSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[[1]]]
    want = 1
    got = solution.matrixSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[[0], [10], [25], [2], [8]]]
    want = 25
    got = solution.matrixSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[[4, 14, 13, 4], [4, 21, 14, 1]]]
    want = 43
    got = solution.matrixSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[[40, 655, 363], [554, 396, 682]]]
    want = 1632
    got = solution.matrixSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[[938], [167], [760], [320], [234]]]
    want = 938
    got = solution.matrixSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[[900, 187], [395, 124], [451, 622], [714, 34]]]
    want = 1351
    got = solution.matrixSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[[25, 41, 5, 54], [35, 2, 60, 48], [1, 22, 47, 55], [2, 4, 11, 48]]]
    want = 148
    got = solution.matrixSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[[12, 26, 16, 12], [41, 1, 2, 6], [38, 45, 9, 25], [18, 22, 29, 41]]]
    want = 126
    got = solution.matrixSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[[234, 492, 348, 635, 971, 194, 505], [889, 873, 244, 938, 737, 6, 488]]]
    want = 4396
    got = solution.matrixSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[[677, 457, 892], [483, 110, 349], [283, 449, 683], [21, 888, 700], [478, 33, 211], [966, 236, 834]]]
    want = 2257
    got = solution.matrixSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

