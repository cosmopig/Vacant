"""Scoring checks for lcb_3528 -- NOT part of any workspace.

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
    args = [[1, 3, 1, 5]]
    want = 7
    got = solution.findMaximumScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[4, 3, 1, 3, 2]]
    want = 16
    got = solution.findMaximumScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[5]]
    want = 0
    got = solution.findMaximumScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[36303, 77014, 59208, 6680, 27715, 29121, 38752, 99333]]
    want = 498387
    got = solution.findMaximumScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[55420]]
    want = 0
    got = solution.findMaximumScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[94, 1, 54, 1, 76, 1, 92, 1, 47, 1, 81, 1, 53, 1, 76, 1, 57, 1, 44, 1, 33, 1, 34, 1, 44, 1, 96, 1, 42, 1, 96, 1, 7, 1, 76, 1, 95, 1, 49, 1, 33, 1, 96, 1, 75, 1, 14, 1, 50, 1, 64, 1, 92, 1, 76, 1, 70, 1, 76, 1, 61, 1, 71, 1, 51, 1, 85, 1, 18, 1, 15, 1, 49, 1, 91, 1, 11, 1, 77, 1, 81, 1, 4, 1, 52, 1, 47, 1, 78, 1, 34, 1, 92, 1, 50, 1, 23, 1, 85, 1]]
    want = 9452
    got = solution.findMaximumScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[82214]]
    want = 0
    got = solution.findMaximumScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[62395]]
    want = 0
    got = solution.findMaximumScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[100000, 1, 100000, 1, 100000, 1, 100000, 1, 100000, 1]]
    want = 900000
    got = solution.findMaximumScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[2, 7]]
    want = 2
    got = solution.findMaximumScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[1, 5]]
    want = 1
    got = solution.findMaximumScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[1000, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1000]]
    want = 99000
    got = solution.findMaximumScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [[42, 21, 53, 97, 93, 97, 92, 66, 7, 44]]
    want = 719
    got = solution.findMaximumScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [[1, 4]]
    want = 1
    got = solution.findMaximumScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [[8]]
    want = 0
    got = solution.findMaximumScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [[10000, 1, 10000, 1, 10000, 1, 10000, 1, 10000, 1]]
    want = 90000
    got = solution.findMaximumScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [[6]]
    want = 0
    got = solution.findMaximumScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [[9]]
    want = 0
    got = solution.findMaximumScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [[83268, 6927, 78430, 61777, 34816, 16797, 19171, 37279, 57673, 61130, 62581, 37998, 28960, 18748, 50398, 1877, 70763, 26341, 1193, 36007, 26720, 86286, 70377, 51901, 90532, 51261, 29952, 77005, 74728, 29982, 79729, 86233, 75530, 45433, 11005, 38617, 35758, 2011, 15428, 61851, 77103, 71638, 98344, 82767, 33362, 71593, 90577, 82066, 48366, 8715, 4205, 33111, 31368, 69942, 63496, 41108, 20710, 48233, 11258, 12482, 2051, 13253, 46887, 39801, 28395, 34063, 8207, 28891, 96153, 73919, 2735, 36275, 23907, 55177, 7417, 67256, 97111, 56715, 47789, 58660, 3837, 44182, 84210, 4450, 82629, 7160, 38229, 98747, 79700, 26877, 47863, 3885, 38145, 52594, 40372, 6423, 1752, 66854, 15411, 33035, 33071, 18839, 83433, 42253, 10243, 19236, 30858, 74969, 92522, 50284, 19771, 12278, 20776, 99468, 60111, 7099, 77037, 5735, 18323, 76220, 25444, 56716, 90910, 53940, 43802, 42106, 4674, 30905, 53256, 88116, 96358, 63177, 75290, 96185, 75522, 77945, 62386, 22764, 50789, 57097, 79256, 18710]]
    want = 13415068
    got = solution.findMaximumScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [[1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000]]
    want = 45000
    got = solution.findMaximumScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [[10000, 9999, 9998, 9997, 9996, 9995, 9994, 9993, 9992, 9991, 9990, 9989, 9988, 9987, 9986, 9985, 9984, 9983, 9982, 9981, 9980, 9979, 9978, 9977, 9976, 9975, 9974, 9973, 9972, 9971, 9970, 9969, 9968, 9967, 9966, 9965, 9964, 9963, 9962, 9961, 9960, 9959, 9958, 9957, 9956, 9955, 9954, 9953, 9952, 9951, 9950, 9949, 9948, 9947, 9946, 9945, 9944, 9943, 9942, 9941, 9940, 9939, 9938, 9937, 9936, 9935, 9934, 9933, 9932, 9931, 9930, 9929, 9928, 9927, 9926, 9925, 9924, 9923, 9922, 9921, 9920, 9919, 9918, 9917, 9916, 9915, 9914, 9913, 9912, 9911, 9910, 9909, 9908, 9907, 9906, 9905, 9904, 9903, 9902, 9901]]
    want = 990000
    got = solution.findMaximumScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [[68]]
    want = 0
    got = solution.findMaximumScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [[11, 25]]
    want = 11
    got = solution.findMaximumScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = [[12005, 35332, 57327, 54247, 83740, 15407, 44613, 79329, 660, 16057, 5296, 47576, 38803, 93495, 40674, 4639, 35458, 97580, 96259, 77006, 62052, 31509, 76743, 83253, 65025, 11644, 72564, 94181, 42747, 45547, 30705, 49180, 55430, 71731, 84914, 53696, 41554, 91010, 67042, 14056, 45053, 33599, 31650, 93934, 99568, 85255, 94569, 85623, 24318, 78128, 28632, 94947, 38578, 1656, 47053, 92742, 91343, 79273, 94279, 26358, 61497, 43017, 59318, 88249, 4054, 92321, 80808, 53630, 67415, 26633, 54956, 36185, 99073, 38621, 58786, 14063, 90300, 69796, 65098, 93127, 63114, 23028, 4199, 92808, 28731, 10931, 94235, 50519, 45759, 52361, 21736, 59278, 95828, 32441, 40276, 16080, 33736, 20142, 63911, 34737, 72147, 70199, 28623, 80588, 46874, 46796, 17943, 47174, 83122, 72266, 88425, 74943, 50032, 65900, 1581, 52838, 45561, 66169, 25829, 75564, 83851, 47706, 99290, 94240, 66020, 18917, 39373, 58289, 46917, 46599, 89424, 43011, 54794, 37390, 84792, 38215, 98196, 61089, 11663, 90519, 58000, 77277, 29718, 79098, 24822, 96221, 51843, 38, 44610, 20845, 79277, 94094, 40257, 62985, 96142, 13002, 14283, 19145, 93929, 2921, 76820, 66446, 73099, 44218, 717, 42124, 95403, 71548, 19354, 68672, 87820, 47156, 69540, 13921, 45332, 32597, 56808, 54395]]
    want = 17166835
    got = solution.findMaximumScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = [[84, 85, 1, 73, 61, 69, 86, 73, 41, 87, 58, 47, 71, 29, 15, 95, 13, 14, 35, 82, 2, 26, 35, 86, 18, 73, 38, 39, 81, 38, 13, 20, 9, 6, 90, 40, 100, 98, 100, 63, 73, 5, 16, 73, 73, 11, 94, 22, 21, 45, 38, 96, 27, 69, 39, 98, 83, 20, 54, 62, 52, 96, 72, 19, 96, 58]]
    want = 6184
    got = solution.findMaximumScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = [[44690, 35242, 41845, 37953, 2409, 22609, 25003, 79772, 48328, 53342, 24411, 88031, 44170, 15684, 34070, 40224, 43491, 11335, 14135, 57057, 30285, 49093, 14894, 25368, 89422, 3552, 57897, 75201, 31145, 41125, 92669, 3791, 1195, 94347, 86430, 71128, 76104, 26036, 25727, 7777, 99757, 56774, 16762, 3160, 52246, 91338, 31972, 13367, 72263, 25773, 77510, 89288, 37343, 73517, 14308, 12822, 7757, 28559, 48902, 2944, 75362, 4107, 86588, 5744, 33174, 6954, 57888, 33561, 71633, 48491, 96026, 74465, 51579, 82482, 7680, 71673, 72621, 51130, 4783, 16270, 35771, 10110, 48112, 60308, 6117, 81839, 29433, 90580, 62637, 58839, 93774, 63646, 70857, 86733, 90641, 26632, 34082, 22686, 23878, 10102, 21823, 11080, 50693, 78092, 77298, 10651, 94439, 41163, 54230, 47091, 40684, 95810, 4524, 30146, 71387, 54101, 56786, 3660, 31861, 18519, 37825, 69823]]
    want = 11331606
    got = solution.findMaximumScore(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

