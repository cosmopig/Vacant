"""Scoring checks for lcb_3269 -- NOT part of any workspace.

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
    args = [[1, 2, 3, 4, 5, 6], [1, 1]]
    want = 4
    got = solution.countMatchingSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [[1, 4, 4, 1, 3, 5, 5, 3], [1, 0, -1]]
    want = 2
    got = solution.countMatchingSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [[81, 50], [-1]]
    want = 1
    got = solution.countMatchingSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [[7, 57, 88], [-1]]
    want = 0
    got = solution.countMatchingSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [[28, 53, 21], [0]]
    want = 0
    got = solution.countMatchingSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [[5, 47, 63, 48], [-1, 0]]
    want = 0
    got = solution.countMatchingSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [[46, 60, 80, 98, 90], [0, 1]]
    want = 0
    got = solution.countMatchingSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [[9, 83, 77, 75, 39, 32, 68, 60], [0]]
    want = 0
    got = solution.countMatchingSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [[73, 26, 7, 20, 30, 48, 97], [-1, 1]]
    want = 1
    got = solution.countMatchingSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [[17, 19, 71, 21, 2, 24, 29], [0, -1, 0]]
    want = 0
    got = solution.countMatchingSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [[88, 35, 41, 84, 38, 30, 87, 7], [0, 1, 0, 1, -1, 1]]
    want = 0
    got = solution.countMatchingSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [[73, 34, 14, 60, 77, 97, 54, 63], [-1, 1, 0, -1, -1, 0]]
    want = 0
    got = solution.countMatchingSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [[501399232, 959315981, 630569939, 369992778, 762747706, 678500115, 290334310, 666493456, 207228447, 367090709, 710041308, 135377803, 814213426, 969179920, 869845371, 276379138, 120760857, 852013521, 967284240, 76906837, 464555393, 865016650, 788827506, 750075661, 847293256, 74072686, 273445644, 611123245, 679977255, 717345474, 672117374, 280314168, 18176283, 651591389, 946339492, 884013286, 863214339, 121877045, 936428905, 749504839, 49112178, 961728742, 118501222, 442201631, 950793264, 180831825, 51869751, 502194993, 826181405, 198659336, 587636696, 222864939, 623098844, 210888296, 398223150, 59909422, 352052866, 429669422, 64797567, 780553664, 286945028, 289350308, 607115484, 416826628, 227986024, 665979338, 938728931, 385600482, 799076139, 408699336, 456756072, 482748621, 879865330, 493872639, 393551506, 925116932, 981007406, 454780366, 652424028, 991421291, 166830803, 484315076, 907419950, 875405057, 939199322, 153628762, 967592872, 419748504, 797841033, 533613156, 763571640, 462980381, 865162358, 906034855, 973792201, 150079861, 982936258, 499336540, 384170831, 15599924], [1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1]]
    want = 0
    got = solution.countMatchingSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [[131844005, 503539488, 895277194, 759135098, 222859496, 417206297, 93592988, 652746849, 668575746, 426968159, 90365765, 524804995, 424162038, 852071046, 595357210, 495180102, 671676834, 876299439, 994737405, 627163327, 244830313, 602073054, 300741633, 718338014, 289606104, 39647787, 321603458, 111918550, 601078319, 225088907, 103288961, 512810211, 257054465, 258736734, 792225867, 940177318, 176181969, 463804773, 936882278, 82890317, 212577344, 883127335, 158830242, 839256780, 413346255, 235128553, 309360347, 183335816, 935094040, 716290736, 242939618, 768597219, 867126752, 588146428, 708144623, 744416831, 646490848, 591132747, 896874946, 708473731, 653644741, 988864797, 684605163, 632823994, 860471013, 156163540, 457954345, 621980039, 553883429, 973856399, 847853262, 301416141, 67641836, 343357596, 428499293, 259578322, 344728849, 561456318, 273243699, 788203584, 350552917, 808682861, 788006599, 961916298, 480628920, 117333757, 572805397, 941296324, 914575507, 789429393, 373909251, 1504179, 335023081, 404799938, 519327858, 749008948, 355046964, 375123262, 858160530, 666369522], [1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1, 1, -1]]
    want = 0
    got = solution.countMatchingSubarrays(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

