"""Scoring checks for lcb_3239 -- NOT part of any workspace.

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
    args = [26, 1]
    want = 3
    got = solution.minimumOperationsToMakeEqual(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [54, 2]
    want = 4
    got = solution.minimumOperationsToMakeEqual(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [25, 30]
    want = 5
    got = solution.minimumOperationsToMakeEqual(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [5, 1]
    want = 1
    got = solution.minimumOperationsToMakeEqual(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [11, 1]
    want = 1
    got = solution.minimumOperationsToMakeEqual(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [55, 1]
    want = 2
    got = solution.minimumOperationsToMakeEqual(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [55, 2]
    want = 3
    got = solution.minimumOperationsToMakeEqual(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [9, 96]
    want = 87
    got = solution.minimumOperationsToMakeEqual(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [90, 23]
    want = 6
    got = solution.minimumOperationsToMakeEqual(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [63, 70]
    want = 7
    got = solution.minimumOperationsToMakeEqual(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [80, 35]
    want = 20
    got = solution.minimumOperationsToMakeEqual(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [4865, 8501]
    want = 3636
    got = solution.minimumOperationsToMakeEqual(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [2160, 4559]
    want = 2399
    got = solution.minimumOperationsToMakeEqual(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [1642, 5290]
    want = 3648
    got = solution.minimumOperationsToMakeEqual(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [8545, 6788]
    want = 1757
    got = solution.minimumOperationsToMakeEqual(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

