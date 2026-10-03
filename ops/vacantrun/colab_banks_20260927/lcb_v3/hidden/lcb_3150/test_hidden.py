"""Scoring checks for lcb_3150 -- NOT part of any workspace.

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
    args = ['100011001', 3]
    want = '11001'
    got = solution.shortestBeautifulSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = ['1011', 2]
    want = '11'
    got = solution.shortestBeautifulSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = ['000', 1]
    want = ''
    got = solution.shortestBeautifulSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = ['10', 2]
    want = ''
    got = solution.shortestBeautifulSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = ['011', 3]
    want = ''
    got = solution.shortestBeautifulSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = ['0111', 4]
    want = ''
    got = solution.shortestBeautifulSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = ['1001', 3]
    want = ''
    got = solution.shortestBeautifulSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = ['0001', 4]
    want = ''
    got = solution.shortestBeautifulSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = ['00001', 5]
    want = ''
    got = solution.shortestBeautifulSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = ['00110', 4]
    want = ''
    got = solution.shortestBeautifulSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = ['011000', 1]
    want = '1'
    got = solution.shortestBeautifulSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = ['11111', 5]
    want = '11111'
    got = solution.shortestBeautifulSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = ['00011100010011000101001100010111000010010000010111000110111001101011111001000110000000101110', 36]
    want = '1110001001100010100110001011100001001000001011100011011100110101111100100011'
    got = solution.shortestBeautifulSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = ['10000011110011001011110000100010100111010011101111011110110101111010111110111001010101001110110', 50]
    want = '1100101111000010001010011101001110111101111011010111101011111011100101010100111011'
    got = solution.shortestBeautifulSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = ['0101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101', 50]
    want = '101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101010101'
    got = solution.shortestBeautifulSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

