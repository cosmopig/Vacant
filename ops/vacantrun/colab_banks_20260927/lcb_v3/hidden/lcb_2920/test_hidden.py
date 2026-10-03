"""Scoring checks for lcb_2920 -- NOT part of any workspace.

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
    args = [[1, 2, 1, 2]]
    want = 1
    got = solution.minimumSeconds(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[2, 1, 3, 3, 2]]
    want = 2
    got = solution.minimumSeconds(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[5, 5, 5, 5]]
    want = 0
    got = solution.minimumSeconds(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[9]]
    want = 0
    got = solution.minimumSeconds(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[8, 9]]
    want = 1
    got = solution.minimumSeconds(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[9464]]
    want = 0
    got = solution.minimumSeconds(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[8, 8, 8, 7]]
    want = 1
    got = solution.minimumSeconds(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[10, 7, 2, 5]]
    want = 2
    got = solution.minimumSeconds(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[1, 9, 4, 10, 2]]
    want = 2
    got = solution.minimumSeconds(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[2, 6, 10, 9, 5]]
    want = 2
    got = solution.minimumSeconds(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[675193734, 675193734, 675193734, 675193734, 675193734, 675193734, 675193734, 675193734, 675193734, 675193734]]
    want = 0
    got = solution.minimumSeconds(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[39, 90, 69, 36, 27, 21, 67, 15, 65, 89, 23, 70, 96, 90, 19, 64, 61, 76, 29, 50, 85, 34, 22, 68, 98, 52, 37, 100, 92, 94, 24, 75, 26, 3, 88, 62, 53, 56, 81, 35, 29, 80, 75, 15, 65, 25, 76, 68, 36, 98, 93, 83, 41, 13, 26, 87, 43, 43, 32, 53, 69, 59, 29, 52, 14, 10, 19, 65, 76, 42, 57, 33, 84, 17, 21, 7, 73, 92, 22, 11, 58, 11, 64, 48, 8, 48, 61, 52, 21, 67, 80, 39, 21, 3, 77, 18, 19, 83, 73, 13]]
    want = 19
    got = solution.minimumSeconds(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [[897, 231, 228, 879, 851, 153, 175, 90, 23, 46, 112, 662, 603, 530, 954, 536, 320, 328, 359, 507, 622, 86, 845, 803, 983, 135, 488, 21, 123, 137, 55, 159, 208, 105, 763, 669, 945, 178, 358, 398, 583, 779, 76, 456, 767, 820, 777, 130, 116, 201, 107, 313, 850, 498, 535, 406, 863, 580, 972, 219, 628, 979, 220, 816, 801, 812, 310, 57, 468, 816, 208, 486, 275, 237, 985, 820, 318, 621, 458, 175, 992, 564, 847, 6, 395, 252, 909, 93, 920, 710, 669, 112, 485, 436, 93, 925, 473, 751, 1, 606]]
    want = 27
    got = solution.minimumSeconds(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

