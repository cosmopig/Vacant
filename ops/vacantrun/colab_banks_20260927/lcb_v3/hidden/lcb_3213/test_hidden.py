"""Scoring checks for lcb_3213 -- NOT part of any workspace.

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
    args = [[1, 3, 2, 3, 3], 2]
    want = 6
    got = solution.countSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[1, 4, 2, 1], 3]
    want = 0
    got = solution.countSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[8], 1]
    want = 1
    got = solution.countSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[5, 8, 9, 5], 4]
    want = 0
    got = solution.countSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[2, 6, 6, 10, 5, 5, 9], 2]
    want = 0
    got = solution.countSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[9, 2, 3, 9, 9, 3, 7, 8, 10], 3]
    want = 0
    got = solution.countSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[5, 3, 5, 9, 8, 4, 1, 8, 8, 3], 1]
    want = 28
    got = solution.countSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[7, 6, 1, 8, 10, 7, 6, 10, 3, 6], 3]
    want = 0
    got = solution.countSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[66, 4, 32, 15, 24, 34, 5, 10, 33, 42], 1]
    want = 10
    got = solution.countSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[4036, 6325, 9128, 2663, 6238, 9498, 9088, 8341, 9586, 7636], 10]
    want = 0
    got = solution.countSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[10, 7, 9, 1, 10, 9, 8, 1, 6, 5, 10, 8, 1, 1, 10, 4, 5, 6, 7, 9, 8, 3, 7, 6, 7, 5, 3, 10, 5, 8, 3, 1, 10, 10, 7, 3, 8, 4, 4, 3, 2, 10, 6, 1, 1, 3, 1, 3, 7, 6, 2, 2, 5, 8, 10, 5, 5, 9, 2, 4, 4, 6, 4, 10, 4, 9, 9, 5, 1, 5, 9, 8, 2, 3, 7, 8, 9, 6, 6, 8, 6, 9, 3, 3, 8, 8, 4, 3, 9, 6, 2, 4, 8, 5, 6, 3, 3, 9, 6, 7], 1]
    want = 4127
    got = solution.countSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[35, 72, 27, 23, 2, 30, 40, 25, 2, 44, 67, 63, 92, 90, 7, 81, 71, 46, 66, 74, 15, 65, 94, 5, 87, 9, 58, 2, 16, 27, 61, 51, 14, 58, 72, 75, 36, 78, 27, 84, 29, 31, 86, 71, 73, 59, 35, 62, 70, 42, 86, 27, 22, 64, 50, 23, 31, 58, 24, 74, 95, 5, 50, 37, 100, 56, 86, 70, 4, 54, 82, 9, 78, 10, 13, 35, 59, 24, 36, 46, 39, 6, 28, 62, 9, 99, 53, 20, 2, 94, 61, 18, 68, 40, 82, 98, 61, 76, 81, 94], 3]
    want = 0
    got = solution.countSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

