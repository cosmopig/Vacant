"""Scoring checks for lcb_3297 -- NOT part of any workspace.

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
    args = ['abacaba', 3]
    want = 2
    got = solution.minimumTimeToInitialState(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = ['abacaba', 4]
    want = 1
    got = solution.minimumTimeToInitialState(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = ['abcbabcd', 2]
    want = 4
    got = solution.minimumTimeToInitialState(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = ['g', 1]
    want = 1
    got = solution.minimumTimeToInitialState(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = ['uw', 1]
    want = 2
    got = solution.minimumTimeToInitialState(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = ['zk', 1]
    want = 2
    got = solution.minimumTimeToInitialState(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = ['zk', 2]
    want = 1
    got = solution.minimumTimeToInitialState(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = ['yea', 2]
    want = 2
    got = solution.minimumTimeToInitialState(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = ['tqk', 1]
    want = 3
    got = solution.minimumTimeToInitialState(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = ['wcp', 1]
    want = 3
    got = solution.minimumTimeToInitialState(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = ['jmoz', 3]
    want = 2
    got = solution.minimumTimeToInitialState(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = ['qsgyt', 1]
    want = 5
    got = solution.minimumTimeToInitialState(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = ['vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv', 15]
    want = 1
    got = solution.minimumTimeToInitialState(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = ['banmdhxjedvjflpvhnoqsmikwdllsnqskkgrjwwsjjxeglvhrq', 25]
    want = 2
    got = solution.minimumTimeToInitialState(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = ['awzowpopxvslnxixfddcffolqdeppqakwjhfpppgbgidmyqnne', 44]
    want = 2
    got = solution.minimumTimeToInitialState(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

