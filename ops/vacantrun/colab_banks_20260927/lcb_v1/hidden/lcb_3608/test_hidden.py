"""Scoring checks for lcb_3608 -- NOT part of any workspace.

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
    args = [[1, 2, 3, 4]]
    want = 10
    got = solution.subsequencePairCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[10, 20, 30]]
    want = 2
    got = solution.subsequencePairCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[1, 1, 1, 1]]
    want = 50
    got = solution.subsequencePairCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[198, 190, 195, 192, 190, 190, 199, 200, 199, 190, 197, 199, 196, 196, 198, 196, 200, 194, 193, 197, 200, 198, 190, 195, 193, 199, 200, 193, 198, 191, 193, 192, 200, 199, 192, 196, 195, 192, 200, 192, 190, 194, 194, 193, 193, 195, 194, 190, 196, 200, 198, 200, 196, 196, 190, 191, 194, 197, 191, 194, 192, 195, 199, 193, 199, 196, 194, 190, 196, 200]]
    want = 570445224
    got = solution.subsequencePairCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[6]]
    want = 0
    got = solution.subsequencePairCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[200, 100, 25, 3, 200, 100, 25, 3, 200, 100, 25, 3, 200, 100, 25, 3, 200, 100, 25, 3, 200, 100, 25, 3, 200, 100, 25, 3, 200, 100, 25, 3, 200, 100, 25, 3, 200, 100, 25, 3, 200, 100, 25, 3, 200, 100, 25, 3, 200, 100, 25, 3, 200, 100, 25, 3, 200, 100, 25, 3, 200, 100, 25, 3, 200, 100, 25, 3, 200, 100, 25, 3, 200, 100, 25, 3, 200, 100, 25, 3, 200, 100, 25, 3, 200, 100, 25, 3, 200, 100, 25, 3, 200, 100, 25, 3, 200, 100, 25, 3]]
    want = 330553388
    got = solution.subsequencePairCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[23, 28, 22, 27, 22, 27, 20, 23, 27, 30, 30, 22, 24, 24, 20, 25, 27, 22, 27, 21, 29, 23, 23, 27, 26, 28, 27, 20, 28, 21, 22, 27, 24, 28, 20, 24, 21, 20, 29, 24, 22, 20, 24, 27, 30, 29, 21, 25, 22, 22, 27, 24, 22, 29, 22, 25, 25, 23, 25, 24, 26, 21, 28, 25, 26, 20, 24, 27, 27, 23, 20, 24, 23, 21, 24]]
    want = 44197311
    got = solution.subsequencePairCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[7, 2]]
    want = 0
    got = solution.subsequencePairCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[29, 21, 29, 25, 23, 27, 27, 29, 20, 28, 26, 30, 24, 24, 26, 22, 29, 28, 20, 22, 23, 30, 27, 30, 24, 30, 24, 24, 25, 30, 22, 29, 23, 30, 20, 28, 20, 29, 27, 22, 24, 28, 27, 20, 25, 21, 28, 21, 22, 28, 29, 20, 27, 29, 22, 22, 30, 24, 25, 20, 29, 20, 23, 21, 24, 23, 24, 29, 24, 29, 21, 23, 28, 29, 21]]
    want = 770388314
    got = solution.subsequencePairCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[52, 54, 159, 88, 174, 171, 104, 86, 84, 78, 99, 58, 89, 71, 75, 72, 110, 99, 74, 53, 120, 186, 185, 130, 93, 74, 71, 196, 106, 128, 68, 163, 72, 56, 109, 130, 195, 176, 94, 103, 171, 154, 173, 81, 130, 108, 62, 179, 135, 183, 198, 117, 145, 65, 190, 52, 122, 117, 58, 134, 151, 99, 54, 161, 160, 131, 100, 51, 87, 182, 148, 122, 106, 84, 194, 147, 79, 182, 189, 174, 112, 66, 60, 163, 91, 179, 72, 80, 56, 194, 82, 162, 84, 185, 186, 89, 93, 104, 104, 152]]
    want = 379805933
    got = solution.subsequencePairCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[192, 196, 197, 196, 199, 195, 199, 192, 196, 190, 193, 199, 200, 197, 200, 200, 191, 197, 196, 198, 198, 200, 194, 197, 196, 191, 194, 197, 200, 193, 195, 195, 194, 190, 196, 190, 191, 195, 190, 199, 198, 196, 191, 194, 190, 198, 196, 191, 197, 199, 200, 195, 192, 197, 192, 193, 198, 197, 193, 192, 199, 200, 191, 195, 193, 193, 193, 198, 190, 191]]
    want = 551478611
    got = solution.subsequencePairCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[193, 193, 200, 197, 190, 194, 195, 200, 191, 199, 194, 190, 198, 194, 191, 198, 199, 190, 200, 196, 200, 191, 192, 194, 194, 193, 192, 195, 192, 192, 196, 191, 194, 200, 193, 196, 194, 196, 192, 197, 196, 192, 198, 198, 195, 197, 196, 192, 196, 192, 200, 197, 198, 191, 194, 199, 194, 191, 200, 199, 198, 199, 196, 195, 198, 191, 197, 196, 199, 200, 195, 192, 199, 196, 194, 198, 190, 192, 198, 190, 195, 191, 200, 196, 200, 193, 197, 196, 190, 192, 194, 196, 193, 194, 200, 197, 192, 194, 194, 190, 198, 192, 196, 199, 190, 197, 193, 190, 190, 191, 192, 191, 198, 200, 199, 197, 193, 191, 199, 196, 191, 197, 198, 199, 194, 192, 192, 199, 198, 195, 194, 190, 190, 194, 194, 193, 193, 193, 200, 191, 192, 200, 196, 195, 198, 191, 195, 197, 200, 199, 200, 200, 200, 200, 198, 199, 195, 194, 199, 196, 190, 193, 199, 190, 193, 195, 190, 192, 192, 198, 198, 200, 194, 198, 190, 192, 200, 199, 190, 198, 193, 192, 190, 198, 190, 193, 190, 198, 190, 191, 196, 200, 195, 199, 198, 200, 199, 196, 193, 199]]
    want = 868196975
    got = solution.subsequencePairCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [[9]]
    want = 0
    got = solution.subsequencePairCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [[8]]
    want = 0
    got = solution.subsequencePairCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [[3]]
    want = 0
    got = solution.subsequencePairCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [[1, 8]]
    want = 0
    got = solution.subsequencePairCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [[3]]
    want = 0
    got = solution.subsequencePairCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [[2]]
    want = 0
    got = solution.subsequencePairCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [[7]]
    want = 0
    got = solution.subsequencePairCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [[8, 6]]
    want = 0
    got = solution.subsequencePairCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [[9]]
    want = 0
    got = solution.subsequencePairCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [[2]]
    want = 0
    got = solution.subsequencePairCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [[8, 7]]
    want = 0
    got = solution.subsequencePairCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = [[3]]
    want = 0
    got = solution.subsequencePairCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = [[200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100, 200, 100]]
    want = 464663697
    got = solution.subsequencePairCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = [[22, 28, 24, 23, 27, 22, 29, 25, 27, 29, 28, 22, 24, 30, 24, 21, 21, 22, 29, 25, 29, 30, 23, 27, 30, 21, 30, 26, 30, 27, 21, 23, 25, 29, 23, 30, 20, 22, 20, 25, 20, 26, 26, 23, 29, 20, 23, 24, 23, 30, 27, 30, 24, 30, 20, 22, 25, 24, 30, 26]]
    want = 539101128
    got = solution.subsequencePairCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_27():
    args = [[53, 119, 111, 166, 127, 129, 122, 83, 163, 159, 62, 195, 91, 105, 51, 164, 62, 113, 70, 108, 194, 167, 55, 103, 192, 118, 95, 128, 173, 152, 71, 154, 135, 114, 106, 148, 77, 54, 58, 147, 138, 153, 180, 167, 195, 157, 105, 56, 58, 159, 174, 140, 104, 171, 140, 123, 88, 64, 100, 130, 84, 131, 135, 112, 123, 54, 54, 155, 137, 188, 155, 89, 129, 81, 58, 170, 101, 62, 61, 78]]
    want = 236322461
    got = solution.subsequencePairCount(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

