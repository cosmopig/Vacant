"""Scoring checks for lcb_2832 -- NOT part of any workspace.

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
    args = [[1, 3, 2, 3, 1, 3], 3]
    want = 3
    got = solution.longestEqualSubarray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[1, 1, 2, 2, 1, 1], 2]
    want = 4
    got = solution.longestEqualSubarray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[8], 1]
    want = 1
    got = solution.longestEqualSubarray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[4], 1]
    want = 1
    got = solution.longestEqualSubarray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[1, 1, 5, 3], 3]
    want = 2
    got = solution.longestEqualSubarray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[1, 4, 3, 4, 1, 3], 5]
    want = 2
    got = solution.longestEqualSubarray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[3, 4, 2, 4, 5, 2, 2], 7]
    want = 3
    got = solution.longestEqualSubarray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[10, 8, 9, 4, 4, 5, 1], 7]
    want = 2
    got = solution.longestEqualSubarray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[4, 3, 6, 8, 10, 1, 10], 1]
    want = 2
    got = solution.longestEqualSubarray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[3, 8, 10, 8, 5, 3, 3, 9, 9], 6]
    want = 3
    got = solution.longestEqualSubarray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[3, 7, 6, 10, 2, 4, 5, 9, 3, 8], 5]
    want = 1
    got = solution.longestEqualSubarray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[833, 904, 648, 656, 357, 98, 170, 419, 834, 357, 521, 102, 351, 614, 483, 567, 71, 332, 31, 177, 255, 139, 21, 641, 158, 466, 61, 341, 285, 506, 761, 251, 686, 877, 435, 623, 141, 568, 679, 484, 422, 700, 785, 436, 898, 640, 139, 617, 582, 254, 43, 634, 767, 122, 576, 727, 351, 615, 49, 97, 504, 640, 838, 523, 151, 495, 975, 453, 602, 47, 239, 161, 309, 666, 202, 647, 54, 759, 743, 755, 70, 743, 779, 253, 844, 302, 776, 867, 72, 659, 942, 22, 912, 164, 136, 485, 837, 107, 319, 447, 820, 142, 854, 409, 188, 27, 889, 321, 753, 100, 751, 786, 69, 27, 470, 777, 229, 643, 682, 407, 279, 369, 443, 986, 559, 831, 839, 291, 79, 281, 922, 228, 835, 433, 286, 54, 398, 147, 73, 693, 115, 62, 894, 745, 218, 364, 31, 367, 606, 893, 942, 407, 536, 469, 676, 938, 544, 620, 151, 446, 917, 710, 537, 958, 448, 787, 806, 124, 866, 230, 860, 528, 495, 518, 312, 531, 589, 40, 243, 563, 404, 238, 469, 528, 441, 320, 999, 262, 24, 467, 870, 141, 439, 742, 14, 806, 8, 176, 963, 425, 556, 108, 74, 206, 682, 349, 822, 140, 826, 42, 466, 39, 694, 808, 793, 115, 18, 398, 85, 153, 473, 745, 925, 563, 980, 302, 578, 63, 695, 61, 353, 716, 133, 476, 845, 715, 367, 678, 501, 373, 996, 569, 193, 15, 803, 3, 566, 499, 744, 491, 911, 272, 753, 558, 805, 900, 369, 635, 854, 30, 109, 418, 351, 87, 881, 962, 402, 100, 913, 27, 886, 305, 656, 521, 460, 197, 49, 358, 535, 931, 928, 178, 68, 395, 589, 133, 963, 427, 572, 597, 335, 165, 893, 47, 97, 659, 862, 421, 897, 46, 187, 500, 773, 962, 878, 114, 443, 902, 15, 440, 813, 692, 263, 77, 177, 863, 910, 331, 428, 560, 776, 874, 29, 202, 142, 123, 636, 377, 72, 322, 943, 828, 413, 584, 945, 337, 133, 568, 330, 947, 605, 383, 126, 976, 424, 854, 76, 631, 616, 246, 397, 999, 352, 906, 443, 924, 803, 554, 554, 854, 582, 820, 159, 196, 674, 704, 312, 648, 528, 386, 410, 219, 438, 797, 439, 835, 157, 312, 793, 773, 23, 747, 743, 582, 756, 506, 671, 431, 246, 607, 83, 843, 241, 688, 918, 753, 916, 443, 719, 523, 397, 314, 939, 338, 852, 768, 929, 661, 604, 760, 970, 283, 190, 92, 900, 309, 144, 776, 38, 770, 504, 375, 397, 169, 287, 836, 521, 814, 854, 528, 51, 613, 872, 52, 30, 966, 772, 713, 749, 554, 631, 954, 717, 524, 925, 276, 524, 39, 976, 641, 513, 138, 910, 542], 41]
    want = 2
    got = solution.longestEqualSubarray(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

