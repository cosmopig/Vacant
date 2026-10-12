"""Scoring checks for lcb_2921 -- NOT part of any workspace.

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
    args = ['1', '11']
    want = 10
    got = solution.countSteppingNumbers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = ['90', '101']
    want = 2
    got = solution.countSteppingNumbers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = ['4', '9']
    want = 6
    got = solution.countSteppingNumbers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = ['3', '84']
    want = 21
    got = solution.countSteppingNumbers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = ['1', '66']
    want = 20
    got = solution.countSteppingNumbers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = ['45', '66']
    want = 4
    got = solution.countSteppingNumbers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = ['4', '50']
    want = 14
    got = solution.countSteppingNumbers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = ['9', '68']
    want = 13
    got = solution.countSteppingNumbers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = ['12', '89']
    want = 15
    got = solution.countSteppingNumbers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = ['9888878', '9899998']
    want = 6
    got = solution.countSteppingNumbers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = ['303628', '786017178']
    want = 2704
    got = solution.countSteppingNumbers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = ['31384570389283431', '73857241289720257']
    want = 162182
    got = solution.countSteppingNumbers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = ['399209151314805334158', '863865742870965104736']
    want = 2115150
    got = solution.countSteppingNumbers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = ['1203109284118568358408114942744154309516373371543388344493782743693904745519867118487579839270928580', '6121833782106632749517843393634569515258465712511663330500608285264190592002792370635436513179865625']
    want = 729890404
    got = solution.countSteppingNumbers(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

