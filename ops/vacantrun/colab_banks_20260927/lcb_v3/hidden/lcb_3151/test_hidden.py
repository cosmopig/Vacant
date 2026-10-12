"""Scoring checks for lcb_3151 -- NOT part of any workspace.

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
    args = [[8, 10], [2, 2, 3, 1, 8, 7, 4, 5]]
    want = 16
    got = solution.minProcessingTime(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[10, 20], [2, 3, 1, 2, 5, 8, 4, 3]]
    want = 23
    got = solution.minProcessingTime(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[2], [7, 3, 6, 4]]
    want = 9
    got = solution.minProcessingTime(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[3], [4, 9, 6, 7]]
    want = 12
    got = solution.minProcessingTime(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[9], [1, 8, 7, 9]]
    want = 18
    got = solution.minProcessingTime(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[4], [2, 5, 4, 9]]
    want = 13
    got = solution.minProcessingTime(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[4], [7, 9, 9, 8]]
    want = 13
    got = solution.minProcessingTime(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[9], [4, 5, 8, 3]]
    want = 17
    got = solution.minProcessingTime(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[9], [3, 3, 10, 7]]
    want = 19
    got = solution.minProcessingTime(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[0], [6, 10, 1, 6]]
    want = 10
    got = solution.minProcessingTime(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

