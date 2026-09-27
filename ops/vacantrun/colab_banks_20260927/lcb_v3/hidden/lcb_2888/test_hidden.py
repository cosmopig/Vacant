"""Scoring checks for lcb_2888 -- NOT part of any workspace.

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
    args = [[1, 2, 2, 2]]
    want = 2
    got = solution.minimumIndex(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[2, 1, 3, 1, 1, 1, 7, 1, 2, 1]]
    want = 4
    got = solution.minimumIndex(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[3, 3, 3, 3, 7, 2, 2]]
    want = -1
    got = solution.minimumIndex(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[20, 20, 20, 20, 8]]
    want = 0
    got = solution.minimumIndex(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[1, 9, 1, 1, 1, 1, 17]]
    want = 0
    got = solution.minimumIndex(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[11, 11, 11, 11, 11, 11]]
    want = 0
    got = solution.minimumIndex(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[20, 4, 4, 4, 4, 4, 5, 4]]
    want = 2
    got = solution.minimumIndex(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[143098085, 143098085, 143098085]]
    want = 0
    got = solution.minimumIndex(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[14, 14, 14, 14, 14, 14, 10, 14, 14]]
    want = 0
    got = solution.minimumIndex(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[412663226, 412663226, 657461098, 412663226, 412663226, 412663226]]
    want = 0
    got = solution.minimumIndex(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[386065914, 804335372, 386065914, 386065914, 804335372, 804335372, 804335372]]
    want = -1
    got = solution.minimumIndex(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

