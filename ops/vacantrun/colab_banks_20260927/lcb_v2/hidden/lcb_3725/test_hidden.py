"""Scoring checks for lcb_3725 -- NOT part of any workspace.

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
    args = [[1, 2, 3], 2]
    want = 20
    got = solution.minMaxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[1, -3, 1], 2]
    want = -6
    got = solution.minMaxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[-4, 14], 1]
    want = 20
    got = solution.minMaxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[4], 1]
    want = 8
    got = solution.minMaxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[-18], 1]
    want = -36
    got = solution.minMaxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[-19, -16], 2]
    want = -105
    got = solution.minMaxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[-7, -7], 2]
    want = -42
    got = solution.minMaxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[-4], 1]
    want = -8
    got = solution.minMaxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[-8, 12], 1]
    want = 8
    got = solution.minMaxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[-3], 1]
    want = -6
    got = solution.minMaxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[-7, 13], 1]
    want = 12
    got = solution.minMaxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[12, -15], 2]
    want = -9
    got = solution.minMaxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [[-4, 0], 1]
    want = -8
    got = solution.minMaxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [[14, 12], 2]
    want = 78
    got = solution.minMaxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [[-9, 2], 1]
    want = -14
    got = solution.minMaxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [[15], 1]
    want = 30
    got = solution.minMaxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [[-11, 19], 1]
    want = 16
    got = solution.minMaxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [[-5], 1]
    want = -10
    got = solution.minMaxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [[-13, 17], 2]
    want = 12
    got = solution.minMaxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [[-13], 1]
    want = -26
    got = solution.minMaxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [[-4, -20], 1]
    want = -48
    got = solution.minMaxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [[-5, -4], 2]
    want = -27
    got = solution.minMaxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [[-2, 9], 1]
    want = 14
    got = solution.minMaxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = [[-14, -15], 1]
    want = -58
    got = solution.minMaxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = [[0], 1]
    want = 0
    got = solution.minMaxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = [[2, -4], 2]
    want = -6
    got = solution.minMaxSubarraySum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

