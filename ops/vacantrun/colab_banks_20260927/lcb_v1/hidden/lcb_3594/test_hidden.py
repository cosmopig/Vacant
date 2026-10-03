"""Scoring checks for lcb_3594 -- NOT part of any workspace.

⚠ 計分用的 GT。住在 hidden/ 這棵**另外的樹**，永遠不複製進 agent 的工作區；
  任何把它的內容（含失敗訊息）回饋給模型的路徑都作廢那一批資料。

case 組成 ＝ 題庫的 `visible_tests` ＋ `hidden_tests`（超集），與
vacant_network/codebench.py::LiveCodeBenchLoader 的 `hidden_check` 同一組（ops/gain/data/lcb_bank_v1.jsonl）。
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
    args = [[2, 3, 5, 10]]
    want = 10
    got = solution.getLargestOutlier(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[-2, -1, -3, -6, 4]]
    want = 4
    got = solution.getLargestOutlier(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[1, 1, 1, 1, 1, 5, 5]]
    want = 5
    got = solution.getLargestOutlier(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[-632, -523, -632]]
    want = -523
    got = solution.getLargestOutlier(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[-375, 799, 799]]
    want = -375
    got = solution.getLargestOutlier(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[-665, 642, 642]]
    want = -665
    got = solution.getLargestOutlier(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[-768, 49, -768]]
    want = 49
    got = solution.getLargestOutlier(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[-737, 630, -737]]
    want = 630
    got = solution.getLargestOutlier(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[-495, -787, -495]]
    want = -787
    got = solution.getLargestOutlier(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[427, 427, 271]]
    want = 271
    got = solution.getLargestOutlier(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[166, -854, 166]]
    want = -854
    got = solution.getLargestOutlier(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[524, 524, 87]]
    want = 87
    got = solution.getLargestOutlier(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [[963, -626, 963]]
    want = -626
    got = solution.getLargestOutlier(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [[-489, -489, -658]]
    want = -658
    got = solution.getLargestOutlier(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [[-335, 319, -335]]
    want = 319
    got = solution.getLargestOutlier(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [[485, 269, 485]]
    want = 269
    got = solution.getLargestOutlier(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [[134, -188, -188]]
    want = 134
    got = solution.getLargestOutlier(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [[910, 399, 399]]
    want = 910
    got = solution.getLargestOutlier(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [[-708, -708, 286]]
    want = 286
    got = solution.getLargestOutlier(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [[-625, -711, -711]]
    want = -625
    got = solution.getLargestOutlier(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [[895, -536, 895]]
    want = -536
    got = solution.getLargestOutlier(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [[-656, -386, -656]]
    want = -386
    got = solution.getLargestOutlier(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [[-85, -85, 828]]
    want = 828
    got = solution.getLargestOutlier(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = [[570, -461, -461]]
    want = 570
    got = solution.getLargestOutlier(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = [[-310, -702, -702]]
    want = -310
    got = solution.getLargestOutlier(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = [[-683, -683, -689]]
    want = -689
    got = solution.getLargestOutlier(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_27():
    args = [[-463, -600, -463]]
    want = -600
    got = solution.getLargestOutlier(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

