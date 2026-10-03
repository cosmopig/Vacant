"""Scoring checks for lcb_3209 -- NOT part of any workspace.

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
    args = [[3, 1, 2]]
    want = 4
    got = solution.minimumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[1, 10, 1, 1]]
    want = 2
    got = solution.minimumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[3]]
    want = 3
    got = solution.minimumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[9]]
    want = 9
    got = solution.minimumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[4, 2]]
    want = 4
    got = solution.minimumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[3, 78]]
    want = 3
    got = solution.minimumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[32, 83]]
    want = 32
    got = solution.minimumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[14, 51]]
    want = 14
    got = solution.minimumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[2, 7, 1]]
    want = 3
    got = solution.minimumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[27802]]
    want = 27802
    got = solution.minimumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[98711]]
    want = 98711
    got = solution.minimumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[75, 66, 23, 67]]
    want = 98
    got = solution.minimumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [[34, 66, 37, 60]]
    want = 71
    got = solution.minimumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [[26, 43, 51, 11]]
    want = 69
    got = solution.minimumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [[3382, 3459, 8]]
    want = 3390
    got = solution.minimumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [[5, 83, 49, 87, 24]]
    want = 54
    got = solution.minimumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [[40, 32, 28, 36, 41]]
    want = 68
    got = solution.minimumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [[36, 80, 93, 9, 74, 91]]
    want = 125
    got = solution.minimumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [[4316, 6623, 6642, 9364]]
    want = 10939
    got = solution.minimumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [[29, 42, 87, 9, 84, 40, 65]]
    want = 80
    got = solution.minimumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [[4, 7, 8, 8, 7, 5, 9, 1, 1]]
    want = 17
    got = solution.minimumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [[6, 6, 5, 4, 3, 7, 6, 10, 8]]
    want = 14
    got = solution.minimumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [[60, 44, 55, 73, 38, 51, 41]]
    want = 142
    got = solution.minimumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = [[58, 33, 48, 22, 38, 96, 51]]
    want = 113
    got = solution.minimumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = [[22, 61, 61, 100, 67, 82, 39]]
    want = 122
    got = solution.minimumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = [[70, 50, 45, 71, 90, 35, 58, 73]]
    want = 150
    got = solution.minimumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

