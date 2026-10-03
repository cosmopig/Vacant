"""Scoring checks for lcb_3203 -- NOT part of any workspace.

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
    args = ['abcabc', [[1, 1, 3, 5], [0, 2, 5, 5]]]
    want = [True, True]
    got = solution.canMakePalindromeQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = ['abbcdecbba', [[0, 2, 7, 9]]]
    want = [False]
    got = solution.canMakePalindromeQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = ['acbcab', [[1, 2, 4, 5]]]
    want = [True]
    got = solution.canMakePalindromeQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = ['cu', [[0, 0, 1, 1]]]
    want = [False]
    got = solution.canMakePalindromeQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = ['mwpndnnien', [[2, 4, 8, 8]]]
    want = [False]
    got = solution.canMakePalindromeQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = ['lfsklvdqtmwslnnisijornobgn', [[6, 9, 14, 15]]]
    want = [False]
    got = solution.canMakePalindromeQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = ['urrklehdynrcarniwfkugrkahb', [[12, 12, 16, 18]]]
    want = [False]
    got = solution.canMakePalindromeQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = ['doxhnlmyjvznmy', [[1, 2, 11, 12], [3, 4, 7, 10]]]
    want = [False, False]
    got = solution.canMakePalindromeQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = ['miquuxtxrfkuxibkahgmaruvzuojqfksfrttatslulduldqgbjnbjutmsndpaesmzvompgxiwzxgakvynyoneapcxviqhyhkabpb', [[25, 28, 54, 59]]]
    want = [False]
    got = solution.canMakePalindromeQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = ['tqrnwfcasaqxpzfsjser', [[4, 9, 11, 15], [8, 9, 16, 19], [4, 9, 14, 16], [5, 7, 11, 17], [8, 8, 10, 17]]]
    want = [False, False, False, False, False]
    got = solution.canMakePalindromeQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = ['lvxdjdnghyyskemmlabrqxdqjhrs', [[0, 13, 27, 27], [1, 1, 27, 27], [7, 11, 23, 26], [2, 5, 17, 18], [9, 9, 21, 21]]]
    want = [False, False, False, False, False]
    got = solution.canMakePalindromeQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = ['tstklfxvhvlizq', [[1, 4, 7, 8], [1, 4, 10, 12], [3, 3, 11, 11], [0, 4, 10, 10], [1, 2, 11, 11], [3, 5, 13, 13]]]
    want = [False, False, False, False, False, False]
    got = solution.canMakePalindromeQueries(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

