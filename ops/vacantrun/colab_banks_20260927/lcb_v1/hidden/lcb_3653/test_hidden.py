"""Scoring checks for lcb_3653 -- NOT part of any workspace.

⚠ 計分用的 GT。住在 hidden/ 這棵**另外的樹**，永遠不複製進 agent 的工作區；
  任何把它的內容（含失敗訊息）回饋給模型的路徑都作廢那一批資料。

case 組成 ＝ 題庫的 `visible_tests` ＋ `hidden_tests`（超集），與
vacant_network/codebench.py::LiveCodeBenchLoader 的 `hidden_check` 同一組（ops/gain/data/lcb_bank_v1.jsonl）。
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
    args = [[1, 2], 1]
    want = 3
    got = solution.maxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[-1, -2, -3, -4, -5], 4]
    want = -10
    got = solution.maxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[-5, 1, 2, -3, 4], 2]
    want = 4
    got = solution.maxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[9], 1]
    want = 9
    got = solution.maxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[-8], 1]
    want = -8
    got = solution.maxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[-7, -3], 1]
    want = -3
    got = solution.maxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[-7, -2], 2]
    want = -9
    got = solution.maxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[-9, 3], 1]
    want = 3
    got = solution.maxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[-5, -10], 1]
    want = -5
    got = solution.maxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[5], 1]
    want = 5
    got = solution.maxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[-3, -3], 1]
    want = -3
    got = solution.maxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[-10, 4], 1]
    want = 4
    got = solution.maxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [[-10, -1], 1]
    want = -1
    got = solution.maxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [[-6, -8], 1]
    want = -6
    got = solution.maxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [[-9, -9], 1]
    want = -9
    got = solution.maxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [[-5, 3], 2]
    want = -2
    got = solution.maxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [[-7, -9], 1]
    want = -7
    got = solution.maxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [[6], 1]
    want = 6
    got = solution.maxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [[-6, 7], 2]
    want = 1
    got = solution.maxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [[-7, -7], 1]
    want = -7
    got = solution.maxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [[8], 1]
    want = 8
    got = solution.maxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [[-4, 0], 1]
    want = 0
    got = solution.maxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [[6], 1]
    want = 6
    got = solution.maxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = [[-4, -5], 2]
    want = -9
    got = solution.maxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = [[-7, 9], 2]
    want = 2
    got = solution.maxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = [[0], 1]
    want = 0
    got = solution.maxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_27():
    args = [[2], 1]
    want = 2
    got = solution.maxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

