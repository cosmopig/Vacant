"""Scoring checks for lcb_3682 -- NOT part of any workspace.

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
    args = [3, 2, 1]
    want = 4
    got = solution.countGoodArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [4, 2, 2]
    want = 6
    got = solution.countGoodArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [5, 2, 0]
    want = 2
    got = solution.countGoodArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [1, 3, 0]
    want = 3
    got = solution.countGoodArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [1, 6, 0]
    want = 6
    got = solution.countGoodArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [100000, 100000, 99999]
    want = 100000
    got = solution.countGoodArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [2, 3, 0]
    want = 6
    got = solution.countGoodArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [2, 5, 1]
    want = 5
    got = solution.countGoodArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [2, 7, 1]
    want = 7
    got = solution.countGoodArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [63702, 32885, 23508]
    want = 29257828
    got = solution.countGoodArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [75572, 54634, 46860]
    want = 711519345
    got = solution.countGoodArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [80289, 90610, 6312]
    want = 549624789
    got = solution.countGoodArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [100000, 100000, 99998]
    want = 993100147
    got = solution.countGoodArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [9545, 63836, 5166]
    want = 979111842
    got = solution.countGoodArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [2, 2, 0]
    want = 2
    got = solution.countGoodArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [1, 8, 0]
    want = 8
    got = solution.countGoodArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [90676, 73860, 88831]
    want = 176039447
    got = solution.countGoodArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [2, 9, 0]
    want = 72
    got = solution.countGoodArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [2, 2, 1]
    want = 2
    got = solution.countGoodArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [2, 5, 0]
    want = 20
    got = solution.countGoodArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [2, 7, 0]
    want = 42
    got = solution.countGoodArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [2, 4, 0]
    want = 12
    got = solution.countGoodArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [1, 9, 0]
    want = 9
    got = solution.countGoodArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = [2, 6, 1]
    want = 6
    got = solution.countGoodArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = [56262, 25872, 17159]
    want = 302306442
    got = solution.countGoodArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = [2, 1, 0]
    want = 0
    got = solution.countGoodArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_27():
    args = [1, 7, 0]
    want = 7
    got = solution.countGoodArrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

