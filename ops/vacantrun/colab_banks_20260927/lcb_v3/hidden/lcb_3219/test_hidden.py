"""Scoring checks for lcb_3219 -- NOT part of any workspace.

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
    args = [[1, 5, 3, 9, 8], 2]
    want = [1, 3, 5, 8, 9]
    got = solution.lexicographicallySmallestArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[1, 7, 6, 18, 2, 1], 3]
    want = [1, 6, 7, 18, 1, 2]
    got = solution.lexicographicallySmallestArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[1, 7, 28, 19, 10], 3]
    want = [1, 7, 28, 19, 10]
    got = solution.lexicographicallySmallestArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[97, 7], 28]
    want = [97, 7]
    got = solution.lexicographicallySmallestArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[85, 32], 3]
    want = [85, 32]
    got = solution.lexicographicallySmallestArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[46, 81, 64], 10]
    want = [46, 81, 64]
    got = solution.lexicographicallySmallestArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[7, 59, 68, 74, 69, 11], 1]
    want = [7, 59, 68, 74, 69, 11]
    got = solution.lexicographicallySmallestArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[6, 79, 84, 2, 29, 30, 33], 36]
    want = [2, 79, 84, 6, 29, 30, 33]
    got = solution.lexicographicallySmallestArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[10, 9, 8, 7, 6, 5, 4, 3, 2, 1], 5]
    want = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    got = solution.lexicographicallySmallestArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[20, 5, 3, 17, 8, 11, 13, 18, 20, 8], 4]
    want = [3, 5, 8, 8, 11, 13, 17, 18, 20, 20]
    got = solution.lexicographicallySmallestArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

