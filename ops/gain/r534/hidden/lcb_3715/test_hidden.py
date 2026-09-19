"""Scoring checks for lcb_3715 -- NOT part of any workspace.

⚠ 這個檔案是計分用的 GT。它住在 ops/gain/r534/hidden/ 這棵**另外的樹**裡，
  永遠不複製進 agent 的工作區；任何把它的內容（含失敗訊息）回饋給模型的路徑
  都是 R534 的紅線。

case 組成 ＝ 題庫的 `visible_tests` ＋ `hidden_tests`（超集），與
vacant/codebench.py::LiveCodeBenchLoader 的 `hidden_check` 逐字同一組，
所以算出來的分子與 runs/g_r460_harness_lcb2_*／runs/g_r532_lcb2_* 的
`meets_demand` 是同一把尺。
"""

import solution

def _aeq(a, b):
    """與 vacant/codebench.py::_lcb_check_code 的 __aeq 同一套判等（逐行對應）。"""
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
    args = [[[8, 10, 1], [1, 3, 2], [5, 6, 4]], 4]
    want = 10
    got = solution.maximumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[[1, 10, 3]], 2]
    want = 6
    got = solution.maximumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[[13, 33, 19], [36, 46, 10]], 44]
    want = 509
    got = solution.maximumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[[4, 10, 11], [11, 20, 3], [31, 33, 20], [24, 25, 4], [26, 30, 13], [34, 40, 16], [45, 46, 5]], 16]
    want = 241
    got = solution.maximumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[[46, 48, 2], [37, 39, 3], [7, 17, 2]], 10]
    want = 20
    got = solution.maximumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[[32, 50, 6], [16, 18, 9], [27, 29, 4]], 12]
    want = 72
    got = solution.maximumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[[32, 37, 5]], 16]
    want = 30
    got = solution.maximumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[[7, 10, 1], [18, 19, 16], [13, 14, 18], [29, 30, 8], [24, 28, 8], [1, 2, 12], [36, 38, 12], [21, 22, 10]], 36]
    want = 184
    got = solution.maximumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[[29, 33, 7]], 11]
    want = 35
    got = solution.maximumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[[1, 5, 3], [6, 10, 7], [11, 15, 5]], 5]
    want = 35
    got = solution.maximumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[[1, 3, 4], [4, 8, 2], [9, 15, 6]], 6]
    want = 36
    got = solution.maximumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[[9, 10, 17], [46, 47, 13], [31, 32, 18], [33, 44, 16]], 30]
    want = 254
    got = solution.maximumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [[[5, 9, 10]], 5]
    want = 50
    got = solution.maximumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [[[16, 24, 5], [5, 8, 3], [11, 14, 12], [43, 45, 1], [30, 34, 20], [41, 42, 10]], 17]
    want = 135
    got = solution.maximumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [[[12, 15, 18], [23, 24, 9], [2, 7, 16], [46, 47, 12], [34, 35, 4]], 9]
    want = 96
    got = solution.maximumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [[[11, 12, 11], [6, 7, 9], [43, 45, 2], [24, 28, 11], [38, 39, 7], [48, 50, 11], [2, 5, 17], [29, 34, 15]], 26]
    want = 187
    got = solution.maximumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [[[29, 50, 1], [18, 24, 16], [25, 26, 1]], 38]
    want = 136
    got = solution.maximumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [[[1, 2, 10], [4, 5, 20]], 3]
    want = 40
    got = solution.maximumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [[[30, 49, 12]], 28]
    want = 240
    got = solution.maximumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [[[24, 29, 8], [8, 16, 20], [45, 50, 20], [1, 3, 12], [42, 43, 5], [36, 41, 18], [4, 6, 18]], 6]
    want = 120
    got = solution.maximumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [[[15, 18, 11], [2, 6, 16], [34, 37, 9]], 24]
    want = 124
    got = solution.maximumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [[[1, 100, 10]], 50]
    want = 500
    got = solution.maximumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [[[1, 1000000000, 1000]], 1000000000]
    want = 1000000000000
    got = solution.maximumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = [[[33, 37, 4], [2, 4, 15], [5, 8, 18], [40, 46, 11], [20, 23, 19], [13, 18, 7]], 31]
    want = 235
    got = solution.maximumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = [[[10, 20, 5], [30, 40, 10], [50, 60, 20]], 25]
    want = 270
    got = solution.maximumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = [[[21, 23, 10], [43, 45, 12], [1, 11, 1], [48, 50, 6], [14, 16, 11], [19, 20, 14], [29, 33, 18]], 28]
    want = 187
    got = solution.maximumCoins(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

