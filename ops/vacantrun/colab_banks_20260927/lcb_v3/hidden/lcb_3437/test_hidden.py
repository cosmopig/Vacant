"""Scoring checks for lcb_3437 -- NOT part of any workspace.

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
    args = [[1, 1, 3, 4]]
    want = 6
    got = solution.maximumTotalDamage(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[7, 1, 6, 6]]
    want = 13
    got = solution.maximumTotalDamage(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[160847, 824339, 89046, 408265, 673674, 493487, 592632, 707107, 132420, 520237]]
    want = 4602054
    got = solution.maximumTotalDamage(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[4, 3]]
    want = 4
    got = solution.maximumTotalDamage(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[41, 44, 14, 36, 50, 48, 18, 67, 56, 23, 14, 67, 50, 72, 3, 52, 67, 75, 49, 89, 75, 33, 16, 88, 72, 30, 4, 13, 65, 98, 42, 51, 92, 1, 9, 47, 50, 53, 87, 71, 97, 11, 2, 97, 97, 94, 54, 16, 38, 43, 39, 25, 12, 20, 72, 64, 76, 100, 79, 76, 41, 75, 60, 82, 80, 73, 30, 26, 86, 77, 53, 24, 90, 35, 70, 87, 61, 17, 21, 47, 70, 76, 31, 89, 71, 66, 65, 55, 24, 13, 49, 10, 60, 46, 27, 53, 34, 29, 8, 30]]
    want = 2656
    got = solution.maximumTotalDamage(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[29, 64]]
    want = 93
    got = solution.maximumTotalDamage(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[5, 1, 4]]
    want = 6
    got = solution.maximumTotalDamage(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[39616, 10733, 13830, 98885, 43200, 74247, 24373, 59923, 38559, 5138, 25302, 71922, 53423, 37362, 59036, 57327, 53186, 42800, 83914, 53642, 42767, 68912, 82665, 83390, 72923, 71889, 74482, 81524, 19478, 40954, 97182, 79480, 70037, 15627, 36582, 3992, 76548, 56770, 3982, 5631, 76258, 95260, 51483, 57926, 55753, 82751, 4633, 85930, 17629, 75478, 76428, 96013, 86610, 86529, 53513, 41559, 66969, 36950, 47709, 3117, 70944, 8295, 54209, 41201, 8503, 6595, 45484, 15181, 12007, 52555, 62410, 6196, 79616, 59340, 24165, 22251, 29285, 18860, 96554, 44227, 77757, 98462, 77055, 82113, 31668, 14416, 91916, 54908, 57790, 32104, 77701, 64097, 88235, 98248, 41601, 70173, 53477, 27595, 38452, 93116, 28222, 68748, 72121, 49096, 51909, 95901, 27266, 29146, 16430, 7230, 74958, 34783, 48090, 90940, 18384, 13341, 80450, 55876, 88069, 28585, 78859, 89706, 20257, 51103, 488, 49589, 69447, 93763, 70630, 19017, 88025, 98508, 89004, 41989, 84899, 91142, 7891, 49247, 5277, 27131, 91033, 43260, 9850, 55748, 53031, 52626, 24537, 90544, 58022, 16321, 85041, 41991, 64994, 43066, 7288, 86428, 12164, 58210]]
    want = 8216175
    got = solution.maximumTotalDamage(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[90, 33, 19, 17, 25]]
    want = 167
    got = solution.maximumTotalDamage(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[3, 1, 1, 1, 3]]
    want = 6
    got = solution.maximumTotalDamage(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[45870, 88437, 74036, 22149, 39285, 79950, 15842, 51281, 66247, 55793, 11053, 51513, 93765, 18359, 42634, 20155, 28141, 13079, 50139, 25661, 10813, 78431, 709, 57413, 53609, 66174, 4450, 53576, 72410, 45874, 81765, 66305, 39207, 42174, 19221, 85327, 68348, 48259, 29849, 58703, 37404, 73239, 15859, 16763, 30822, 42997, 62370, 28265, 85877, 12086, 36833, 91838, 93162, 46745, 84481, 81033, 47668, 20179, 12490, 60408, 11692, 57151, 86102, 32283, 6206, 77029, 18330, 62892, 65040, 43937, 38015, 93345, 35027, 92305, 62666, 565, 66504, 37505, 5577, 33579, 21794, 21790, 25736, 34892, 70930, 93429, 2744, 71724, 12163, 28519, 89259, 41039, 59130, 19900, 75402, 97941, 62665, 99466, 8141, 34178, 78003, 92174, 94201, 74675, 84424, 34827, 23563, 47682, 18908, 11767, 28267, 80612, 78906, 83916, 70363, 50656, 21928, 39436, 16361, 56984, 27198, 4861, 98917, 51712, 71449, 19406, 16504, 14856, 91148, 82140, 99703, 3053, 46342, 55080, 97636, 62152, 80332, 68025, 13064, 38014, 86872, 11960, 70600, 57886, 43247, 7510, 3362, 30729, 99809, 653, 7458, 18783, 42376, 20254, 31309, 45922, 27955, 81070, 67068, 76848, 8716, 59696, 96222, 20853, 44089, 83256, 75118, 68869, 11772, 98868, 9169, 77854, 86923, 3965, 64579, 11506, 62877, 45276, 23032, 69994, 42547, 45592, 68782, 20842, 46270, 99139, 29075, 38058, 73485, 54359, 4482, 25247, 39214, 36475, 24157, 9422, 49819, 62415, 63163, 32239, 70047, 13351, 38313, 93193, 4109, 38294, 37948, 99602, 97359, 70775, 5376, 6006, 87178, 4841, 85405, 27872, 322, 86466, 26890, 79463, 49689, 50094, 49177, 18611, 19171, 18867, 69258, 56239, 82196, 65849, 41128, 10821, 64850, 89209, 26931, 39850, 54788, 65966, 64060, 15128, 92378, 4422, 54451, 20474, 33893, 79127, 11349, 11653, 51852, 21471, 42027, 65200, 26210, 48674, 75656, 86387, 89726, 27339, 60260, 93806, 94421, 71528, 85750, 51857, 84458, 39532, 9020, 96554, 80675, 99938, 40341, 7007, 30193, 37429, 38000, 84640, 81154, 15088, 77989, 99638, 7803, 21903, 82457, 99702, 52688, 1406, 59929, 22673, 64622, 89851, 79379, 86914, 84980, 25327]]
    want = 14298696
    got = solution.maximumTotalDamage(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[7, 14, 21, 28, 35, 42, 49, 56, 63, 70]]
    want = 385
    got = solution.maximumTotalDamage(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [[1, 1, 1, 1, 1, 1]]
    want = 6
    got = solution.maximumTotalDamage(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [[10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000, 10000]]
    want = 1000000
    got = solution.maximumTotalDamage(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [[6, 3, 8, 2]]
    want = 11
    got = solution.maximumTotalDamage(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [[97, 57, 17, 27, 89, 61, 52, 90]]
    want = 401
    got = solution.maximumTotalDamage(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [[1]]
    want = 1
    got = solution.maximumTotalDamage(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [[8, 7, 3, 7, 6, 6]]
    want = 17
    got = solution.maximumTotalDamage(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [[41, 34, 67, 97, 71, 62]]
    want = 372
    got = solution.maximumTotalDamage(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [[3, 2, 4, 2, 3, 3, 1, 3, 2]]
    want = 12
    got = solution.maximumTotalDamage(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [[67, 64]]
    want = 131
    got = solution.maximumTotalDamage(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [[10]]
    want = 10
    got = solution.maximumTotalDamage(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [[100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000, 100000]]
    want = 10000000
    got = solution.maximumTotalDamage(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

