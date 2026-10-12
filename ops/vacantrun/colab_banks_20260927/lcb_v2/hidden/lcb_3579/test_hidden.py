"""Scoring checks for lcb_3579 -- NOT part of any workspace.

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
    args = [[1, 2, 3]]
    want = 30
    got = solution.maxGoodNumber(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[2, 8, 16]]
    want = 1296
    got = solution.maxGoodNumber(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[4, 32, 2]]
    want = 1312
    got = solution.maxGoodNumber(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[125, 81, 41]]
    want = 1029329
    got = solution.maxGoodNumber(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[1, 11, 5]]
    want = 221
    got = solution.maxGoodNumber(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[4, 1, 127]]
    want = 2044
    got = solution.maxGoodNumber(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[42, 21, 85]]
    want = 177514
    got = solution.maxGoodNumber(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[6, 84, 71]]
    want = 109127
    got = solution.maxGoodNumber(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[1, 32, 127]]
    want = 16352
    got = solution.maxGoodNumber(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[125, 80, 115]]
    want = 2062800
    got = solution.maxGoodNumber(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[3, 108, 97]]
    want = 63073
    got = solution.maxGoodNumber(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[125, 44, 125]]
    want = 1032044
    got = solution.maxGoodNumber(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [[5, 1, 78]]
    want = 1742
    got = solution.maxGoodNumber(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [[7, 14, 15]]
    want = 2046
    got = solution.maxGoodNumber(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [[6, 55, 80]]
    want = 57168
    got = solution.maxGoodNumber(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [[5, 82, 85]]
    want = 92882
    got = solution.maxGoodNumber(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [[127, 4, 8]]
    want = 16328
    got = solution.maxGoodNumber(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [[4, 106, 112]]
    want = 115540
    got = solution.maxGoodNumber(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [[6, 44, 2]]
    want = 1714
    got = solution.maxGoodNumber(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [[127, 1, 64]]
    want = 32704
    got = solution.maxGoodNumber(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [[32, 16, 8]]
    want = 17440
    got = solution.maxGoodNumber(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [[127, 96, 113]]
    want = 2095328
    got = solution.maxGoodNumber(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [[6, 28, 59]]
    want = 15334
    got = solution.maxGoodNumber(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = [[2, 91, 119]]
    want = 61294
    got = solution.maxGoodNumber(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = [[5, 66, 116]]
    want = 119490
    got = solution.maxGoodNumber(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = [[2, 109, 121]]
    want = 62390
    got = solution.maxGoodNumber(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

