"""Scoring checks for lcb_2839 -- NOT part of any workspace.

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
    args = [[4, 3, 1, 2], [2, 4, 9, 5], [[4, 1], [1, 3], [2, 5]]]
    want = [6, 10, 7]
    got = solution.maximumSumQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[3, 2, 5], [2, 3, 4], [[4, 4], [3, 2], [1, 1]]]
    want = [9, 9, 9]
    got = solution.maximumSumQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[2, 1], [2, 3], [[3, 3]]]
    want = [-1]
    got = solution.maximumSumQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[1], [1], [[1, 1]]]
    want = [2]
    got = solution.maximumSumQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[6], [4], [[7, 9], [5, 4]]]
    want = [-1, 10]
    got = solution.maximumSumQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[1], [4], [[3, 10], [3, 4], [10, 8]]]
    want = [-1, -1, -1]
    got = solution.maximumSumQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[4, 9, 5], [6, 9, 10], [[3, 10], [1, 8]]]
    want = [15, 18]
    got = solution.maximumSumQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[9, 4, 5, 2, 4, 1], [4, 2, 5, 8, 1, 6], [[7, 1]]]
    want = [13]
    got = solution.maximumSumQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[5], [5], [[4, 1], [3, 1], [2, 9], [6, 1], [6, 6]]]
    want = [10, 10, -1, -1, -1]
    got = solution.maximumSumQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[2, 10, 2, 7, 9], [2, 3, 2, 2, 1], [[5, 4], [4, 4], [5, 2]]]
    want = [-1, -1, 13]
    got = solution.maximumSumQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

