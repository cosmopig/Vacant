"""Scoring checks for lcb_3344 -- NOT part of any workspace.

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
    args = [[[3, 10], [5, 15], [10, 2], [4, 4]]]
    want = 12
    got = solution.minimumDistance(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[[1, 1], [1, 1], [1, 1]]]
    want = 0
    got = solution.minimumDistance(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[[61, 98], [8, 53], [49, 13], [38, 87], [71, 41], [40, 37], [12, 68], [70, 27], [17, 23], [38, 9]]]
    want = 99
    got = solution.minimumDistance(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[[4946, 4542], [2771, 7201], [112, 2896], [3369, 3051], [8967, 7892], [7408, 4124], [630, 4152], [4107, 9992], [3, 5745], [4447, 334], [5936, 127], [341, 7968], [7264, 2669], [5513, 3969], [7207, 972], [9661, 5847], [2154, 7250], [3568, 1688], [9433, 2354], [2808, 4260], [9467, 8947], [7928, 8692], [8522, 8794], [3524, 3659], [3273, 3925], [4085, 6673], [6190, 9400], [5466, 7590], [3099, 5329], [3352, 8810], [4504, 878], [417, 5292], [7135, 799], [6808, 4926]]]
    want = 14706
    got = solution.minimumDistance(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[[1, 1], [1, 1], [1, 1], [100000000, 100000000], [100000000, 100000000], [100000000, 100000000], [100000000, 100000000], [100000000, 100000000], [100000000, 100000000], [100000000, 100000000]]]
    want = 199999998
    got = solution.minimumDistance(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[[100000000, 100000000], [100000000, 100000000], [100000000, 100000000], [100000000, 100000000], [100000000, 100000000], [100000000, 100000000], [100000000, 100000000], [100000000, 100000000], [100000000, 100000000], [100000000, 100000000]]]
    want = 0
    got = solution.minimumDistance(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[[3, 2], [3, 9], [7, 10], [4, 4], [8, 10], [2, 7]]]
    want = 10
    got = solution.minimumDistance(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[[748, 4393], [7891, 4608], [4653, 1113], [4110, 357], [9261, 6899], [8676, 8389], [9002, 4344], [2428, 9344], [1373, 9201], [9728, 4221], [7159, 7216], [7109, 4941], [3941, 687], [7962, 4698], [8927, 271], [6557, 8765], [1776, 6394], [6063, 1345], [8689, 3896], [8174, 1038], [6218, 5966], [2200, 6718], [2491, 5284], [7853, 1627], [3324, 1562], [2715, 6654], [2734, 2809], [9249, 6738], [2763, 4467], [1730, 149], [4363, 5266], [3972, 584], [456, 7251], [3278, 811], [6142, 6390], [175, 7469], [7, 650], [7630, 1182], [9998, 772], [1926, 8826], [9417, 7491], [3541, 2538], [6308, 9297], [5899, 7535], [2886, 7982]]]
    want = 16484
    got = solution.minimumDistance(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[[0, 2], [0, 1], [0, 0]]]
    want = 1
    got = solution.minimumDistance(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[[3, 16], [95, 88], [25, 70], [30, 77], [10, 79], [66, 48], [74, 37], [92, 15], [50, 44], [30, 34]]]
    want = 146
    got = solution.minimumDistance(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[[1, 1], [1, 1], [1, 1], [1, 1], [1, 1], [1, 1], [1, 1], [1, 1], [1, 1], [1, 1]]]
    want = 0
    got = solution.minimumDistance(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[0, 0]]
    want = 0
    got = solution.minimumDistance(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [[[3, 10], [1300, 1056], [10, 2], [4, 4]]]
    want = 15
    got = solution.minimumDistance(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [[[10, 53], [2, 6], [1000000, 1000000]]]
    want = 55
    got = solution.minimumDistance(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [[[72, 92], [60, 52], [29, 74], [12, 21], [69, 89], [53, 61], [90, 24], [18, 84], [61, 98], [61, 63], [83, 6], [27, 65], [30, 78], [69, 94], [4, 4], [66, 39], [13, 20], [76, 2], [19, 82], [35, 49], [29, 72], [7, 39], [2, 32], [63, 43], [64, 18], [42, 54], [9, 78], [69, 48], [34, 5], [68, 1], [99, 83], [18, 24], [31, 35], [19, 20], [69, 80], [30, 64], [71, 87], [14, 51], [42, 100], [16, 65], [28, 18], [96, 4], [95, 85], [61, 1], [69, 73], [31, 87], [49, 62], [87, 45], [78, 89], [16, 84], [68, 53], [35, 9], [98, 25], [50, 81], [86, 73], [26, 55], [48, 98], [35, 9], [47, 87], [26, 30], [93, 31], [53, 54], [6, 78], [58, 72], [45, 10], [48, 66], [19, 25], [56, 30], [6, 70], [80, 47], [96, 13], [35, 42], [4, 42], [55, 14], [40, 55], [36, 97], [59, 70], [89, 90], [57, 38], [93, 17], [59, 12], [17, 63], [56, 91], [56, 93], [81, 8], [7, 47], [14, 93], [82, 86], [87, 3], [85, 76], [53, 35], [90, 39], [3, 32], [72, 74], [23, 76], [41, 18], [53, 32], [78, 83], [13, 70], [100000000, 100000000]]]
    want = 174
    got = solution.minimumDistance(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [[[564250, 925867], [879387, 922217], [834051, 359430]]]
    want = 318787
    got = solution.minimumDistance(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [[[93, 76], [24, 6], [47, 77], [28, 49], [7, 12], [75, 50], [54, 55]]]
    want = 106
    got = solution.minimumDistance(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [[[33, 30], [62, 12], [10000, 10000]]]
    want = 47
    got = solution.minimumDistance(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

