"""Scoring checks for lcb_2854 -- NOT part of any workspace.

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
    args = [['aa', 'ab', 'bc']]
    want = 4
    got = solution.minimizeConcatenatedLength(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [['ab', 'b']]
    want = 2
    got = solution.minimizeConcatenatedLength(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [['aaa', 'c', 'aba']]
    want = 6
    got = solution.minimizeConcatenatedLength(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [['pg']]
    want = 2
    got = solution.minimizeConcatenatedLength(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [['ewx']]
    want = 3
    got = solution.minimizeConcatenatedLength(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [['f', 'yqtiz']]
    want = 6
    got = solution.minimizeConcatenatedLength(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [['nunc', 'rfp', 'ikd', 'x']]
    want = 11
    got = solution.minimizeConcatenatedLength(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [['k', 'vpjyt', 'd', 'y', 'pc']]
    want = 10
    got = solution.minimizeConcatenatedLength(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [['w', 'suavw', 'vnbk', 'jk', 'elf']]
    want = 14
    got = solution.minimizeConcatenatedLength(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [['ywwz', 'raew', 'uvurj', 'hfge', 'u']]
    want = 17
    got = solution.minimizeConcatenatedLength(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [['psqybl', 'meyko', 'uokz', 'f', 'mudt']]
    want = 20
    got = solution.minimizeConcatenatedLength(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [['c', 'p', 'ypbja', 'waygf', 'mtj', 'mkd']]
    want = 18
    got = solution.minimizeConcatenatedLength(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

