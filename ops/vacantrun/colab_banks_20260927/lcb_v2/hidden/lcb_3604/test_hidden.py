"""Scoring checks for lcb_3604 -- NOT part of any workspace.

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
    args = [1, 2, 3]
    want = 6
    got = solution.numberOfWays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [5, 2, 1]
    want = 32
    got = solution.numberOfWays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [3, 3, 4]
    want = 684
    got = solution.numberOfWays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [1, 1, 3]
    want = 3
    got = solution.numberOfWays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [1, 1, 8]
    want = 8
    got = solution.numberOfWays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [1, 2, 5]
    want = 10
    got = solution.numberOfWays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [1, 2, 3]
    want = 6
    got = solution.numberOfWays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [711, 855, 855]
    want = 734474073
    got = solution.numberOfWays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [907, 854, 356]
    want = 421276446
    got = solution.numberOfWays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [1, 2, 7]
    want = 14
    got = solution.numberOfWays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [939, 760, 692]
    want = 88639271
    got = solution.numberOfWays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [1, 2, 6]
    want = 12
    got = solution.numberOfWays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [2, 1, 2]
    want = 2
    got = solution.numberOfWays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [709, 658, 871]
    want = 121226132
    got = solution.numberOfWays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [1, 2, 1]
    want = 2
    got = solution.numberOfWays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [1, 3, 2]
    want = 6
    got = solution.numberOfWays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [2, 1, 5]
    want = 5
    got = solution.numberOfWays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [1, 2, 2]
    want = 4
    got = solution.numberOfWays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [1, 3, 1]
    want = 3
    got = solution.numberOfWays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [2, 1, 3]
    want = 3
    got = solution.numberOfWays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [1, 1, 6]
    want = 6
    got = solution.numberOfWays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [2, 1, 4]
    want = 4
    got = solution.numberOfWays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [1, 3, 3]
    want = 9
    got = solution.numberOfWays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = [1, 1, 1]
    want = 1
    got = solution.numberOfWays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = [974, 537, 530]
    want = 611246427
    got = solution.numberOfWays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = [897, 847, 566]
    want = 780654822
    got = solution.numberOfWays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_27():
    args = [829, 708, 820]
    want = 508655958
    got = solution.numberOfWays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

