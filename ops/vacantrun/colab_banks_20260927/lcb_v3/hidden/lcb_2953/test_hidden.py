"""Scoring checks for lcb_2953 -- NOT part of any workspace.

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
    args = [[[1, 2], [4, 2], [1, 3], [5, 2]], 5]
    want = 2
    got = solution.countPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[[1, 3], [1, 3], [1, 3], [1, 3], [1, 3]], 0]
    want = 10
    got = solution.countPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[[6, 96], [62, 22]], 0]
    want = 0
    got = solution.countPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[[39, 22], [17, 27]], 10]
    want = 0
    got = solution.countPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[[3, 1], [9, 0], [1, 4], [5, 8]], 10]
    want = 0
    got = solution.countPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[[109993, 29527], [274048, 742026]], 0]
    want = 0
    got = solution.countPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[[884216, 802714], [478635, 472]], 100]
    want = 0
    got = solution.countPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[[138524, 577595], [931128, 361063]], 10]
    want = 0
    got = solution.countPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[[269067, 257118], [152599, 914513]], 100]
    want = 0
    got = solution.countPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[[2751, 4283], [9663, 7297], [9680, 3711], [3170, 2757], [7986, 7779]], 0]
    want = 0
    got = solution.countPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[[5424, 3975], [4477, 5052], [9562, 7307], [7663, 3016], [9943, 3484]], 1]
    want = 0
    got = solution.countPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[[693, 673], [903, 816], [539, 194], [786, 661], [938, 668], [194, 230]], 50]
    want = 0
    got = solution.countPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [[[3, 6], [6, 4], [10, 10], [8, 10], [8, 3], [0, 0], [10, 5], [1, 7], [3, 4], [1, 3]], 100]
    want = 0
    got = solution.countPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [[[5, 7], [1, 3], [5, 8], [3, 5], [7, 4], [6, 9], [8, 7], [4, 9], [7, 2], [2, 8], [6, 8], [0, 8]], 10]
    want = 0
    got = solution.countPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [[[322062, 94756], [405071, 606085], [351599, 748352], [38681, 474455], [500598, 489545], [305514, 274175]], 50]
    want = 0
    got = solution.countPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [[[47, 997], [832, 987], [252, 940], [864, 929], [813, 461], [700, 805], [583, 147], [581, 777], [798, 750]], 1]
    want = 0
    got = solution.countPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [[[8136, 8400], [1883, 1993], [3946, 2016], [4499, 5227], [9222, 2985], [2947, 2546], [2051, 1163], [6055, 1475]], 100]
    want = 0
    got = solution.countPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [[[3943, 3940], [6164, 9104], [5204, 9768], [981, 3797], [7734, 303], [1884, 4759], [5318, 2230], [6522, 9801], [6087, 5607]], 10]
    want = 0
    got = solution.countPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [[[461237, 588787], [837691, 986668], [468066, 809127], [181999, 258915], [129665, 346625], [788111, 754215], [665009, 176754]], 1]
    want = 0
    got = solution.countPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [[[7, 3], [7, 6], [6, 1], [6, 9], [6, 2], [4, 0], [2, 7], [5, 5], [10, 7], [6, 4], [8, 6], [2, 0], [9, 0], [4, 10], [3, 2], [10, 3], [10, 0]], 0]
    want = 0
    got = solution.countPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [[[7131, 2202], [4906, 9243], [8147, 9525], [4696, 4640], [5250, 2520], [6593, 3517], [7071, 9490], [7437, 5681], [9313, 9564], [8180, 8855]], 50]
    want = 0
    got = solution.countPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [[[949, 143], [764, 199], [243, 626], [347, 671], [976, 234], [241, 647], [101, 344], [974, 715], [912, 9], [925, 44], [594, 705], [907, 954]], 14]
    want = 0
    got = solution.countPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [[[59, 95], [70, 91], [75, 12], [75, 54], [70, 34], [32, 95], [49, 18], [39, 94], [33, 55], [0, 87], [9, 67], [79, 82], [42, 56], [17, 44], [78, 14], [20, 81]], 10]
    want = 0
    got = solution.countPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = [[[754855, 914971], [914204, 82396], [232772, 13204], [172108, 629412], [118706, 916079], [686800, 371210], [985253, 886619], [371055, 532354], [617332, 496687], [721327, 26609]], 1]
    want = 0
    got = solution.countPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = [[[50219, 179531], [912767, 406014], [325006, 857152], [636930, 834887], [729823, 347128], [337631, 359243], [914357, 154696], [404260, 821185], [800785, 61649], [333739, 653211]], 0]
    want = 0
    got = solution.countPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = [[[571032, 398444], [845554, 885697], [746130, 544752], [243439, 849536], [371179, 125066], [519891, 859887], [711973, 847658], [337107, 276628], [331485, 19101], [197332, 243833]], 100]
    want = 0
    got = solution.countPairs(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

