"""Scoring checks for lcb_2869 -- NOT part of any workspace.

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
    args = [[2, 3, 1], [1, 2, 1]]
    want = 2
    got = solution.maxNonDecreasingLength(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[1, 3, 2, 1], [2, 2, 3, 4]]
    want = 4
    got = solution.maxNonDecreasingLength(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[1, 1], [2, 2]]
    want = 2
    got = solution.maxNonDecreasingLength(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[7], [2]]
    want = 1
    got = solution.maxNonDecreasingLength(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[35], [73]]
    want = 1
    got = solution.maxNonDecreasingLength(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[6, 6, 3], [7, 9, 3]]
    want = 2
    got = solution.maxNonDecreasingLength(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[549704557], [853763571]]
    want = 1
    got = solution.maxNonDecreasingLength(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[38, 94, 33], [43, 5, 7]]
    want = 2
    got = solution.maxNonDecreasingLength(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[5, 6, 2, 4], [1, 9, 8, 5]]
    want = 3
    got = solution.maxNonDecreasingLength(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[27848682, 758449970], [788911263, 296067790]]
    want = 2
    got = solution.maxNonDecreasingLength(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[43, 42, 75, 60, 58, 16], [91, 96, 98, 35, 17, 10]]
    want = 3
    got = solution.maxNonDecreasingLength(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[4, 2, 7, 8, 6, 1, 8, 7, 6, 2], [4, 2, 1, 10, 2, 4, 2, 9, 4, 3]]
    want = 4
    got = solution.maxNonDecreasingLength(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

