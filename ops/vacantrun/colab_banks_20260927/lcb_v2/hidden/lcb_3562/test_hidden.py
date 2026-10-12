"""Scoring checks for lcb_3562 -- NOT part of any workspace.

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
    args = [[[1, 3, 2], [4, 5, 2], [1, 5, 5], [6, 9, 3], [6, 7, 1], [8, 9, 1]]]
    want = [2, 3]
    got = solution.maximumWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[[5, 8, 1], [6, 7, 7], [4, 7, 3], [9, 10, 6], [7, 8, 2], [11, 14, 3], [3, 5, 5]]]
    want = [1, 3, 5, 6]
    got = solution.maximumWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[[20, 21, 16], [16, 25, 6]]]
    want = [0]
    got = solution.maximumWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[[21, 24, 32], [23, 25, 27], [2, 7, 21], [2, 7, 28], [2, 9, 5], [12, 19, 22]]]
    want = [0, 3, 5]
    got = solution.maximumWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[[5, 17, 28], [20, 24, 27], [9, 11, 12], [5, 14, 43], [25, 25, 43], [5, 6, 7]]]
    want = [1, 3, 4]
    got = solution.maximumWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[[15, 16, 23], [1, 9, 33], [13, 21, 10], [18, 18, 10], [4, 21, 1], [9, 11, 43], [17, 23, 50]]]
    want = [0, 5, 6]
    got = solution.maximumWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[[8, 15, 32], [20, 21, 8], [8, 16, 29], [7, 12, 50], [16, 25, 27], [12, 17, 2], [8, 12, 45], [5, 10, 50]]]
    want = [3, 4]
    got = solution.maximumWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[[17, 20, 17], [10, 13, 12], [23, 24, 18], [3, 3, 8], [1, 6, 36], [23, 23, 6], [17, 17, 49], [20, 21, 30], [21, 25, 39]]]
    want = [1, 4, 6, 8]
    got = solution.maximumWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[[1, 5, 5], [1, 3, 2], [4, 5, 2]]]
    want = [0]
    got = solution.maximumWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[[1, 1, 1000000000], [1, 1, 1000000000], [1, 1, 1000000000], [1, 1, 1000000000]]]
    want = [0]
    got = solution.maximumWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[[3, 5, 19], [3, 21, 12], [15, 18, 3], [23, 23, 44]]]
    want = [0, 2, 3]
    got = solution.maximumWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[[18, 23, 48], [1, 19, 11], [16, 19, 37], [3, 18, 25], [6, 22, 44], [18, 21, 27], [3, 21, 29], [6, 20, 29], [3, 24, 38], [3, 5, 44]]]
    want = [0, 9]
    got = solution.maximumWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [[[2, 1000000000, 1000000], [1, 1, 1000000]]]
    want = [0, 1]
    got = solution.maximumWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [[[16, 20, 43], [21, 25, 25]]]
    want = [0, 1]
    got = solution.maximumWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [[[1, 1000000000, 1000000], [2, 1000000000, 1000000]]]
    want = [0]
    got = solution.maximumWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [[[4, 5, 2], [7, 10, 6]]]
    want = [0, 1]
    got = solution.maximumWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [[[22, 22, 36], [17, 18, 2], [12, 18, 49], [23, 25, 8], [1, 22, 5]]]
    want = [0, 2, 3]
    got = solution.maximumWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [[[19, 20, 9], [6, 10, 5], [25, 25, 23], [12, 15, 11], [3, 23, 32], [13, 13, 24]]]
    want = [0, 1, 2, 5]
    got = solution.maximumWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [[[7, 19, 16], [19, 21, 34], [1, 11, 31], [4, 9, 29], [22, 22, 25], [23, 25, 48], [4, 13, 15]]]
    want = [1, 2, 4, 5]
    got = solution.maximumWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [[[7, 16, 26], [23, 23, 15], [1, 15, 34], [20, 20, 50], [12, 17, 45], [7, 23, 15], [19, 24, 30], [2, 24, 27], [16, 24, 7], [14, 21, 3]]]
    want = [1, 3, 4]
    got = solution.maximumWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [[[6, 7, 34], [6, 12, 45], [4, 15, 28], [15, 15, 27], [2, 11, 23], [6, 20, 44], [7, 19, 44], [16, 23, 30]]]
    want = [1, 3, 7]
    got = solution.maximumWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [[[12, 20, 24], [3, 9, 21], [6, 10, 35], [6, 6, 25], [7, 7, 2]]]
    want = [0, 2]
    got = solution.maximumWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [[[3, 19, 29], [1, 14, 9], [12, 17, 20], [8, 12, 30]]]
    want = [3]
    got = solution.maximumWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = [[[21, 23, 44], [22, 25, 10], [19, 23, 24]]]
    want = [0]
    got = solution.maximumWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = [[[12, 15, 7], [1, 13, 44], [11, 22, 28], [6, 12, 5], [12, 23, 42], [11, 19, 49], [16, 23, 50], [18, 21, 16], [2, 14, 6], [4, 16, 12]]]
    want = [1, 6]
    got = solution.maximumWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = [[[4, 8, 18], [21, 21, 19]]]
    want = [0, 1]
    got = solution.maximumWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

