"""Scoring checks for lcb_2893 -- NOT part of any workspace.

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
    args = [[2, 3, 6, 1, 9, 2], 5]
    want = 13
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[2, 4, 6, 8], 3]
    want = 20
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[73, 92], 33]
    want = 132
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[85, 69, 63], 18]
    want = 217
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[54, 40, 31, 84], 9]
    want = 191
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[61, 46, 95, 85], 72]
    want = 241
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[79, 93, 29, 36], 21]
    want = 216
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[73, 33, 63, 70], 80]
    want = 169
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[54, 29, 97, 100], 79]
    want = 154
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[70, 58, 2, 92, 7, 93], 100]
    want = 222
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[857353, 96331, 386391, 816108, 827248, 428468, 326035, 710726, 505362, 133522, 267602, 475509, 47092, 392831, 983512, 944163, 904138, 389574, 197368, 548854, 759879, 922519, 598297, 190737, 659402, 872800, 151323, 202933, 636470, 330438, 202733, 125334, 854430, 504788, 943883, 362899, 942526, 497646, 224971, 807779, 630920, 629114, 860704, 890439, 777278, 853899, 857599, 929178, 744640, 611907, 33832, 468958, 953488, 369232, 851815, 961138, 800550, 686409, 64120, 468717, 623784, 232299, 295631, 839343, 644555, 844983, 897515, 923078, 495239, 113047, 916261, 931954, 947328, 290798, 448538, 908366, 643414, 670226, 333254, 514960, 185901, 747548, 699623, 519039, 848260, 27116, 372050, 514714, 787587, 813961, 851464, 151183, 972384, 628991, 895869, 763947, 312563, 347491, 69376, 87021], 1]
    want = 57584526
    got = solution.maxScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

