"""Scoring checks for lcb_3243 -- NOT part of any workspace.

⚠ 計分用的 GT。住在 hidden/ 這棵**另外的樹**，永遠不複製進 agent 的工作區；
  任何把它的內容（含失敗訊息）回饋給模型的路徑都作廢那一批資料。

case 組成 ＝ 題庫的 `visible_tests` ＋ `hidden_tests`（超集），與
vacant_network/codebench.py::LiveCodeBenchLoader 的 `hidden_check` 同一組（ops/gain/data/lcb_bank_v3.jsonl）。
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
    args = [1, 6000, 4, '124']
    want = 5
    got = solution.numberOfPowerfulInt(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [15, 215, 6, '10']
    want = 2
    got = solution.numberOfPowerfulInt(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [1000, 2000, 4, '3000']
    want = 0
    got = solution.numberOfPowerfulInt(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [36, 275, 9, '9']
    want = 24
    got = solution.numberOfPowerfulInt(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [20, 623, 4, '1']
    want = 23
    got = solution.numberOfPowerfulInt(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [47, 388, 2, '11']
    want = 2
    got = solution.numberOfPowerfulInt(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [81, 861, 3, '30']
    want = 3
    got = solution.numberOfPowerfulInt(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [92, 914, 6, '41']
    want = 6
    got = solution.numberOfPowerfulInt(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [9251, 82480, 9, '49']
    want = 732
    got = solution.numberOfPowerfulInt(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [8778, 99924, 7, '53032']
    want = 1
    got = solution.numberOfPowerfulInt(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [9768663, 63434076, 1, '111111']
    want = 2
    got = solution.numberOfPowerfulInt(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [2946568, 67236501, 6, '403']
    want = 15778
    got = solution.numberOfPowerfulInt(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [7244775770970, 58490828595615, 6, '2060']
    want = 201768035
    got = solution.numberOfPowerfulInt(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [408142522598107, 532089352496953, 3, '121220233212332']
    want = 0
    got = solution.numberOfPowerfulInt(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [900407863935940, 961459078569857, 9, '581747672523731']
    want = 0
    got = solution.numberOfPowerfulInt(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

