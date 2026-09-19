"""Scoring checks for lcb_3779 -- NOT part of any workspace.

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
    args = [[1, 2, 3, 4, 5, 6, 7, 8]]
    want = 14
    got = solution.maxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[2, 1, 1, 1, 1, 1, 1, 1]]
    want = 3
    got = solution.maxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[5, 1, 2, 4]]
    want = 5
    got = solution.maxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[1, 2, 3, 4]]
    want = 4
    got = solution.maxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[999, 999, 1000, 1]]
    want = 1000
    got = solution.maxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[4, 5, 2, 3]]
    want = 5
    got = solution.maxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[3, 1, 4, 3]]
    want = 4
    got = solution.maxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[4, 1, 5, 5]]
    want = 5
    got = solution.maxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[2, 3, 5, 1]]
    want = 5
    got = solution.maxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[1, 2, 2, 1]]
    want = 2
    got = solution.maxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[5, 4, 5, 2]]
    want = 5
    got = solution.maxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[5, 2, 5, 2]]
    want = 5
    got = solution.maxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [[5, 3, 4, 4]]
    want = 5
    got = solution.maxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [[1, 1, 4, 1]]
    want = 4
    got = solution.maxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [[3, 5, 3, 8]]
    want = 8
    got = solution.maxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [[2, 5, 2, 3]]
    want = 5
    got = solution.maxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [[1, 1, 1, 1]]
    want = 1
    got = solution.maxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [[4, 1, 4, 4]]
    want = 4
    got = solution.maxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [[2, 8, 6, 10]]
    want = 10
    got = solution.maxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [[8, 4, 9, 7]]
    want = 9
    got = solution.maxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [[5, 1, 1, 1]]
    want = 5
    got = solution.maxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [[4, 2, 3, 1]]
    want = 4
    got = solution.maxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [[3, 3, 4, 5]]
    want = 5
    got = solution.maxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = [[3, 4, 5, 5]]
    want = 5
    got = solution.maxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = [[4, 2, 4, 2]]
    want = 4
    got = solution.maxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = [[2, 5, 3, 2]]
    want = 5
    got = solution.maxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

