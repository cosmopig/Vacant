"""Scoring checks for lcb_3494 -- NOT part of any workspace.

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
    args = [3, 2, [1, 3], [5]]
    want = 13
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [2, 2, [7], [4]]
    want = 15
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [10, 10, [420, 1, 597, 1, 905, 1, 261, 1, 681], [101, 1, 333, 1, 502, 1, 409, 1, 787]]
    want = 13988
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [6, 2, [1, 3, 2, 3, 1], [1]]
    want = 16
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [17, 18, [781, 307, 573, 596, 536, 761, 591, 848, 858, 302, 652, 540, 770, 607, 809, 322], [841, 828, 682, 480, 391, 915, 948, 736, 933, 705, 909, 717, 881, 954, 807, 297, 696]]
    want = 175365
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [10, 20, [543, 1, 831, 1, 737, 1, 241, 1, 471], [69, 1, 130, 1, 259, 1, 701, 1, 324, 1, 840, 1, 265, 1, 609, 1, 299, 1, 779]]
    want = 24503
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [5, 3, [1, 1, 1, 1], [1, 1]]
    want = 14
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [7, 7, [16, 8, 1, 10, 13, 3], [18, 2, 3, 12, 12, 15]]
    want = 333
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [9, 8, [7, 7, 4, 3, 1, 2, 3, 5], [2, 3, 1, 1, 2, 2, 1]]
    want = 134
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [2, 2, [215], [215]]
    want = 645
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [10, 20, [939, 911, 880, 751, 716, 621, 618, 328, 98], [990, 967, 926, 817, 785, 721, 655, 653, 544, 350, 278, 248, 234, 206, 148, 138, 61, 52, 32]]
    want = 77464
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [20, 20, [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1], [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]]
    want = 399
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [8, 2, [2, 4, 3, 3, 5, 1, 1], [5]]
    want = 43
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [2, 2, [832], [918]]
    want = 2582
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [1, 7, [], [1, 2, 1, 1, 2, 1]]
    want = 8
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [20, 20, [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1], [1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000]]
    want = 19380
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [1, 20, [], [1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000]]
    want = 19000
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [5, 6, [3, 3, 3, 3], [5, 3, 5, 5, 1]]
    want = 83
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [20, 20, [794, 744, 448, 293, 101, 197, 955, 51, 749, 485, 52, 511, 981, 101, 283, 149, 44, 636, 947], [413, 746, 603, 720, 636, 193, 67, 928, 520, 575, 323, 838, 10, 619, 344, 810, 901, 181, 743]]
    want = 131105
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [5, 5, [527, 527, 527, 527], [527, 527, 527, 527]]
    want = 12648
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [20, 20, [812, 1, 974, 1, 871, 1, 117, 1, 453, 1, 199, 1, 719, 1, 596, 1, 408, 1, 263], [94, 1, 523, 1, 261, 1, 271, 1, 547, 1, 614, 1, 878, 1, 522, 1, 749, 1, 989]]
    want = 49461
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [20, 1, [1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000], []]
    want = 19000
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [10, 20, [1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000], [1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000]]
    want = 199000
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = [20, 20, [537, 294, 694, 235, 534, 607, 413, 356, 888, 924, 425, 91, 243, 136, 260, 941, 443, 649, 685], [239, 749, 577, 940, 809, 562, 366, 824, 877, 714, 578, 698, 785, 206, 999, 199, 76, 642, 453]]
    want = 160334
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = [3, 4, [21, 54], [99, 4, 96]]
    want = 432
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = [7, 8, [100, 262, 33, 273, 422, 318], [204, 107, 56, 189, 129, 95, 46]]
    want = 6366
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

