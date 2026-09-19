"""Scoring checks for lcb_3789 -- NOT part of any workspace.

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
    args = [4, [[2, 3], [1, 4]]]
    want = 9
    got = solution.maxSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [5, [[1, 2], [2, 5], [3, 5]]]
    want = 12
    got = solution.maxSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [20, [[12, 7], [9, 11]]]
    want = 147
    got = solution.maxSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [25, [[16, 14], [25, 10], [20, 19]]]
    want = 211
    got = solution.maxSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [25, [[11, 22], [18, 19], [22, 21]]]
    want = 241
    got = solution.maxSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [100000, [[38054, 60707], [65632, 33008], [49790, 73536]]]
    want = 3504756124
    got = solution.maxSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [100000, [[94051, 50717], [65219, 30956]]]
    want = 4698283850
    got = solution.maxSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [100000, [[57398, 39782], [60283, 47438]]]
    want = 3305217454
    got = solution.maxSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [100000, [[70201, 83570], [12828, 98288], [98252, 70024]]]
    want = 4877578024
    got = solution.maxSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [25, [[16, 9], [18, 23], [5, 17]]]
    want = 241
    got = solution.maxSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [10, [[2, 10], [5, 7]]]
    want = 53
    got = solution.maxSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [20, [[11, 18], [17, 14]]]
    want = 177
    got = solution.maxSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [100000, [[96712, 51569], [97482, 62650]]]
    want = 4842234650
    got = solution.maxSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [25, [[4, 3], [25, 2], [24, 12]]]
    want = 301
    got = solution.maxSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [25, [[15, 13], [8, 16], [17, 10]]]
    want = 227
    got = solution.maxSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [10, [[5, 7], [6, 5]]]
    want = 35
    got = solution.maxSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [100000, [[1, 2]]]
    want = 5000050000
    got = solution.maxSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [25, [[14, 7], [18, 10], [4, 6]]]
    want = 217
    got = solution.maxSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [25, [[22, 20], [19, 18], [17, 7]]]
    want = 210
    got = solution.maxSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [25, [[3, 10], [4, 19], [17, 22]]]
    want = 270
    got = solution.maxSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [25, [[9, 17], [13, 21], [10, 24]]]
    want = 260
    got = solution.maxSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [25, [[9, 1], [5, 7], [7, 10]]]
    want = 230
    got = solution.maxSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [20, [[17, 7], [8, 9]]]
    want = 182
    got = solution.maxSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = [100000, [[50000, 50001], [99999, 100000]]]
    want = 4999950001
    got = solution.maxSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = [100000, [[1, 2], [99999, 100000]]]
    want = 4999950001
    got = solution.maxSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = [25, [[2, 22], [7, 21], [17, 8]]]
    want = 290
    got = solution.maxSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

