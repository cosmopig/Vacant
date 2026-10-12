"""Scoring checks for lcb_3603 -- NOT part of any workspace.

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
    args = [[-1, 0, 0, 1, 1, 2], 'aababa']
    want = [True, True, False, True, True, True]
    got = solution.findAnswer(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[-1, 0, 0, 0, 0], 'aabcb']
    want = [True, True, True, True, True]
    got = solution.findAnswer(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[-1, 5, 1, 5, 2, 0, 7, 0, 5], 'ekkfkibbe']
    want = [False, True, True, True, True, False, True, True, True]
    got = solution.findAnswer(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[-1, 0, 15, 15, 8, 7, 9, 11, 5, 13, 1, 2, 1, 5, 12, 10, 2], 'jehiekkffkceekefb']
    want = [False, False, False, True, True, False, True, False, False, True, False, True, True, True, True, False, True]
    got = solution.findAnswer(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[-1, 17, 9, 17, 17, 0, 9, 19, 19, 16, 6, 18, 11, 15, 16, 8, 0, 9, 9, 6], 'eigiffffhfcbhkcbgjkj']
    want = [False, True, True, True, True, True, False, True, False, False, True, False, True, True, True, False, True, False, False, False]
    got = solution.findAnswer(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[-1, 2, 0, 1], 'bbge']
    want = [False, False, False, True]
    got = solution.findAnswer(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[-1, 7, 7, 4, 7, 7, 2, 0], 'chefeddh']
    want = [False, True, False, True, False, True, True, True]
    got = solution.findAnswer(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[-1, 3, 0, 2], 'cccc']
    want = [True, True, True, True]
    got = solution.findAnswer(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[-1, 3, 3, 0], 'daca']
    want = [False, True, True, True]
    got = solution.findAnswer(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[-1, 0, 0], 'gii']
    want = [False, True, True]
    got = solution.findAnswer(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[-1, 4, 4, 1, 0, 2, 4], 'bfgiigf']
    want = [False, False, True, True, True, True, True]
    got = solution.findAnswer(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[-1, 0, 0, 2, 3, 3], 'ggicic']
    want = [True, True, True, False, True, True]
    got = solution.findAnswer(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [[-1], 'd']
    want = [True]
    got = solution.findAnswer(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [[-1, 0], 'ii']
    want = [True, True]
    got = solution.findAnswer(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [[-1, 0], 'ee']
    want = [True, True]
    got = solution.findAnswer(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [[-1, 3, 5, 5, 5, 0, 5], 'fafcaac']
    want = [True, True, True, False, True, False, True]
    got = solution.findAnswer(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [[-1, 4, 4, 9, 0, 9, 5, 5, 2, 2, 2], 'jjjehhhcced']
    want = [False, True, False, True, False, True, True, True, True, True, True]
    got = solution.findAnswer(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [[-1, 9, 3, 0, 0, 0, 0, 5, 13, 3, 2, 2, 3, 9], 'bgbhkjbcdjkcia']
    want = [False, True, False, False, True, False, True, True, True, False, True, True, True, False]
    got = solution.findAnswer(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [[-1, 4, 0, 5, 0, 7, 7, 1], 'fdekcaak']
    want = [False, False, True, True, False, False, True, True]
    got = solution.findAnswer(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [[-1, 0, 8, 0, 8, 2, 5, 10, 11, 5, 2, 3, 1], 'deceeecceejcd']
    want = [True, False, False, False, True, False, True, True, False, True, False, True, True]
    got = solution.findAnswer(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [[-1, 6, 10, 17, 14, 4, 0, 2, 13, 14, 15, 16, 11, 6, 2, 1, 15, 1, 4], 'kbkfbhaahggaahfkggh']
    want = [False, False, False, True, False, True, True, True, True, True, False, True, True, True, False, False, False, False, True]
    got = solution.findAnswer(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [[-1, 0, 1, 2], 'ijji']
    want = [True, False, False, True]
    got = solution.findAnswer(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [[-1, 3, 1, 0, 3], 'hehea']
    want = [True, False, True, False, True]
    got = solution.findAnswer(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = [[-1, 4, 3, 4, 5, 0, 4], 'ijcdjhc']
    want = [False, True, True, False, True, False, True]
    got = solution.findAnswer(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = [[-1, 0], 'ce']
    want = [False, True]
    got = solution.findAnswer(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = [[-1, 3, 0, 2, 9, 7, 1, 2, 7, 12, 0, 7, 7, 12], 'ikakdbhhgdbceb']
    want = [False, False, False, False, True, True, True, False, True, True, True, True, False, True]
    got = solution.findAnswer(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

