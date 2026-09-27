"""Scoring checks for lcb_3345 -- NOT part of any workspace.

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
    args = [[1, 2, 3], 3]
    want = 6
    got = solution.sumOfPower(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[2, 3, 3], 5]
    want = 4
    got = solution.sumOfPower(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[1, 2, 3], 7]
    want = 0
    got = solution.sumOfPower(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[8, 5, 6, 9, 8, 6, 5, 6, 3, 10, 2, 2, 3, 4, 6, 4, 4, 10, 2, 5, 2, 8, 5, 1, 1, 1, 4, 3, 2, 1, 4, 10, 5, 9, 3, 4, 5, 3, 9, 10, 4, 9, 8, 4, 5, 4, 7, 6, 8, 5, 9, 3, 8, 2, 8, 9, 3, 7, 1, 1, 3, 1, 2, 2, 10, 2, 2, 8, 2, 5, 4, 9, 4, 8, 8, 2, 10, 1, 10, 3, 4, 5, 3, 10, 9, 9, 5, 2, 9, 6, 7, 6, 10, 10, 5, 10, 9, 3, 8, 3], 12]
    want = 402263131
    got = solution.sumOfPower(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[25, 48, 95, 37, 67, 86, 83, 50, 99, 14, 27, 67, 70, 34, 43, 61, 1, 81, 88, 13, 86, 9, 13, 37, 36, 42, 32, 21, 4, 73, 44, 88, 16, 71, 16, 54, 74, 34, 27, 79, 31, 65, 42, 78, 15, 40, 79, 27, 2, 3, 55, 20, 94, 63, 61, 28, 19, 18, 15, 25, 5, 20, 11, 13, 12, 31, 25, 80, 13, 82, 95, 87, 96, 79, 2, 83, 36, 69, 68, 82, 41, 22, 93, 13, 11, 74, 29, 94, 40, 78, 10, 57, 12, 4, 80, 30, 41, 73, 64, 89], 100]
    want = 269124302
    got = solution.sumOfPower(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[1651, 6907, 7158, 2041, 3041, 5778, 4457, 9176, 1004, 5411, 3484, 1273, 3178, 9097, 2604, 7758, 861, 6949, 2408, 6366, 7589, 9398, 5882, 9542, 161, 1183, 3961, 81, 488, 4851, 4045, 9004, 3910, 7120, 5250, 171, 3673, 9042, 3315, 2222, 571, 4361, 3517, 5838, 7597, 9741, 303, 8761, 6463, 6082, 8238, 1756, 1067, 4347, 2658, 1082, 9068, 4075, 6515, 1573, 4627, 8666, 9680, 5465, 5150, 1399, 4654, 7095, 6078, 9432, 1152, 1228, 10, 4516, 9027, 7820, 3505, 3866, 3705, 1622, 4260, 6020, 2785, 9600, 2331, 6014, 4936, 600, 9742, 291, 825, 4696, 5803, 7903, 924, 9380, 3493, 7791, 2569, 1161], 100]
    want = 0
    got = solution.sumOfPower(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[5281, 3456, 279, 6490, 7674, 1171, 487, 7294, 9525, 1941, 276, 4625, 1613, 4376, 5364, 7236, 8085, 4383, 9052, 9149, 2913, 1961, 4535, 7959, 5183, 2418, 1740, 3423, 7042, 8022, 2687, 3973, 4326, 3808, 3975, 5263, 6822, 825, 772, 1026, 4093, 1901, 3607, 9184, 8792, 2202, 4557, 2896, 9383, 7419, 6261, 3926, 9622, 1968, 6798, 2184, 134, 2502, 5034], 98]
    want = 0
    got = solution.sumOfPower(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[7, 5, 10, 8, 2, 3, 6], 4]
    want = 0
    got = solution.sumOfPower(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[10, 4, 3, 1, 10, 2, 5, 4, 4, 5, 2, 2, 3, 3, 9, 9, 10, 2, 10, 3, 6, 3, 3, 9, 9, 8, 1, 2, 7, 8, 3, 7, 3, 3, 3, 1, 2, 10, 5, 4, 10, 4, 8, 4, 6, 10, 9, 6, 9, 1, 2, 6, 2, 10, 8, 2, 2, 4, 2, 5, 10, 10, 9, 8, 2, 5, 6, 5, 3, 3, 1, 4, 7, 10, 10, 9, 7, 4, 4, 3, 10, 9, 6, 10, 7, 9, 10, 1, 4, 10, 6, 7, 2, 6, 9, 5, 8, 6, 8, 9], 9]
    want = 340940602
    got = solution.sumOfPower(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[9, 10, 2, 1, 9, 5, 9, 7, 5], 2]
    want = 256
    got = solution.sumOfPower(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[586, 4942, 4198, 4616, 8724, 8088, 879, 5186, 8156, 185, 4291, 7476, 9440, 8971, 9465, 9161, 471, 1020, 2107, 7618, 4710, 8272, 2142, 1545, 7946, 2518, 4517, 1833, 2120, 2951, 8930, 833, 6488, 8209, 5441, 9270, 1214, 6236, 3539, 9205, 1427, 9612, 2488, 6474, 1305, 9097, 5403, 5897, 5740, 3029, 4392, 4143, 2365, 7380, 5812, 5625, 1233, 5838, 9466, 4522, 5177, 3945, 5973, 2689, 2492, 5088, 2073, 6317, 7857, 7782, 5570, 8969, 1290, 1731, 9307, 8165, 7757, 7653, 7137, 9108, 4079, 9409, 831, 6832, 9104, 5679, 5934, 3848, 8848, 7338, 8343, 3843, 6182, 3128], 80]
    want = 0
    got = solution.sumOfPower(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[1, 3, 7, 8], 1]
    want = 8
    got = solution.sumOfPower(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [[5, 8, 8], 1]
    want = 0
    got = solution.sumOfPower(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [[5, 1], 5]
    want = 2
    got = solution.sumOfPower(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [[5846, 5524, 2254, 855, 9808, 6911, 1571, 2226, 5563, 2039, 9205, 9154, 668, 824, 2966, 3724, 7987, 6433, 3942, 9317, 8040, 4281, 1814, 3015, 4111, 6698, 4252, 3062, 9644, 7426, 8686, 1273, 393, 9582, 5138, 8387, 299, 1959, 9216, 4002, 9219, 2817, 1184, 1683, 2066, 6903, 8908, 7394, 2600, 9736, 6313, 187, 7920, 1423, 2620, 7186, 1361, 1342, 9639, 4227, 7713, 4367, 5596, 4584, 6501, 5871, 899, 4987, 8168, 6433, 9170, 8914, 3322, 7577, 181, 1187, 5649, 4398, 5466, 1976, 484, 7917, 3702, 9618, 5493, 9619, 348, 3015, 6811, 5308, 8156, 2273, 6033, 3749, 9913, 7186, 2934, 6815, 1932, 2242], 10]
    want = 0
    got = solution.sumOfPower(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [[8, 10, 8, 9, 1, 2, 5, 10, 4, 2, 8, 7, 8, 7, 4, 9, 4, 8, 6, 1, 9, 5, 5, 2, 6, 1, 2, 4, 10, 4, 6, 1, 8, 3, 3, 5, 2, 5, 10, 1, 5, 2, 4, 10, 9, 2, 7, 9, 3, 8, 9, 6, 5, 8, 10, 3, 5, 6, 8, 10, 3, 5, 2, 2, 6, 4, 1, 9, 5, 4, 9, 4, 4, 1, 10, 5, 5, 8, 9, 7, 7, 9, 10, 6, 9, 1, 7, 1, 1, 1, 7, 10, 6, 10, 2, 3, 3, 9, 3, 5], 6]
    want = 452355121
    got = solution.sumOfPower(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [[8, 1, 1, 8, 7], 2]
    want = 8
    got = solution.sumOfPower(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [[3, 17, 2, 7], 17]
    want = 8
    got = solution.sumOfPower(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [[8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8], 14]
    want = 0
    got = solution.sumOfPower(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [[1853, 6002, 3796, 5178, 6330, 2757, 9079, 2498, 1722, 576, 9624, 3494, 3885, 1906, 1683, 7490, 3383, 9870, 1623, 5922, 1581, 4873, 6109, 357, 1228, 5995, 6514, 6234, 2161, 872, 2827, 6163, 2646, 3702, 4055, 2007, 4016, 8624, 9670, 8831, 862, 1209, 3096, 7582, 7144, 9093, 1108, 1393, 4042, 3270, 5822, 7169, 1914, 9763, 5512, 3755, 2713, 1236, 3224, 5515, 5478, 8050, 2412, 7530, 4582, 2510, 9167, 3582, 4251, 2201, 8242, 1397, 6883, 7828, 586, 6481, 2637, 4095, 8605, 1529, 3683, 3275, 4941, 5363, 3276, 5327, 2113, 380, 2831, 1717, 5669, 3755, 8478, 227, 6502, 4945, 760, 1598, 4046, 5677], 58]
    want = 0
    got = solution.sumOfPower(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [[29, 49, 81, 9, 33, 16, 60, 29, 54, 90, 2, 76, 44, 33, 14, 24, 73], 57]
    want = 65536
    got = solution.sumOfPower(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [[7391, 1959, 9584, 3656, 4068, 7063, 6869, 3168, 8138, 4167, 905, 9144, 1132, 9215, 4464, 1467, 8052, 4074, 7857, 9581, 3017, 1225, 6396, 1737, 1556, 7999, 155, 166, 9887, 4879, 7845, 1381, 4444, 9332, 9619, 4881, 1973, 2071, 5747, 6831, 1307, 4086, 3068, 9489, 9358], 4]
    want = 0
    got = solution.sumOfPower(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [[1], 1]
    want = 1
    got = solution.sumOfPower(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = [[9, 6, 4, 6, 8], 9]
    want = 16
    got = solution.sumOfPower(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = [[74, 94, 65, 4, 20, 28, 88, 57, 84, 34, 85, 33, 37, 42, 98, 84, 19, 78, 28, 84, 7, 67, 90, 7, 76, 64, 18, 36, 69, 61, 7, 44, 14, 95, 69, 16, 17, 66, 77, 2, 57, 77, 21, 22, 96, 86, 40, 47, 2, 77, 2, 31, 98, 92, 16, 35, 32, 39, 74, 38, 100, 80, 16, 29, 71, 76, 14, 94, 71, 60, 51, 90, 79, 1, 49, 90, 34, 9, 42, 4, 75, 4, 38, 100, 24, 1, 47, 3, 14, 37, 82, 83, 41, 94, 40, 37, 14, 40, 53, 54], 13]
    want = 451344681
    got = solution.sumOfPower(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = [[9, 8, 4, 4, 9, 8, 5, 10, 2, 6, 1, 6, 8, 8, 4, 4, 6, 8, 2, 1, 7, 10, 9, 9, 6, 10, 7, 5, 9, 6, 4, 2, 5, 9, 4, 7, 1, 4, 6, 3, 10, 3, 4, 9, 2, 10, 8, 1, 6, 1, 6, 7, 9, 6, 1, 2, 8, 1, 9, 1, 6, 1, 9, 2, 9, 1, 10, 10, 1, 10, 6, 10, 7, 6, 2, 2, 1, 6, 6, 4, 5, 7, 2, 8, 3, 10, 1, 3, 9, 2, 10, 8, 2, 5, 8, 6, 5, 4, 2, 1], 29]
    want = 732827802
    got = solution.sumOfPower(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_27():
    args = [[9, 2, 10, 9, 4, 5, 2, 8, 5, 5, 2, 1, 10, 2, 6, 1, 5, 2, 4, 5, 4, 6, 5, 8, 7, 9, 5, 7, 3, 4, 10, 3, 3, 7, 9, 10, 1, 5, 4, 8, 3, 2, 2, 10, 2, 6, 8, 6, 7, 4, 6, 10, 5, 3, 4, 1, 9, 8, 5, 4, 2, 8, 5, 10, 2, 7, 6, 8, 6, 5, 7, 6, 1, 8, 8, 8, 8, 1, 8, 2, 8, 6, 1, 1, 4, 6, 2, 1, 10, 5, 2, 4, 6, 9, 2, 2, 9, 6, 2, 1], 4]
    want = 190923775
    got = solution.sumOfPower(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

