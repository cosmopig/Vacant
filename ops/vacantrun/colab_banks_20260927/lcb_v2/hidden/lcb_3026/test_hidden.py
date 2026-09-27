"""Scoring checks for lcb_3026 -- NOT part of any workspace.

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
    args = [2, 3]
    want = 4
    got = solution.minimumPossibleSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [3, 3]
    want = 8
    got = solution.minimumPossibleSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [1, 1]
    want = 1
    got = solution.minimumPossibleSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [43, 3]
    want = 988
    got = solution.minimumPossibleSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [544, 838]
    want = 200490
    got = solution.minimumPossibleSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [19, 32]
    want = 235
    got = solution.minimumPossibleSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [39636, 49035]
    want = 156198582
    got = solution.minimumPossibleSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [39636, 49035]
    want = 156198582
    got = solution.minimumPossibleSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [27, 17]
    want = 530
    got = solution.minimumPossibleSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [28, 43]
    want = 553
    got = solution.minimumPossibleSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [39636, 49035]
    want = 156198582
    got = solution.minimumPossibleSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [16, 6]
    want = 162
    got = solution.minimumPossibleSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [41, 14]
    want = 1065
    got = solution.minimumPossibleSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [19, 47]
    want = 190
    got = solution.minimumPossibleSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [2, 1]
    want = 3
    got = solution.minimumPossibleSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [67, 402]
    want = 2278
    got = solution.minimumPossibleSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [46, 14]
    want = 1315
    got = solution.minimumPossibleSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [39636, 49035]
    want = 156198582
    got = solution.minimumPossibleSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [39636, 49035]
    want = 156198582
    got = solution.minimumPossibleSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [40, 8]
    want = 928
    got = solution.minimumPossibleSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [31, 20]
    want = 685
    got = solution.minimumPossibleSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [39636, 49035]
    want = 156198582
    got = solution.minimumPossibleSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [516, 452]
    want = 198636
    got = solution.minimumPossibleSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = [43, 23]
    want = 1298
    got = solution.minimumPossibleSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = [15, 29]
    want = 134
    got = solution.minimumPossibleSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = [17, 13]
    want = 219
    got = solution.minimumPossibleSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_27():
    args = [29, 33]
    want = 643
    got = solution.minimumPossibleSum(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

