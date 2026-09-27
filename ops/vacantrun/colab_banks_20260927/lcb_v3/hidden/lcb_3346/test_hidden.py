"""Scoring checks for lcb_3346 -- NOT part of any workspace.

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
    args = ['zbbz', 3]
    want = 'aaaz'
    got = solution.getSmallestString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = ['xaxcd', 4]
    want = 'aawcd'
    got = solution.getSmallestString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = ['lol', 0]
    want = 'lol'
    got = solution.getSmallestString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = ['pburzjfykzskvov', 572]
    want = 'aaaaaaaaaaaaaaa'
    got = solution.getSmallestString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = ['rmwtocuefgxvomcnjdbbxargvutrubukahwwqibfoutwrxddhhfoezgeejgogkzduvvwpkqpcdyegxxinlccmpoikfyobclpfbag', 1345]
    want = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
    got = solution.getSmallestString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = ['suznmyedrzifcfhtxrihjwhjdezdlewvggrkocveoejjloixzdrunxmldfvahahdwtqhbggudvyxuvdnrvaacydukvcosfjykfxb', 1534]
    want = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
    got = solution.getSmallestString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = ['aaaaaaaaaa', 1496]
    want = 'aaaaaaaaaa'
    got = solution.getSmallestString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = ['x', 1]
    want = 'w'
    got = solution.getSmallestString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = ['bnbotldjwlxkdlpipnkcbqgiirhcodvbdwjbzfpydubvoksrddvfmobcbljlvtzkugdfqjtcqasckzicpiijexedcamrjfrfoqsa', 1464]
    want = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
    got = solution.getSmallestString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = ['zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz', 658]
    want = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
    got = solution.getSmallestString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = ['polopokkpnmmnknmnnomkkmnnmnplpmklplpklnmnpppklnkplpookmolmpomkpnpnpmonoppoomolomkmlomlllmmlkomkmnlmo', 1146]
    want = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaak'
    got = solution.getSmallestString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = ['sptqicfahmkrrbjnwrjceswuohkxqwzvslqyaespruflavqcejjukkvufgmlsbwmwfkcxzghgnkflybumnekruqgclznqsuirgni', 0]
    want = 'sptqicfahmkrrbjnwrjceswuohkxqwzvslqyaespruflavqcejjukkvufgmlsbwmwfkcxzghgnkflybumnekruqgclznqsuirgni'
    got = solution.getSmallestString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = ['abzabzabzabzabzabz', 100]
    want = 'aaaaaaaaaaaaaaaaaa'
    got = solution.getSmallestString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = ['ababccbcaaacaaaacacb', 10]
    want = 'aaaaaaaaaaabaaaacacb'
    got = solution.getSmallestString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = ['mmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmm', 100]
    want = 'aaaaaaaaimmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmmm'
    got = solution.getSmallestString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = ['rcpkftfkeewunadktrxnpfavhtngegfbnkloekfvhpymvxzypygvifwdtrarxeubzlvbopahesdvblnrzbirgdpwyqatpqjslaer', 1617]
    want = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
    got = solution.getSmallestString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = ['oblulgsbrzdtncxuimydzqywqzxalphmvwnrlpzlthslflppbrllghxbgegpelhaeqfyvkqhrnudbzeqezeaknhjixyynzpifgmd', 1624]
    want = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
    got = solution.getSmallestString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = ['zazazzazza', 50]
    want = 'aaaaaaaaaa'
    got = solution.getSmallestString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = ['itwsojztabhosrilekusigrxcmdihkyzmadwwagnpcjroonkdudiaqsktjaopcqlhtbanhhvlssgrkmqshbjiusfbnslcfzkqgud', 1837]
    want = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
    got = solution.getSmallestString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = ['dyvtouyqwmaumnroabtsoybbiqqjdiduolhjbuwzaiwpidtooizrnzzpcvtxnxsruozdpozsjmmahfulkosgyiidcduajtikoxwy', 500]
    want = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaabahfulkosgyiidcduajtikoxwy'
    got = solution.getSmallestString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = ['ogqsssbqykgyoiouyfflxdfoukxzajzchggmuhqxzgshtragvjn', 1468]
    want = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
    got = solution.getSmallestString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = ['a', 26]
    want = 'a'
    got = solution.getSmallestString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = ['xxzyxxxzyz', 1]
    want = 'wxzyxxxzyz'
    got = solution.getSmallestString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = ['b', 1]
    want = 'a'
    got = solution.getSmallestString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = ['wjjqexhmvihjdqjtzknlytuabzsltupsddmghzhrdkwrkiynxnardgocffzmeskwezjlpzmvzvragnpycvokrgcmxerueqeppkdq', 1567]
    want = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
    got = solution.getSmallestString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = ['zxqgllipjsicrmktqkxiwyqctdvfsatbfyidytchsaamckmazkxokczzcvqvbjszskyegphdnumpqenxsjhezyhkmmbblbifcbth', 1371]
    want = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
    got = solution.getSmallestString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_27():
    args = ['zazazazaaazazazzazaaazazaaaaazzaazzzzzzazazzzazzaa', 10]
    want = 'aaaaaaaaaaaaaaaaaaaaaaazaaaaazzaazzzzzzazazzzazzaa'
    got = solution.getSmallestString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

