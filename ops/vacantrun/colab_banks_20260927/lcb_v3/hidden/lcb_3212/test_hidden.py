"""Scoring checks for lcb_3212 -- NOT part of any workspace.

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
    args = [[1, 2, 3, 4]]
    want = 8
    got = solution.numberOfGoodPartitions(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[1, 1, 1, 1]]
    want = 1
    got = solution.numberOfGoodPartitions(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[1, 2, 1, 3]]
    want = 2
    got = solution.numberOfGoodPartitions(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[11, 12]]
    want = 2
    got = solution.numberOfGoodPartitions(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[10, 9, 1, 1]]
    want = 4
    got = solution.numberOfGoodPartitions(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[3, 8, 16, 2]]
    want = 8
    got = solution.numberOfGoodPartitions(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[20, 17, 19, 5]]
    want = 8
    got = solution.numberOfGoodPartitions(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[3, 3, 5, 5, 4]]
    want = 4
    got = solution.numberOfGoodPartitions(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[16, 11, 7, 12]]
    want = 8
    got = solution.numberOfGoodPartitions(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[6, 17, 1, 12, 7, 6]]
    want = 1
    got = solution.numberOfGoodPartitions(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[19, 20, 16, 4, 15, 7]]
    want = 32
    got = solution.numberOfGoodPartitions(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[13, 2, 35, 46, 26, 59, 83, 99, 75, 62, 14, 69, 85, 51, 24, 65, 51, 63, 75, 36, 39, 9, 99, 91, 57, 66, 17, 87, 21, 18, 77, 28, 43, 18, 64, 65, 54, 23, 70, 50, 22, 2, 94, 85, 24, 25, 99, 46, 20, 12, 83, 79, 44, 51, 38, 44, 66, 33, 61, 95, 69, 36, 16, 43, 18, 10, 41, 23, 35, 28, 74, 74, 19, 26, 67, 21, 98, 47, 42, 48, 54, 59, 4, 3, 41, 27, 84, 94, 80, 10, 50, 81, 86, 41, 49, 10, 51, 33, 51, 92, 39, 14, 27, 44, 80, 6, 68, 77, 47, 1, 46, 86, 57, 90, 64, 95, 5, 2, 83, 68, 70, 28, 74, 59, 76, 25, 28, 2, 97, 32, 95, 7, 28, 86, 40, 49, 66, 44, 14, 81, 100, 11, 90, 95, 42, 79, 85, 83, 30, 87, 88, 26, 88, 35, 6, 29, 51, 66, 36, 60, 1, 47, 39, 81, 21, 37, 75, 70, 68, 77, 22, 3, 1, 74, 27, 56, 95, 39, 17, 100, 93, 52, 71, 96, 24, 4, 15, 91, 66, 45, 59, 46, 81, 34, 11, 21, 87, 53, 70, 20, 56, 51, 80, 10, 90, 71, 39, 59, 41, 19, 26, 100, 99, 86, 83, 41, 12, 14, 52, 35, 62, 57, 19, 12, 83, 96, 56, 33, 66, 89, 71, 35, 59, 83, 82, 100, 100, 73, 8, 12, 25, 70, 99, 50, 80, 48, 62, 18, 76, 51, 13, 28, 29, 81, 24, 81, 10, 42, 62, 35, 70, 19, 92, 16, 17, 31, 64, 89, 97, 65, 61, 11, 26, 67, 82, 28, 2, 35, 40, 12, 26, 78, 94, 74, 32, 71, 80, 70, 28, 94, 37, 3, 75, 63, 97, 15, 68, 82, 36, 2, 42, 14, 31, 86, 92, 2, 6, 32, 96, 64, 55, 52, 44, 94, 94, 33, 30, 98, 27, 15, 87, 19, 84, 25, 80, 39, 48, 83, 70, 97, 31, 56, 32, 8, 18, 78, 13, 50, 85, 65, 40, 28, 49, 76, 9, 8, 54, 91, 79, 86, 37, 83, 23, 95, 17, 44, 68, 33, 68, 70, 64, 94, 40, 38, 85, 99, 98, 86, 93, 5, 65, 39, 48, 80, 56, 62, 71, 50, 80, 22, 77, 73, 86, 57, 32, 9, 75, 77, 35, 96, 26, 19, 44, 51, 70, 15, 57, 71, 64, 54, 3, 32, 61, 86, 14, 75, 70, 96, 67, 53, 77, 93, 70, 19, 67, 68, 13, 86, 49]]
    want = 1
    got = solution.numberOfGoodPartitions(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

