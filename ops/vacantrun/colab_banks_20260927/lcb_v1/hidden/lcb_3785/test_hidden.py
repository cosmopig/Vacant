"""Scoring checks for lcb_3785 -- NOT part of any workspace.

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
    args = [[1, 2, 3, 4], [[1, 2], [2, 3], [3, 4], [4, 5]]]
    want = 2
    got = solution.countArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[1, 2, 3, 4], [[1, 10], [2, 9], [3, 8], [4, 7]]]
    want = 4
    got = solution.countArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[1, 2, 1, 2], [[1, 1], [2, 3], [3, 3], [2, 3]]]
    want = 0
    got = solution.countArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[1, 1], [[1000000000, 1000000000], [1, 1000000000]]]
    want = 1
    got = solution.countArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[25, 86], [[12, 79], [17, 110]]]
    want = 38
    got = solution.countArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[8, 54], [[8, 30], [54, 120]]]
    want = 23
    got = solution.countArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[1, 1], [[1, 1], [1000000000, 1000000000]]]
    want = 0
    got = solution.countArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[40, 92], [[40, 100], [92, 142]]]
    want = 51
    got = solution.countArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[1000000000, 1000000000], [[1, 1], [1, 1]]]
    want = 1
    got = solution.countArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[17, 81], [[36, 58], [67, 110]]]
    want = 11
    got = solution.countArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[21, 22], [[6, 12], [91, 110]]]
    want = 0
    got = solution.countArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[1, 1], [[1, 1000000000], [1, 1000000000]]]
    want = 1000000000
    got = solution.countArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [[1, 1], [[1, 1], [1, 1000000000]]]
    want = 1
    got = solution.countArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [[1, 1], [[1000000000, 1000000000], [1000000000, 1000000000]]]
    want = 1
    got = solution.countArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [[16, 99], [[34, 35], [71, 110]]]
    want = 0
    got = solution.countArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [[1000000000, 1000000000], [[1000000000, 1000000000], [1, 1]]]
    want = 0
    got = solution.countArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [[1, 1], [[1, 1], [1, 1]]]
    want = 1
    got = solution.countArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [[40, 35], [[91, 110], [79, 110]]]
    want = 20
    got = solution.countArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [[13, 7], [[13, 107], [7, 37]]]
    want = 31
    got = solution.countArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [[27, 4], [[27, 49], [4, 76]]]
    want = 23
    got = solution.countArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [[17, 50], [[17, 50], [50, 84]]]
    want = 34
    got = solution.countArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [[14, 95], [[14, 75], [95, 140]]]
    want = 46
    got = solution.countArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [[8, 100], [[75, 110], [21, 53]]]
    want = 0
    got = solution.countArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = [[1000000000, 1000000000], [[1, 1], [1, 1000000000]]]
    want = 1
    got = solution.countArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = [[11, 42], [[22, 55], [72, 110]]]
    want = 15
    got = solution.countArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = [[1000000000, 1000000000], [[1000000000, 1000000000], [1000000000, 1000000000]]]
    want = 1
    got = solution.countArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_27():
    args = [[10, 75], [[10, 96], [75, 135]]]
    want = 61
    got = solution.countArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

