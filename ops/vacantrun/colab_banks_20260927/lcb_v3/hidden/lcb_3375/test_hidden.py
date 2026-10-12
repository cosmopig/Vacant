"""Scoring checks for lcb_3375 -- NOT part of any workspace.

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
    args = [[3, 6, 9], 3]
    want = 9
    got = solution.findKthSmallest(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[5, 2], 7]
    want = 12
    got = solution.findKthSmallest(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[4, 9, 19, 20, 12], 1]
    want = 4
    got = solution.findKthSmallest(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[23, 20, 12, 11, 8, 6, 4, 2, 1], 1582907270]
    want = 1582907270
    got = solution.findKthSmallest(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[21, 5, 18, 17, 8, 11, 19, 25, 13, 10, 24, 23, 15], 1218177966]
    want = 2242115680
    got = solution.findKthSmallest(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15], 47350]
    want = 47350
    got = solution.findKthSmallest(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[20], 230954314]
    want = 4619086280
    got = solution.findKthSmallest(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[22, 20, 18, 16, 15, 11, 10, 9, 3, 1], 175442064]
    want = 175442064
    got = solution.findKthSmallest(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[25], 2000000000]
    want = 50000000000
    got = solution.findKthSmallest(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[5], 7]
    want = 35
    got = solution.findKthSmallest(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[2, 8, 3, 4, 6], 6]
    want = 9
    got = solution.findKthSmallest(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[10, 17, 16, 2, 8, 21, 4, 18, 20, 6], 1939408996]
    want = 3514563510
    got = solution.findKthSmallest(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [[1], 2000000000]
    want = 2000000000
    got = solution.findKthSmallest(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [[9, 10, 23, 3, 24, 21], 1685167354]
    want = 3954984609
    got = solution.findKthSmallest(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [[24, 25], 2000000000]
    want = 25000000000
    got = solution.findKthSmallest(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [[8, 4], 78]
    want = 312
    got = solution.findKthSmallest(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [[12, 9, 17, 23, 24, 2, 13, 10, 25, 18, 22, 3, 1, 16, 20], 397079711]
    want = 397079711
    got = solution.findKthSmallest(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [[7, 16, 20, 12, 19], 955]
    want = 3084
    got = solution.findKthSmallest(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [[4, 7, 19, 3, 17, 1, 20, 8, 14, 15], 968251697]
    want = 968251697
    got = solution.findKthSmallest(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [[1, 10, 100, 1000, 10000], 2000000000]
    want = 2000000000
    got = solution.findKthSmallest(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [[7, 5, 2, 6], 20]
    want = 30
    got = solution.findKthSmallest(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [[1], 1]
    want = 1
    got = solution.findKthSmallest(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [[1, 4, 7, 6], 6]
    want = 6
    got = solution.findKthSmallest(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = [[4, 12, 18, 19, 10, 11, 13, 6, 24, 20, 25, 1, 9, 21], 1]
    want = 1
    got = solution.findKthSmallest(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = [[16, 17, 18, 19, 20, 21, 22, 23, 24, 25], 2000000000]
    want = 5581697380
    got = solution.findKthSmallest(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = [[25], 1]
    want = 25
    got = solution.findKthSmallest(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

