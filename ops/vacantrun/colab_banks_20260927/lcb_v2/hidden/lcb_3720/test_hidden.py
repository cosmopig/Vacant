"""Scoring checks for lcb_3720 -- NOT part of any workspace.

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
    args = [5, [[1, 0, 1], [2, 0, 2], [3, 0, 1], [4, 3, 1], [2, 1, 1]], 2]
    want = 1
    got = solution.minMaxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [5, [[0, 1, 1], [0, 2, 2], [0, 3, 1], [0, 4, 1], [1, 2, 1], [1, 4, 1]], 1]
    want = -1
    got = solution.minMaxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [5, [[1, 2, 1], [1, 3, 3], [1, 4, 5], [2, 3, 2], [3, 4, 2], [4, 0, 1]], 1]
    want = 2
    got = solution.minMaxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [5, [[1, 2, 1], [1, 3, 3], [1, 4, 5], [2, 3, 2], [4, 0, 1]], 1]
    want = -1
    got = solution.minMaxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [3, [[2, 1, 21], [0, 2, 71]], 1]
    want = -1
    got = solution.minMaxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [3, [[0, 1, 34], [2, 0, 88], [1, 2, 9]], 1]
    want = 88
    got = solution.minMaxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [3, [[1, 0, 58], [1, 2, 36], [0, 2, 13]], 1]
    want = -1
    got = solution.minMaxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [3, [[0, 1, 26], [1, 0, 35], [1, 2, 94]], 2]
    want = -1
    got = solution.minMaxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [3, [[1, 2, 42], [1, 2, 8]], 1]
    want = -1
    got = solution.minMaxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [2, [[0, 1, 12]], 1]
    want = -1
    got = solution.minMaxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [3, [[2, 1, 45], [2, 0, 14], [1, 2, 20]], 2]
    want = 20
    got = solution.minMaxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [3, [[2, 0, 79], [1, 2, 80], [1, 2, 54]], 1]
    want = 79
    got = solution.minMaxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [3, [[0, 1, 17], [2, 0, 38]], 1]
    want = -1
    got = solution.minMaxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [3, [[1, 2, 21], [0, 2, 84], [0, 1, 41]], 2]
    want = -1
    got = solution.minMaxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [2, [[1, 0, 94]], 1]
    want = 94
    got = solution.minMaxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [3, [[1, 0, 66], [0, 1, 39]], 2]
    want = -1
    got = solution.minMaxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [3, [[1, 2, 51], [2, 1, 61]], 1]
    want = -1
    got = solution.minMaxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [3, [[2, 0, 75], [1, 0, 69], [1, 0, 97]], 1]
    want = 75
    got = solution.minMaxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [3, [[0, 2, 70], [2, 0, 11], [0, 1, 50]], 2]
    want = -1
    got = solution.minMaxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [3, [[0, 2, 16], [1, 0, 25]], 1]
    want = -1
    got = solution.minMaxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [3, [[2, 0, 27], [2, 0, 17], [0, 2, 60]], 2]
    want = -1
    got = solution.minMaxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [2, [[1, 0, 4]], 1]
    want = 4
    got = solution.minMaxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [3, [[2, 0, 83], [1, 0, 22], [0, 1, 64]], 1]
    want = 83
    got = solution.minMaxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = [3, [[0, 2, 24], [2, 1, 2], [0, 2, 93]], 2]
    want = -1
    got = solution.minMaxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = [3, [[2, 0, 98], [0, 2, 12], [2, 0, 65]], 2]
    want = -1
    got = solution.minMaxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = [2, [[1, 0, 8]], 1]
    want = 8
    got = solution.minMaxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_27():
    args = [3, [[0, 2, 86], [1, 2, 29]], 1]
    want = -1
    got = solution.minMaxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_28():
    args = [2, [[1, 0, 22]], 1]
    want = 22
    got = solution.minMaxWeight(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

