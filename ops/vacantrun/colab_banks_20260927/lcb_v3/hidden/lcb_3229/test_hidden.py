"""Scoring checks for lcb_3229 -- NOT part of any workspace.

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
    args = [[1, 2, 3, 4, 5]]
    want = 6
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[10, 12, 13, 14, 15]]
    want = 11
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[22, 33, 22, 33, 22]]
    want = 22
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[6]]
    want = 0
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[48, 82]]
    want = 34
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[3, 79, 7]]
    want = 76
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[55, 49, 23]]
    want = 37
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[1, 80, 99, 46]]
    want = 132
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[90, 16, 27, 67]]
    want = 114
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[52, 84, 75, 77, 75, 75, 85]]
    want = 46
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[79, 76, 83, 14, 70, 85, 54]]
    want = 110
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[43, 87, 73, 85, 12, 53, 25, 42, 62, 59]]
    want = 191
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [[29471663, 71689165, 41127046, 30210507, 95424035, 27506338, 58019206, 9953143, 4200518, 58987766]]
    want = 223905049
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

