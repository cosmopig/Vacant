"""Scoring checks for lcb_2834 -- NOT part of any workspace.

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
    args = [[1, 6, 7, 8], [1, 7, 2], [2, 9, 5]]
    want = [5, 6, 8, 9]
    got = solution.relocateMarbles(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[1, 1, 3, 3], [1, 3], [2, 2]]
    want = [2]
    got = solution.relocateMarbles(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[2, 5], [2, 5], [5, 9]]
    want = [9]
    got = solution.relocateMarbles(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[8, 9], [9, 8, 10, 7, 2, 7, 4], [10, 7, 2, 9, 7, 4, 9]]
    want = [9]
    got = solution.relocateMarbles(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[2, 72, 623, 788, 170, 897, 235], [788, 897, 72, 170, 498], [665, 247, 498, 253, 259]]
    want = [2, 235, 247, 253, 259, 623, 665]
    got = solution.relocateMarbles(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[457095, 94531, 607022, 227833, 620726, 840345, 418973, 888519], [888519, 457095, 227833], [344253, 903515, 944677]]
    want = [94531, 344253, 418973, 607022, 620726, 840345, 903515, 944677]
    got = solution.relocateMarbles(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[379, 47, 526, 650, 280, 538, 953, 608, 587, 408, 809, 535, 702, 679, 970, 749, 961, 434, 441, 392, 716, 565, 206, 495, 114, 757, 957, 325, 440, 292, 278, 268, 91, 548], [535, 650, 47], [379, 716, 615]]
    want = [91, 114, 206, 268, 278, 280, 292, 325, 379, 392, 408, 434, 440, 441, 495, 526, 538, 548, 565, 587, 608, 615, 679, 702, 716, 749, 757, 809, 953, 957, 961, 970]
    got = solution.relocateMarbles(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[334, 45, 36], [334, 45, 909, 53, 36, 835, 833, 914, 409, 660, 907, 299, 698, 392, 875, 222, 623, 216, 522, 969, 436, 87, 792, 455, 748, 925, 663, 506, 681, 613, 130, 195, 549, 335, 520, 159, 354, 282, 91, 484], [835, 909, 53, 914, 660, 833, 409, 907, 698, 216, 299, 623, 392, 875, 222, 792, 522, 436, 969, 506, 87, 455, 925, 748, 282, 663, 613, 681, 130, 195, 549, 354, 335, 520, 159, 484, 91, 243, 596, 50]]
    want = [50, 243, 596]
    got = solution.relocateMarbles(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[27539, 748727, 874535, 783551, 848603, 35609, 191500, 87757, 302371, 207275, 3474, 293483, 370356, 665843, 948511, 860353, 334254, 96492, 91367, 213240, 662621, 615935, 655734, 108295], [108295, 96492, 302371, 207275, 848603], [134634, 987511, 720977, 116323, 118817]]
    want = [3474, 27539, 35609, 87757, 91367, 116323, 118817, 134634, 191500, 213240, 293483, 334254, 370356, 615935, 655734, 662621, 665843, 720977, 748727, 783551, 860353, 874535, 948511, 987511]
    got = solution.relocateMarbles(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[8, 9, 8, 10, 7, 4, 8, 5, 2, 4, 4, 7, 2, 1, 10, 5, 3, 3, 5, 8, 9, 5, 8, 8, 7, 6, 5, 5, 4, 10, 2, 8, 10, 5, 4, 10, 6, 9, 10, 7, 1, 3, 2, 4, 4, 3, 5, 6, 5, 2, 10, 6, 2, 1, 10, 4, 3, 7, 10, 8, 2, 6, 4, 4, 10, 7, 4, 7, 7, 1, 6, 5, 1, 10, 6, 4, 9, 6, 10, 7, 7, 5, 7, 2, 9, 9, 1, 5], [4, 10, 8, 6, 4, 3, 7, 3, 2, 8, 5, 10, 1, 9, 3, 10, 2, 2, 6, 10, 5, 4, 9, 2, 7, 5, 1], [2, 4, 4, 9, 8, 3, 5, 10, 9, 3, 1, 1, 2, 7, 10, 9, 2, 6, 10, 5, 4, 9, 2, 6, 5, 1, 7]]
    want = [6, 7]
    got = solution.relocateMarbles(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[7, 3, 1, 10, 7], [3, 8, 3, 4, 7, 6, 2, 10, 3, 1, 4, 7, 1, 3, 10, 8, 4, 4, 9, 2, 5, 1, 9, 8, 6, 4, 5, 5, 4, 8, 2, 8, 5, 8, 9, 3, 8, 6, 3, 3, 6, 3, 9, 2, 3, 4, 3, 1, 8, 2, 6, 9, 1, 3, 9, 7, 8, 2, 4, 9, 5, 3, 6, 6, 7, 2, 8, 1, 10, 8, 8, 8, 4, 1, 1, 8, 4, 9, 3, 10, 5, 5, 3, 3, 5, 4, 10, 10, 9, 10], [8, 3, 4, 6, 6, 2, 3, 10, 8, 4, 7, 1, 3, 10, 4, 5, 4, 9, 2, 6, 1, 9, 8, 6, 4, 5, 5, 4, 8, 2, 8, 5, 8, 9, 3, 8, 6, 3, 3, 6, 3, 9, 2, 3, 4, 3, 1, 8, 2, 6, 9, 1, 3, 9, 7, 8, 2, 4, 9, 5, 3, 6, 6, 7, 2, 8, 1, 10, 8, 8, 8, 4, 1, 1, 8, 4, 9, 3, 10, 5, 5, 3, 3, 5, 4, 10, 10, 9, 10, 8]]
    want = [8]
    got = solution.relocateMarbles(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

