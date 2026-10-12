"""Scoring checks for lcb_3588 -- NOT part of any workspace.

⚠ 計分用的 GT。住在 hidden/ 這棵**另外的樹**，永遠不複製進 agent 的工作區；
  任何把它的內容（含失敗訊息）回饋給模型的路徑都作廢那一批資料。

case 組成 ＝ 題庫的 `visible_tests` ＋ `hidden_tests`（超集），與
vacant_network/codebench.py::LiveCodeBenchLoader 的 `hidden_check` 同一組（ops/gain/data/lcb_bank_v1.jsonl）。
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
    args = ['FFF']
    want = 3
    got = solution.countWinningSequences(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = ['FWEFW']
    want = 18
    got = solution.countWinningSequences(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = ['F']
    want = 1
    got = solution.countWinningSequences(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = ['FFF']
    want = 3
    got = solution.countWinningSequences(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = ['FWFWFFFWWFEEEFFFEFWWFEFWFEFWEWFWEWFFFFWWWEWEEEEFEWFWEFWFFWEWEFWFEWFEEEFWFFFEEEWFWEFEFEFWWFWFFWWEEWEFWWWFEWEFWWWEFFFFEFEWFFWEWEFFWEEEFFWWEWFEWWFWWWWEWEWEEFFEEWWWFEEFWWFFFEEEFWWEEEFFWFWEWFEEEWFEWEEWEEEFFFWFWEWFFFFFWEWEWWWWWEWWWFEWWEWEEFWEEWWFEEFWWFEWWWFWWFFEFWEEEWWFWEEEFWWWFFWFFWFFEFWF']
    want = 516242703
    got = solution.countWinningSequences(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = ['WFE']
    want = 4
    got = solution.countWinningSequences(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = ['FWEWFEEWEEEEFEWEFFEFFFFEEEFWFFFFFFFFFEFFFEWWEEEFEEFFFFFFWEFWFFFFFFWFFWFFFFWFFEFFFWFFFWFWWFFFFEFEFFFWFFFFWWFFEFFFFFFFWWFFFFFEFFFEFFEFFFF']
    want = 757703704
    got = solution.countWinningSequences(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = ['EE']
    want = 2
    got = solution.countWinningSequences(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = ['FWF']
    want = 5
    got = solution.countWinningSequences(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = ['FFFWWFFWFWFFFFEFFEFFWFFFEFFFFFFEFFFWFWEFFFFFFFEFFWEFWEWFFFFEFEFFWFEWFFFEFFFFWFFFFFFEFWF']
    want = 106659328
    got = solution.countWinningSequences(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = ['FWWWFWFWWEEWFEFEWEFFFWWFEWWWWWWFEWEFFWEWFFWFWWWWFFWEWFEFFFEWEWFWWFEEFEEEFFEEFWEWFEFWEFEWFFFWEWEFFFWFFFFWWFFEFEWWFWWFWWWFEFFWWEWEEFEFFEFFFEFWEFEFEWFEEEEFWEEFWFEWWWWEEFEWFFWFEFEEFEEWEFWFWFEEEWWWEWFWFEFEFFEFWFWEFFWFEFFEFEWFWEFWWEEEWFFEWWFFWWEWWFEEEFEFWEWWWEFEFFEWEWFEWEWEFFFEEEWEWFWFEWFEWWFFEWFFWFFWFEEFFFWEEWFEEFWWFFEEFWWFFFEWEEFWFWEEWWFWEEEWWEEEEEEEEFWFWEEEWEWFEEEWEEEWEWWWWWWEWEEEEWEWFFWFEFEEEEWFWWEWWFEWWWFWFFEFWEWEEFFFWWEWFFEWFFEWEFEEWEWFEFWWFEEFWFEWFFWFWWEFEFFFFWEFWWEWWFEWEFWWWWWWFFEFEFEEWEEEEFEWEWWWFEFFFEEEFWFEFWFEWWEWWFEWEFFWWWWEEFWWFFWFFWWEEWFFEFEWEFWEEFFEFEEEWWWEEEWEWFFFEWFFWEFWWFFFFWFWFFEWWWEEWWEWEEFWWFFEWFEFFEWEWFWEEWWEFFWEFWFWFEFEWFEWEFWWWFWFFWFEEFWEEWFFFEEFWEFEFFWEEWFFEFEWEEFEWFEEFWEWFFEWFEWEWWWWEWWEEFEWWFEWEWWEWWEEWFWFFEEEEWWEEFWWWWFFFWWEEEEEWEWWFWEFWEFFWEFWFFWEFEEEEWFEFFFFFFWWWEEFWWEEWFEEFFFWFWFEEEEWEEWFEEFFEEFFEFWFEWEWEWFEWEEWWFEEEWWEEWEFFEWEEWEWWWEEWWWFWWFWFEWEWFEWWEEEWWEEFFWWWWWFFFFWWFFEWEWWEWEEEFFEWFEFWEWWFFEWWEWFWWEWEWEEEEEEEFWWEWFWFWEEWEEFFFWEWFFFWWFEFEWFWFFFEWFEWEFWFWEE']
    want = 323124361
    got = solution.countWinningSequences(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = ['FEE']
    want = 4
    got = solution.countWinningSequences(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = ['WWE']
    want = 4
    got = solution.countWinningSequences(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = ['FEW']
    want = 4
    got = solution.countWinningSequences(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = ['WWFEFWFWFEWWEFEFWFWEFFEWEWWEFEWWFEEEEFFFEWEFEFFWEWEWEWEWFEWWFEFWFWEFEEFWWFWWFFWWWWEEWEWWFEEEEEEWFEWWFEFEFEEWWWFWWWFWFEWEFFEWWWWFWWWWWFEEFEEFFFWEEEEFFWWEEFEWWFFEFWEWWEWWWEEWEWEEEEWWFWWEWWWFFEFFW']
    want = 786347194
    got = solution.countWinningSequences(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = ['WFF']
    want = 4
    got = solution.countWinningSequences(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = ['FEF']
    want = 6
    got = solution.countWinningSequences(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = ['FE']
    want = 2
    got = solution.countWinningSequences(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = ['FWFFFFFFFFFFFEFFWFEFWFFFFFWWFWEFEEFWWFEFEFFEFFFFFEFWWFFFWFWFFFFFFWEFFFFEWWWFEFFWFFFFFFFEEFFFEWEFEEFFFFFFF']
    want = 335667764
    got = solution.countWinningSequences(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = ['WEF']
    want = 4
    got = solution.countWinningSequences(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = ['EFFFFWEEFWWFWEWWWWEWEWFWWEEFEFEEEWEWWFWFEWFEWFFFFWFWEFEWEFWFWFEEFEEWFWWFWWEWEFWWWFFEWFEFWWEFFEEEEWEWWWWEWFEFEEEWFFWWEFEFEFWEWFWWEFFWFEEEWEWWWFEWFFWWFEFEWEEFWFFEEEWFWWEWFFEWEFWFEEFFWWWEWEEFEWWWWWWFFEEWWEEWFWWFFEEFEWFWEWFWFWW']
    want = 829877890
    got = solution.countWinningSequences(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = ['FW']
    want = 2
    got = solution.countWinningSequences(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = ['WWF']
    want = 5
    got = solution.countWinningSequences(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = ['FFFFFWFWFFFWFEWEEFEFFWEFFFEWEFFFFFFWFEFFFFEWFFFWFFFWFWEFFEFFFFEFFWFWEFFWFFFFFEFWFWWFWFEFFFFFFFFEFFWFEFFFWFFEFEFEFFFFFFEFFWFFF']
    want = 684215373
    got = solution.countWinningSequences(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = ['WWW']
    want = 3
    got = solution.countWinningSequences(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = ['WFW']
    want = 6
    got = solution.countWinningSequences(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

