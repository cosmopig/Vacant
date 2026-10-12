"""Scoring checks for lcb_3495 -- NOT part of any workspace.

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
    args = [[[1, 2], [3, 4], [2, 3], [-3, 0]], 2]
    want = [-1, 7, 5, 3]
    got = solution.resultsArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[[5, 5], [4, 4], [3, 3]], 1]
    want = [10, 8, 6]
    got = solution.resultsArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[[6, 10], [0, -10], [2, -6]], 2]
    want = [-1, 16, 10]
    got = solution.resultsArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[[1, 4], [9, 2]], 3]
    want = [-1, -1]
    got = solution.resultsArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[[10, -3]], 8]
    want = [-1]
    got = solution.resultsArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[[0, 0], [1, 0], [1, -1], [1, -2], [1, -3], [1, -4], [1, -5], [1, -6], [1, -7], [1, -8]], 10]
    want = [-1, -1, -1, -1, -1, -1, -1, -1, -1, 9]
    got = solution.resultsArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[[7, 7], [-9, 4]], 2]
    want = [-1, 14]
    got = solution.resultsArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[[4, 6], [2, 4]], 3]
    want = [-1, -1]
    got = solution.resultsArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[[-9, -5], [0, 4], [-10, 5], [-6, 9], [-4, 8]], 5]
    want = [-1, -1, -1, -1, 15]
    got = solution.resultsArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[[-8, -8], [-1, -3], [-9, 3], [9, 4], [6, -8]], 9]
    want = [-1, -1, -1, -1, -1]
    got = solution.resultsArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[[-2, 4], [-8, 2], [5, -8]], 10]
    want = [-1, -1, -1]
    got = solution.resultsArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[[0, -4], [-8, 8], [-2, 7]], 12]
    want = [-1, -1, -1]
    got = solution.resultsArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [[[2, 4]], 1]
    want = [6]
    got = solution.resultsArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [[[6, -6], [2, 6]], 8]
    want = [-1, -1]
    got = solution.resultsArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [[[7, -1], [-5, 10], [-1, 6]], 5]
    want = [-1, -1, -1]
    got = solution.resultsArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [[[-7, -8], [-3, -10], [2, -9], [-7, -1], [1, -9]], 6]
    want = [-1, -1, -1, -1, -1]
    got = solution.resultsArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [[[-7, -1]], 3]
    want = [-1]
    got = solution.resultsArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [[[-655058479, -526499115], [-175413349, -311101210], [-799335796, 540876557], [-549060257, -987390254], [60507381, 987160166], [-144773285, -964632696], [-34721762, -977967584], [-961357470, 656339033], [-996703854, 462027213], [-570982073, 14531457]], 1]
    want = [1181557594, 486514559, 486514559, 486514559, 486514559, 486514559, 486514559, 486514559, 486514559, 486514559]
    got = solution.resultsArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [[[92, -77], [21, -62], [-60, -40], [-100, 56], [-98, -37], [-29, 30]], 1]
    want = [169, 83, 83, 83, 83, 59]
    got = solution.resultsArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [[[-10, -5], [0, 4], [0, -3], [-7, -3], [0, -5]], 5]
    want = [-1, -1, -1, -1, 15]
    got = solution.resultsArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [[[-739635989, 828679767]], 1]
    want = [1568315756]
    got = solution.resultsArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [[[-7, 0], [2, 4], [-8, 2], [0, -6], [5, -3]], 12]
    want = [-1, -1, -1, -1, -1]
    got = solution.resultsArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [[[-7, 2], [-1, -3]], 10]
    want = [-1, -1]
    got = solution.resultsArray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

