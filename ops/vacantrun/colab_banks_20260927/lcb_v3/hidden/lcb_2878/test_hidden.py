"""Scoring checks for lcb_2878 -- NOT part of any workspace.

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
    args = [[2, 2, 3, 1, 1, 0], 3]
    want = True
    got = solution.checkArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[1, 3, 1, 1], 2]
    want = False
    got = solution.checkArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[6, 6, 9, 6, 4, 9, 3, 10, 10], 2]
    want = False
    got = solution.checkArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[8, 2, 7, 6, 7, 8, 5, 4, 4, 5], 5]
    want = False
    got = solution.checkArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[0, 7, 5, 2, 6, 5, 4, 10, 4, 8], 5]
    want = False
    got = solution.checkArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[4, 8, 9, 5, 2, 10, 7, 10, 1, 8], 1]
    want = True
    got = solution.checkArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[7, 9, 0, 7, 9, 10, 2, 10, 2, 5], 5]
    want = False
    got = solution.checkArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[77, 39, 45, 53, 67, 60, 67, 94, 58, 83], 1]
    want = True
    got = solution.checkArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[62, 84, 65, 82, 25, 59, 65, 13, 43, 39], 3]
    want = False
    got = solution.checkArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[275, 359, 358, 791, 94, 57, 502, 669, 189, 506], 10]
    want = False
    got = solution.checkArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[263, 593, 185, 455, 804, 616, 593, 225, 601, 588], 2]
    want = False
    got = solution.checkArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

