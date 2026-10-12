"""Scoring checks for lcb_3692 -- NOT part of any workspace.

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
    args = ['abaacbaecebce', 'ba*c*ce']
    want = 8
    got = solution.shortestMatchingSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = ['baccbaadbc', 'cc*baa*adb']
    want = -1
    got = solution.shortestMatchingSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = ['a', '**']
    want = 0
    got = solution.shortestMatchingSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = ['madlogic', '*adlogi*']
    want = 6
    got = solution.shortestMatchingSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = ['tbjzlwrnyowcqq', 'rnyo**w']
    want = 5
    got = solution.shortestMatchingSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = ['abc', '*d*']
    want = -1
    got = solution.shortestMatchingSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = ['srs', 'r**s']
    want = 2
    got = solution.shortestMatchingSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = ['yglralsgqsucy', 'lrals**']
    want = 5
    got = solution.shortestMatchingSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = ['jsytevwz', 'j*v*']
    want = 6
    got = solution.shortestMatchingSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = ['mnfpmxvmdkmivqahndjr', 'p*mxv*iv']
    want = 10
    got = solution.shortestMatchingSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = ['otqqkeeycttc', 'ot*qqkee*ycttc']
    want = 12
    got = solution.shortestMatchingSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = ['iyqpfgvisrc', 'visr**']
    want = 4
    got = solution.shortestMatchingSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = ['vxiqejqngivjlaqnlab', 'vxiqej*la*ab']
    want = 19
    got = solution.shortestMatchingSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = ['kvwaqq', 'kv*w*']
    want = 3
    got = solution.shortestMatchingSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = ['qwaxulodslq', 'ax*lod*sl']
    want = 8
    got = solution.shortestMatchingSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = ['ltallsvasteokhxmv', 'lta*ll*eo']
    want = 12
    got = solution.shortestMatchingSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = ['wybakrgjn', 'wyb**jn']
    want = 9
    got = solution.shortestMatchingSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = ['cvtrmfmvuhzncqffl', 'fl**']
    want = 2
    got = solution.shortestMatchingSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = ['uwkpnqhynsedqqgdw', 'k**edq']
    want = 11
    got = solution.shortestMatchingSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = ['vacbudlhfpq', 'acb*lh*pq']
    want = 10
    got = solution.shortestMatchingSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = ['j', 'j**']
    want = 1
    got = solution.shortestMatchingSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = ['lxrfchoowqtpt', 'lx**hoo']
    want = 8
    got = solution.shortestMatchingSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = ['wmcxykodwzcahdri', 'mc**zcahd']
    want = 13
    got = solution.shortestMatchingSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = ['vctrpbs', 'vc*trpb*']
    want = 6
    got = solution.shortestMatchingSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = ['jyhpbbpund', 'bbp*un*']
    want = 5
    got = solution.shortestMatchingSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = ['mmkbuwtspzbmlpwn', 'buw*t*']
    want = 4
    got = solution.shortestMatchingSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_27():
    args = ['hy', 'h**']
    want = 1
    got = solution.shortestMatchingSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_28():
    args = ['fkjfpyogpwrf', 'py**']
    want = 2
    got = solution.shortestMatchingSubstring(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

