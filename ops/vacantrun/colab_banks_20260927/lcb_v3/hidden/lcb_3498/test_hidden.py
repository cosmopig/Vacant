"""Scoring checks for lcb_3498 -- NOT part of any workspace.

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
    args = [[1, 0, 1, 2, 4, 3], 4]
    want = 2
    got = solution.minChanges(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[0, 1, 2, 3, 3, 6, 5, 4], 6]
    want = 2
    got = solution.minChanges(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0], 0]
    want = 0
    got = solution.minChanges(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[38, 34, 26, 3, 16, 9, 5, 29, 38, 11, 19, 32, 18, 30, 2, 26, 3, 10, 10, 10], 42]
    want = 9
    got = solution.minChanges(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[1, 0, 0, 1, 0, 1, 1, 0, 0, 0, 1, 1, 1, 1, 0, 0], 1]
    want = 4
    got = solution.minChanges(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[4, 10, 9, 0, 3, 11, 12, 3, 7, 11, 7, 13, 5, 3, 6, 4], 16]
    want = 5
    got = solution.minChanges(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[5, 8, 8, 4, 5, 7, 6, 2, 5, 1], 8]
    want = 3
    got = solution.minChanges(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[47, 3], 50]
    want = 0
    got = solution.minChanges(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774, 27774], 100000]
    want = 0
    got = solution.minChanges(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[0, 1], 50]
    want = 0
    got = solution.minChanges(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0, 10, 10, 0, 0], 10]
    want = 0
    got = solution.minChanges(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[38017, 96975], 100000]
    want = 0
    got = solution.minChanges(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [[468, 9532], 10000]
    want = 0
    got = solution.minChanges(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [[2, 3, 4, 5, 4, 2, 4, 0], 5]
    want = 2
    got = solution.minChanges(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [[1, 1, 1, 1], 2]
    want = 0
    got = solution.minChanges(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [[18, 1, 7, 15], 19]
    want = 1
    got = solution.minChanges(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [[5, 2], 5]
    want = 0
    got = solution.minChanges(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [[9, 2, 7, 7, 8, 9, 1, 5, 1, 9, 4, 9, 4, 7], 9]
    want = 4
    got = solution.minChanges(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [[2, 9, 7, 6, 5, 12, 12, 4, 4, 6, 9, 0, 1, 8, 7, 3], 12]
    want = 6
    got = solution.minChanges(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [[462, 38], 500]
    want = 0
    got = solution.minChanges(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [[79705, 63133, 54338, 63451, 3558, 52838, 16137, 53357, 9607, 1239], 100000]
    want = 4
    got = solution.minChanges(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [[356, 144], 500]
    want = 0
    got = solution.minChanges(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [[0, 2], 10]
    want = 0
    got = solution.minChanges(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = [[62604, 18262], 100000]
    want = 0
    got = solution.minChanges(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = [[0, 1], 1]
    want = 0
    got = solution.minChanges(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = [[9, 4, 4, 4, 8, 2, 0, 4, 5, 9, 8, 8, 0, 6, 4, 6, 2, 5, 2, 2, 0, 4, 7, 7, 8, 0, 7, 4, 9, 3, 1, 3, 3, 9, 1, 3, 5, 7, 3, 3, 9, 9, 4, 9, 4, 8, 4, 5, 9, 3, 3, 8, 6, 5, 2, 5, 5, 8, 1, 10, 2, 4, 2, 6, 9, 5, 4, 3, 4, 1, 0, 10, 6, 0, 8, 1, 5, 8, 3, 1, 1, 10, 0, 3, 1, 8, 0, 4, 7, 8, 1, 9, 2, 3, 2, 10, 6, 9, 1, 5], 10]
    want = 34
    got = solution.minChanges(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

