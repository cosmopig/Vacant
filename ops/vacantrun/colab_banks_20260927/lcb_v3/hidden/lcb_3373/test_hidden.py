"""Scoring checks for lcb_3373 -- NOT part of any workspace.

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
    args = [[4, 2, 9, 5, 3]]
    want = 3
    got = solution.maximumPrimeDifference(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[4, 8, 2, 8]]
    want = 0
    got = solution.maximumPrimeDifference(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[95, 18, 14, 79, 28, 12, 55, 52]]
    want = 0
    got = solution.maximumPrimeDifference(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[17, 63, 57, 41, 97, 22, 88, 49, 47, 39, 63, 22, 91, 45, 66, 72, 66, 83, 10, 54, 14, 90, 20, 1, 40, 27, 21, 47, 2, 61, 63, 34]]
    want = 29
    got = solution.maximumPrimeDifference(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[11, 77, 73, 67, 32, 42, 48, 24, 18, 39, 82, 94, 92, 2, 78, 4, 3, 72, 100, 47, 13, 91, 65, 68, 50, 99, 84, 12, 33, 46, 37, 91, 93, 35, 30, 48, 37, 91, 92, 5, 89, 42, 27, 45, 27, 33, 54, 9, 85, 30, 70, 52, 75, 28, 40, 62, 29, 88, 59, 79, 82, 53, 31, 19, 68, 96, 74, 76, 24, 30, 37, 30, 50, 13, 17, 19, 57, 58, 87, 80, 96, 55, 49, 13, 75, 2, 68, 96, 35, 86, 16, 54, 88, 2, 44, 11, 72, 69, 78, 71]]
    want = 99
    got = solution.maximumPrimeDifference(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[51, 13, 4, 69, 21, 22, 84, 58, 61, 37, 70, 30, 85, 51, 20]]
    want = 8
    got = solution.maximumPrimeDifference(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[62, 65, 17, 95, 19, 21, 60, 28]]
    want = 2
    got = solution.maximumPrimeDifference(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[11, 78, 30, 95, 61, 64, 52, 10, 42, 94, 70, 56, 21, 32, 61, 8, 50, 8, 36, 66, 23, 26, 63, 69, 9, 59, 62, 85, 43, 37, 89, 10, 30, 52, 69, 22, 6, 84, 26, 41, 89, 14, 17, 53, 91, 8, 43, 15, 22, 65, 57, 59, 1, 18, 4, 43, 22, 7, 32, 84, 34, 67, 40, 62, 33, 15, 78, 24, 60, 5, 92, 68, 11, 45, 100, 55, 66, 88, 32, 73, 57, 57, 24, 91, 45, 3, 76, 100, 89, 52, 46, 42, 71, 79, 100, 37, 94, 89, 64, 26, 22, 62, 49, 9, 85, 18, 15, 34, 32, 89, 84, 69, 71, 18, 91, 53, 86, 68, 34, 3, 86, 39, 9, 26, 43, 65, 66, 83, 61, 33, 9, 20, 41, 36, 68, 86, 33, 53, 79, 56, 22, 90, 13, 26, 16, 57, 22, 82, 39, 8, 50, 98, 46, 84, 93, 78, 3, 57, 63, 34, 31, 27, 91, 77, 59, 39, 45, 46, 21, 61, 49, 10, 18, 77, 34, 29, 99, 36, 100, 4, 48, 94, 53, 8, 5, 82, 59, 20, 2, 95, 32, 93, 50, 19, 49, 96, 9, 41, 39, 63, 67, 77, 29, 44, 6, 58, 45, 41, 66, 45, 98, 30, 80, 31, 46, 9, 80, 39, 71, 13, 29, 91, 59, 22, 24, 6, 44, 9, 73, 27, 93, 81, 45, 15, 38, 56, 7, 100, 28, 98, 88, 38, 43, 24, 4, 93, 40, 24, 15, 49, 42, 37, 84, 89, 98, 52, 70, 85, 76, 93, 17, 76, 55, 84, 33, 77, 27, 11, 80, 89, 55, 1, 98, 1, 13, 2, 28, 45, 14, 87, 61, 41, 23, 89, 8, 69, 46, 24, 75, 36, 23, 2, 43, 79, 81, 15, 92, 40, 5, 4, 41, 91, 95, 96, 42, 62, 43, 23, 91, 74, 34, 96, 41, 42, 95, 92, 27, 12, 99, 99, 26, 59, 87, 40, 13, 74, 79, 77, 85, 31, 3, 41, 35, 44, 29, 17, 44, 39, 43, 8, 61, 91, 85, 30, 87, 48, 52, 46, 61, 60, 30, 17, 6, 42, 32, 58, 56, 77, 71, 85, 54, 71, 81, 98, 68, 74, 68, 10, 64, 31, 78, 38, 48, 53, 68, 88, 89, 50, 78, 53, 9, 75, 6, 31, 17, 85, 67, 64, 34, 19, 39, 24, 54, 56, 59, 8, 64, 71, 31, 59, 84, 27, 14, 26, 88, 28, 51, 79, 98, 59, 36, 13, 23, 51, 16, 53, 26, 63, 68, 89, 31, 18, 98, 53, 36, 81, 47, 9, 45, 84, 3, 26, 80, 10, 14, 45, 49, 85, 24, 68, 83, 18, 57, 34, 49, 36, 41, 52, 79, 92, 6, 89, 58, 91, 28, 99, 12, 63, 8, 2, 12, 69, 27, 73, 71, 21, 46, 30, 98, 82, 26, 98, 91, 100, 16, 59, 71, 81, 100, 34, 97, 76, 68, 50, 84, 78, 34, 55, 78, 42, 4, 33, 36, 23, 54, 1, 2, 11, 14, 99, 42, 11, 7, 97, 61, 42, 49, 16, 44, 76, 44, 1, 60, 99, 44, 86, 51, 46, 61, 86, 25, 6, 72, 64, 13, 7, 57, 39, 53, 16, 26, 32, 96, 52, 54, 63, 25, 81, 17, 8, 72, 16, 33, 41, 55, 24, 99, 18, 50, 46, 72, 84, 88, 72, 87, 61, 94, 93, 40, 64, 96, 46, 47, 59, 77, 65, 18, 81, 26, 79, 91, 12, 88, 17, 40, 64, 57, 36, 46, 83, 89, 47, 70, 68, 14, 83, 77, 6, 100, 22, 25, 54, 28, 97, 45, 69, 90, 77, 20, 78, 89, 22, 26, 38, 41, 75, 84, 61, 28, 21, 23, 94, 21, 95, 91, 25, 6, 86, 72, 49, 56, 21, 3, 34, 60, 97, 52, 1, 37, 38, 77, 68, 95, 32, 5, 26, 67, 18, 77, 18, 18, 61, 96, 63, 63, 6, 39, 13, 34, 70, 71, 71, 31, 8, 40, 76, 28, 72, 32, 66, 67, 23, 31, 60, 100, 43, 92, 61, 61, 62, 19, 33, 59, 30, 22, 93, 2, 43, 24, 94, 100, 8, 16, 17, 47, 76, 96, 99, 82, 60, 82, 22, 1, 20, 99, 77, 68, 35, 39, 65, 38, 10, 56, 88, 40, 70, 63, 57, 64, 50, 40, 45, 21, 37, 90, 15, 24, 73, 46, 99, 66, 100, 21, 27, 27, 31, 34, 78, 55, 73, 50, 93, 72, 67, 42, 15, 36, 33, 98, 80, 40, 33, 73, 49, 67, 76]]
    want = 744
    got = solution.maximumPrimeDifference(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[7, 32, 60, 91, 44, 100, 54, 28, 78, 49, 33, 73, 55, 89]]
    want = 13
    got = solution.maximumPrimeDifference(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[66, 92, 64, 32, 27, 2, 39, 43, 6]]
    want = 2
    got = solution.maximumPrimeDifference(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[79, 38, 87, 63, 17, 31, 97, 27, 42]]
    want = 6
    got = solution.maximumPrimeDifference(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[61, 81, 73, 54, 49, 89, 28, 84, 72, 45, 43, 1]]
    want = 10
    got = solution.maximumPrimeDifference(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [[38, 22, 72, 44, 46, 21, 1, 57, 67]]
    want = 0
    got = solution.maximumPrimeDifference(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [[2, 73, 2, 2, 53, 41, 7, 67, 23, 31, 97, 17, 83, 71, 43, 59, 79, 23, 79, 3, 47, 41, 7, 17, 89, 13, 13, 11, 97, 73, 61, 83, 97, 13, 59, 97, 97, 23, 29, 47, 83, 23, 73, 73, 83, 5, 31, 71, 41]]
    want = 48
    got = solution.maximumPrimeDifference(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

