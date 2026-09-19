"""Scoring checks for lcb_3649 -- NOT part of any workspace.

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
    args = [[3, 4, 1], 1]
    want = 4
    got = solution.findMinimumTime(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[2, 5, 4], 2]
    want = 5
    got = solution.findMinimumTime(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[1000000, 1000000, 1000000, 1000000, 1000000, 1000000, 1000000, 1000000], 5]
    want = 1466196
    got = solution.findMinimumTime(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[334267, 123460, 65278, 147595, 720057, 84774, 705691, 733613], 9]
    want = 134458
    got = solution.findMinimumTime(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[50, 4], 6]
    want = 12
    got = solution.findMinimumTime(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[1000000, 1000000, 1000000, 1000000, 1000000, 1000000, 1000000, 1000000], 4]
    want = 1568963
    got = solution.findMinimumTime(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[1000000, 1000000, 1000000, 1000000, 1000000, 1000000, 1000000, 1000000], 10]
    want = 1245267
    got = solution.findMinimumTime(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[1000000, 1000000, 1000000, 1000000, 1000000, 1000000, 1000000, 1000000], 2]
    want = 2021805
    got = solution.findMinimumTime(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[253442], 5]
    want = 253442
    got = solution.findMinimumTime(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[549140], 4]
    want = 549140
    got = solution.findMinimumTime(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[9], 5]
    want = 9
    got = solution.findMinimumTime(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[918874], 4]
    want = 918874
    got = solution.findMinimumTime(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [[40, 50], 4]
    want = 50
    got = solution.findMinimumTime(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [[6], 9]
    want = 6
    got = solution.findMinimumTime(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [[639950, 936093, 255843, 806529, 408212, 600644, 63343, 580478], 1]
    want = 931475
    got = solution.findMinimumTime(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [[9, 14], 4]
    want = 12
    got = solution.findMinimumTime(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [[539261], 7]
    want = 539261
    got = solution.findMinimumTime(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [[1000000, 1000000, 1000000, 1000000, 1000000, 1000000, 1000000, 1000000], 1]
    want = 2717859
    got = solution.findMinimumTime(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [[1000000, 1000000, 1000000, 1000000, 1000000, 1000000, 1000000, 1000000], 6]
    want = 1394957
    got = solution.findMinimumTime(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [[972959], 5]
    want = 972959
    got = solution.findMinimumTime(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [[358080], 9]
    want = 358080
    got = solution.findMinimumTime(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [[1000000, 1000000, 1000000, 1000000, 1000000, 1000000, 1000000, 1000000], 3]
    want = 1730369
    got = solution.findMinimumTime(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [[12, 23], 4]
    want = 17
    got = solution.findMinimumTime(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = [[17, 21], 1]
    want = 28
    got = solution.findMinimumTime(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = [[26], 6]
    want = 26
    got = solution.findMinimumTime(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = [[1000000, 1000000, 1000000, 1000000, 1000000, 1000000, 1000000, 1000000], 9]
    want = 1270922
    got = solution.findMinimumTime(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

