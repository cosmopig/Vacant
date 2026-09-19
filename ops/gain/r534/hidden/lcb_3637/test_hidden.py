"""Scoring checks for lcb_3637 -- NOT part of any workspace.

⚠ 這個檔案是計分用的 GT。它住在 ops/gain/r534/hidden/ 這棵**另外的樹**裡，
  永遠不複製進 agent 的工作區；任何把它的內容（含失敗訊息）回饋給模型的路徑
  都是 R534 的紅線。

case 組成 ＝ 題庫的 `visible_tests` ＋ `hidden_tests`（超集），與
vacant/codebench.py::LiveCodeBenchLoader 的 `hidden_check` 逐字同一組，
所以算出來的分子與 runs/g_r460_harness_lcb2_*／runs/g_r532_lcb2_* 的
`meets_demand` 是同一把尺。
"""

import solution

def _aeq(a, b):
    """與 vacant/codebench.py::_lcb_check_code 的 __aeq 同一套判等（逐行對應）。"""
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
    args = ['123']
    want = 2
    got = solution.countBalancedPermutations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = ['112']
    want = 1
    got = solution.countBalancedPermutations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = ['12345']
    want = 0
    got = solution.countBalancedPermutations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = ['0190035257658904724000542508409803242234436653967811672494672303090861917917356']
    want = 710223309
    got = solution.countBalancedPermutations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = ['431152516293932449441706638057530553442896017919031182068882200666309714667766']
    want = 458967982
    got = solution.countBalancedPermutations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = ['6775138823146607027059975826014800440585453041346326310462756081948238893588643']
    want = 0
    got = solution.countBalancedPermutations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = ['80055803262890813332135274422972250668495372524036135400623161297536985292749194']
    want = 923508197
    got = solution.countBalancedPermutations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = ['99999999999999999999999999999999999999999999999999999999999999999999999999999999']
    want = 1
    got = solution.countBalancedPermutations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = ['23']
    want = 0
    got = solution.countBalancedPermutations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = ['25']
    want = 0
    got = solution.countBalancedPermutations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = ['21']
    want = 0
    got = solution.countBalancedPermutations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = ['24']
    want = 0
    got = solution.countBalancedPermutations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = ['16']
    want = 0
    got = solution.countBalancedPermutations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = ['28']
    want = 0
    got = solution.countBalancedPermutations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = ['35']
    want = 0
    got = solution.countBalancedPermutations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = ['15']
    want = 0
    got = solution.countBalancedPermutations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = ['0848304430197011230489227679661082774027310203122082449885741743619920982758530']
    want = 407658119
    got = solution.countBalancedPermutations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = ['0562057596273341019714591233533645521604031587888067223824119583439733612632868']
    want = 709233020
    got = solution.countBalancedPermutations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = ['32']
    want = 0
    got = solution.countBalancedPermutations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = ['31']
    want = 0
    got = solution.countBalancedPermutations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = ['10']
    want = 0
    got = solution.countBalancedPermutations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = ['13']
    want = 0
    got = solution.countBalancedPermutations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = ['85732999540009697256207998098927971700963266979132717350106850822888110553396226']
    want = 19853391
    got = solution.countBalancedPermutations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = ['17']
    want = 0
    got = solution.countBalancedPermutations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = ['22']
    want = 1
    got = solution.countBalancedPermutations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = ['62082795085990152011621293661553196317066639314756128596765414910657205764969762']
    want = 0
    got = solution.countBalancedPermutations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_27():
    args = ['18']
    want = 0
    got = solution.countBalancedPermutations(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

