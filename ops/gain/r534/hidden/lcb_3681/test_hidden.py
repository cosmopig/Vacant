"""Scoring checks for lcb_3681 -- NOT part of any workspace.

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
    args = [[[1, 1], [1, 3], [3, 1], [3, 3]]]
    want = 4
    got = solution.maxRectangleArea(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[[1, 1], [1, 3], [3, 1], [3, 3], [2, 2]]]
    want = -1
    got = solution.maxRectangleArea(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[[1, 1], [1, 3], [3, 1], [3, 3], [1, 2], [3, 2]]]
    want = 2
    got = solution.maxRectangleArea(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[[84, 97], [95, 62], [96, 10], [96, 62], [95, 10], [32, 40], [50, 43], [2, 14], [98, 94], [72, 18]]]
    want = 52
    got = solution.maxRectangleArea(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[[100, 79], [10, 74], [100, 74], [10, 79], [73, 29]]]
    want = 450
    got = solution.maxRectangleArea(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[[41, 57], [95, 22], [50, 0], [6, 61], [6, 57], [14, 24], [24, 96], [27, 9], [41, 61], [45, 42]]]
    want = 140
    got = solution.maxRectangleArea(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[[8, 52], [45, 61], [8, 61], [45, 52], [15, 63]]]
    want = 333
    got = solution.maxRectangleArea(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[[52, 17], [12, 54], [52, 54], [12, 17], [56, 4]]]
    want = 1480
    got = solution.maxRectangleArea(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[[94, 39], [34, 56], [94, 56], [34, 39], [14, 46]]]
    want = 1020
    got = solution.maxRectangleArea(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[[19, 5], [8, 94], [75, 80], [38, 94], [56, 96], [38, 22], [73, 22], [51, 0], [94, 55], [73, 94]]]
    want = 2520
    got = solution.maxRectangleArea(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[[51, 34], [23, 34], [100, 89], [95, 99], [55, 3], [22, 89], [22, 49], [48, 41], [100, 49], [14, 89]]]
    want = 3120
    got = solution.maxRectangleArea(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[[100, 80], [67, 79], [100, 79], [67, 80], [80, 47]]]
    want = 33
    got = solution.maxRectangleArea(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [[[0, 0], [0, 2], [2, 0], [2, 2], [3, 3]]]
    want = 4
    got = solution.maxRectangleArea(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [[[29, 11], [27, 97], [29, 97], [42, 20], [27, 11], [40, 63], [93, 7], [63, 94], [73, 98], [45, 92]]]
    want = 172
    got = solution.maxRectangleArea(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [[[96, 14], [7, 76], [92, 54], [4, 52], [8, 5], [54, 63], [65, 53], [8, 76], [53, 76], [7, 5]]]
    want = 71
    got = solution.maxRectangleArea(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [[[13, 8], [22, 39], [13, 39], [22, 8], [85, 6]]]
    want = 279
    got = solution.maxRectangleArea(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [[[4, 36], [40, 64], [66, 75], [4, 51], [34, 96], [84, 70], [67, 36], [17, 26], [67, 51], [68, 83]]]
    want = 945
    got = solution.maxRectangleArea(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [[[5, 8], [42, 77], [5, 77], [42, 8], [55, 65]]]
    want = 2553
    got = solution.maxRectangleArea(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [[[2, 32], [21, 32], [18, 13], [84, 62], [84, 32], [89, 10], [60, 41], [72, 62], [2, 62], [45, 2]]]
    want = -1
    got = solution.maxRectangleArea(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [[[3, 27], [6, 16], [3, 16], [6, 27], [40, 13]]]
    want = 33
    got = solution.maxRectangleArea(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [[[42, 3], [30, 1], [8, 12], [78, 31], [53, 37], [99, 89], [62, 51], [99, 51], [80, 47], [62, 89]]]
    want = 1406
    got = solution.maxRectangleArea(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [[[61, 37], [51, 99], [61, 99], [51, 37], [1, 95]]]
    want = 620
    got = solution.maxRectangleArea(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [[[39, 86], [92, 78], [93, 70], [68, 97], [21, 35], [43, 97], [43, 77], [50, 18], [17, 76], [68, 77]]]
    want = 500
    got = solution.maxRectangleArea(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = [[[23, 57], [10, 19], [23, 19], [10, 57], [87, 25]]]
    want = 494
    got = solution.maxRectangleArea(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = [[[29, 42], [70, 17], [29, 17], [70, 42], [85, 89]]]
    want = 1025
    got = solution.maxRectangleArea(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = [[[25, 13], [81, 80], [64, 12], [75, 47], [58, 97], [53, 96], [25, 35], [40, 13], [40, 35], [88, 48]]]
    want = 330
    got = solution.maxRectangleArea(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_27():
    args = [[[17, 31], [6, 16], [17, 16], [6, 31], [10, 100]]]
    want = 165
    got = solution.maxRectangleArea(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

