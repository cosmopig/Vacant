"""Scoring checks for lcb_3587 -- NOT part of any workspace.

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
    args = [2, 1, [[2, 3]], [[0, 2], [1, 0]]]
    want = 3
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [3, 2, [[3, 4, 2], [2, 1, 2]], [[0, 2, 1], [2, 0, 4], [3, 2, 0]]]
    want = 8
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [5, 5, [[1, 4, 2, 1, 1], [3, 3, 3, 3, 1], [1, 5, 2, 6, 1], [1, 1, 5, 11, 2], [3, 2, 3, 5, 1]], [[0, 7, 1, 3, 4], [6, 0, 1, 3, 2], [6, 1, 0, 4, 6], [9, 5, 10, 0, 3], [1, 5, 4, 6, 0]]]
    want = 43
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [1, 2, [[2], [2]], [[0]]]
    want = 4
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [1, 2, [[7], [1]], [[0]]]
    want = 8
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [1, 2, [[6], [3]], [[0]]]
    want = 9
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [1, 1, [[5]], [[0]]]
    want = 5
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [6, 6, [[1, 8, 1, 4, 9, 7], [9, 2, 2, 4, 2, 3], [2, 2, 1, 2, 3, 4], [9, 1, 2, 6, 2, 2], [4, 1, 3, 1, 2, 9], [5, 9, 8, 4, 4, 2]], [[0, 4, 2, 3, 6, 9], [1, 0, 2, 1, 10, 5], [2, 1, 0, 2, 6, 1], [1, 7, 2, 0, 8, 6], [8, 2, 2, 1, 0, 4], [5, 1, 2, 5, 4, 0]]]
    want = 49
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [1, 2, [[2], [1]], [[0]]]
    want = 3
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [6, 3, [[3, 2, 8, 4, 2, 6], [2, 7, 3, 10, 4, 9], [1, 2, 1, 11, 4, 1]], [[0, 1, 8, 1, 3, 3], [1, 0, 9, 5, 5, 4], [3, 1, 0, 1, 3, 9], [1, 2, 1, 0, 2, 2], [2, 3, 1, 2, 0, 1], [1, 3, 1, 1, 2, 0]]]
    want = 26
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [5, 4, [[3, 8, 4, 6, 9], [3, 3, 1, 4, 1], [2, 3, 11, 1, 1], [8, 2, 1, 4, 1]], [[0, 2, 10, 5, 7], [7, 0, 2, 2, 6], [8, 1, 0, 3, 1], [4, 6, 3, 0, 4], [3, 3, 9, 2, 0]]]
    want = 37
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [2, 1, [[2, 3]], [[0, 4], [10, 0]]]
    want = 10
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [2, 1, [[2, 8]], [[0, 1], [4, 0]]]
    want = 8
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [2, 1, [[3, 1]], [[0, 1], [1, 0]]]
    want = 3
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [1, 2, [[11], [4]], [[0]]]
    want = 15
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [1, 2, [[4], [1]], [[0]]]
    want = 5
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [4, 6, [[4, 1, 1, 1], [7, 3, 2, 11], [1, 2, 5, 2], [3, 1, 4, 1], [1, 2, 6, 2], [1, 1, 7, 1]], [[0, 4, 2, 2], [2, 0, 2, 6], [2, 2, 0, 7], [8, 2, 5, 0]]]
    want = 44
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [5, 4, [[3, 2, 1, 1, 4], [5, 6, 2, 1, 4], [4, 5, 4, 2, 5], [3, 8, 1, 1, 4]], [[0, 10, 3, 3, 6], [5, 0, 1, 3, 1], [1, 1, 0, 3, 5], [2, 5, 2, 0, 1], [6, 1, 1, 1, 0]]]
    want = 33
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [1, 2, [[2], [9]], [[0]]]
    want = 11
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [2, 1, [[1, 1]], [[0, 1], [6, 0]]]
    want = 6
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [1, 1, [[7]], [[0]]]
    want = 7
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [1, 1, [[1]], [[0]]]
    want = 1
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [1, 2, [[6], [2]], [[0]]]
    want = 8
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = [4, 6, [[2, 2, 8, 6], [2, 2, 4, 1], [8, 2, 5, 7], [2, 4, 4, 2], [2, 3, 6, 1], [2, 6, 6, 3]], [[0, 3, 3, 2], [9, 0, 1, 5], [3, 1, 0, 3], [1, 2, 4, 0]]]
    want = 36
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = [4, 5, [[3, 2, 3, 8], [3, 4, 8, 4], [3, 5, 11, 1], [8, 6, 1, 5], [1, 4, 4, 8]], [[0, 4, 1, 5], [9, 0, 1, 5], [4, 2, 0, 3], [10, 1, 4, 0]]]
    want = 40
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = [2, 1, [[1, 1]], [[0, 6], [1, 0]]]
    want = 6
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

