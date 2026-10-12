"""Scoring checks for lcb_3793 -- NOT part of any workspace.

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
    args = ['a', 'a']
    want = 2
    got = solution.longestPalindrome(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = ['abc', 'def']
    want = 1
    got = solution.longestPalindrome(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = ['b', 'aaaa']
    want = 4
    got = solution.longestPalindrome(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = ['abcde', 'ecdba']
    want = 5
    got = solution.longestPalindrome(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = ['ffcrxpxpmxfdoszudpstqnhioahnbn', 'kpdizmywliqvkqevumspsfvyhrs']
    want = 5
    got = solution.longestPalindrome(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = ['tn', 'but']
    want = 3
    got = solution.longestPalindrome(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = ['tqrkyvaknctsxieyobebofepsuu', 'tghyrqlytksmzybnfz']
    want = 7
    got = solution.longestPalindrome(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = ['a', 'b']
    want = 1
    got = solution.longestPalindrome(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = ['xg', 'c']
    want = 1
    got = solution.longestPalindrome(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = ['kz', 'z']
    want = 2
    got = solution.longestPalindrome(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = ['eeeeeeeeeeeeeeeeeeeeeeeeeeeeee', 'eeeeeeeeeeeeeeeeeeeeeeeeeeeeee']
    want = 60
    got = solution.longestPalindrome(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = ['d', 'rkw']
    want = 1
    got = solution.longestPalindrome(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = ['ukp', 'kr']
    want = 3
    got = solution.longestPalindrome(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = ['n', 'no']
    want = 2
    got = solution.longestPalindrome(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = ['l', 's']
    want = 1
    got = solution.longestPalindrome(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = ['x', 'wud']
    want = 1
    got = solution.longestPalindrome(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = ['aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaa']
    want = 58
    got = solution.longestPalindrome(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = ['dddddddddddddddddddddddddddddd', 'ddddddddddddddddddddddddddddd']
    want = 59
    got = solution.longestPalindrome(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = ['k', 'ez']
    want = 1
    got = solution.longestPalindrome(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = ['cccccccccccccccccccccccccccc', 'cccccccccccccccccccccccccccc']
    want = 56
    got = solution.longestPalindrome(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = ['ecvtyjghaxrmrvvaoqhkfvyvwdqqtd', 'ruxlmjztnjbvnjbcbfuypkh']
    want = 5
    got = solution.longestPalindrome(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = ['bbbbbbbbbbbbbbbbbbbbbbbbbbb', 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbb']
    want = 57
    got = solution.longestPalindrome(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = ['jp', 'few']
    want = 1
    got = solution.longestPalindrome(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = ['f', 'zzvz']
    want = 3
    got = solution.longestPalindrome(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = ['w', 'oliq']
    want = 1
    got = solution.longestPalindrome(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = ['rvx', 'wh']
    want = 1
    got = solution.longestPalindrome(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_27():
    args = ['ab', 'ba']
    want = 4
    got = solution.longestPalindrome(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_28():
    args = ['zzzzzzzzzzzzzzzzzzzzzzzzzzz', 'zzzzzzzzzzzzzzzzzzzzzzzzzz']
    want = 53
    got = solution.longestPalindrome(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

