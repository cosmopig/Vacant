"""Scoring checks for lcb_3485 -- NOT part of any workspace.

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
    args = [[6, 0, 3], 2]
    want = 4
    got = solution.maxPossibleScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[2, 6, 13, 13], 5]
    want = 5
    got = solution.maxPossibleScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[4, 4, 2, 7, 10], 5]
    want = 3
    got = solution.maxPossibleScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[3, 10, 6, 10, 2], 4]
    want = 3
    got = solution.maxPossibleScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[4, 10, 8], 10]
    want = 8
    got = solution.maxPossibleScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[5, 10], 10]
    want = 15
    got = solution.maxPossibleScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[1, 5, 10], 8]
    want = 8
    got = solution.maxPossibleScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[0, 9, 2, 9], 2]
    want = 2
    got = solution.maxPossibleScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[1, 1, 0, 0, 1, 0, 0, 1, 1, 1, 0, 0, 0, 1, 0, 1, 0, 0, 1, 0, 0, 1, 0, 1, 0, 1, 1, 1, 0, 0, 1, 1, 0, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 1, 1, 1, 0, 1, 1, 1, 0, 0, 0, 0, 0, 1, 0, 1, 1, 0, 0, 1, 1, 0, 0, 0, 1, 1, 0, 0, 1, 0, 1, 1, 1, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 1, 0, 1, 1, 0, 0, 1, 1, 0, 0, 0, 0], 1]
    want = 0
    got = solution.maxPossibleScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[1000000, 999990, 999980, 999970, 999960, 999950, 999940, 999930, 999920, 999910], 10]
    want = 11
    got = solution.maxPossibleScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[1000000000, 1000, 0], 1000]
    want = 2000
    got = solution.maxPossibleScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[7, 0, 10, 5, 0, 10, 7, 4, 6, 8, 10, 10, 5, 8, 8, 6, 9, 8, 8, 5, 5, 8, 0, 10, 9, 3, 2, 7, 1, 4, 4, 9, 6, 7, 8, 4, 2, 7, 5, 7, 8, 4, 3, 1, 4, 0, 9, 3, 10, 9, 6, 2, 8, 1, 6, 8, 0, 5, 3, 2, 5, 7, 7, 10, 4, 8, 7, 10, 10, 9, 3, 6, 9, 7, 1, 9, 10, 0, 0, 0, 3, 4, 0, 0, 7, 6, 10, 10, 10, 1, 4, 4, 9, 7, 0, 5, 4, 4, 7, 0], 10]
    want = 0
    got = solution.maxPossibleScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [[2, 0, 0, 8], 2]
    want = 2
    got = solution.maxPossibleScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [[1000000000, 0], 1000000000]
    want = 2000000000
    got = solution.maxPossibleScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [[0, 1000000000, 500000000], 1000]
    want = 500000500
    got = solution.maxPossibleScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [[1000000000, 1000000000], 1000000000]
    want = 1000000000
    got = solution.maxPossibleScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [[4, 6], 6]
    want = 8
    got = solution.maxPossibleScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [[89, 522], 0]
    want = 433
    got = solution.maxPossibleScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [[0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 170, 180, 190, 200, 210, 220, 230, 240, 250, 260, 270, 280, 290, 300, 310, 320, 330, 340, 350, 360, 370, 380, 390, 400, 410, 420, 430, 440, 450, 460, 470, 480, 490, 500, 510, 520, 530, 540, 550, 560, 570, 580, 590, 600, 610, 620, 630, 640, 650, 660, 670, 680, 690, 700, 710, 720, 730, 740, 750, 760, 770, 780, 790, 800, 810, 820, 830, 840, 850, 860, 870, 880, 890, 900, 910, 920, 930, 940, 950, 960, 970, 980, 990], 1000000000]
    want = 10101020
    got = solution.maxPossibleScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [[21, 71], 100]
    want = 150
    got = solution.maxPossibleScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [[3769, 644712], 1000000000]
    want = 1000640943
    got = solution.maxPossibleScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [[10, 7, 5, 0], 0]
    want = 2
    got = solution.maxPossibleScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [[10, 10, 6], 4]
    want = 4
    got = solution.maxPossibleScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = [[1, 8, 2, 2], 10]
    want = 5
    got = solution.maxPossibleScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = [[1, 1, 3, 4, 5, 8, 8, 10, 10, 10], 1000000000]
    want = 111111112
    got = solution.maxPossibleScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = [[3, 2, 9, 2, 0], 3]
    want = 2
    got = solution.maxPossibleScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

