"""Scoring checks for lcb_3000 -- NOT part of any workspace.

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
    args = [[4, 3, 2, 4], 2]
    want = 0
    got = solution.minAbsoluteDifference(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[5, 3, 2, 10, 15], 1]
    want = 1
    got = solution.minAbsoluteDifference(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[1, 2, 3, 4], 3]
    want = 3
    got = solution.minAbsoluteDifference(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[2], 0]
    want = 0
    got = solution.minAbsoluteDifference(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[4, 30], 1]
    want = 26
    got = solution.minAbsoluteDifference(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[9, 6, 10, 6, 3, 2, 9, 9, 8, 6], 9]
    want = 3
    got = solution.minAbsoluteDifference(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[64, 64, 79, 45, 97, 80, 7, 31, 64], 6]
    want = 0
    got = solution.minAbsoluteDifference(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[6, 3, 31, 96, 94, 85, 84, 48, 71, 65], 0]
    want = 0
    got = solution.minAbsoluteDifference(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[56, 22, 85, 65, 100, 9, 1, 30, 59, 25], 1]
    want = 3
    got = solution.minAbsoluteDifference(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[474, 496, 674, 942, 25, 782, 221, 27, 38, 558], 1]
    want = 2
    got = solution.minAbsoluteDifference(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[1394, 9416, 7827, 471, 7459, 2601, 3042, 896, 5381, 9946, 2082, 6694, 893, 9903, 9960, 473, 1654, 9753, 9029, 3665, 2196, 1954, 8097, 111, 1672, 8211, 5431, 9955, 3984, 3862, 3417, 378, 6625, 6475, 663, 5392, 1982, 1395, 9960, 8294, 7702, 367, 9418, 6554, 1042, 6387, 1961, 3907, 1798, 456, 4797, 3285, 4861, 9595, 3200, 213, 3501, 7539, 7378, 2111, 5646, 4655, 2287, 6194, 6097, 8683, 9603, 6920, 2705, 5782, 8017, 1122, 289, 7761, 9377, 2644, 8983, 5027, 3875, 6047, 5188, 2416, 1699, 7217, 6285, 7301, 2497, 7117, 8589, 4706, 4899, 8989, 3388, 567, 7423, 9589, 5316, 3080, 6412, 6966], 1]
    want = 0
    got = solution.minAbsoluteDifference(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[72279, 90421, 91174, 98371, 96379, 39130, 28714, 21781, 98259, 87071, 40356, 65104, 67569, 98317, 9403, 8178, 53142, 99366, 1221, 45053, 9504, 735, 20032, 28575, 61875, 13342, 67023, 3354, 24807, 62907, 45768, 1318, 9192, 31204, 80120, 61353, 87946, 69340, 16611, 74906, 74865, 81429, 36311, 83038, 66296, 88879, 12641, 1779, 20581, 66775, 2361, 74791, 26924, 1613, 98315, 78636, 44960, 22826, 30080, 9537, 16255, 16128, 71644, 34830, 28126, 28387, 33454, 76495, 7678, 23754, 85758, 87407, 59185, 59606, 85210, 30120, 2504, 16437, 51851, 2898, 80632, 28728, 37922, 88174, 99561, 27162, 54461, 60259, 90591, 18460, 71514, 97549, 86607, 58644, 84484, 15674, 28623, 47310, 4100, 6910], 99]
    want = 65369
    got = solution.minAbsoluteDifference(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

