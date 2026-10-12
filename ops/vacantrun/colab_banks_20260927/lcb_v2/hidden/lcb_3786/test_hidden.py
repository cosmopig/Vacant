"""Scoring checks for lcb_3786 -- NOT part of any workspace.

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
    args = ['abced', 2]
    want = 3
    got = solution.longestPalindromicSubsequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = ['aaazzz', 4]
    want = 6
    got = solution.longestPalindromicSubsequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = ['aut', 3]
    want = 2
    got = solution.longestPalindromicSubsequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = ['gd', 1]
    want = 1
    got = solution.longestPalindromicSubsequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = ['sgkvtpfhzaqqcpqurwtqstflvuejhauizysxckogelgdqynxdkqhexxpsdqoikugqafyvfmfulakvbtzxzampusrkbuae', 98]
    want = 75
    got = solution.longestPalindromicSubsequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = ['y', 2]
    want = 1
    got = solution.longestPalindromicSubsequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = ['mda', 18]
    want = 3
    got = solution.longestPalindromicSubsequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = ['a', 1]
    want = 1
    got = solution.longestPalindromicSubsequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = ['abababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababab', 189]
    want = 200
    got = solution.longestPalindromicSubsequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = ['sk', 13]
    want = 2
    got = solution.longestPalindromicSubsequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = ['y', 11]
    want = 1
    got = solution.longestPalindromicSubsequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = ['uzfmbdvwujewribdgfbebndxfloifvxzjpcspkvnpbacihvldfkobtuvbbyndprbbhlxduzeegkipmjerjtwlpwohcjsbijk', 67]
    want = 69
    got = solution.longestPalindromicSubsequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = ['jixbqrflevtrkjrayzqdgjwwvxyjrtunnzhboevkodqvxdxndhiohvlwjaxposzgtroesslejvnjnyssnxknpxoorguao', 64]
    want = 67
    got = solution.longestPalindromicSubsequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = ['eoaomoywvhgftyeadslggdpdsowqyuinzginteozwrpoeuxbaqlx', 87]
    want = 48
    got = solution.longestPalindromicSubsequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = ['eq', 23]
    want = 2
    got = solution.longestPalindromicSubsequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = ['n', 10]
    want = 1
    got = solution.longestPalindromicSubsequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = ['alr', 5]
    want = 1
    got = solution.longestPalindromicSubsequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = ['s', 8]
    want = 1
    got = solution.longestPalindromicSubsequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = ['gyyygdukgyrcgydpotkezwnrzpkxiqgxeoncnjsxckvmvuodbibbgoevgkcjinturopgnaomhvhmrqucfewpvolcqnvmeq', 45]
    want = 63
    got = solution.longestPalindromicSubsequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = ['vd', 10]
    want = 2
    got = solution.longestPalindromicSubsequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = ['zyxwvutsrqponmlkjihgfedcbazyxwvutsrqponmlkjihgfedcbazyxwvutsrqponmlkjihgfedcbazyxwvutsrqponmlkjihgfedcbazyxwvutsrqponmlkjihgfedcbazyxwvutsrqponmlkjihgfedcbazyxwvutsrqponmlkjihgfedcbazyxwvutsrqponmlkji', 34]
    want = 47
    got = solution.longestPalindromicSubsequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = ['yr', 15]
    want = 2
    got = solution.longestPalindromicSubsequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = ['ctwwaozjgjjinhfldoftqbgwhtxnlyianmqzfzxikumijtrkcjzmpvniueqpttsnykbpjjulpassurpgzqvygxhnkwuxbvqitz', 50]
    want = 68
    got = solution.longestPalindromicSubsequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = ['ndfwchtqjxxomjirkhvhqpdcvdkwdstvmuzulbexnrefduegggwxuhdtzqhzwafhuorqeyzwaxhcogqqcdnsxaadyydrsoyvuwmm', 149]
    want = 88
    got = solution.longestPalindromicSubsequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = ['l', 76]
    want = 1
    got = solution.longestPalindromicSubsequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = ['z', 14]
    want = 1
    got = solution.longestPalindromicSubsequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

