"""Scoring checks for lcb_3560 -- NOT part of any workspace.

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
    args = [1, 1, [[0, 0]]]
    want = 4
    got = solution.maxMoves(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [0, 2, [[1, 1], [2, 2], [3, 3]]]
    want = 8
    got = solution.maxMoves(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [0, 0, [[1, 2], [2, 4]]]
    want = 3
    got = solution.maxMoves(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [20, 4, [[4, 26], [33, 17], [41, 30], [26, 43], [12, 39], [26, 17], [46, 10], [17, 3], [3, 0], [20, 29], [25, 24], [49, 2], [39, 48], [6, 22]]]
    want = 175
    got = solution.maxMoves(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [1, 5, [[1, 9]]]
    want = 2
    got = solution.maxMoves(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [32, 33, [[36, 6], [49, 17], [25, 14], [49, 2], [20, 26], [40, 37], [11, 25], [32, 3], [33, 26], [28, 5], [33, 3]]]
    want = 120
    got = solution.maxMoves(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [1, 6, [[2, 4]]]
    want = 1
    got = solution.maxMoves(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [22, 4, [[43, 44], [32, 32], [24, 31], [49, 22], [22, 0], [9, 35], [1, 23], [10, 45], [48, 9], [24, 36], [48, 47]]]
    want = 155
    got = solution.maxMoves(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [3, 6, [[7, 0]]]
    want = 4
    got = solution.maxMoves(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [42, 1, [[39, 47], [8, 49], [14, 49], [43, 1], [38, 39], [0, 16], [19, 36], [19, 42], [25, 2], [3, 45], [41, 37], [16, 47], [37, 37], [9, 17], [16, 27]]]
    want = 198
    got = solution.maxMoves(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [25, 26, [[43, 36], [49, 5], [18, 2], [5, 17], [31, 18], [43, 37], [27, 28], [38, 33], [5, 23], [46, 39], [16, 36]]]
    want = 132
    got = solution.maxMoves(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [28, 38, [[10, 31], [6, 38], [45, 10], [11, 17], [1, 15], [47, 32], [1, 20], [9, 1], [48, 5], [41, 8], [48, 35]]]
    want = 163
    got = solution.maxMoves(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [37, 12, [[15, 41], [39, 49], [43, 22], [12, 30], [21, 34], [0, 13], [25, 38], [40, 13], [41, 19]]]
    want = 116
    got = solution.maxMoves(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [21, 20, [[36, 34], [40, 42], [2, 46], [30, 29], [38, 27], [8, 1], [44, 23], [6, 25], [17, 12], [25, 1], [6, 45], [44, 28], [15, 7], [24, 19], [40, 23]]]
    want = 175
    got = solution.maxMoves(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [2, 7, [[1, 1]]]
    want = 3
    got = solution.maxMoves(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [3, 5, [[8, 7]]]
    want = 3
    got = solution.maxMoves(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [17, 1, [[28, 26], [42, 28], [16, 14], [1, 20], [34, 33], [49, 36], [49, 4], [13, 9], [38, 31], [33, 13], [13, 23], [33, 7]]]
    want = 138
    got = solution.maxMoves(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [21, 27, [[3, 26], [8, 5], [23, 29], [45, 44], [42, 28], [26, 44], [26, 30], [5, 35], [39, 19], [40, 49], [12, 7], [29, 3]]]
    want = 148
    got = solution.maxMoves(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [0, 0, [[49, 49], [0, 49], [49, 0]]]
    want = 93
    got = solution.maxMoves(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [1, 0, [[9, 3]]]
    want = 5
    got = solution.maxMoves(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [8, 4, [[5, 33], [32, 31], [3, 39], [22, 10], [35, 28], [23, 36], [34, 12], [26, 32], [34, 32], [36, 15], [33, 27], [28, 35]]]
    want = 109
    got = solution.maxMoves(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [9, 12, [[27, 0], [0, 3], [16, 43], [28, 16], [30, 44], [1, 19], [41, 18], [15, 10], [8, 26], [43, 13], [40, 2]]]
    want = 147
    got = solution.maxMoves(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [16, 33, [[26, 37], [41, 34]]]
    want = 22
    got = solution.maxMoves(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = [8, 28, [[23, 27], [8, 23], [2, 42], [7, 29], [22, 39], [14, 45], [33, 37], [13, 12]]]
    want = 78
    got = solution.maxMoves(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = [28, 26, [[10, 42], [34, 6], [6, 14], [12, 38], [46, 4], [8, 12], [10, 24], [0, 21], [35, 42], [46, 24], [22, 40]]]
    want = 142
    got = solution.maxMoves(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = [1, 3, [[1, 1]]]
    want = 2
    got = solution.maxMoves(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_27():
    args = [0, 0, [[40, 40], [41, 41], [42, 42], [43, 43], [44, 44], [45, 45], [46, 46], [47, 47], [48, 48], [49, 49]]]
    want = 62
    got = solution.maxMoves(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

