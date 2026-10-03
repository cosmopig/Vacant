"""Scoring checks for lcb_3563 -- NOT part of any workspace.

⚠ 計分用的 GT。住在 hidden/ 這棵**另外的樹**，永遠不複製進 agent 的工作區；
  任何把它的內容（含失敗訊息）回饋給模型的路徑都作廢那一批資料。

case 組成 ＝ 題庫的 `visible_tests` ＋ `hidden_tests`（超集），與
vacant_network/codebench.py::LiveCodeBenchLoader 的 `hidden_check` 同一組（ops/gain/data/lcb_bank_v2.jsonl）。
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
    args = [[[1, 2, 3], [4, 3, 2], [1, 1, 1]]]
    want = 8
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[[8, 7, 6], [8, 3, 2]]]
    want = 15
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[[100, 7, 4], [99, 8, 4], [98, 4, 2], [97, 5, 1], [96, 8, 7], [95, 1, 10], [94, 5, 5], [93, 4, 3], [92, 6, 2], [91, 10, 7]]]
    want = 955
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[[15, 7, 10, 6], [18, 11, 10, 19], [2, 11, 12, 18]]]
    want = 52
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[[15, 7, 2, 10], [10, 10, 7, 7], [7, 18, 13, 13]]]
    want = 43
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[[3, 2, 4, 5, 1], [9, 6, 8, 7, 10]]]
    want = 15
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[[7, 2, 6, 3, 5, 8, 1, 4], [9, 13, 15, 14, 11, 16, 10, 12], [17, 21, 18, 23, 19, 22, 20, 24], [32, 25, 26, 27, 28, 29, 31, 30], [36, 37, 39, 40, 34, 38, 35, 33], [46, 47, 42, 43, 45, 41, 48, 44]]]
    want = 168
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[[16, 18], [20, 20], [18, 18], [1, 15]]]
    want = 69
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[[7, 18, 18], [2, 20, 2], [5, 1, 15]]]
    want = 53
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[[18, 1], [10, 13]]]
    want = 31
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[[84, 1], [1, 61]]]
    want = 145
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[[9, 19], [11, 3]]]
    want = 30
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [[[15, 15, 9, 15]]]
    want = 15
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [[[13, 14, 14], [14, 18, 18], [20, 14, 20], [20, 4, 14]]]
    want = 65
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [[[5, 7, 6, 5, 100, 1, 6, 1, 2], [6, 1, 8, 3, 7, 6, 3, 7, 3], [1, 4, 1, 2, 5, 3, 4, 7, 4], [5, 6, 6, 6, 5, 10, 1, 7, 5], [2, 8, 4, 2, 9, 10, 2, 1, 8], [1, 3, 1, 4, 9, 5, 10, 6, 8], [5, 9, 3, 8, 5, 7, 6, 1, 5], [10, 9, 8, 7, 6, 9, 8, 7, 3]]]
    want = 149
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [[[7, 6], [19, 8], [15, 7]]]
    want = 41
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [[[2, 1, 5, 4, 3], [7, 9, 10, 6, 8], [13, 12, 14, 11, 15], [19, 18, 16, 20, 17], [24, 23, 22, 21, 25], [30, 28, 29, 26, 27], [35, 31, 34, 32, 33], [40, 38, 36, 39, 37], [42, 43, 41, 45, 44], [49, 47, 46, 48, 50]]]
    want = 275
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [[[100, 8, 8, 4, 10, 1, 8, 8, 6], [99, 4, 7, 7, 4, 4, 7, 3, 9], [98, 8, 3, 5, 2, 1, 4, 7, 10], [97, 6, 10, 3, 6, 10, 3, 2, 8]]]
    want = 394
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [[[29, 34, 35, 37, 43, 90], [34, 34, 35, 37, 43, 90], [35, 35, 35, 37, 43, 90], [37, 37, 37, 37, 43, 90], [43, 43, 43, 43, 43, 90], [90, 90, 90, 90, 90, 90]]]
    want = 268
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [[[8, 6, 20, 11], [16, 16, 9, 11]]]
    want = 36
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [[[4, 5, 6, 7], [4, 5, 6, 7], [1, 2, 3, 8], [1, 2, 3, 8]]]
    want = 24
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [[[15, 17, 24, 25, 59, 73, 90], [17, 17, 24, 25, 59, 73, 90], [24, 24, 24, 25, 59, 73, 90], [25, 25, 25, 25, 59, 73, 90], [59, 59, 59, 59, 59, 73, 90], [73, 73, 73, 73, 73, 73, 90], [90, 90, 90, 90, 90, 90, 90]]]
    want = 303
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [[[97]]]
    want = 97
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = [[[74, 74, 74, 74, 74, 74], [74, 74, 74, 74, 74, 74], [74, 74, 74, 74, 74, 74], [74, 74, 74, 74, 74, 74]]]
    want = 74
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = [[[1, 2, 3, 4, 5, 6, 7, 8, 9, 10], [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]]]
    want = 55
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = [[[12, 15, 24, 33, 37, 56, 79, 86, 89], [15, 15, 24, 33, 37, 56, 79, 86, 89], [24, 24, 24, 33, 37, 56, 79, 86, 89], [33, 33, 33, 33, 37, 56, 79, 86, 89], [37, 37, 37, 37, 37, 56, 79, 86, 89], [56, 56, 56, 56, 56, 56, 79, 86, 89], [79, 79, 79, 79, 79, 79, 79, 86, 89], [86, 86, 86, 86, 86, 86, 86, 86, 89], [89, 89, 89, 89, 89, 89, 89, 89, 89]]]
    want = 431
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

