"""Scoring checks for lcb_2891 -- NOT part of any workspace.

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
    args = [[4, 6, 1, 2], 2]
    want = 3
    got = solution.maximumBeauty(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[1, 1, 1, 1], 10]
    want = 4
    got = solution.maximumBeauty(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[2, 10], 4]
    want = 2
    got = solution.maximumBeauty(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[1, 97, 5, 12], 49]
    want = 4
    got = solution.maximumBeauty(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[56, 19, 26, 86, 99], 37]
    want = 4
    got = solution.maximumBeauty(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[47, 73, 48, 83, 22], 503]
    want = 5
    got = solution.maximumBeauty(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[84, 81, 90, 57, 35, 75, 78], 0]
    want = 1
    got = solution.maximumBeauty(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[43, 31, 42, 70, 99, 92, 65], 3]
    want = 2
    got = solution.maximumBeauty(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[0, 1, 2, 3, 4, 5, 6, 7, 8, 9], 0]
    want = 1
    got = solution.maximumBeauty(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[5, 3, 5, 9, 1, 3, 5, 8, 9, 10], 3375]
    want = 10
    got = solution.maximumBeauty(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[10, 0, 10, 0, 10, 0, 10, 0, 10, 0], 10]
    want = 10
    got = solution.maximumBeauty(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

