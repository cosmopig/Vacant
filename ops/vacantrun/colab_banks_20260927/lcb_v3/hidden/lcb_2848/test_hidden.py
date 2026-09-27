"""Scoring checks for lcb_2848 -- NOT part of any workspace.

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
    args = [[2, 3, 6]]
    want = 2
    got = solution.specialPerm(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[1, 4, 3]]
    want = 2
    got = solution.specialPerm(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[3, 6]]
    want = 2
    got = solution.specialPerm(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[2, 9]]
    want = 0
    got = solution.specialPerm(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[9, 3]]
    want = 2
    got = solution.specialPerm(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[8, 2]]
    want = 2
    got = solution.specialPerm(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[1, 2]]
    want = 2
    got = solution.specialPerm(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[1, 4]]
    want = 2
    got = solution.specialPerm(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[3, 19]]
    want = 0
    got = solution.specialPerm(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[10, 4, 3]]
    want = 0
    got = solution.specialPerm(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[14, 7, 8]]
    want = 0
    got = solution.specialPerm(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[296573006, 843224034, 611728152, 710630427, 167640710, 512370634, 670120901, 726495939, 771393204, 404562485, 406564308, 199755311, 985371443, 874785529]]
    want = 0
    got = solution.specialPerm(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [[862055003, 862055004, 862055005, 862055006, 862055007, 862055008, 862055009, 862055010, 862055011, 862055012, 862055013, 862055014, 862055015, 862055016]]
    want = 0
    got = solution.specialPerm(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [[100000007, 200000014, 300000021, 400000028, 500000035, 600000042, 700000049, 800000056, 900000063, 1000000070, 1100000077, 1200000084, 1300000091, 1400000098]]
    want = 0
    got = solution.specialPerm(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

