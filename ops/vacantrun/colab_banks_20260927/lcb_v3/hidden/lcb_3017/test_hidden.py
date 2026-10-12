"""Scoring checks for lcb_3017 -- NOT part of any workspace.

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
    args = [10, 20, 3]
    want = 2
    got = solution.numberOfBeautifulIntegers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [1, 10, 1]
    want = 1
    got = solution.numberOfBeautifulIntegers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [5, 5, 2]
    want = 0
    got = solution.numberOfBeautifulIntegers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [1, 1, 1]
    want = 0
    got = solution.numberOfBeautifulIntegers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [19, 50, 2]
    want = 6
    got = solution.numberOfBeautifulIntegers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [94, 94, 9]
    want = 0
    got = solution.numberOfBeautifulIntegers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [94, 100, 1]
    want = 3
    got = solution.numberOfBeautifulIntegers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [52, 396, 9]
    want = 5
    got = solution.numberOfBeautifulIntegers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [47, 735, 2]
    want = 15
    got = solution.numberOfBeautifulIntegers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [90, 110, 16]
    want = 1
    got = solution.numberOfBeautifulIntegers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [934, 991, 1]
    want = 0
    got = solution.numberOfBeautifulIntegers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [1, 1000000000, 1]
    want = 24894045
    got = solution.numberOfBeautifulIntegers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [33340762, 612987024, 1]
    want = 18196584
    got = solution.numberOfBeautifulIntegers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [36954768, 642296821, 14]
    want = 1240042
    got = solution.numberOfBeautifulIntegers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [17946863, 807558969, 17]
    want = 1319380
    got = solution.numberOfBeautifulIntegers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

