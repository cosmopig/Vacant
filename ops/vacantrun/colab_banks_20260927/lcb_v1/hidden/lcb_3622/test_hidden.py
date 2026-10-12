"""Scoring checks for lcb_3622 -- NOT part of any workspace.

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
    args = [[1, 4, 5], 1, 2]
    want = 2
    got = solution.maxFrequency(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[5, 11, 20, 20], 5, 1]
    want = 2
    got = solution.maxFrequency(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[61, 6], 56, 2]
    want = 2
    got = solution.maxFrequency(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[18, 57], 97, 2]
    want = 2
    got = solution.maxFrequency(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[2], 7, 0]
    want = 1
    got = solution.maxFrequency(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[89, 78], 97, 0]
    want = 1
    got = solution.maxFrequency(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[1, 90], 76, 1]
    want = 1
    got = solution.maxFrequency(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[56, 16], 68, 1]
    want = 2
    got = solution.maxFrequency(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[61, 70], 55, 2]
    want = 2
    got = solution.maxFrequency(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[90, 80], 12, 1]
    want = 2
    got = solution.maxFrequency(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[67, 80], 48, 1]
    want = 2
    got = solution.maxFrequency(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[6], 1, 0]
    want = 1
    got = solution.maxFrequency(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [[2, 49], 97, 0]
    want = 1
    got = solution.maxFrequency(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [[89, 88], 69, 2]
    want = 2
    got = solution.maxFrequency(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [[100000, 100000], 1, 1]
    want = 2
    got = solution.maxFrequency(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [[52, 50], 100, 1]
    want = 2
    got = solution.maxFrequency(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [[995, 470, 150, 685, 904, 184, 24, 419, 151, 63, 388, 691, 236, 797, 853, 511, 292, 770, 917, 638, 881, 53, 382, 553, 682, 942, 526, 939, 230, 574, 6, 21, 856, 180, 831, 227, 467, 564, 409, 355, 847, 199, 922, 151, 927, 542, 344, 772, 522, 790, 74, 412, 589, 104, 399, 972, 248, 177, 905, 28, 267, 768, 722, 763, 345, 807, 97, 195, 949, 724, 535, 925, 344, 231, 983, 979, 457, 683, 148, 752, 424, 256, 446, 262, 663, 852, 680, 513, 82, 297, 644, 963, 461, 642, 756, 176, 912, 420, 901, 333, 60, 645, 688, 907, 757, 656, 45, 749, 369, 189, 663, 52, 462, 798, 573, 907, 144, 922, 161, 395, 765, 84, 872, 364, 772, 111, 115, 981, 792, 189, 430, 273, 898, 355, 253, 294, 329, 35, 85, 584, 947, 976, 365, 487, 351, 377, 94, 21, 261, 624, 942, 113, 215, 925, 297, 55, 479, 499, 299, 522, 354, 260, 919, 603, 541, 306, 263, 626, 355, 902, 543, 282, 63, 696, 91, 329, 388, 632, 165, 596, 306, 633, 180, 428, 869, 704, 573, 364, 464, 136, 436, 544, 894, 670, 962, 458, 627, 34, 944, 871, 225, 198, 235, 823, 391, 18, 937, 910, 621, 807, 440, 576, 94, 226, 530, 606, 812, 38, 124, 33, 799, 644, 209, 716, 728, 572, 131, 665, 105, 644, 385, 692, 845, 384, 828, 220, 196, 768, 792, 4, 543, 21, 748, 456, 383, 873, 785, 589, 767, 456, 246, 368, 398, 846, 94, 100, 783, 908, 216, 211, 700, 585, 232, 698, 653, 577, 596, 376, 315, 244, 602, 90, 991, 788, 263, 89, 361, 300, 651, 159, 178, 450, 499, 474, 154, 499, 307, 295, 22, 648, 115, 84, 356, 295, 266, 573, 575, 493, 407, 34, 991, 340, 836, 712, 457, 534, 277, 420, 12, 279, 382, 1, 864, 168, 416, 345, 806, 873, 665, 714, 494, 318, 432, 262, 304, 381, 302, 986, 73, 32, 829, 556, 340, 773, 188, 556, 901, 760, 564, 262, 495, 728, 938, 715, 735, 249, 487, 825, 773, 921, 226, 360, 786, 530, 16, 831, 359, 395, 892, 268, 5, 384, 334, 962, 839, 730, 992, 465, 316, 137, 659, 694, 653, 105, 532, 758, 111, 686, 245, 931, 554, 9, 686, 100, 465, 659, 541, 82, 386, 571, 517, 261, 660, 603, 432, 914, 836, 817, 828, 463, 438, 957, 521, 367, 364, 185, 379, 354, 3, 358, 215, 71, 451, 662, 638, 555, 119, 586, 828, 521, 119, 821, 984, 124, 577, 66, 485, 474, 771, 85, 266, 907, 757, 820, 400, 705, 483, 121, 907, 581, 334, 207, 587, 969, 65, 684, 129, 246, 327, 596, 144, 909, 106, 228, 348, 417, 204, 733, 49, 329, 130, 682, 936, 268, 944, 839, 410, 943, 201, 291, 629, 585, 779, 935, 737, 381, 852, 414, 149, 178, 177, 662, 101, 767, 645, 223, 750, 799, 627, 67, 406, 613, 431, 252, 514, 587, 507, 246, 699, 459, 478, 775, 251, 17, 87, 660, 110, 47, 551, 963, 37, 851, 139, 37, 35, 583, 78, 527, 599, 450, 362, 689, 790, 935, 230, 412, 28, 5, 899, 493, 761, 971, 663, 767, 579, 590, 535, 75, 698, 989, 202, 495, 346, 894, 249, 310, 16, 302, 277, 253, 718, 107, 240, 567, 275, 385, 561, 779, 464, 913, 423, 425, 284, 690, 671, 94, 327, 193, 636, 238, 533, 914, 506, 111, 325, 462, 985, 578, 299, 323, 18, 832, 471, 949, 910, 209, 670, 589, 954, 144, 276, 389, 369, 633, 178, 192, 926, 632, 844, 628, 957, 77, 925, 631, 403, 201, 679, 178, 859, 838, 569, 194, 254, 553, 512, 187, 803, 697, 411, 766, 922, 739, 471, 415, 733, 86, 130, 484, 795, 406, 23, 862, 297, 785, 410, 261, 188, 527, 713, 349, 834, 114, 211, 58, 300, 264, 94, 413, 179, 812, 356, 902, 697, 574, 490, 126, 56, 905, 688, 864, 999, 427, 123, 641, 553, 434, 480, 707, 846, 87, 854, 401, 727, 308, 806, 922, 570, 540, 452, 228, 165, 928, 373, 134, 201, 474, 692, 569, 755, 608, 278, 47, 619, 171, 950, 116, 478, 245, 135, 771, 773, 614, 545, 163, 824, 464, 50, 578, 415, 184, 256, 986, 849, 603, 443, 255, 988, 273, 183, 659, 282, 24, 761, 482, 335, 627, 972, 374, 156, 490, 281, 444, 917, 399, 723, 683, 347, 252, 535, 281, 539, 719, 480, 747, 751, 354, 480, 931, 76, 376, 146, 748, 776, 958, 271, 395, 266, 444, 399, 438, 659, 499, 914, 134, 30, 52, 738, 922, 348, 680, 511, 203, 128, 183, 90, 187, 176, 510, 954, 339, 467, 780, 801, 691, 575, 697, 140, 579, 340, 601, 277, 903, 844, 783, 99, 853, 859, 128, 296, 255, 582, 327, 537, 558, 251, 643, 641, 291, 204, 250, 752, 784, 597, 592, 359, 87, 367, 889, 461, 248, 875, 825, 748, 881, 813, 16, 380, 65, 700, 265, 257, 585, 576, 91, 195, 370, 684, 522, 112, 318, 773, 353, 510, 451, 853, 694, 481, 642, 648, 18, 105, 606, 660, 706, 110, 629, 740, 772, 679, 4, 572, 239, 921, 304, 860, 879, 532, 522, 622, 940, 389, 309, 937, 290, 665, 271, 875, 790, 190, 578, 213, 379, 755, 65, 352, 821, 428, 949, 260, 685, 129, 766, 319, 308, 888, 404, 113, 238, 895, 216, 443, 526, 57, 706, 464, 967, 924, 758, 719, 194, 136, 80, 22, 895, 97, 996, 18, 192, 813, 253, 152, 752, 538, 131, 244, 245, 249, 81, 325, 929, 288, 87, 747, 879, 902, 497, 376, 629, 563, 429, 467, 690, 686, 143, 361, 26, 779, 943, 111, 164, 956, 725, 852, 977, 966, 494, 993, 275, 576, 967, 648, 873, 199, 873, 653, 850, 162, 239, 28, 187, 414, 375, 344, 906, 135, 474, 836, 876, 914, 691, 43, 443, 690, 357, 414, 852, 824, 299, 740, 947, 716, 853, 846, 868, 416, 250, 183, 159, 476, 10, 129, 735, 300, 585, 44, 492, 446, 504, 317, 196, 91, 228, 380, 433, 954, 104, 952, 604, 234, 248, 714, 243, 330, 713, 898, 245, 549, 765, 867, 440, 997, 203, 383, 700, 643, 701, 862, 134, 364, 592, 665, 25, 204, 337, 830, 699, 283, 912, 111, 874, 653, 49, 596, 530, 882, 481, 18, 253, 735, 676, 198, 20, 250, 955, 189, 680, 173, 586, 894, 160, 497, 926, 250, 777, 303, 233, 381, 932, 832, 538, 531, 845, 783, 753, 6, 405, 712, 286, 534, 189, 754, 829, 931, 998, 909, 613, 447, 768, 904, 81, 779, 867, 150, 159, 703, 902, 302, 249, 801, 146, 630, 899, 908, 697, 838, 557, 59, 728, 324, 294, 495, 316, 897, 263, 842, 484, 239, 748, 21, 357, 723, 20, 138, 983, 965, 559, 963, 321, 425, 698, 606, 455, 119, 192, 769, 145, 29, 832, 829, 628, 315, 55, 121, 821, 121, 114, 891, 167, 344, 922, 735, 434, 110, 366, 624, 533, 514, 447, 95, 198, 140, 133, 912, 711, 806, 436, 351, 224, 601, 726, 482, 48, 598, 139, 862, 214, 415, 111, 637, 549, 236, 414, 865, 713, 102, 444, 853, 631, 955, 60, 173, 354, 184, 266, 412, 668, 428, 362, 520, 970, 251, 542, 694, 234, 224, 862, 797, 659, 526, 548, 672, 488, 688, 93, 211, 37, 825, 533, 396, 476, 844, 7, 336, 415, 558, 452, 302, 3, 703, 422, 942, 117, 598, 631, 655, 928, 12, 861, 539, 277], 251, 61]
    want = 67
    got = solution.maxFrequency(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [[23, 38], 86, 2]
    want = 2
    got = solution.maxFrequency(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [[6, 80], 45, 0]
    want = 1
    got = solution.maxFrequency(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [[88, 53], 27, 2]
    want = 2
    got = solution.maxFrequency(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [[61, 60], 27, 0]
    want = 1
    got = solution.maxFrequency(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [[59, 34], 61, 1]
    want = 2
    got = solution.maxFrequency(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [[42, 84], 55, 1]
    want = 2
    got = solution.maxFrequency(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = [[9], 0, 0]
    want = 1
    got = solution.maxFrequency(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = [[76, 92], 41, 1]
    want = 2
    got = solution.maxFrequency(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = [[63, 73], 29, 0]
    want = 1
    got = solution.maxFrequency(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

