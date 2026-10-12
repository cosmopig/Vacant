"""Scoring checks for lcb_2979 -- NOT part of any workspace.

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
    args = [5, [[0, 0, 1], [0, 2, 2], [1, 3, 2]]]
    want = 3
    got = solution.maximizeTheProfit(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [5, [[0, 0, 1], [0, 2, 10], [1, 3, 2]]]
    want = 10
    got = solution.maximizeTheProfit(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [4, [[1, 3, 70]]]
    want = 70
    got = solution.maximizeTheProfit(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [1, [[0, 0, 53]]]
    want = 53
    got = solution.maximizeTheProfit(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [1, [[0, 0, 1000]]]
    want = 1000
    got = solution.maximizeTheProfit(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [5, [[4, 4, 3], [3, 3, 28]]]
    want = 31
    got = solution.maximizeTheProfit(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [3, [[1, 2, 66], [0, 2, 13]]]
    want = 66
    got = solution.maximizeTheProfit(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [5, [[0, 1, 7], [3, 4, 6], [1, 3, 2]]]
    want = 13
    got = solution.maximizeTheProfit(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [20, [[14, 15, 3], [16, 17, 5], [9, 10, 4]]]
    want = 12
    got = solution.maximizeTheProfit(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [100, [[48, 96, 79], [10, 52, 74], [24, 42, 83], [53, 83, 9], [56, 97, 38]]]
    want = 162
    got = solution.maximizeTheProfit(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [1000, [[759, 918, 4], [727, 894, 9], [275, 580, 9], [205, 978, 7], [997, 998, 1]]]
    want = 19
    got = solution.maximizeTheProfit(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [1000, [[354, 643, 137], [455, 903, 782], [931, 971, 659], [451, 620, 148], [633, 876, 127]]]
    want = 1441
    got = solution.maximizeTheProfit(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

