"""Scoring checks for lcb_3292 -- NOT part of any workspace.

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
    args = [[2, 2, 0], [2, 2, 2, 2, 3, 2, 2, 1]]
    want = 8
    got = solution.earliestSecondToMarkIndices(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[1, 3], [1, 1, 1, 2, 1, 1, 1]]
    want = 6
    got = solution.earliestSecondToMarkIndices(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[0, 1], [2, 2, 2]]
    want = -1
    got = solution.earliestSecondToMarkIndices(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[1, 3, 0, 2, 6, 2, 0], [2]]
    want = -1
    got = solution.earliestSecondToMarkIndices(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[1, 9, 7, 6, 0, 7, 5], [1, 5]]
    want = -1
    got = solution.earliestSecondToMarkIndices(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[2, 8, 3, 7, 9, 10], [5, 4, 4, 5]]
    want = -1
    got = solution.earliestSecondToMarkIndices(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[7, 7, 9, 4, 0, 3, 9, 6], [7, 3, 1, 8]]
    want = -1
    got = solution.earliestSecondToMarkIndices(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[3, 5, 7, 9, 9, 0, 0, 9, 2, 6], [5, 1, 7, 3]]
    want = -1
    got = solution.earliestSecondToMarkIndices(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[4, 1, 2, 5, 7], [1, 5, 4, 4, 5, 5, 4, 3, 5, 2]]
    want = -1
    got = solution.earliestSecondToMarkIndices(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[3, 0], [2, 2, 1, 2, 1, 2, 2, 2, 1, 1, 1, 1, 2, 1]]
    want = 5
    got = solution.earliestSecondToMarkIndices(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[3, 5, 0, 0, 3, 0], [1, 5, 5, 1, 3, 6, 6, 2, 6, 2, 1, 2, 1, 5, 2, 5]]
    want = -1
    got = solution.earliestSecondToMarkIndices(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[888018, 591426, 570202, 176136, 936227, 539656, 569394, 290932, 180408, 0], [10, 10, 10, 10, 10, 10, 10, 10, 10, 10]]
    want = -1
    got = solution.earliestSecondToMarkIndices(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

