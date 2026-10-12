"""Scoring checks for lcb_3196 -- NOT part of any workspace.

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
    args = [[1, 2, 6, 4], 3]
    want = 3
    got = solution.maxFrequencyScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[1, 4, 4, 2, 4], 0]
    want = 3
    got = solution.maxFrequencyScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[1, 13], 0]
    want = 1
    got = solution.maxFrequencyScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[7, 9], 25]
    want = 2
    got = solution.maxFrequencyScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[13, 15, 16], 6]
    want = 3
    got = solution.maxFrequencyScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[2, 1, 9, 9, 5, 6], 69]
    want = 6
    got = solution.maxFrequencyScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[4, 3, 11, 3, 17, 7, 12], 1]
    want = 3
    got = solution.maxFrequencyScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[15, 12, 9, 3, 20, 5, 5, 1, 9], 4]
    want = 3
    got = solution.maxFrequencyScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[3, 6, 6, 9, 4, 2, 3, 10, 5, 6], 0]
    want = 3
    got = solution.maxFrequencyScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[5, 2, 2, 4, 3, 1, 2, 4, 5, 4], 27]
    want = 10
    got = solution.maxFrequencyScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[6, 4, 10, 3, 7, 5, 3, 9, 7, 1], 12]
    want = 7
    got = solution.maxFrequencyScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

