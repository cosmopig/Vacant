"""Scoring checks for lcb_3801 -- NOT part of any workspace.

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
    args = [10, 20]
    want = 2
    got = solution.beautifulNumbers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [1, 15]
    want = 10
    got = solution.beautifulNumbers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [8160, 560222044]
    want = 374578664
    got = solution.beautifulNumbers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [14, 17]
    want = 0
    got = solution.beautifulNumbers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [12, 15]
    want = 0
    got = solution.beautifulNumbers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [14, 16]
    want = 0
    got = solution.beautifulNumbers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [4, 4]
    want = 1
    got = solution.beautifulNumbers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [18, 20]
    want = 1
    got = solution.beautifulNumbers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [9, 10]
    want = 2
    got = solution.beautifulNumbers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [10, 10]
    want = 1
    got = solution.beautifulNumbers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [9592, 946577333]
    want = 636555796
    got = solution.beautifulNumbers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [776, 776]
    want = 0
    got = solution.beautifulNumbers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [8, 13]
    want = 3
    got = solution.beautifulNumbers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [9, 12]
    want = 2
    got = solution.beautifulNumbers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [15, 19]
    want = 0
    got = solution.beautifulNumbers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [995038326, 997826789]
    want = 1633702
    got = solution.beautifulNumbers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [5883, 477462691]
    want = 317560661
    got = solution.beautifulNumbers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [3066, 877964804]
    want = 589724130
    got = solution.beautifulNumbers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [6519, 777221270]
    want = 522035747
    got = solution.beautifulNumbers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [3141, 634219825]
    want = 426273641
    got = solution.beautifulNumbers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [19, 22]
    want = 2
    got = solution.beautifulNumbers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [16, 18]
    want = 0
    got = solution.beautifulNumbers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [3008, 501499977]
    want = 333134617
    got = solution.beautifulNumbers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = [2, 7]
    want = 6
    got = solution.beautifulNumbers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = [8747, 716697279]
    want = 482524455
    got = solution.beautifulNumbers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = [10, 13]
    want = 1
    got = solution.beautifulNumbers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

