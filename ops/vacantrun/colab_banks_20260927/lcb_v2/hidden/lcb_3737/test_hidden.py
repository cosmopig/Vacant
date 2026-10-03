"""Scoring checks for lcb_3737 -- NOT part of any workspace.

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
    args = [4, [[3, 5, 7], [6, 2, 9], [4, 8, 1], [7, 3, 5]]]
    want = 9
    got = solution.minCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [6, [[2, 4, 6], [5, 3, 8], [7, 1, 9], [4, 6, 2], [3, 5, 7], [8, 2, 4]]]
    want = 18
    got = solution.minCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [2, [[6, 0, 10], [5, 7, 5]]]
    want = 5
    got = solution.minCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [2, [[0, 6, 4], [2, 4, 8]]]
    want = 4
    got = solution.minCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [2, [[7, 9, 4], [2, 7, 3]]]
    want = 6
    got = solution.minCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [2, [[1, 8, 9], [3, 0, 10]]]
    want = 1
    got = solution.minCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [2, [[32, 14, 0], [61, 55, 16]]]
    want = 30
    got = solution.minCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [2, [[3, 6, 8], [8, 2, 3]]]
    want = 5
    got = solution.minCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [2, [[5, 6, 9], [7, 7, 4]]]
    want = 9
    got = solution.minCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [2, [[5, 0, 1], [0, 5, 6]]]
    want = 0
    got = solution.minCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [2, [[7, 2, 1], [8, 8, 3]]]
    want = 5
    got = solution.minCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [2, [[2, 6, 8], [3, 7, 8]]]
    want = 9
    got = solution.minCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [2, [[0, 7, 8], [7, 4, 5]]]
    want = 4
    got = solution.minCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [2, [[74, 97, 4], [88, 33, 87]]]
    want = 37
    got = solution.minCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [2, [[5, 2, 2], [9, 2, 10]]]
    want = 4
    got = solution.minCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [2, [[1, 4, 2], [3, 4, 6]]]
    want = 5
    got = solution.minCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [2, [[5, 2, 8], [3, 4, 10]]]
    want = 5
    got = solution.minCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [2, [[9, 0, 7], [4, 7, 8]]]
    want = 4
    got = solution.minCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [2, [[9, 14, 53], [71, 93, 54]]]
    want = 63
    got = solution.minCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [2, [[1, 6, 8], [2, 2, 4]]]
    want = 3
    got = solution.minCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [2, [[58, 3, 57], [2, 41, 42]]]
    want = 5
    got = solution.minCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [2, [[6, 4, 4], [6, 2, 4]]]
    want = 6
    got = solution.minCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [2, [[26, 100, 22], [2, 41, 6]]]
    want = 24
    got = solution.minCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = [2, [[9, 9, 3], [10, 9, 4]]]
    want = 12
    got = solution.minCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = [2, [[86, 3, 38], [93, 78, 93]]]
    want = 96
    got = solution.minCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = [2, [[48, 40, 77], [34, 68, 93]]]
    want = 74
    got = solution.minCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

