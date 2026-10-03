"""Scoring checks for lcb_2827 -- NOT part of any workspace.

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
    args = [[2, 3, 6]]
    want = True
    got = solution.canTraverseAllPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[3, 9, 5]]
    want = False
    got = solution.canTraverseAllPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[4, 3, 12, 8]]
    want = True
    got = solution.canTraverseAllPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[28, 4]]
    want = True
    got = solution.canTraverseAllPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[95, 10]]
    want = True
    got = solution.canTraverseAllPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[80, 49, 80, 44]]
    want = False
    got = solution.canTraverseAllPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[2, 19, 9, 2, 2, 23]]
    want = False
    got = solution.canTraverseAllPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[13, 7, 7, 22, 3, 14]]
    want = False
    got = solution.canTraverseAllPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[25, 70, 79, 93, 71, 68, 80]]
    want = False
    got = solution.canTraverseAllPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[3, 5, 3, 6, 3, 3, 5, 4, 4, 3]]
    want = False
    got = solution.canTraverseAllPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[12, 21, 7, 18, 6, 15, 26, 3, 2]]
    want = True
    got = solution.canTraverseAllPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[58, 8, 7, 87, 10, 98, 51, 22, 52, 18]]
    want = True
    got = solution.canTraverseAllPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [[16, 22, 21, 12, 19, 1, 27, 2, 22, 30]]
    want = False
    got = solution.canTraverseAllPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [[49, 73, 84, 7, 74, 6, 20, 64, 14, 71]]
    want = False
    got = solution.canTraverseAllPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [[37, 55, 11, 6, 93, 78, 63, 90, 62, 73]]
    want = False
    got = solution.canTraverseAllPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [[57, 25, 43, 18, 77, 19, 54, 65, 63, 78]]
    want = False
    got = solution.canTraverseAllPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [[673, 164, 409, 403, 636, 228, 920, 571, 528, 230]]
    want = False
    got = solution.canTraverseAllPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [[7340, 1470, 7332, 8782, 1074, 9319, 4461, 1372, 4665, 2501]]
    want = False
    got = solution.canTraverseAllPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [[37469, 73970, 24975, 85796, 40860, 17014, 25167, 29726, 49865, 60142]]
    want = True
    got = solution.canTraverseAllPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [[2, 793, 184, 303, 58, 216, 307, 458, 324, 386, 172, 891, 497, 21, 276, 286, 201, 327, 36, 96]]
    want = False
    got = solution.canTraverseAllPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [[937, 959, 788, 353, 696, 618, 288, 695, 467, 200, 133, 715, 806, 634, 495, 257, 670, 161, 516, 20, 561, 799, 557, 692, 483, 616, 801, 878, 31, 304, 219, 131, 883, 501, 954, 525, 287, 638, 910, 207, 5, 376, 796]]
    want = False
    got = solution.canTraverseAllPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [[631, 289, 216, 355, 644, 564, 671, 771, 946, 29, 491, 46, 418, 270, 587, 569, 675, 357, 895, 418, 603, 690, 782, 163, 451, 279, 975, 293, 130, 751, 285, 352, 313, 90, 364, 64, 107, 78, 347, 810, 471, 729, 289, 259, 648, 273, 700, 495, 696, 248]]
    want = False
    got = solution.canTraverseAllPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [[4, 7, 1, 4, 4, 3, 4, 1, 6, 10, 8, 4, 9, 4, 7, 1, 3, 5, 3, 9, 2, 5, 4, 10, 9, 1, 4, 9, 7, 6, 10, 4, 8, 5, 5, 5, 8, 4, 8, 8, 3, 8, 7, 8, 6, 9, 3, 6, 2, 2, 7, 7, 2, 5, 10, 5, 10, 9, 10, 3, 10, 9, 10, 5, 5, 7, 7, 1, 8, 8, 6, 5, 10, 8, 2, 10, 4, 5, 6, 3, 1, 6, 5, 7, 7, 6, 4, 5, 5, 1, 4, 2, 7, 2, 3, 3, 2, 1, 6, 4]]
    want = False
    got = solution.canTraverseAllPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = [[237, 452, 9, 76, 844, 108, 513, 60, 251, 494, 12, 299, 820, 576, 635, 121, 853, 230, 800, 667, 686, 917, 375, 594, 484, 933, 251, 358, 226, 126, 116, 405, 879, 212, 648, 714, 875, 998, 826, 142, 814, 592, 319, 789, 872, 737, 700, 702, 460, 876, 341, 947, 996, 467, 991, 772, 693, 419, 563, 967, 842, 675, 672, 857, 759, 409, 245, 89, 323, 372, 652, 419, 15, 325, 757, 489, 419, 491]]
    want = False
    got = solution.canTraverseAllPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = [[28, 93, 11, 66, 72, 21, 84, 64, 13, 33, 25, 65, 12, 43, 28, 24, 47, 79, 63, 97, 31, 93, 51, 38, 51, 13, 5, 1, 91, 86, 55, 18, 92, 38, 89, 89, 70, 96, 93, 15, 97, 47, 76, 35, 32, 98, 98, 98, 98, 34, 6, 78, 14, 50, 81, 34, 63, 60, 83, 43, 35, 6, 85, 30, 31, 44, 82, 57, 11, 84, 27, 19, 91, 29, 39, 11, 71, 27, 30, 3, 83, 58, 75, 15, 94, 78, 39, 70, 5, 47, 48, 89, 2, 44, 6, 84, 16, 98, 66, 7]]
    want = False
    got = solution.canTraverseAllPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = [[887, 296, 608, 250, 295, 620, 899, 459, 84, 991, 342, 639, 659, 670, 542, 425, 686, 978, 406, 951, 793, 181, 891, 770, 93, 844, 137, 395, 266, 66, 239, 392, 927, 592, 9, 276, 207, 863, 885, 199, 380, 923, 414, 20, 11, 197, 29, 845, 324, 649, 880, 120, 180, 373, 338, 870, 137, 491, 748, 826, 865, 954, 101, 800, 912, 884, 581, 863, 802, 761, 247, 420, 340, 562, 835, 833, 409, 777, 770, 305, 112, 273, 370, 64, 303, 29, 63, 462, 599, 737, 368, 899, 828, 577, 379, 192, 364, 186, 554, 663]]
    want = False
    got = solution.canTraverseAllPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_27():
    args = [[89, 836, 565, 61, 56, 298, 331, 682, 481, 456, 771, 822, 703, 377, 146, 270, 673, 323, 559, 150, 20, 730, 455, 656, 487, 650, 779, 774, 897, 966, 872, 925, 482, 279, 74, 419, 738, 836, 271, 329, 337, 600, 863, 890, 774, 268, 997, 295, 93, 693, 36, 669, 346, 123, 204, 547, 612, 246, 404, 989, 401, 280, 923, 251, 260, 83, 958, 905, 801, 291, 338, 567, 373, 473, 471, 272, 95, 648, 103, 106, 961, 989, 823, 843, 532, 784, 278, 307, 31, 125, 585, 875, 228, 421, 883, 894, 395, 780, 384, 215]]
    want = False
    got = solution.canTraverseAllPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

