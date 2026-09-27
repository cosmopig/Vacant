"""Scoring checks for lcb_3593 -- NOT part of any workspace.

⚠ 計分用的 GT。住在 hidden/ 這棵**另外的樹**，永遠不複製進 agent 的工作區；
  任何把它的內容（含失敗訊息）回饋給模型的路徑都作廢那一批資料。

case 組成 ＝ 題庫的 `visible_tests` ＋ `hidden_tests`（超集），與
vacant_network/codebench.py::LiveCodeBenchLoader 的 `hidden_check` 同一組（ops/gain/data/lcb_bank_v1.jsonl）。
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
    args = [[2, 4, 8, 16]]
    want = 64
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[1, 2, 3, 4, 5]]
    want = 60
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[3]]
    want = 9
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[4, 11, 24]]
    want = 264
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[11, 15]]
    want = 225
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[23, 25, 8, 12, 13, 16, 24, 30, 22, 11, 16, 10, 21, 1, 27, 22, 6, 11, 11, 4, 20, 7, 26, 23, 18, 7, 24, 2, 20, 27, 29, 8, 23, 10, 28, 12, 6, 16, 14, 13, 12, 16, 3, 21, 20, 24, 8, 16, 11, 7, 7, 15, 17, 24, 4, 7, 6, 28, 27, 11, 13, 24, 9, 25, 4, 4, 23, 9, 15, 29, 13, 23, 5, 5, 18, 19, 10, 18, 2, 10, 21, 8, 29, 14, 24, 13, 21, 22, 28, 8, 30, 23, 26, 29, 1, 4, 1, 5, 19, 4]]
    want = 2329089562800
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[15, 3, 3, 19, 9, 26, 23, 28, 24, 25, 16, 30, 9, 11, 9, 22, 13, 23, 30, 12, 22, 2, 10, 16, 13, 21, 29, 18, 18, 7, 15, 1, 3, 12, 25, 9, 11, 4, 30, 1, 16, 28, 8, 23, 19, 11, 19, 30, 1, 29, 21, 6, 25, 14, 22, 11, 22, 16, 29, 5, 25, 12, 8, 22, 20, 15, 6, 14, 4, 5, 3, 22, 4, 12, 8, 11, 13, 6, 18, 5, 4, 28, 2, 24, 19, 7, 22, 22, 22, 8, 4, 4, 15, 7, 22, 20, 22, 4, 25, 12]]
    want = 45668422800
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[7]]
    want = 49
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[7, 23, 30]]
    want = 4830
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[2, 16, 18]]
    want = 288
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[15]]
    want = 225
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[28, 13]]
    want = 784
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [[13, 27, 27, 13, 21, 28, 7, 8, 23, 26, 20, 6, 13, 17, 19, 26, 26, 24, 15, 5, 3, 8, 9, 12, 21, 26, 15, 13, 20, 12, 14, 2, 17, 11, 26, 26, 5, 28, 16, 5, 23, 18, 10, 30, 2, 14, 8, 18, 21, 9, 3, 6, 26, 11, 12, 30, 14, 14, 26, 4, 13, 24, 8, 27, 18, 30, 4, 21, 28, 16, 17, 14, 8, 29, 20, 5, 7, 3, 2, 1, 8, 3, 26, 4, 7, 14, 24, 17, 15, 8, 29, 1, 4, 4, 27, 21, 21, 15, 2, 10]]
    want = 465817912560
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [[11, 4]]
    want = 121
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [[15, 23]]
    want = 529
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [[14, 5]]
    want = 196
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [[18, 19, 29, 25, 19, 18, 15, 13, 12, 11, 20, 9, 8, 24, 11, 10, 19, 24, 3, 18, 12, 27, 29, 19, 23, 9, 18, 4, 21, 13, 28, 13, 27, 21, 29, 15, 27, 22, 11, 16, 1, 5, 29, 12, 9, 20, 5, 21, 4, 27, 19, 14, 17, 10, 29, 29, 26, 15, 27, 9, 30, 6, 9, 29, 7, 29, 11, 23, 29, 4, 28, 8, 25, 21, 30, 12, 10, 2, 11, 7, 4, 13, 7, 11, 19, 5, 2, 19, 5, 20, 1, 5, 11, 10, 26, 17, 27, 13, 18, 2]]
    want = 2329089562800
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [[2, 29]]
    want = 841
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [[25, 5, 22, 16, 21, 23, 26, 19, 20, 13, 5, 17, 8, 4, 7, 26, 18, 6, 13, 17, 13, 6, 23, 11, 9, 25, 11, 12, 19, 8, 14, 16, 4, 16, 9, 21, 20, 22, 24, 3, 20, 7, 28, 14, 5, 29, 21, 9, 9, 25, 18, 13, 12, 2, 6, 8, 24, 11, 14, 14, 2, 19, 2, 24, 19, 2, 22, 2, 7, 26, 5, 13, 13, 21, 1, 17, 13, 15, 30, 30, 29, 26, 15, 8, 1, 9, 8, 8, 16, 3, 4, 12, 16, 20, 24, 9, 18, 30, 14, 14]]
    want = 776363187600
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [[24, 26]]
    want = 676
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [[3, 4]]
    want = 16
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [[26, 16]]
    want = 676
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [[20, 7, 11, 10, 30, 28, 12, 8, 27, 1, 17, 25, 27, 16, 18, 26, 20, 10, 11, 9, 9, 24, 30, 27, 3, 18, 1, 4, 3, 6, 12, 11, 25, 19, 18, 14, 21, 2, 11, 14, 16, 17, 10, 6, 23, 20, 29, 21, 10, 25, 1, 1, 6, 2, 30, 20, 25, 24, 13, 20, 2, 11, 16, 16, 27, 8, 19, 12, 9, 24, 22, 19, 20, 6, 17, 3, 18, 27, 18, 5, 10, 27, 2, 3, 7, 21, 2, 7, 29, 24, 16, 15, 8, 25, 27, 11, 1, 13, 26, 18]]
    want = 2329089562800
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = [[15, 17]]
    want = 289
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = [[6, 14, 20]]
    want = 840
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = [[26, 17, 29, 9, 1, 28, 2, 22, 18, 29, 16, 6, 1, 3, 24, 12, 21, 3, 22, 14, 27, 6, 6, 1, 26, 12, 29, 24, 8, 11, 2, 1, 24, 3, 20, 26, 11, 15, 26, 7, 17, 19, 4, 14, 6, 7, 28, 23, 1, 3, 4, 25, 20, 3, 28, 21, 12, 28, 30, 8, 20, 13, 2, 18, 21, 19, 23, 20, 28, 2, 14, 4, 13, 1, 17, 14, 7, 15, 30, 12, 15, 20, 19, 25, 4, 25, 4, 29, 13, 1, 19, 8, 6, 19, 18, 3, 8, 21, 14, 1]]
    want = 2329089562800
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_27():
    args = [[21, 3, 16, 26, 12, 2, 26, 23, 14, 3, 29, 8, 25, 3, 29, 12, 19, 15, 7, 1, 3, 22, 18, 20, 11, 22, 26, 12, 27, 4, 9, 5, 29, 17, 29, 19, 2, 26, 15, 21, 21, 17, 10, 29, 7, 6, 25, 26, 29, 17, 5, 20, 7, 15, 3, 9, 24, 3, 3, 7, 27, 25, 29, 25, 2, 9, 23, 26, 12, 14, 26, 3, 5, 19, 8, 18, 10, 28, 28, 20, 15, 18, 29, 19, 30, 26, 27, 10, 13, 24, 7, 7, 9, 24, 16, 29, 2, 13, 22, 11]]
    want = 2329089562800
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

