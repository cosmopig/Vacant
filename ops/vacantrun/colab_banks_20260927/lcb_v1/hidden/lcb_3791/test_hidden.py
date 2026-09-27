"""Scoring checks for lcb_3791 -- NOT part of any workspace.

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
    args = [[4, 2, 5], [3, 5, 4]]
    want = 1
    got = solution.numOfUnplacedFruits(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[3, 6, 1], [6, 4, 7]]
    want = 0
    got = solution.numOfUnplacedFruits(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[4], [4]]
    want = 0
    got = solution.numOfUnplacedFruits(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[31], [6]]
    want = 1
    got = solution.numOfUnplacedFruits(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[35, 61], [76, 56]]
    want = 1
    got = solution.numOfUnplacedFruits(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[52], [83]]
    want = 0
    got = solution.numOfUnplacedFruits(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[93], [50]]
    want = 1
    got = solution.numOfUnplacedFruits(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[38, 2], [59, 63]]
    want = 0
    got = solution.numOfUnplacedFruits(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[61], [1]]
    want = 1
    got = solution.numOfUnplacedFruits(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[59, 59], [27, 46]]
    want = 2
    got = solution.numOfUnplacedFruits(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[9], [22]]
    want = 0
    got = solution.numOfUnplacedFruits(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[96, 27], [17, 44]]
    want = 1
    got = solution.numOfUnplacedFruits(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [[63], [19]]
    want = 1
    got = solution.numOfUnplacedFruits(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [[47], [46]]
    want = 1
    got = solution.numOfUnplacedFruits(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [[31], [20]]
    want = 1
    got = solution.numOfUnplacedFruits(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [[41], [49]]
    want = 0
    got = solution.numOfUnplacedFruits(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [[95], [17]]
    want = 1
    got = solution.numOfUnplacedFruits(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [[24, 84], [16, 35]]
    want = 1
    got = solution.numOfUnplacedFruits(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [[98, 63], [67, 85]]
    want = 1
    got = solution.numOfUnplacedFruits(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [[26], [17]]
    want = 1
    got = solution.numOfUnplacedFruits(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [[94], [11]]
    want = 1
    got = solution.numOfUnplacedFruits(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [[93], [11]]
    want = 1
    got = solution.numOfUnplacedFruits(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [[74, 81], [41, 22]]
    want = 2
    got = solution.numOfUnplacedFruits(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = [[85], [9]]
    want = 1
    got = solution.numOfUnplacedFruits(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = [[94], [25]]
    want = 1
    got = solution.numOfUnplacedFruits(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = [[5], [20]]
    want = 0
    got = solution.numOfUnplacedFruits(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

