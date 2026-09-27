"""Scoring checks for lcb_2755 -- NOT part of any workspace.

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
    args = ['leetscode', ['leet', 'code', 'leetcode']]
    want = 1
    got = solution.minExtraChar(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = ['sayhelloworld', ['hello', 'world']]
    want = 3
    got = solution.minExtraChar(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = ['d', ['u', 'siufp']]
    want = 1
    got = solution.minExtraChar(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = ['b', ['fbl', 'ohtht', 'imvacly']]
    want = 1
    got = solution.minExtraChar(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = ['puqlxn', ['egkxndna', 'tsqcrfkfp']]
    want = 6
    got = solution.minExtraChar(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = ['y', ['td', 'jbuy', 'cg', 'qvq', 'i']]
    want = 1
    got = solution.minExtraChar(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = ['efqv', ['u', 'jwk', 'wuic', 'sn', 'z']]
    want = 4
    got = solution.minExtraChar(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = ['mqsuxzkpzu', ['e', 'z', 'lxp', 'u', 'komf']]
    want = 6
    got = solution.minExtraChar(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = ['bhmjkaagpo', ['lwogxkjwi', 'dwyyk', 'ixdoqci']]
    want = 10
    got = solution.minExtraChar(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = ['ciupnp', ['ucv', 'form', 'ltp', 'vhxl', 's']]
    want = 6
    got = solution.minExtraChar(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = ['jiyoqmm', ['m', 'ymf', 'xhepz', 'tt', 'cyi']]
    want = 5
    got = solution.minExtraChar(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = ['mbj', ['aqohwcojivnjnznofgulaxiqftihsisnm', 'itbrxjzo', 'wiob', 'oqlnpypnx', 'ffgojqsmomnfcdtsuoqiylenbejeradapgenpgnstczo', 'zludwiwcxnsyoaamfrdcildyipdjoraztb', 'xegguwsldxamckxkpaqw', 'ctqmyibnclbwpdsftlzudoarlulvwcdvbbd', 'rgojereilhzxqepvmfrtrwisaoqwjwnsknkcel', 'evdzvkotezpgyztvrxmvsiyapcayhaddoxnfvcyvsbcxml', 'mldvpfjipcptrx', 'vnvyszhssmr', 'tqghcmpnesxvehhnotemhxkaorksmwdxpbegbmupbvrppfveup', 'frevdqpwyqqetjcsszbyzmatxsyefcitogxcburqvmeqspsn', 'glmgzdrpqlyjguqvwbklxaumaqvvz', 'lebgseljgxekhonifctg', 'tgtumrjjxyumpq', 'ipcyjocctgftqxuxmmbwysszstfufegrbkmsywv', 'cruejdahkjmhrgsglmfrdnnbzzexknlhq', 'qdpfaletimkozgrurarsodqkknytnospahpykhscmpk', 'yddbxxvssvckttktwajxcmafbng', 'yjhrgcyqwywtrblmzdcuqyebsoieirwt', 'qmvsyuoqpnwrubfipwzjonltempxvdfrnkahxtisfhjs', 'hdqebxgulymc', 'csiwkg', 'zmnstmxqqwyotpwnugqtmrxmlnbzxoiupyckryyhuzynb', 'ixymvtorvqgmmnstzvosnhaiyhrzy', 'orqxamcornjurbuaghqlkowcb', 'dxqsxcwihspcjburmbvjioweypgnukvyoieds', 'nlsqzqscrrvkmaap', 'bgmdhjdmgixnpo', 'hjqayflpwyjotfst', 'kdbvsrnjrmratcwgwtqoyylwtdvkjfjjdyftvyudyxpcyqj', 'mkepssstpbzlspwgrglqindkdseqfrssvlmgpbeo', 'mnolkutldjxkqmhrqgzxkwlhvcgmlxsrvrrqtmhordifwwmbkp', 'djpad', 'dpqsvcsxvlemrih', 'qfvbqfsklcsvsxhfqjbkqxbteltmtofbasqxeopbgnqbywfhen', 'hfhuij', 'hmsfhdpoxkkbjovzqkzdtldmwafaencjirlixtb', 'rtfoe', 'zdhehucpdgaunwpplulcujqrmakmybhhalaecuy', 'jpflebnsxlwaf', 'xzsgwvgadroxonehvydvhxxxfkhmdtcthtmlabnrrjewsjvywv', 'fkyeseggscxwalnkkiskmuwvkplurtd', 'umje', 'jybcfxsfdirehsgjqcuxcqcuimnk', 'fhwdfmbgkbitzwohgjgunthw', 'kyaaffmhdltdjsrxrjaisliytt', 'qjnthwumfajzvayoulaumleljqjmcukezkrwsdhxzjrgfgclgn']]
    want = 3
    got = solution.minExtraChar(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = ['rexdgbldkqagnhjtgqrwucgvpszptdgtpkqxfkx', ['xmtovslyjgukwdtuzuggxcoeuiubhafs', 'odzkzxetdwofsdjdrztpoudewvzqnfshshd', 'mgyvpoqjbarhl', 'fwfezbjsprkqmhcgtejyswairmxsr', 'znoomkfmiugmgxeynqyr', 'rdvwftwwulmwxiqaujvnigpvfotanyavmkzxgvpmlci', 'tkhlkoinqzhcggtajnvkxclkkunaayemhut', 'sslgksaadx', 'elwbfcmblryfbxjhwmjcjakyqxqdnkeaupwqq', 'nwkxtutpxbtfdjhhuafrhxirshsefroebfrsz', 'yplgszirpdtggzukhefeuijkskazqzuiptdkxtjwuqfbobft', 'mpnvlsbgmhymejxqip', 'ufrnaodzzvsmojambwyqhcrenvmfale', 'luvtziufzkuyapdxpbdoxqx', 'vkpuqkiltdzwqihhdqgdkbkkjd', 'otkatsdljdlvowczmjzsrracmvy', 'dngvvoosurh', 'slqwqsxkfhbdquxvxmiyzljhkqfruypldicrvofiyb', 'vxzffizdrvalasljaflkfmdkyhiujajywdws', 'ezafkwrpkvicpu', 'vlprarzfdazofgxxfauzuomwqcdprlscrk', 'enadudyaphvspklpekuslbiybploolpxctivccmbfjsfswf', 'wcgereyajkkuxalr', 'rcaoevngsav', 'dyhbayuoperlf', 'ykgjhysjctkatxcusdmlnzlzz', 'jrwkkqsmgnscsdlajqrisxdijgrhoykhxcimjkiei', 'bgftkmsxbfaxqptsvbz', 'apkhgmaatvhzpspnzvfeqjuvjtpbvtte', 'fsmgmiuhufzohsciugrabeotuqbndpoyjdig', 'vwkoainmgagcjaip', 'hywwdhxbqfczlapiqqwykpgzjjcmqnbuqwdnttgigoxr', 'dwlaixvaqtoqvxv', 'apgjwazbwcuvzdxrcoiteapteqmuifuvvvsrextwcfsw', 'gvplskmlmqqbvofflh', 'tmapjkngifoatrajdubmwbelkyvixhajeflte', 'igtyzmjeyoi', 'nsubkohodrzuonguazuzypnvmaxgzccwierloblk', 'pwdzlljjtreakegjpbtncjasd', 'jqycmhlxtnjnwmjzipdgcazlcjrxasvzg', 'dktgxdhcrh', 'ydeclbniwwmprfzlljnjlsyjmdzwzv', 'nrfunclxtcwjbhshbeqsqwcnlyksabltwevfxfxdfontgg', 'gomoigrilblzetisknchnyitqcbgsdvtqu', 'ppioiihsxvldgetsnxigerxartlefzjsmkxmkuc', 'wstgocouympxtkvxolavablsqikcaqae', 'hegxzlopldwjrerbrsyhgortgsekoz', 'ocwvzahflqh', 'jydejrjsjidqkolqjddfdkzjatukyxozpmqo', 'buizauqnmpj']]
    want = 39
    got = solution.minExtraChar(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = ['frickzggjkpukhvnxcobqspnnaalkjvpnmrhmzikjupzldsxb', ['gupaoxiattxtctlpcbylcdxfhflzatdmhtcyqzlwop', 'snuzxkpxvfixrcubmlnjpnhxdeaypnlldwhcynwojktkb', 'ahugmldkaeqxzdwpblcnbxuxfzrockdqlkepmbivvpwzpsjgj', 'ssudvtzsdlxgucfc', 'zlropnfwuk', 'smalwustqjpmqlrcebiywjybpxvrbbzppudyzsuxy', 'xhzeprgszlalakhpgheebeffmvbkkovsevdcyrhtoy', 'enpsvrbpuotowurid', 'pwtorgnpfzhqfzxebkqjaombegoflxbwapczhjcghn', 'wthiqdosebpaykuabxjhmwnclpzgrosukgwauyxoncedz', 'jigfyluhisbpueaazbxzrrmxolqmumnhktwx', 'fdxtgdgvhkvqeltzmqqammcfkulsmojzmgrjqhmpx', 'dxvadxnxzkdjwjkbtbspt', 'ryosapxpctp', 'shmbxsbkltyjwaijfgbwvwtwwkbqydqoxqgi', 'ubtpayhxhcfhicwyuovirbeuozgd', 'zgvkxbmuuxxhyxnolvhvuztzuhjuxofiloyh', 'qlqukjvcskpmqeelupigsxwxkzoonwkqccodlptrkfqqm', 'bbxvhxpyckenrwlhixibpibmyopkksnk', 'argpkriyzjvzngyox', 'dexpudzesjuhqcqnaeslpbxuazhxbjlgtxzafdmeymbzpt', 'nvuqxogssdmgmcbzclbjokzpttjksvzegncfrnzcfhbgz', 'vvtmbekmdngleiw', 'ooghwbrmvmjwuizyxvj', 'qhscxnolzy', 'dlwxogcqcjpgclyosimrqylswba', 'vldjsyvdxfyxbcjarutybsxupefivdjmzfbie', 'sdmndfatewuxaktpdsgqnjhlmruszmjgivbmfv', 'aaupkerrjuuezwwzwdliphyfkdipxpjpwqdlxncbxenffg', 'hdhgqqkqresuedcwszuxaiinxxw', 'vphmkpcdmefnczzmdhcvuxfoaitry', 'hwiaqevofxxpxmodbmltidvvfsqnwfqalnhlsknasrym', 'mjydjuaujfdcaobyzwzpcicdxeytbgtetzl', 'garglglzpjidikygnyyjzcquzp', 'wjkcpztilehufvwvoypfbrlatldogbzmhmfwgibcen', 'btkhsivugkhfkwqeekwunfqqzjfhmcuwwx', 'ahozkbyayeuuwxjjxpnjvltytwkatgquvaugcutqeaysnwov', 'sxgukbovzenlgszpxeadvaxf', 'msfihwysgviyutuib', 'bvkwjwlnsmabgercvii', 'bbgudafmuckeqyawmjwadnfzoe', 'lbamkrhpkqutpe', 'ccepppktrnvpuwxoyxckxosoh', 'uvrtzyqdgemtkvnvzubsrfhwjifxzzzmnccpmxfxrznkfi', 'rndozlawndnxjunbwivvagzpiqvzijvkic', 'mfkdbikynmidqgdingxfvgbzdjspq']]
    want = 49
    got = solution.minExtraChar(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

