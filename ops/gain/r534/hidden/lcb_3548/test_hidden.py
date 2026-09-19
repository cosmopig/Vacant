"""Scoring checks for lcb_3548 -- NOT part of any workspace.

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
    args = [3, 5]
    want = 27
    got = solution.countGoodIntegers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [1, 4]
    want = 2
    got = solution.countGoodIntegers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [5, 6]
    want = 2468
    got = solution.countGoodIntegers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [1, 5]
    want = 1
    got = solution.countGoodIntegers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [1, 3]
    want = 3
    got = solution.countGoodIntegers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [10, 2]
    want = 39718144
    got = solution.countGoodIntegers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [1, 6]
    want = 1
    got = solution.countGoodIntegers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [6, 8]
    want = 5221
    got = solution.countGoodIntegers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [9, 9]
    want = 4623119
    got = solution.countGoodIntegers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [6, 6]
    want = 3109
    got = solution.countGoodIntegers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [1, 7]
    want = 1
    got = solution.countGoodIntegers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [2, 8]
    want = 1
    got = solution.countGoodIntegers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [2, 2]
    want = 4
    got = solution.countGoodIntegers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [3, 4]
    want = 54
    got = solution.countGoodIntegers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [3, 2]
    want = 108
    got = solution.countGoodIntegers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [1, 1]
    want = 9
    got = solution.countGoodIntegers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [1, 5]
    want = 1
    got = solution.countGoodIntegers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [10, 1]
    want = 41457024
    got = solution.countGoodIntegers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [2, 7]
    want = 1
    got = solution.countGoodIntegers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [2, 6]
    want = 1
    got = solution.countGoodIntegers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [10, 5]
    want = 19284856
    got = solution.countGoodIntegers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [9, 4]
    want = 33175696
    got = solution.countGoodIntegers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [8, 4]
    want = 494818
    got = solution.countGoodIntegers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = [3, 6]
    want = 30
    got = solution.countGoodIntegers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = [9, 5]
    want = 15814071
    got = solution.countGoodIntegers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = [2, 9]
    want = 1
    got = solution.countGoodIntegers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_27():
    args = [1, 9]
    want = 1
    got = solution.countGoodIntegers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

