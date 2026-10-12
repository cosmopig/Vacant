"""Scoring checks for lcb_3507 -- NOT part of any workspace.

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
    args = [5, 7]
    want = 3
    got = solution.nonSpecialCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [4, 16]
    want = 11
    got = solution.nonSpecialCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [2, 3]
    want = 2
    got = solution.nonSpecialCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [91, 95]
    want = 5
    got = solution.nonSpecialCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [529, 529]
    want = 0
    got = solution.nonSpecialCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [55, 65]
    want = 11
    got = solution.nonSpecialCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [4, 851]
    want = 838
    got = solution.nonSpecialCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [1, 1000000000]
    want = 999996599
    got = solution.nonSpecialCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [2, 5]
    want = 3
    got = solution.nonSpecialCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [717419405, 907173109]
    want = 189753386
    got = solution.nonSpecialCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [382041195, 382041769]
    want = 575
    got = solution.nonSpecialCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [1, 14]
    want = 12
    got = solution.nonSpecialCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [3, 4]
    want = 1
    got = solution.nonSpecialCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [1, 2]
    want = 2
    got = solution.nonSpecialCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [48, 50]
    want = 2
    got = solution.nonSpecialCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [528, 530]
    want = 2
    got = solution.nonSpecialCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [131022348, 131022348]
    want = 1
    got = solution.nonSpecialCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [804928157, 804936576]
    want = 8420
    got = solution.nonSpecialCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [1000000000, 1000000000]
    want = 1
    got = solution.nonSpecialCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [811402, 814647]
    want = 3246
    got = solution.nonSpecialCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [884278897, 905459878]
    want = 21180953
    got = solution.nonSpecialCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [1, 8]
    want = 7
    got = solution.nonSpecialCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [14110767, 551533749]
    want = 537420893
    got = solution.nonSpecialCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = [1, 12]
    want = 10
    got = solution.nonSpecialCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = [88, 173]
    want = 84
    got = solution.nonSpecialCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = [2, 4]
    want = 2
    got = solution.nonSpecialCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

