"""Scoring checks for lcb_3629 -- NOT part of any workspace.

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
    args = ['abcyy', 2]
    want = 7
    got = solution.lengthAfterTransformations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = ['azbk', 1]
    want = 5
    got = solution.lengthAfterTransformations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = ['k', 13]
    want = 1
    got = solution.lengthAfterTransformations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = ['pe', 9]
    want = 2
    got = solution.lengthAfterTransformations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = ['hw', 1]
    want = 2
    got = solution.lengthAfterTransformations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = ['kd', 3]
    want = 2
    got = solution.lengthAfterTransformations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = ['l', 10]
    want = 1
    got = solution.lengthAfterTransformations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = ['h', 14]
    want = 1
    got = solution.lengthAfterTransformations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = ['s', 20]
    want = 2
    got = solution.lengthAfterTransformations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = ['uc', 2]
    want = 2
    got = solution.lengthAfterTransformations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = ['hy', 8]
    want = 3
    got = solution.lengthAfterTransformations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = ['c', 3]
    want = 1
    got = solution.lengthAfterTransformations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = ['v', 7]
    want = 2
    got = solution.lengthAfterTransformations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = ['lj', 7]
    want = 2
    got = solution.lengthAfterTransformations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = ['k', 16]
    want = 2
    got = solution.lengthAfterTransformations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = ['g', 8]
    want = 1
    got = solution.lengthAfterTransformations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = ['l', 6]
    want = 1
    got = solution.lengthAfterTransformations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = ['i', 10]
    want = 1
    got = solution.lengthAfterTransformations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = ['f', 10]
    want = 1
    got = solution.lengthAfterTransformations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = ['e', 7]
    want = 1
    got = solution.lengthAfterTransformations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = ['zz', 7]
    want = 4
    got = solution.lengthAfterTransformations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = ['p', 16]
    want = 2
    got = solution.lengthAfterTransformations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = ['d', 8]
    want = 1
    got = solution.lengthAfterTransformations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = ['v', 7]
    want = 2
    got = solution.lengthAfterTransformations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = ['k', 10]
    want = 1
    got = solution.lengthAfterTransformations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = ['xp', 8]
    want = 3
    got = solution.lengthAfterTransformations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

