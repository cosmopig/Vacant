"""Scoring checks for lcb_3750 -- NOT part of any workspace.

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
    args = [[1, 3, 1, 4, 1, 3, 2], [0, 3, 5]]
    want = [2, -1, 3]
    got = solution.solveQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[1, 2, 3, 4], [0, 1, 2, 3]]
    want = [-1, -1, -1, -1]
    got = solution.solveQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[9, 3, 9, 3, 3, 3, 11, 3, 18, 3, 7, 9, 11, 7, 6, 14, 3, 5], [4, 1, 6, 3, 14, 13, 5, 12, 16, 9, 11]]
    want = [1, 2, 6, 1, -1, 3, 1, 6, 3, 2, 7]
    got = solution.solveQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[14, 14, 4, 2, 19, 19, 14, 19, 14], [2, 4, 8, 6, 3]]
    want = [-1, 1, 1, 2, -1]
    got = solution.solveQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[5, 14, 4], [1]]
    want = [-1]
    got = solution.solveQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[34, 95, 189, 158, 77, 51, 16, 58, 118, 189, 162, 110, 16, 42, 1, 118, 189, 71, 1, 189, 189, 11, 158, 6, 48, 93, 16, 95, 30, 93, 126, 93, 14, 154, 93, 14, 39, 170, 166, 162, 148, 163, 7, 42, 14, 64, 111, 163, 189, 1, 173, 124, 77, 42, 187, 98, 13, 189, 78, 77, 63, 167, 58, 42], [19, 21, 27, 46, 30, 56, 1, 5, 53, 34, 38, 59, 44, 57, 63, 39, 49, 14, 48, 33, 47, 3, 35, 62, 9, 58, 13, 15, 37, 22]]
    want = [1, -1, 26, -1, -1, -1, 26, -1, 10, 3, -1, 7, 9, 9, 10, 29, 29, 4, 9, -1, 6, 19, 3, 9, 7, -1, 14, 7, -1, 19]
    got = solution.solveQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[11, 17, 14, 18, 16, 16, 14, 13, 15, 12, 3, 6, 7, 11, 11], [7, 9, 6, 14, 4, 2, 13, 1, 12, 10, 3]]
    want = [-1, -1, 4, 1, 1, 4, 1, -1, -1, -1, -1]
    got = solution.solveQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[18, 7, 7, 7, 18, 7, 18, 18, 7, 7, 2, 17, 7, 4], [2, 3, 1, 6, 12, 9, 5, 13]]
    want = [1, 1, 1, 1, 3, 1, 2, -1]
    got = solution.solveQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[5, 20, 12, 14, 12, 17, 13, 7, 7, 5, 20, 5, 5, 5, 12, 19, 6], [3, 14, 2, 0, 8, 12, 16, 6, 7, 11, 4, 10]]
    want = [-1, 5, 2, 4, 1, 1, -1, -1, 1, 1, 2, 8]
    got = solution.solveQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[3, 3, 19, 9, 7, 14, 3, 16, 18, 20, 5, 3, 18, 3, 9, 19], [3, 10, 4, 1, 5, 0, 14, 8]]
    want = [5, -1, -1, 1, -1, 1, 5, 4]
    got = solution.solveQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[14, 20, 11], [1, 2]]
    want = [-1, -1]
    got = solution.solveQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[6, 12, 17, 9, 16, 7, 6], [5, 6, 0, 4]]
    want = [-1, 1, 1, -1]
    got = solution.solveQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [[8, 12, 12, 8, 12, 8, 12, 3], [5, 4, 7]]
    want = [2, 2, -1]
    got = solution.solveQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [[19, 19, 1, 9], [3]]
    want = [-1]
    got = solution.solveQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [[19, 20, 19, 3, 16, 4, 4, 3, 3, 10, 4, 4, 12, 5, 4], [7, 10, 0, 6, 13, 8, 12, 1, 9]]
    want = [1, 1, 2, 1, -1, 1, -1, -1, -1]
    got = solution.solveQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [[16, 14, 10, 14, 7], [2, 3, 1]]
    want = [-1, 2, 2]
    got = solution.solveQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [[15, 19, 4, 4, 18, 14, 13, 4], [3, 5, 6, 0, 4]]
    want = [1, -1, -1, -1, -1]
    got = solution.solveQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [[82, 70, 5, 180, 146, 62, 46, 6, 86, 125, 6, 123, 46, 99, 6, 36, 57, 199, 86, 186, 103, 7, 119, 57, 86, 113, 62, 98, 99, 99, 51, 185, 93, 146, 82, 146, 48, 86, 125, 86, 138, 195, 105, 142, 199, 36, 92, 60, 86, 14, 8, 125, 91, 37, 36, 48, 163, 185, 180, 70, 93, 6, 105, 199, 61, 98, 188, 64, 113, 36, 88, 134, 171, 86, 156, 164, 6, 125, 122, 199, 91, 163, 156, 14, 88, 196, 94], [65, 75, 16, 4, 31, 62, 58, 15, 60, 47, 41, 84, 72, 39, 52, 20, 9, 42, 26, 50, 37, 32, 36, 56, 71, 49, 23, 7, 76, 48, 64, 66, 46, 81, 35, 27, 57, 51, 54, 74]]
    want = [38, -1, 7, 29, 26, 20, 32, 30, 28, -1, -1, 14, -1, 2, 28, -1, 19, 20, 21, -1, 2, 28, 19, 25, -1, 34, 7, 3, 15, 9, -1, -1, -1, 25, 2, 38, 26, 13, 9, 8]
    got = solution.solveQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [[5, 20, 18, 8, 6, 18, 5, 3, 7, 6, 20], [10, 2, 5, 6, 9, 8, 7]]
    want = [2, 3, 3, 5, 5, -1, -1]
    got = solution.solveQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [[135, 36, 70, 110, 83, 56, 174, 110, 43, 73, 44, 72, 3, 112, 43, 64, 5, 195, 165, 43, 185, 149, 121, 77, 145, 90, 63, 72, 160, 145, 101, 170, 196, 105, 108, 77, 172, 112, 110, 3, 200, 108, 82, 32, 110, 17, 82, 30, 132, 110, 1, 70, 190, 137, 158, 147, 135, 110, 194, 119, 150, 157, 110, 64, 44, 110, 91, 90, 101, 197, 135, 149, 139, 175, 153, 75, 80, 176, 70, 28, 91, 10, 83, 63, 59, 73, 38, 27, 110, 34, 26, 155, 110, 44, 192, 195, 80, 43, 118], [7, 1, 81, 84, 83, 10, 73, 74, 33, 97, 23, 22, 53, 85, 35, 88, 25, 16, 76, 68, 15, 39, 70, 37, 13, 93, 87, 24, 43, 62, 51, 17, 34, 45, 86, 69, 94, 72, 55, 47, 31, 92, 8, 82, 98, 54, 57, 66, 40, 26, 18, 41, 9, 58, 56, 27]]
    want = [4, -1, -1, -1, 42, 16, -1, -1, -1, 10, 12, -1, -1, 23, 12, 4, 42, -1, 20, 38, 48, 27, 14, 24, 24, 16, -1, 5, -1, 3, 27, 21, 7, -1, -1, -1, -1, -1, -1, -1, -1, 4, 6, 21, -1, -1, 5, 14, -1, 42, -1, 7, 23, -1, 14, 16]
    got = solution.solveQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [[2], [0]]
    want = [-1]
    got = solution.solveQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [[17, 16, 5, 16, 16, 3, 19, 11, 16, 14, 16, 14, 1, 6, 12, 16, 15, 19], [17, 4, 14, 9, 8, 0, 7, 5, 13, 11, 6]]
    want = [7, 1, -1, 2, 2, -1, -1, -1, -1, 2, 7]
    got = solution.solveQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [[12, 19, 12, 8, 12, 10], [0, 5, 3, 1]]
    want = [2, -1, -1, -1]
    got = solution.solveQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = [[4, 2, 4, 2, 4, 8, 18, 4, 4, 15, 19, 4, 16, 16, 16, 20, 7, 10, 4], [11, 7, 9, 14, 10, 13, 18, 2, 1, 17]]
    want = [3, 1, -1, 1, -1, 1, 1, 2, 2, -1]
    got = solution.solveQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = [[17, 7, 19, 16, 17, 16, 16, 4, 12, 5, 8, 1, 2, 16, 9, 5, 17, 16, 17, 16], [7, 12, 9, 11, 19, 15, 6, 16]]
    want = [-1, -1, 6, -1, 2, 6, 1, 2]
    got = solution.solveQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = [[4, 6, 15, 2, 11, 16, 6, 4, 6, 15, 15, 4, 20], [6, 8, 9, 11, 3, 5]]
    want = [2, 2, 1, 2, -1, -1]
    got = solution.solveQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

