"""Scoring checks for lcb_3354 -- NOT part of any workspace.

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
    args = ['???']
    want = 'abc'
    got = solution.minimizeStringValue(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = ['a?a?']
    want = 'abac'
    got = solution.minimizeStringValue(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = ['y']
    want = 'y'
    got = solution.minimizeStringValue(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = ['?zfhmdpp??ob??g?wlhy?????b??xj??????j???gh???b?ei?pmqbm?????a?z??n?a???l??n?i?e??ru?qzl???v?mtk?bm??']
    want = 'azfhmdppacobccgcwlhydddeebffxjfgghiijjjkghkklbneinpmqbmooopqaqzrrnrassslstntiteuuruvqzlvwwvxmtkxbmyy'
    got = solution.minimizeStringValue(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = ['?r?o?a?e?h?p?g?c?j?b?m?n?y?h?p?i?a?g?z?o?x?u?s?n?i?q?b?s?k?r?s?s?u?a?o?m?t?r?s?h?a?t?r?z?q?z?u?x?l?u']
    want = 'brbocacechdpdgdcdjebemenfyfhfpfigagghzioixjujsjnkikqkblslklrmsmsnunaoopmptqrqsthtavtvrvzwqwzwuxxylyu'
    got = solution.minimizeStringValue(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = ['?fbvzwnll?']
    want = 'afbvzwnllc'
    got = solution.minimizeStringValue(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = ['ounuyppurycu?zwtcbamkljrfvltttqrmheuohgmbbfnoomihbtn?kejefxhndpkmz']
    want = 'ounuyppurycuazwtcbamkljrfvltttqrmheuohgmbbfnoomihbtnskejefxhndpkmz'
    got = solution.minimizeStringValue(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = ['c?boygcfznkvzealctoukmpbbfqyt?wzudxd?lhpbfgdjtzyqitekmrrjihxlcrblyvxeuewqlizynvosesdiajkngrnl?nyp?hzxvyeiibikeu?mnlrslytgbfcwuwzvcuwhz?xupmedfdjytja?lfsgewmvimltcu?xempnrnnpzzvuakgofcygpherssxxtucnwbgqxukbbhysyrxdigfjeucqpypfcyvybjnybx?qngzh?azwbohyyyhqgtcaqzwnxaeivhvucamboifuqlklsgtv?zewyaqvtrcjiiluteeaix?cydpkzzpdvsjdweb?krcillealgo?i?eytjpwtrhsedhyvhqfacqlykhiffgmhwkduzhs?rod?fwdyom?oupsncjtfqy?yjyhbxye?wdzafiwjaqapsqzhszrluhmmvcltevnsbemamknsdxrfmtrpitqvchqonmhirollylocuwtivgaekknbjoqeknwabnmkuvmohunoaefujtfcmgqwjsdycqydlsmkq??ydbcemycxtgvpcvncfrsdx?wuausknmnylm?eqzyq?zbbzoczwqbaplsfzxtshwhgtsillijajgdppmvllpxgisnmtpifwsncbubnov?tudjrguvlvrepmkbrbwmfbccpalrjtzzzrjwjojoo?strjdgz?otdyeou?baiqpfdtwbhijh?nrxqo?sijlxsyjsu?selyriqhitvydazj?jvfrv?gouclmjwb??qoadgmhtjndqbxmbwocoktjcrxfxooymmkospgn?gajdjxnygtetlgmdastxmvcau??qyc?rfmwreebtwjjsgyjlqkvagkmigyydtqqklnpyxmeiwcyfdt?zeargufagndhuwosoydlnhpimbvqrsfbfllajpnfgjthrpj?bczqocqhuqkqckpnflbrzgsxwzkgjcuboydaylfkcjyfuigbjdasrjiztjtobeakkn?z']
    want = 'caboygcfznkvzealctoukmpbbfqytdwzudxdflhpbfgdjtzyqitekmrrjihxlcrblyvxeuewqlizynvosesdiajkngrnlfnyphhzxvyeiibikeuhmnlrslytgbfcwuwzvcuwhzhxupmedfdjytjahlfsgewmvimltcuhxempnrnnpzzvuakgofcygpherssxxtucnwbgqxukbbhysyrxdigfjeucqpypfcyvybjnybxiqngzhiazwbohyyyhqgtcaqzwnxaeivhvucamboifuqlklsgtvkzewyaqvtrcjiiluteeaixkcydpkzzpdvsjdwebkkrcillealgokikeytjpwtrhsedhyvhqfacqlykhiffgmhwkduzhskrodofwdyompoupsncjtfqypyjyhbxyepwdzafiwjaqapsqzhszrluhmmvcltevnsbemamknsdxrfmtrpitqvchqonmhirollylocuwtivgaekknbjoqeknwabnmkuvmohunoaefujtfcmgqwjsdycqydlsmkqppydbcemycxtgvpcvncfrsdxpwuausknmnylmpeqzyqrzbbzoczwqbaplsfzxtshwhgtsillijajgdppmvllpxgisnmtpifwsncbubnovrtudjrguvlvrepmkbrbwmfbccpalrjtzzzrjwjojoorstrjdgzvotdyeouvbaiqpfdtwbhijhvnrxqovsijlxsyjsuvselyriqhitvydazjwjvfrvwgouclmjwbwxqoadgmhtjndqbxmbwocoktjcrxfxooymmkospgnxgajdjxnygtetlgmdastxmvcauxxqycxrfmwreebtwjjsgyjlqkvagkmigyydtqqklnpyxmeiwcyfdtxzeargufagndhuwosoydlnhpimbvqrsfbfllajpnfgjthrpjxbczqocqhuqkqckpnflbrzgsxwzkgjcuboydaylfkcjyfuigbjdasrjiztjtobeakknxz'
    got = solution.minimizeStringValue(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = ['clbxzcywxmzohcrehnnautefdicxcizavtt?phv']
    want = 'clbxzcywxmzohcrehnnautefdicxcizavttgphv'
    got = solution.minimizeStringValue(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

