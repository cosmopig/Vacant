"""Scoring checks for lcb_3674 -- NOT part of any workspace.

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
    args = [[6, 3, 1, 2, 4, 4], 7]
    want = 17
    got = solution.countNonDecreasingSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[6, 3, 1, 3, 6], 4]
    want = 12
    got = solution.countNonDecreasingSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[1000000000, 1, 1, 1, 1], 1000000000]
    want = 12
    got = solution.countNonDecreasingSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[1, 1000000000], 999999999]
    want = 3
    got = solution.countNonDecreasingSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[12], 1]
    want = 1
    got = solution.countNonDecreasingSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[6, 5, 4, 3, 2, 1], 15]
    want = 21
    got = solution.countNonDecreasingSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[14], 1]
    want = 1
    got = solution.countNonDecreasingSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[13], 1]
    want = 1
    got = solution.countNonDecreasingSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[3], 1]
    want = 1
    got = solution.countNonDecreasingSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[1000000000, 1], 999999999]
    want = 3
    got = solution.countNonDecreasingSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[1, 1], 1000000000]
    want = 3
    got = solution.countNonDecreasingSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[6, 5, 4, 3, 2, 1], 14]
    want = 20
    got = solution.countNonDecreasingSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [[3], 1]
    want = 1
    got = solution.countNonDecreasingSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [[1], 1]
    want = 1
    got = solution.countNonDecreasingSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [[7], 1]
    want = 1
    got = solution.countNonDecreasingSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [[12], 1]
    want = 1
    got = solution.countNonDecreasingSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [[1000000000, 1], 999999998]
    want = 2
    got = solution.countNonDecreasingSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [[15], 1]
    want = 1
    got = solution.countNonDecreasingSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [[12], 1]
    want = 1
    got = solution.countNonDecreasingSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [[6], 1]
    want = 1
    got = solution.countNonDecreasingSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [[15], 1]
    want = 1
    got = solution.countNonDecreasingSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [[8], 1]
    want = 1
    got = solution.countNonDecreasingSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [[14], 1]
    want = 1
    got = solution.countNonDecreasingSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = [[1, 1000000000], 999999998]
    want = 3
    got = solution.countNonDecreasingSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = [[19], 1]
    want = 1
    got = solution.countNonDecreasingSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = [[17], 1]
    want = 1
    got = solution.countNonDecreasingSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

