"""Scoring checks for lcb_3783 -- NOT part of any workspace.

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
    args = [4, 6]
    want = [3, 4, 1, 2]
    got = solution.permute(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [3, 2]
    want = [3, 2, 1]
    got = solution.permute(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [2, 3]
    want = []
    got = solution.permute(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [100, 910773911318901]
    want = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 91, 86, 81, 94, 89, 84, 79, 98, 83, 82, 85, 90, 87, 80, 99, 92, 97, 100, 93, 88, 95, 96]
    got = solution.permute(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [1, 1]
    want = [1]
    got = solution.permute(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [1, 1]
    want = [1]
    got = solution.permute(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [100, 987952744058429]
    want = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 91, 98, 79, 84, 93, 82, 83, 100, 87, 90, 85, 88, 95, 92, 97, 80, 99, 94, 81, 86, 89, 96]
    got = solution.permute(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [1, 1]
    want = [1]
    got = solution.permute(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [1, 1]
    want = [1]
    got = solution.permute(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [100, 60071615558619]
    want = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 88, 91, 94, 83, 96, 85, 86, 87, 100, 81, 82, 93, 92, 97, 98, 95, 80, 99, 84, 89, 90]
    got = solution.permute(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [2, 1]
    want = [1, 2]
    got = solution.permute(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [1, 1]
    want = [1]
    got = solution.permute(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [2, 2]
    want = [2, 1]
    got = solution.permute(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [100, 861099165996912]
    want = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 89, 100, 85, 98, 83, 82, 81, 94, 95, 80, 79, 88, 91, 84, 97, 96, 99, 92, 93, 90, 87, 86]
    got = solution.permute(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [2, 1]
    want = [1, 2]
    got = solution.permute(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [1, 1]
    want = [1]
    got = solution.permute(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [2, 3]
    want = []
    got = solution.permute(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [2, 2]
    want = [2, 1]
    got = solution.permute(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [100, 42679393288594]
    want = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 86, 85, 90, 81, 100, 99, 82, 87, 94, 93, 88, 83, 96, 97, 80, 95, 98, 89, 92, 91, 84]
    got = solution.permute(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [2, 2]
    want = [2, 1]
    got = solution.permute(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [2, 2]
    want = [2, 1]
    got = solution.permute(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [1, 2]
    want = []
    got = solution.permute(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [1, 1]
    want = [1]
    got = solution.permute(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = [100, 652499363915162]
    want = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 87, 90, 91, 92, 81, 80, 93, 96, 83, 94, 95, 84, 89, 86, 79, 82, 99, 88, 85, 100, 97, 98]
    got = solution.permute(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = [1, 1]
    want = [1]
    got = solution.permute(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = [20, 26336378880001]
    want = []
    got = solution.permute(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_27():
    args = [2, 2]
    want = [2, 1]
    got = solution.permute(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

