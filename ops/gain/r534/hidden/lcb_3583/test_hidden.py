"""Scoring checks for lcb_3583 -- NOT part of any workspace.

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
    args = [[2, 3, 4], [0, 2, 2]]
    want = [1, 2, 2]
    got = solution.gcdValues(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[4, 4, 2, 1], [5, 3, 1, 0]]
    want = [4, 2, 1, 1]
    got = solution.gcdValues(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[2, 2], [0, 0]]
    want = [2, 2]
    got = solution.gcdValues(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[6, 8], [0]]
    want = [2]
    got = solution.gcdValues(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[7, 1], [0]]
    want = [1]
    got = solution.gcdValues(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[7, 8], [0]]
    want = [1]
    got = solution.gcdValues(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[2, 13], [0]]
    want = [1]
    got = solution.gcdValues(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[2, 11], [0]]
    want = [1]
    got = solution.gcdValues(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[1, 2, 3, 4, 5], [1, 6, 8, 9, 2, 0, 3, 4, 5, 7]]
    want = [1, 1, 1, 2, 1, 1, 1, 1, 1, 1]
    got = solution.gcdValues(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[1, 5], [0]]
    want = [1]
    got = solution.gcdValues(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[7, 12], [0]]
    want = [1]
    got = solution.gcdValues(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[6, 3], [0]]
    want = [3]
    got = solution.gcdValues(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [[7, 8], [0]]
    want = [1]
    got = solution.gcdValues(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [[3, 11], [0]]
    want = [1]
    got = solution.gcdValues(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [[1, 1, 1, 1, 1], [2, 3, 5, 9, 0, 4, 1, 7, 6, 8]]
    want = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
    got = solution.gcdValues(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [[3, 8], [0]]
    want = [1]
    got = solution.gcdValues(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [[2, 3, 5, 7, 11, 13], [9, 6, 5, 7, 13, 11, 1, 2, 4, 14, 12, 10, 0, 8, 3]]
    want = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
    got = solution.gcdValues(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [[1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, 987, 1597, 2584, 4181, 6765, 10946, 17711, 28657, 46368], [188, 188, 188, 188, 189]]
    want = [1, 1, 1, 1, 1]
    got = solution.gcdValues(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [[1, 50000], [0]]
    want = [1]
    got = solution.gcdValues(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [[7, 3], [0]]
    want = [1]
    got = solution.gcdValues(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [[2, 4, 6, 8, 10], [1, 7, 0, 6, 3, 2, 5, 4, 8, 9]]
    want = [2, 2, 2, 2, 2, 2, 2, 2, 2, 4]
    got = solution.gcdValues(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [[1, 6], [0]]
    want = [1]
    got = solution.gcdValues(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [[7, 6], [0]]
    want = [1]
    got = solution.gcdValues(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = [[2, 6, 30, 210, 2310, 30030], [11, 7, 1, 12, 9, 14, 4, 10, 2, 5, 6, 0, 13, 3, 8]]
    want = [30, 6, 2, 210, 30, 2310, 2, 30, 2, 6, 6, 2, 210, 2, 6]
    got = solution.gcdValues(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = [[6, 5], [0]]
    want = [1]
    got = solution.gcdValues(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = [[1, 4], [0]]
    want = [1]
    got = solution.gcdValues(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_27():
    args = [[3, 9], [0]]
    want = [3]
    got = solution.gcdValues(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

