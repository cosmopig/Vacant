"""Scoring checks for lcb_3777 -- NOT part of any workspace.

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
    args = [[1, 2, 3], 2, 10]
    want = 6
    got = solution.maxProduct(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[0, 2, 3], -5, 12]
    want = -1
    got = solution.maxProduct(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[2, 2, 3, 3], 0, 9]
    want = 9
    got = solution.maxProduct(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[8, 3, 0, 8, 7, 10, 0, 10, 0, 7, 0, 7, 0, 11, 0, 3, 4, 4, 5, 0, 1, 7, 9, 12, 1, 5, 9, 7, 0, 9, 5, 0, 5, 4, 10, 6, 8, 4, 12, 9, 9, 4, 11, 7, 10, 4, 9, 11, 8, 1, 2, 9, 6, 11, 8, 8, 12, 0, 4, 6, 4, 3, 11, 0, 7, 3, 4, 10, 12, 6, 2, 7, 0, 4, 4, 1, 8, 8, 8, 2, 10, 12, 9, 0, 0, 10, 9, 3, 8, 0, 10, 3, 8, 10, 2, 8, 12, 1, 2, 5], -52379, 5000]
    want = -1
    got = solution.maxProduct(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[11], 11, 20]
    want = 11
    got = solution.maxProduct(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[4], 4, 10]
    want = 4
    got = solution.maxProduct(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12], -100000, 5000]
    want = -1
    got = solution.maxProduct(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12], 100000, 5000]
    want = -1
    got = solution.maxProduct(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[1, 7, 4, 10, 11, 11, 9, 6, 2, 4, 9, 0, 4, 0, 7, 5, 2, 10, 8, 2, 4, 11, 10, 4, 7, 8, 12, 12, 3, 2, 7, 4, 9, 11, 1, 9, 12, 4, 8, 0], -5, 500]
    want = 495
    got = solution.maxProduct(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[1], 1, 20]
    want = 1
    got = solution.maxProduct(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[4], 4, 10]
    want = 4
    got = solution.maxProduct(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[1, 7, 12, 12, 3, 6, 0, 4, 11, 7, 8, 11, 5, 10, 8, 5, 1, 9, 9, 5, 5, 0, 11, 7, 7, 8, 10, 10, 7, 3, 6, 11, 9, 12, 0, 9, 7, 1, 0, 3, 9, 7, 10, 7, 8, 0, 8, 12, 0, 9], -11, 100]
    want = 90
    got = solution.maxProduct(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [[6, 12, 7, 2, 7, 1, 7, 12, 12, 9, 5, 8, 3, 12, 8, 6, 8, 8, 8, 11, 10, 11, 6, 4, 1, 11, 11, 12, 3, 9, 8, 7, 8, 8, 1, 6, 10, 3, 6, 0, 5, 0, 9, 11, 0, 9, 7, 8, 10, 8], -21, 500]
    want = 490
    got = solution.maxProduct(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [[0], 0, 10]
    want = 0
    got = solution.maxProduct(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [[10, 9, 9, 1, 7, 7, 0, 3, 7, 4, 11, 1, 4, 4, 6, 0, 0, 2, 9, 12, 6, 5, 9, 11, 9, 0, 1, 6, 6, 1, 2, 6, 9, 7, 3, 8, 5, 5, 12, 3, 9, 5, 6, 3, 11, 0, 10, 11, 5, 10, 5, 8, 10, 0, 3, 0, 3, 9, 3, 5, 12, 9, 9, 1, 6, 10, 1, 8, 10, 4, 9, 11, 6, 9, 12, 10, 8, 7, 5, 1, 9, 3, 2, 12, 9, 5, 8, 3, 7, 0, 5, 6, 10, 4, 12, 9, 10, 7, 10, 9], 1, 1000]
    want = 1000
    got = solution.maxProduct(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [[3, 4, 3, 12, 12, 12, 2, 9, 10, 12, 10, 3, 10, 10, 10, 7, 1, 7, 8, 8, 2, 4, 5, 1, 1, 5, 6, 3, 4, 9, 8, 0, 5, 1, 9, 2, 7, 3, 4, 10, 9, 6, 11, 11, 7, 3, 3, 1, 6, 5, 4, 7, 6, 12, 3, 6, 9, 10, 4, 5, 12, 7, 3, 5, 11, 5, 6, 11, 11, 11, 12, 5, 3, 7, 10, 5, 7, 5, 8, 2, 1, 8, 0, 9, 1, 8, 2, 6, 12, 11, 2, 7, 7, 6, 7, 1, 12, 10, 6, 12], -29184, 1000]
    want = -1
    got = solution.maxProduct(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [[3], 3, 10]
    want = 3
    got = solution.maxProduct(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [[3], 3, 10]
    want = 3
    got = solution.maxProduct(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [[6, 1, 4, 8, 10, 0, 11, 8, 12, 0, 4, 9, 1, 2, 7, 8, 6, 2, 9, 5, 1, 3, 8, 9, 11, 5, 1, 5, 9, 9, 1, 10, 12, 10, 8, 0, 5, 0, 5, 4], 2, 200]
    want = 200
    got = solution.maxProduct(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [[3], 3, 10]
    want = 3
    got = solution.maxProduct(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [[9], 9, 10]
    want = 9
    got = solution.maxProduct(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [[7, 8, 12, 2, 9, 0, 5, 12, 10, 1, 11, 9, 5, 9, 7, 12, 12, 12, 6, 7, 5, 7, 9, 2, 7, 7, 11, 8, 9, 1, 6, 12, 11, 6, 1, 4, 2, 6, 5, 4], 15, 100]
    want = 100
    got = solution.maxProduct(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [[2], 2, 20]
    want = 2
    got = solution.maxProduct(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = [[11], 11, 20]
    want = 11
    got = solution.maxProduct(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = [[12], 12, 20]
    want = 12
    got = solution.maxProduct(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = [[4], 4, 20]
    want = 4
    got = solution.maxProduct(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_27():
    args = [[3], 3, 10]
    want = 3
    got = solution.maxProduct(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

