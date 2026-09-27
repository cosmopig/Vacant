"""Scoring checks for lcb_3298 -- NOT part of any workspace.

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
    args = [[2, 1, 5, 1, 1]]
    want = 3
    got = solution.maxSelectedElements(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[1, 4, 7, 10]]
    want = 1
    got = solution.maxSelectedElements(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[9, 5]]
    want = 1
    got = solution.maxSelectedElements(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[10, 58, 89, 60, 55]]
    want = 2
    got = solution.maxSelectedElements(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[1, 3, 3, 4, 5, 6, 7, 8, 9, 10]]
    want = 10
    got = solution.maxSelectedElements(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[1, 2, 3, 4, 5, 6, 7, 8, 10, 10]]
    want = 10
    got = solution.maxSelectedElements(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[2, 2, 4, 4, 6, 6, 8, 8, 10, 10]]
    want = 10
    got = solution.maxSelectedElements(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[16, 14, 12, 11, 10, 8, 7, 4, 3, 1]]
    want = 5
    got = solution.maxSelectedElements(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[0, 10, 2, 10, 4, 10, 6, 10, 8, 10]]
    want = 3
    got = solution.maxSelectedElements(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[95, 39, 80, 90, 55, 90, 83, 5, 20, 98]]
    want = 2
    got = solution.maxSelectedElements(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[33, 99, 15, 16, 62, 21, 13, 77, 90, 53]]
    want = 3
    got = solution.maxSelectedElements(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

