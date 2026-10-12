"""Scoring checks for lcb_3482 -- NOT part of any workspace.

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
    args = ['abcdef', ['abdef', 'abc', 'd', 'def', 'ef'], [100, 1, 1, 10, 5]]
    want = 7
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = ['aaaa', ['z', 'zz', 'zzz'], [1, 10, 100]]
    want = -1
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = ['lbgishk', ['lbgishk'], [4]]
    want = 4
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = ['hfrlcks', ['hfrlcks', 'rlcks', 'k', 'hfrl'], [3, 14, 10, 13]]
    want = 3
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = ['twnpxyhva', ['pxyhva', 'twnpxyhva', 'wnpx'], [3, 19, 8]]
    want = 19
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = ['kcozfniglrpwbeumwwyknitonfmhldatrfsqdiyjlftfxhmvedsmjlfarutorurtoupgtvfgykumnqyyhskxxgvltcazkjjmfkwt', ['hldatrfsqdiyjlftfxhmveds', 'tvfgykumnqyyhskxxgvl', 'nqyyhskxxgvltcazkjjmfkwt', 'yjlftfxhmvedsmjlfarut', 'cazkjjmfk', 'gykumnqyyhskxxgvltcazkjjmfkwt', 'vfgykumnqyyhskxxgvltcazkjjmfkwt', 'cazkjjmfkwt', 'rutorurtoupgtvfgykumnqyyhskxxgvltcazkjjmfkwt', 'mjlfarutorurtoupgtvfgykumnqyyhskxxgvltcaz', 'umwwyknitonfmhldatrfsqdiyjlftfxhmvedsmjlfarutoru', 'rutorurtoupgtvfgykumnqyyhskxxgvltcazkjjmfkwt', 'mhldatrfsqdiyjlftfxhmvedsmjlfarutorurtoupgtvfgykumnqyyhskxxgvl', 'fniglrpw', 'torurtoupgtvfgykumnqyyhskxxgvltcazkjjmfkwt', 'utorurtoupgtvf', 'nitonfmhldatrfsqdiyjlftfxhmvedsmj', 'rfsqdiyjlftfxhmvedsmjlfarutorurto', 'tonfmhldatrfsqdiyjlftfxhmvedsmjlfarutorurtoupgtvfgyku', 'qyyhskxxgvltcazkjjmfkwt', 'vedsmjlfarutorurtoupgtvfgykumnqyyhskxxgvltcazkjjmfkwt', 'fkwt', 'vedsmjlfaruto', 'yyhskxxgvltcazkjjmfkwt', 'umnqyyhskxxgvltcazkjjmfkwt', 'rfsqdiyjlftfxhmvedsmjlfar', 'nqyyhskxxgvltcazkjjmfkwt', 'eumwwyknitonfmhldatrfsqdiyjlftfxhmvedsmjlfarutoru', 'hskxxgvltcazkjjmfkwt', 'kum', 'fmhldatrfsqdiyjlftfxhmvedsmjlf', 'rfsqdiyjlftfxhmvedsmjlfarutoru', 'xgvltcazkjjmfkwt', 'rtoupgtvfgykumnqyyhskxxgvltcazkjjmfkwt', 'vfgykumnqyyhskxxgvltcazkjjmfkwt', 'kwt', 'jlfarutorurtoupgtvfgykumnqyyhskxxgvltcazkjjmfkw', 'hskxxgvltcazkjjmfkwt', 'tcazkjjmfkwt', 'yjlftfxhmvedsmjlfarutorurtoupgtvfgykumnqyyhskxxgvltcazkjjmfkwt', 'zfniglrpwbeumwwyknitonfmhldat', 'tfxhmvedsmjlfarutorur', 'fniglrpwbeumwwyknitonfmhldatrfsqdiyjlftfxhmvedsmjlfarutorurtoupgtvfgykumnqyyhskxxgvltcazk', 'mfkwt', 'hldatrfsqdiyjlftfxhmvedsmjlfarutorurtoupgtvfgykumnqyyhs', 'hmvedsmjlfarutorurtoupgtvfgykumnqyyhskxxgvltcazkjjm', 'hskxxgvltca', 'datrfsqdiyjlftfxhmvedsmjlfarutorurto', 'fniglrpwbeumwwyknitonfmhldat', 'x', 'cozfniglrpwbeumwwyknitonfmhldatrfsqdiyjlftfxh', 'fxhmvedsmjlfarutorurtoupgtvfgykumnqyyhskxxgvltcazkjjmfkwt', 'fsqdiyjlftfxhmvedsmjlfarutorurtoupgtvfgykumnqyyhskxxgvltcazkjjmfkwt', 'fkwt', 'ltcazkjjmfkwt', 'yhskxxgvltcazkjjmfkwt', 'umwwyknitonfmhldatrfsqdiyjlftfxhmvedsmjlfarutorurtoupgtvfgykumnqyyhskxxgvltcazkjjmfkwt', 'wt', 'glrpwbeumwwyknitonfmhldatrfsqdiyjlftfxhmvedsmjlfarutorurtoupgtvfgykumnqyyhskxxgvltcazkjjmf', 'upgtvfgykumnqyyhskxxgvltcazkjjmfkwt', 'tonfmhldatrfsqdiyjlftfxhmvedsmjlfarutorurtoupgtvfgykumnqyyhskx', 'lfarutorurtoupgtvfgykumnqyyhskxxgvltcazkjjmfkwt', 'wwyknitonfmhldatrfsqdiyjlftfxhmvedsmjlfarutorurtoupgtvfgykumnqyyhskxxgvltcazkjjm', 'hskxxgvlt', 'mhldatrfsqdiyjlftfxhmvedsmjlfarutorurtoupgtvfgykumnqyyhskxxgvltcazkjjmfkwt', 'orurtoupgtvfgykumnqyyhskxxgvltcazkjjmfkwt', 'wyknitonfmhldatrfsqdiyjlftfxhmvedsmjlfarutorurtoupgtvfgykumnqyyhskxxgvl', 'eumwwyknitonfmhldatrfsqdiyjlftfxhmvedsmjlfarutorurtoupg', 'atrfsqdiyjlftfxhmvedsmjlfarutorurtoupgtvfgykumnqyyhskxxgvltcazkjjmfkwt', 'cazkjjmfkwt', 'rutorurtoupgtvfg', 'azkjjmfkwt', 'pgtvfgykumnqyyhskxxgvltcazkjjmfkwt', 'ykumnqyyhskxxgvltcazkjjmfkwt', 'urtoupgtvfgykumnqyyhs', 'orurt', 'ftfxhmvedsmjlfarutorurtoupgtvfgykum', 'jmfkwt', 'gvltcazkjjmfkwt', 'lftfxhmvedsmjlfarutorurtoupgtvfgykumnqyyhskxxgvltcazkjjmfkwt', 'yyhskxxgvltcazkjjmfkwt', 'pwbeumwwyknitonfmhld', 'ykumnqyyhskxxgvltcazkjjmfkwt', 'oupgtvfgyku', 'nqyyhskxxgvltcazkjjmfkwt', 'gvltcazkjjmfkwt', 'nfmhldatrfsqdiyjlftfxhmvedsmjlfarutorurtoupgtvfgykum', 'jlftfxhmvedsmjlfarutorurtoupgtvfgykumnqyyhskxxgvltcazkjjmfkwt', 'atrfsqdiyjlftfxhmvedsmjlf', 'kwt', 'umnqyyhskxxgvltcazkjjmfkwt', 'fgykumnq', 'fsqdiyjl', 'tvfgykumnqyyhskxxgv', 'beumwwyknitonfmhldatrfsqdiyjlftfxhmvedsmjlfarutorurtoupgtvfgykumnqyyhskxxgvltcazkjjmf', 'tcazkjjmfkwt', 'kcozfniglrpwbeumwwyknitonfmhldatrfsqdiyjlftfxhmvedsmjlfarutorurtoupgtvfgykumnqyy', 'yhskxxgvltcazkjjmfkwt', 'azkjjmfkwt', 'mhldatrfsqdiyjlftfxhmvedsmjlfarutorurtoupgtvfgykumnqyyhskxxgvltcazkjjmfkwt'], [699, 580, 581, 309, 228, 321, 112, 180, 29, 648, 720, 950, 210, 302, 571, 583, 695, 482, 373, 140, 468, 325, 937, 637, 739, 896, 656, 180, 652, 250, 394, 95, 401, 416, 988, 164, 150, 509, 698, 981, 584, 894, 8, 277, 20, 456, 356, 469, 856, 991, 397, 99, 22, 430, 789, 852, 98, 81, 101, 170, 371, 456, 640, 616, 711, 376, 818, 673, 17, 507, 174, 55, 608, 952, 39, 150, 476, 275, 955, 616, 291, 838, 718, 74, 64, 233, 186, 964, 383, 851, 223, 128, 445, 423, 513, 673, 278, 984, 418, 331]]
    want = 787
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = ['hwyix', ['w', 'i', 'hwyix'], [4, 5, 3]]
    want = 3
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = ['abcabc', ['abc', 'bc', 'a', 'b', 'c', 'ab', 'bcabc'], [3, 2, 1, 1, 1, 2, 5]]
    want = 6
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = ['jfpsqybyj', ['psqybyj', 'f', 'jf', 'j'], [7, 2, 7, 5]]
    want = 14
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = ['oykj', ['oykj'], [5]]
    want = 5
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = ['ababababab', ['ab', 'abab', 'babab'], [2, 2, 5]]
    want = 6
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = ['abcdef', ['abc', 'def', 'abcdef'], [1, 1, 100]]
    want = 2
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = ['ofaufttu', ['ofaufttu'], [4]]
    want = 4
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = ['mvcjwiysry', ['ysr', 'sry', 'wiys', 'jwi', 'y', 'm', 'iysr', 'y', 'cjwi', 'cjwiy'], [7, 2, 7, 1, 3, 8, 9, 7, 7, 4]]
    want = -1
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = ['ababababababababababababababab', ['ab', 'abab', 'babab'], [2, 5, 4]]
    want = 30
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = ['tioiqusvdjrmyemjupyjaglowitghyyncpwnxuonoduyvaqhmzikqliupazztwgkrzfpegjgolmxqkzokjomvwpardvkcoubkthsqojcjalqzdvgmjafnuhirpfqadpbgabfvzllidmrntyscmnajnbxnowufqgececdaeyqtjnancdkymkatfojraohwirxqsodpfqlbvikjsiixuqjldicgfkcwnajhrxowfzegqztplktbrfempwjvsrgydnapzxxmboptlpizrxmkcmbiylvkpstvvggymjnimayxhkkllbqnbgfdavleqhqwhmksvaondwjsbfkjunpjhsbxervfpegocqlnoyvtxgytrowzrzpcoohleezulnkzdinhtyizxgkbzqiqstbaxmmhpaweqpjmefjngmmkhpyqunhstxipegtamttxeadetjsxucavilnyvqntgztjgdubszusaksdhtrezewzpgblqyembnqntpecioiiafgzvwkgccyvnltjhazzyfnicskgsglsgfzfmqetsyqkklncrzcluvdwcjajsthflotyfcnptuhryhcewfdcyrzdircixfasgpzhozasmslr', ['punhmyukaoedwyjlzoabkbzggkqgdnetbgwvm', 'eycmtoeqtduejceecb', 'lclkzxvyq', 'gevnqrtjwfsjjfwwiysnbcqqjambgruiyrkmqlgbumxvo', 'qunorft', 'hkjd', 'xytsft', 'gflprectxgzjffyggozatweuitg', 'dbwyofkjzxjzoqjwldwdkjbndmgaxtpkoivrvbvqkijpqnc', 'yjxbuizuinxediocasycgclfd', 'qtqdwbcpuhugeimojpncqosfrrkjvbjkwhiyemm', 'rrjkcudppbystyn', 'kvkytpsbnlottppvbmqwbk', 'nwwxhfnxtldpdgjczhlygnnicnlvvnihpwpxxbvil', 'kfqbbngbfcmvfqrejzbamjxegjxlesyehlfnkfkqhdovq', 'thkkyaujwdybukgdrlxhuqiigpseipnhra', 'bygztnuqhx', 'zezmctdzgclcexdmpvawbumusdcenqqjlwdtx', 'afxgx', 'iggftvbbefzpoiyagezghbmrhcotphoeqbb', 'qcxauaxuxbvwqprxazukqgywljzdzjqfhqnjf', 'qiwhyszeoucaszgjwgde', 'pxvjdvjwskycnjiudgxnrfrrxcega', 'mlsilpfcedpchcailwdxfeucwcnkodneqynlegrcdcn', 'jymtqnxgbdpelmyjsgbvsjdiwqhjriagpohxowjnei', 'kcahyztfgxelmcpvld', 'aktunjkibbihhwjwuhwaaknfak', 'ruilfcshccaebvpdeqbueogoybagwgpjjhydk', 'uzcbssahahlepvxafroxiydarvwobhmusptcudyfnbgtjbvu', 'zbqhihpgxmngclrwzokckelynnzixjfzgpywduxa', 'hjozxkwdktzhojisv', 'mdslnxqjzdoybbdfnksdoktdkiumtsaepfmzipgytfzx', 'dhnttcioswmeqyzrhlatvcoknmkbihrrqar', 'ypvqzrnxslzrrcfngtxmzjdv', 'vybfspjpneruujbihloywkfkqygbbnc', 'vmshenurhkpvulnswnqtkiknoxwlqlndplamvgnv', 'nxnuvqxbcveukclejggckpjkcrvvehhsxpvstkaiuv', 'xxmcobcuzgesvoyiejvgakzxuaaokqohjoci', 'pgiccbbip', 'tjreyyyvmacxwkydzugbfbsyzkpseaevykeiee', 'tflluirucvxmbcphzexyoiczrcimqwskzpdo', 'mfdlhlkcbnruzyowjqwrbqrssajgagkijwzskoukiw', 'iqxlwbsbdtebfohlyatbeyzcuffynnrmnsayujkzdjhauv', 'zakdnrqwtivkzhaagjwegsqk', 'mbgvxohiiopjikqmbxowrhd', 'vdubfdqn', 'lkqjzgenwtikaxzntcotrpgulopgxli', 'hfwhczwijvazbracgfjgwtitfosbdzxsudzcqh', 'jmplcaaucrsfeucphixyqddbspsxjhrhfreimcg', 'nftadvtraeqtxxhglsirqhiotjpx', 'usnzd', 'gzhimafdfycvqwgstvtndkbubwkfuml', 'cmiktnm', 'bbimtpppuhsmyjtolerdaa', 'ivjjokdsf', 'qpzu', 'ezftfxguqzpvqkmevnqxqerfekqsqphmwuy', 'hpwlrxaiovfvjqoqyombvdneuuuox', 'tzsxuguhdvlkkqg', 'znheuolgnrteruuqwxllv', 'rptawfkamjtvvdwqqjjlxtkamgcpcylrmeyyypvkmlpuwkadq', 'kiqhpg', 'dopvvziswgznbplnpgqsw', 'lnjumfmcgbycayhflkynyiupfpykvepdcbte', 'l', 'hrocawzrzfcfqhoefejaqiodzvoxu', 'rrcnavsoxqrjsmozlyuc', 'vzhbsgguwstjaexayeuyklsrndaluxyzpus', 'doopepirloigiaahbnzlxpczkmbec', 'ckgzbscdkgwxenjxojleugvbevlssmrvybasbfrgdkz', 'ieeomvjadtfemldhcutbhmddmecrblakvmcescyntynvjeyf', 'pyyhonlzosqsnhfpdrxluyozppzgnaiyhzjzexukja', 'lvmvdbvvu', 'mrztjlrgxlhwqzyatshwxqhtiggzkury', 'ta', 'zeaswuhwciowsvsosksqmrqrq', 'wr', 'goybyfxpccsvhkiddycdwqalfvylbjcvyqetnomltte', 'rsqehsizvh', 'pvypuswyqlwebm', 'ffzqofhucsimywfyvnrzrxlwrctjqdtbiwyxntsdizunmhthqm', 'oebjsayyoiksdeiwpspyoaqsif', 'jauiekqbxcrlguvdsmjna', 'cqzxconvluvxyqcidqvnbwtamqpvawzrtvnalhlghpb', 'fwveoqhudohdgyplsteqfqywaewjavzt', 'mbhghthdaatuwdznbaeb', 'ce', 'ijfnbaivbqwmikjwsebintpeofbyczjji', 'czswxkodhqr', 'nevqyqpbsdgclhpowvobl', 'ymbnswjijmrro', 'vsba', 'vknikhwvxgumdtnuffkhfmcjvhzecxlwgunwnxkahqamakxr', 'cayabhety', 'ylkirjbkvkxcwfnuayznra', 'vbllxdbvdxeziqaccbjoksfnveffzqnogzlkuverolxb', 'awvyadsxxecwsfiqnjshbcvqfineh', 'qjreogr', 'wnzmnbxbiwoxwwtvlkcswokpjkelwh', 'yulzgbtustcwxfchzonbygsadadizlavaysitmbqwxlmnoki', 'oggvpnpjgzimiukvdoqxfwhhlglwphilpz', 'aqyzspylghgkxxuzqwdeyghkciwbmohvlxsvatwbdgocq', 'fw', 'upkwbsoezdjfgpcjm', 'zdoiivhupqygfecxviq', 'lusvybdpobbndmemrheifcujzuhunqsvbvoylhgilaa', 'vfax', 'fypllscjjekzdmpwdpgunyyxcqsgr', 'lllhzgferpyntswwaydyniypahwyilfyeaefywvmirnlemkn', 'fihzrlkdtfmgnumfbqmipkkridhtwm', 'vmygfpbuisrngfviommqfxrid', 'nlfufkcnelkjwzrrdr', 'foufyfciqrzohezhohjutknvzvguaovuhhnl', 'nyupmwvmiqclncjowbayvdtbsonawnelvhykowwvdhdfogvqdj', 'ghvqpbirrcmcxflibzpgmknrkwftruwiwzrxzpcbesbwqckf', 'azbjjlqwpwoosrkzzmfi', 'hquoxhxhqhvrcmociwhvxxlrq', 'drrpy', 'ils', 'xxduwgvgzrqydjip', 'fjmabwdxnd', 'zmsrlovsfhabbwuydtlnfrevktxikdvk', 'vvbktjrcmfdyxzdrafgpxvjbfppntrytxjhvjjmwrvgmk', 'lweznnfzhvnammkldekwzcmz', 'oktts', 'aljjgnwshqbooedeovrvxugfkuvidevbcslmadus', 'ylwfupxayyvnqkxzyepqtqxqoopjpj', 'wzyxxynvegmuudbjalpjrqoim', 'onzdjwtxxhopfvcldqozhbjdkeoialmaqcr', 'lfkuwstkikpdekicjqnfrcftcpulfnsrmzzmgvclsthid', 'yenpaazh', 'ohexwrrmjvargynreeuywofparhyxannaarcdiz', 'gwdmsdyppzmgivcbigulptdvt', 'wh', 'uzkauwyrauhyebrrgwkhfataqabkoshdhreo', 'oaiitgncpwzcrenbnvjijlgpkeje', 'gelcwyfqjcsumwjoqiohroxivivfrdjtgojebuxgj', 'lpb', 'htsfzxslxf', 'jcsnbbizswdvijf', 'qwtjddmqzikld', 'eyjmcuebshgwshabbycibnsnbvqfbfwljvveswbusbztnnw', 'czhyyycvmcezmceknwpijqazxfpflby', 'xmgrrmlglemraqmjevmtr', 'umoauzbmahbdpgfwketjzauesfentfgaskgokrjtnxfyv', 'wuxfbulclnfmgwjenss', 'lhgypvvacwatenhpkrqrjsohbuixifccgthjkr', 'yulrebtfkeelqiluaugjwtuyvywgspyhuqhsquacfdawlces', 'ygkzmgtrg', 'twljjzvwatoexyclznytvkosxfpdrospasshsvmzd', 'sigyhmqsdkclkdwhym', 'kfxwswckiowolrxhjfqw', 'bwtnviwyriajljytfqaunpvnh', 'nwiozzblqzwjbvfd', 'nezmvjztszrneunfvyxtde', 'worytkgkpdlhxlhfkpthsqwujqiqiou', 'sdzxymqhigxacriwojetkmwkqfpwnvreheschzokvrbhbo', 'pwnmstyxmxwiomnrwzxldnephyxbzxsawtzkaduc', 'tmskmoljxk', 'swucyswustt', 'vldleohsg', 'iiqxprlxvoyhjywkn', 'xfdcyyxwypkgiwkcqypacffmeprglqxbqtqw', 'qdifgpdczpuzpungdcfweerqxauakjqgcnu', 'hhd', 'nmibmkqzlfugrtpkuotguktahrutnsos', 'woajlgkcuudihlndguafiawudxryrf', 'ccilbdblcrzyvhqapkfaltetkvgfvbsariwjunkfbmngheft', 'whoahvfdkaszntrloduntwtcrdfzqkqyr', 'vtepsgitxwxcolfquuiipxy', 'pttjffyqrbrkvwkvdjfslybmziyradnwrgiqatacnzaiotby', 'iwhzzamdxjnctbyogvomuiranu', 'geppsfyfbfhyjf', 'zy', 'on', 'kcimjwnovuusackxekjdzvtwifdrrojehktteyjt', 'pkqsuptimyx', 'zffsxkhvlzyisuktvblidjsholanlgeukhwhgpzsqjps', 'zucawikhyrhefouogois', 'vdsjktcznt', 'hpmfkwgqjjqkbghex', 'alsbcgwvaejjzpuvlbymppvezfrvd', 'x', 'lakyyynnhdzpagwzaphqjoaxlibbosgvzgjsc', 'zhkxkplehuhuhifmbvbioretlldlzsboadopnfggeyfsldg', 'xtcyjidcqvgjgnadohvwgtustxeywtrhgkdlvkbzkjtitbthjn', 'merjggzwmbpecjsynrmcbfgnahbevgptberkmou', 'uxdatsafxdbwtnobnfrnotkpydrzwxvncslrikeux', 'dumxxpomqtxfrvomflpqseoztpzhyqcuwjww', 'kxafzlrosra', 'yncsdq', 'jny', 'gxejssfaotqjfeceiqkgcxymkirxmqraznjgw', 'unsgxlwyzhjhfoekwmxbzaliyrzaijeh', 'djuqumaknpirtdlvetcxqahznn', 'jzdvfyzlwbcuafuezfatwnxbwflwvotoclvinuczqsgftabqcf', 'iwgymd', 'ktzlzqhklkkguttbi', 'crxxewxyrauobwtzsdlhfrwqkcllsoqrsdqzq', 'nsxtydlahpizvxlcsplfyvxslngvsvhrobcn', 'eabhpm', 'biuosqbqkgvydbjndgwyzzdlunprujnnceyhmspwqihphtgfj', 'uafxbbarghbtrbxemtvidroytfovzfjasxhdhfmvfo', 'obfqdeeswgdtulupepyzyryyqaaudjuredwiff', 'imwopaathwiumtmfbglknxqbqybrm', 'gxaebcjzxt', 'bovsqdgmxpbvlgusrzjajxivimausec', 'qvhwnjwgventvdvlgwpxhironsdynt', 'asblmhwnhzgnrcrctofmtxy', 'ondgkqalhclwlfowrgel', 'hwvmclrrgpewirggupiur', 'sudorhzcrkinocskjncprpmsiozorlbv', 'shfwwgvmyaacszamzzwfnmliwwcdpdvhnnpfmwftdtrojunt', 'klutefgtxuwpfpwqdhdxodmmspgxsqld', 'egmmrrmbzoqnmeyipwuviqgzkkolses', 'kdraaboiewthztbmkowhyhoalhoulinebusfsr', 'yxsqznufunteztakxnsoqy', 'gpdqsnknzxsuimcxwvsynzwdsctvhfyzjgbyaaso', 'kihdgmrfsuhoomhnoowhvwzlysnhwdowpkuzkeybgeufmd', 'lzwjvutdyja', 'iegmepujkeyzwjkyqpqazgmlwyekwyhluzyrnjfykc', 'zhxxtcq', 'jmhxlhcrzpaktnwsvyiewmjlwdotfkqeurwgpi', 'uqhdtcereuzhqdznimprbnnsydjef', 'yyfx', 'dvq', 'rbtfgtten', 'tqiqqhjzdkubqilvqbwzyucezv', 'ynxmhizomxgjvnolw', 'qwrhgtp', 'wbmzfxtuuyh', 'sxbf', 'pjoyripumptvqxavrwfuzpeqgbr', 'decdmuxiwsbnhiyxfcejaenrt', 'wlewoeazyuqwpydsetnpulptmvtyxtfqkilzjzhzy', 'fstuxhggtqubccrdlgzvefsjtlcqmzgrlfquvfkwvqcn', 'kvapcvtfrrxtyxmxxysmakzsfhkqcjozgs', 'fjsfclfjhbauegk', 'ozadetlhdqkjqt', 'nwjabul', 'lgdxnjhiadnskrzoaqugzwypqq', 'ogxi', 'mxlcmjpqiyxrpzk', 'trnebgunthlbrcxafuskmplhwclanthpyeigmkqofpbsj', 'gsl', 'gmanhfhrbtvptxoupmq', 'vfez', 'vulezewdicabhprdoropycyjrlyiysdeqzuqemcffjw', 'hnvqlobjvtrexoduaaypbzoht', 'xbfaemasglerqfdpf', 'stdsigutsxplszqntykpquqfrqmqrdlwbgbteaootp', 'mhbvwftwkko', 'gtahzjnyuzntsundqdjmbtfbnzqpxla', 'o', 'ufrtpdaxxmzfbtgfpyjxcjcfdmplowtfjfengy', 'hfauhohrdwewvkkp', 'ougccdintekvruuacdoabpjaefvwhvoaa', 'vdxajtjrvx', 'bhgtfxnbqrivnciagzpnbs', 'fvxlf', 'le', 'tqvuuqgedsyylxpvcgvzxgrjvpxbwksbtzsdcby', 'vpatxlstvlqsnwytvaromeskwycjpltchpgdjtlg', 'zbjhzaanvwlnpgjylvgvxafapnjxiizvssqvjhngwvfc', 'gnpoyfwjgjsfmrxremvsujilxwtatwthaol', 'zgymzvkrfgdstyrobvg', 'cqklipobfhnxm', 'thvzjmmqsxtufyaxgjoteknhdttjghxrbhbvc', 'htrzhedzbuscqy', 'sx', 'otfruebnziisysangxlbakawkecqgvycwwnqopbyahtlpqoa', 'xalegkaivjuwyppxzbcegnxorabjumal', 'gkybtoitndjsljfnazgxuxugwfqzjolhvvfiwkhwq', 'fiyczdvlbztlnkegvjnjhzwoedyx', 'ghsrjcpctkpbyfsobkgdubywdshksvftmmdoekolxe', 'egkzzuksdolgcmbrackpufnkergzlbadnckzbkvnpfqurkiai', 'qxlde', 'xehygzwivtldttpaizkeybawdpvuusztyakhgyrfgkvmbfgr', 'lucygwzyjqborhudmufjbianlvgafnoem', 'qlbuwihwcyhiqidjgfigrxkelbnzcppnjpmfcomdgb', 'hlivlaxcshfthsflbkldtcrzquobjeyspogjyaqmzawjyy', 'ufhmtuhdukdebgnjobpmerbwj', 'tumvtlwcyyertwefmmtqoevevzbymmpwwgyfadsoh', 'wdmerblimcozop', 'y', 'mioepbekylujwzochtonakpniopffaegwpooqttaxogvfztgw', 'zhjlzwjnfyijoewmmc', 'jhlwuildzapfedpnrlhiymb', 'bheiwcmg', 'dlidaxbh', 'sddhhhckipojehyopmmzipyxmfwdcsq', 'cjvdwtizflfxbxidcbw', 'jhisweabpfyayffutodtbyfigfevj', 'ogcmxtsnjedqklkxyrrfrnopyztbxazvsoy', 'niiqefdfpooidxnqceffsulijvoiqtlpbywolbirgvrii', 'nbwxygzdbiwjoizuzcdxcdhnoogzgvhsbv', 'hfvztfterfldereseedxxaphlmbjdbkyk', 'udcfpdnkfbjevxnznhbputuythqvqlmroztkmotutwbgkjomn', 'fcpanbxvtc', 'pmnimnvpblyqkiphrcqrv', 'hckqczcqtqbqgrezyulhev', 'xiefblanxutzlubuqqdztmdjdjnhzqipxxblrm', 'rbypudkgyllurwuxfcongortiqigumbeiarwildldcybshhbu', 'ivjrccvbrgiifmbhbdagrykiqicjfkyqiotfpnyqdaulvo', 'xtihvkpbareemasobiitjssbrxnpr', 'ywkphuqhwbswfn', 'w', 'mpmbljzbrzkewinlhgiww', 'ndqlhxkuein', 'jaslwgaqfcuxiwqgrsmug', 'kdqouhdmwghuyyewjfqpdmd', 'wqrfsdviuqpdtdiyikdgtevbgakxjdlqwvdqleu', 'qvehmtbdgpurercfbtjbbssupecsnaoopxljdtvspalku', 'pdahbqruheykdybapwe', 'lcigjziwgiwwmdsxqkqfrksqlghsillmmambbqnmyolwvhbsvy', 'gpaopgnbggqjzpcrdnxkrucjhvbgp', 'ouutlztkfwbmkbpoxyiaukowwulaucwhoeqv', 'tcptiyem', 'vxbjuygliwoldzczfxvsbcnzny', 'mkzkizikxkileptrrariivknidaxkkkydw', 'yaxlcsjklfrkeabliagipom', 'flmimtadehragyjpczimnagspmyhuxhwrjjnlblcha', 'iueavrinv', 'dqvkudsdnyipzbsucrqgh', 'msi', 'tzsvfrgowehahfmnppvdvcahddb', 'okjwihowgppqpvyvjpl', 'eftbazxbikdowrmbbonqhpgldotwkyguqg', 'oyelgfkoifyqeqisnys', 'flhrdtynqhrxxdfkscyfpenpsavdzhcrff', 'bshutgnkvbp', 'xvlsqepubwogkdwahpxtobbsgsgjbbozqyagq', 'younbrtlghxtvmodkggbimpqpnbkzqrbsudkggcucpd', 'uumzgijbyolardqtvb', 'dfmcvrjkrufxrbojzsjfdnhdnvplnlip', 'lggyqtvhltqvejiinmddrxxplzfhopfdpjvredwlyqeaabzz', 'pezhahfqpagodqzxdetiqgvfizcvpzvnmrhwymavsycjcznrpj', 'nujubkyzcrscbtoumomjqfndzkkxgluetnx', 'iv', 'fanatgsgihqodoancrtazznukngvcyfjfwobtshwcwl', 'qvoqcytcwszmbuhlf', 'nnq', 'aev', 'uxxtarewbtpicvhowdiftdfzeriszqogakrcprtnwvxtcl', 'mkkdlujoaxrgpcxsymtoijsxurltzasxlzkzbthtiywduwpzzw', 'vasipfjnowjldhnreakxizkemgyqqgzayrlqv', 'ytkufwhddqwikznbtqsicdovhqnvtbdmrakhuzbsjkop', 'slycymwzsvypmgkj', 'llplirfmfmyzlpaqhrlg', 'yqxnpamgql', 'lnpthuvidgrxzeykmnncqaqimijpfnnffgatotnbglbzao', 'ojtnbxlametnaislltfqxtmvnp', 'sctenvslwbcco', 'rysgcskapubcaqubqnsqeleyeuvsdtwacovmvaiqhg', 'yxmvts', 'uvudncnsetbgbzzhjeudjemqcwd', 'qq', 'iliomvutjxjneiimsjg', 'utzqpxtdskufrseviyazrwhbfweivsbdvc', 'dexrhsq', 'maegwrhpnidtrwtminombrvum', 'etge', 'jzaqauxcddnhjyh', 'tfwmwwpgaxqskwaeghcd', 'mcstlulkdnmhiqkdddjrwooslpozcdaoxtkyx', 'ximsxmbefqgkmmyjqrrtcbhszhgvvhzjwxdlizxwfwqw', 'iuga', 'zulhmpsuarwcmjgpf', 'solxbdbzcatnyephyyaevjfzrhlwuih', 'yjiyccekwuwlroiga', 'ewazpnraxzqzmbjztegolaskqzbktvotlkiqiwr', 'pzfh', 'onmebegcnqjklzdvdmmlqdpzgedyqn', 'hhnyytxvzvoksnmjnewcanavoxympegfelznxwmzxsvrnwfluy', 'lujoqexspxsgqbhiyifeqmanufqxkygaqaijkmwsiyzhqhy', 'rertpsgjldqqhcbulhngdrmcscvaamgbjzyetczko', 'yjt', 'rbgvsqkpjzfdokkgcwrokdqljtigljdyzupf', 'wcdxfqgxpnsrtykb', 'lrwnvazuxuyoxnsziuydljtlvddvtc', 'fepkocugtodjaeexdhkwfajqppiwmaydjxltm', 'yrythjlztwed', 'pgllrbjnrvqrlvswphcksfkjxtthkzkpkvnmncxvjymojbe', 'kqryjjw', 'fdilxmtldb', 'oh', 'rhzxjuzuyhkocawpmflckazmeszboshondzwfhgg', 'iozrfqzllxacyjxrmecmohqoiqnyxqbbucvfgkbmmrofhls', 'okcybzstfxvobvcmggsslhvmd', 'nejuymudrgijtgwgawaqtokmlpmkzapdaheh', 'elkkmvioehztjivyukdsr', 'nbtqifkchzbrhxjrcwmgvywidniqqywxxobkirrxavcrlzzym', 'krmghdrtecgvbvk', 'iofztqdfemfepmatznwwukehjmarqocrrpad', 'inrjvciwwgyimbismezb', 'hnjxxnvblgqgcmequemlgltfazyzsemfpodmkqlsswx', 'gmhyrncfwzzofehejrcffegmhxpygaihkhdsxkslrqqtg', 'wpjwrefwnaytbtvfztegiik', 'pbzjsudehvhktazykkypttozoaibwocp', 'jhelllhtulhdplsczvwzshnhdjf', 'nddvtqrgpfullnobslxvczlvpolnv', 'hvjpxbwfxvochlnaj', 'eumpdedzarpwkhswirynixpiezd', 'o', 'fgfvtakwnkqcnkczcgwkyykrlfwzixjuotk', 'wmgknjchxreqvhruxylwlhsuqumxkqbdhdcvmbvcwbmdrblebw', 'ztyxfllssxotxvpusiu', 'ayscstgtdgojucdfkyyiufmn', 'rophnzsqhkv', 'ayrsuuhjwlowqboltxrrp', 'vkqfsspzfubfonycfryphgwcbdzvzwezboxlibtawqnyqwu', 'uqlvdepoxqkkzdrols', 'xyrporeqvbpnglssjmxzncmoead', 'rhkwsishyujcxthdnloa', 'wwhhjogunvyjll', 'aqpmsklehffdrjicygupcrqgqvncyaeoytoqtwbeulog', 'fhpxyoenuzimxswubbdsnmctcotuoehhjuaeyhlz', 'levfbuwurpisifakqlvgxnmqvanigtedovnhpcdzlrfny', 'xpse', 'cjkmfxxwibivlgiqitkhrxseffwcfhiayjuaqtdam', 'vgxqxmqxbg', 'qnmdswgtscplijfyhznmjqdschpbpetyyvzukbgbzfboueoxf', 'stwsmhrhcqxwgvkoxaxbrtzqxc', 'lvvhmhwrirlocflrvpwwjftwwcldgdrsdhobjbaqzcdfwsnjd', 'wru', 'inbxnzbioxscgzrnfcjekounazppfip', 'dknmpzrzyhlztqtuumylistzrfigrtqfsklibvpyhalkh', 'rrrocmtlgbokbnddf', 'i', 'tsiwcmlnrphxoierzmmzdkoopem', 'sodrwfiknduixyweaiqvxauhtgfc', 'amqwxyobyhubaylehmceeuorugprkxcvzcbyjhdlhexabeu', 'cadzizgetg', 'eckavfvwjlpjzgmgfabmvzikkafauepslarnksufkhfxrzblpl', 'bs', 'cejbehnnrfepfsbuouewzjpjysxazevloaajldblzruqwlf', 'mmbuhpqlm', 'kodyjjxaazueqbahiqvvwhvapwwtreufeqojndnzdvubxxssg', 'hkfdpefyrsrtfgqmzccbbwsawlcvbgrny', 'onrrjgbqtzzzcifgoofmgmfyxgdaiuxlxjjcvsbplubzadl', 'mhhrbytuwoaef', 'khogrdrjnpxoazkvywqfarwimfmcszkebnawfctmffygrjfve', 'spvqppcuqpaltrqhrlekv', 'srtuszftmrlmx', 'okwtkgrsxcutlilvgwjmezefuhipahqjnfkitxrmxakgonfyc', 'gyvjqgtxrhnfntlpqevkrrdzukyqdynapkjgwvd', 'toafqeodcpwemgqrxphgnfbulfbuqmi', 'slvsgnfpwhctua', 'achpsvzvnshxzipmxauizhmfbvupwvt', 'bctsyiwopknrzcsbaszhddpfkghewpru', 'zwirifnvbtkbqosotsevo', 'kdrxjfaadciwxmvfjfadb', 'bkv', 'chnemuvekvufkorwecpinlgbaufpaf', 'idiwezzmggmninpykfsbwjafiny', 'x', 'oyvocruraurbgfkicvcxnsi', 'vybbtzmkqxduwwyrhxmiiuyhd', 'l', 'rfdxejhqinoxvvsnzh', 'tcpfpjsopmlhewylzu', 'nyuifdvurpncqtitbjhhsnnkgkgnyqyykqvwkopoydxjhmar', 'smfktixpitmkpyyxea', 'ixpehxrwxsbpufoklnggudaskyshcezwxkthtmngfzftwrqzoa', 'lfkkzrrkvlseoppcgmhnckvdbuca', 'qnvpsapkmdjjbxbaebibceatvg', 'mkcyebkgifia', 'yk', 'xkhsyjsbyfvmjlejptueebpmoszxnrpokvufrsztfocaluxl', 'scjtnbvkppmthfhgmv', 'qhryewsgoxzlmohmqxpfdnvidydfzzljq', 'pqoa', 'zkoyiiorrbqyxhueqacewnlxcoizbujlxkrm', 'jzwivjxzkcgmyazfwnkzowobccord', 'ouwfh', 'wlzsequdrwudqftbvgavjoyrjkuyba', 'qmjhztrcxqzvhrzwhboktxwimlv', 'ffofmzvcwhcheccgpptvuvydsrcyvaeewox', 'zeuuygqrlgymufcscmyqcndakmjefqkllmlowwswlkkrstudtm', 'yinfivzmazkmbkdzjjshcwcbgmvoacelgk', 'bif', 'kskajcgcxepgsokjrycqdmutvtoupschzhcdapwrnwhsrjbqy', 'xootpzpfkepbeilcygakovjdtnixhujbgtzvqwgzbakaxhyb', 'whhwlezfqtrnlzpewxxyynkpersmlblsane', 'dggcdkumbtsnx', 'dfeigobzifkolsiomoxvewxjyihpkynls', 'mlptwrvxmkbftbdifixgglyzjsuo', 'okpofeflkncxonkuclwsbdtikvfvq', 'dualqdw', 'uobxwsnfwizpuovb', 'rrwhazunqpamtswbpxazfvxrv', 'pyxfqhcgaruxwhikxtlusviitrfvfpclrhxblmhrhwavamop', 'vflgczqxhbnxjkxpfbwssacmkfaapgsxqiwyp', 'vqvlpkbyqygkbpmq', 'rwjrlfgxotgobjmcrtjipzxgpcoxjcvoycz', 'esmuyvdjmlnnduoteietbdlsulhkqoiqellgmjthqszzz', 'iqoatnccxcvdplxynsadwocghtacq', 'edfcmypxndsxlyuhmdjqkamyg', 'yvcmbxtefnwwajbkioetzuonpkmigyujxkwzsjpcdhm', 'dopvyuvruvmvjxxclszeizwldeodiqjztwixemnjwnactrxocb'], [9522, 9401, 6599, 5347, 7241, 2422, 9473, 6091, 54, 1041, 5318, 1879, 2042, 5887, 1448, 2291, 5017, 775, 8134, 2047, 9748, 1863, 2370, 7582, 5874, 8093, 3519, 6594, 2034, 8001, 6853, 7602, 8151, 1140, 2420, 1559, 5835, 2301, 7290, 4697, 5106, 9737, 9735, 883, 2248, 2146, 7344, 6155, 8549, 9361, 254, 3679, 7365, 3299, 6590, 7929, 1952, 9891, 3924, 4262, 2894, 8787, 8194, 935, 2427, 4140, 7989, 8366, 7931, 960, 957, 3474, 3581, 4765, 8742, 5936, 2978, 1150, 3897, 1444, 1157, 7149, 3645, 2475, 5557, 9232, 2729, 4252, 8725, 1220, 391, 1241, 2341, 1348, 7434, 541, 4112, 9826, 1456, 3460, 4154, 6748, 9951, 2368, 3932, 2925, 749, 5421, 1503, 6591, 6997, 7774, 5008, 6659, 1629, 9740, 3290, 6965, 6495, 4829, 495, 3562, 7648, 3353, 9932, 6040, 7512, 175, 1041, 7338, 4533, 2857, 4913, 3950, 6614, 9657, 4199, 2918, 2843, 2111, 344, 1272, 7095, 3369, 4861, 734, 6816, 7010, 2532, 2250, 3413, 777, 4588, 7352, 5425, 7060, 4205, 2132, 124, 1041, 3510, 1746, 1581, 9650, 2002, 5205, 4233, 1745, 7106, 9534, 6697, 9649, 7113, 9492, 2937, 9067, 6067, 100, 1063, 4169, 1350, 8514, 2268, 4446, 9353, 4598, 8779, 1222, 1973, 4238, 8362, 748, 1536, 7638, 6147, 3328, 8191, 3588, 7289, 8357, 333, 4100, 5856, 8636, 2412, 5067, 7939, 8444, 6661, 3268, 6658, 8982, 5232, 4934, 1489, 133, 1425, 4891, 1467, 8494, 6036, 1964, 5093, 5452, 2257, 1598, 6712, 9535, 3498, 3106, 2406, 3699, 8317, 296, 9630, 9127, 2967, 4699, 9704, 6020, 3513, 2055, 9777, 2338, 5639, 3461, 9582, 6686, 2482, 2536, 1420, 5421, 376, 356, 8741, 6100, 5087, 1389, 1649, 3835, 1839, 7165, 5018, 4927, 5175, 6638, 4725, 4347, 4581, 8779, 3283, 4255, 6396, 8795, 8773, 3407, 8690, 7302, 3310, 2379, 8366, 2269, 4521, 4321, 1109, 4844, 2850, 3713, 5825, 4841, 9880, 5430, 5810, 2056, 6911, 6032, 7723, 6733, 8228, 9363, 2213, 9430, 409, 8868, 5245, 2204, 3445, 9673, 6629, 7857, 5310, 8033, 5096, 7628, 5670, 8150, 1641, 981, 9487, 7240, 7572, 6001, 6003, 6744, 6619, 6814, 8612, 9121, 9742, 5150, 7259, 4653, 3765, 218, 165, 6804, 4833, 2321, 7362, 7910, 3515, 6786, 2054, 5014, 2186, 2763, 6915, 7782, 3198, 5733, 8867, 622, 8024, 9309, 9137, 9584, 2407, 938, 8474, 2267, 4458, 4016, 2000, 5335, 2984, 4928, 5217, 1392, 4830, 7319, 5159, 3653, 6511, 7533, 4375, 2569, 3416, 806, 1802, 1733, 770, 8753, 8239, 30, 9053, 2419, 8245, 5843, 741, 9635, 4726, 4334, 7655, 591, 5588, 93, 3291, 1888, 2081, 4009, 9430, 3594, 7120, 8319, 6324, 5835, 8024, 9047, 8245, 8827, 6210, 6124, 4350, 316, 654, 6570, 4523, 2791, 5109, 4202, 5724, 5738, 3021, 7290, 5216, 6735, 5858, 725, 6629, 9036, 6734, 9276, 5748, 6564, 969, 7266, 7763, 3503, 9234, 7634, 5099, 9342, 2134, 4558, 5959, 7321, 5959, 9711, 4265, 9980, 8776, 2905, 9985, 6998, 3964, 3933, 7481, 1842, 1679, 1900, 6553, 393, 9687, 9859, 1476, 5260, 7609, 4860, 6727, 7033, 5626, 9459, 5969, 1602, 3055, 6905, 7975, 5183, 5112, 2040, 8211, 9805, 6317, 5502, 5130, 941, 4819, 7289, 9854, 3675, 6197, 7904, 3957, 5308, 7058, 6320, 137, 1055, 9987, 4779]]
    want = -1
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = ['kcozfniglrpwbeumwwyknitonfmhldatrfsqdiyjlftfxhmvedsmjlfarutorurtoupgtvfgykumnqyyhskxxgvltcazkjjmfkwt', ['ru', 'lf', 'fniglrp', 'vl', 'yyhskxxgvl', 'umwwykni', 'ltcazkjj', 'ldatrfs', 'umnqyyh', 'glrpwb', 'lfarutoru', 'umnqyy', 'nitonfmhl', 'jlftf', 'hskxxg', 'mhld', 'qdi', 'gtv', 'hs', 'xhmveds', 'glrp', 'onfmh', 'datrfsqd', 'wwyknit', 'fk', 'u', 'gtvfg', 'ftfxhmve', 'yyhskxxgvl', 'qdi', 'ur', 'vedsmjl', 'hsk', 'diyjlftf', 'tfxhm', 'mwwyk', 'fkwt', 'pgtv', 'trfsqd', 'to', 'xxgvlt', 'v', 'fkw', 'mnqyyh', 'nig', 'mwwykn', 't', 'nfmhldat', 'x', 'itonfm', 'x', 'lrpwbe', 'd', 'umwwyknito', 'kumnq', 'kumnqyyhs', 'm', 'sm', 'hmvedsm', 'zfniglrpw', 'hskxxgvl', 'yyhskxxg', 'yjl', 'kcozfni', 'qyyh', 'hm', 'arutoru', 'gyk', 'wbeu', 'nitonfmh', 'jlftfxhm', 'zkj', 'knit', 'fniglrpwbe', 'mhldatrfsq', 'cozfnigl', 'ar', 'fkwt', 'rutoru', 'vltc', 'be', 'atrfsqdiy', 'd', 'jjmfkw', 'jlftfxh', 'lfa', 'fg', 'mfkwt', 'a', 'gtvf', 'utor', 'd', 'farutorur', 't', 'ftfxhm', 'datrfs', 'jj', 'knitonfmhl', 'vf', 'rpwb'], [95, 51, 42, 19, 49, 4, 32, 7, 6, 15, 66, 65, 1, 72, 83, 68, 31, 31, 76, 32, 89, 45, 84, 72, 43, 7, 47, 11, 97, 46, 19, 39, 82, 67, 41, 22, 52, 76, 9, 47, 57, 5, 88, 36, 47, 59, 85, 89, 33, 44, 58, 64, 84, 27, 46, 12, 77, 9, 30, 9, 9, 28, 56, 89, 67, 26, 79, 76, 64, 22, 58, 42, 30, 41, 44, 7, 23, 53, 90, 81, 12, 10, 86, 99, 31, 85, 25, 21, 29, 12, 90, 56, 85, 22, 47, 93, 88, 1, 67, 49]]
    want = -1
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = ['bqugno', ['bqugno'], [1]]
    want = 1
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = ['zpeapbke', ['zpeapbke', 'z'], [8, 1]]
    want = 8
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = ['n', ['n', 'n'], [10, 2]]
    want = 2
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = ['kcozfniglrpwbeumwwyknitonfmhldatrfsqdiyjlftfxhmvedsmjlfarutorurtoupgtvfgykumnqyyhskxxgvltcazkjjmfkwt', ['gy', 'n', 'mfk', 'um', 'fs', 'qdi', 'mfk', 'w', 'ltca', 'pgt'], [4150, 968, 6064, 5724, 2847, 3584, 7604, 1025, 5196, 5529]]
    want = -1
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = ['wldqn', ['ldq', 'wldqn'], [1, 1]]
    want = 1
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = ['zlzmyesvylxwiooifkvpkkkgdceqxjogyfxxzdcljutgdtlwlpgiopssjxgwqdnyoequfbdhrzncbddwfjlmmmrmqhcnjsrkxlidcyvjirikyqlsspwwondyuenhegjtvgyfcihqplzcdvlqvapkmdonewvipsibuqktnsvqpyfsrwmlrgadspiwempczhtcfbjystddzdbmcexqkxdsmecixekkttoebqybiupfnqnyghbbnxjfgzlhbiqmrqkvwloacxthpfscplmubrodwbpijhqfqnylyqqmcgrflwjkubzkigwkazivhwpmfvbtjvjkwmcxrlppuzpeylslttnpzeymibukrxjtnzmvhwupfkrgzqhphvikoxpwytiwviucelpepcowpixxinnfysjnjwvxspncyiajzpwnsogzxrancwmidxcdhsucvdarbdhihtibuktffsbaaecvjqdcbrxuioxnzyqjvajnzgzmtvgolvnjyjcswyrzgcfktpenzdfazogmzvugnxbyvbnuqhbudcusbawtnnldeszjcxscsicbubnouvtlqmnlinoaswkhltdqhprqtrnihzolehfsitdhehokrmebxvotbwiojmxincqbbvoulqztxstpjlkvaqdgruqvmfgnsdtsxmyoojjoresemxhiricynnzzpfmpmducuhqcioewenvozznulvjbvijpdwnpxrdrpbohgsiwaxzsapnuztjprexufostpbdyvamhqirtparrzgysyacswaxyidxmvdkilyzsawwjsvbbojrkzuilfdhkphzvxyrsajkupheasjcihsxqpxsfdrspfrtqpmyyqmwrhejjugwnemopxggaqtthnnnixqnzwbhjdfipwzkmlrflczdcejevdjvvckeaetynmtibcazpydtzfiisipknbqccipocltuuqbypzjpdoabiujrrkvfclhphqilywtrsqaspweddrpwr', ['w', 'eszjc', 'w', 'e', 'e', 'c', 'ys', 'heasj', 'i', 'dceje'], [33, 75, 16, 31, 64, 53, 39, 11, 75, 7]]
    want = -1
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = ['sgsipzma', ['s', 's', 'g', 'ipzma'], [1, 5, 2, 1]]
    want = 5
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = ['xgaehtpairarxcvxgovydcksosqjrtkzwhzwbvxbrewwuwzwwxxbdw', ['bflwojofvbaktkuv', 'gjsuzfszamujyxka', 'upkqxgnuvqdb', 'wyprbmwqrxitqey', 'bqfhcjzhilagbjb', 'juqnsvmkozg', 'he', 'x', 'czmeiuocplksn', 'xcnqajqwjsvbjvlzw', 'zvpzysslcrzjian', 'ece', 'kckxjvtavqho', 'hoc', 'ofaklpkyqcfw', 'kka', 'qgamhxa', 'crfqijlehgkfq', 'lhthyqkftxind', 'zvhlpcsguag', 'kaozacfgttp', 'cwunzgvlnyfhlpsozr', 'accafesumnuifpwjfm', 'tytg', 'jlhskoc', 'dzsuwfdeujhwhv', 'tf', 'oyqwtvairjj', 'sqegxb', 'kbrorbebicszhspqszw', 'dhjmokzux', 'ikknjkmtqc', 'wvkndur', 'akptv', 'rfazollgyzfhxgifxlh', 'ivri', 'xzdsnvblwgmslaosa', 'djbizi', 'fcgwytnsxunhhxb', 'swmwwekcppg', 'esup', 'zcr', 'yjrgmjyw', 'onnqtzuojraumk', 'noapzwjfbrqgigxgwh', 'nowgdaucsevuxdabj', 'zqwskdgr', 'udaosmjnbkdqbtaaztu', 'jnxarsgz', 'sivjuq'], [764, 44, 758, 304, 325, 970, 836, 936, 698, 457, 390, 858, 63, 616, 827, 593, 131, 573, 52, 24, 714, 554, 101, 738, 483, 861, 21, 508, 429, 669, 343, 255, 213, 676, 459, 477, 46, 128, 583, 536, 928, 67, 5, 22, 845, 456, 505, 843, 914, 73]]
    want = -1
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = ['mvcjwiysry', ['wiysry', 'ysry', 'sry', 'wiysry', 'ry', 'mvcjwiysry', 'wiys', 'sry', 'y', 'vcjwiysry', 'y', 'ysry', 'mvcjwiysry', 'wiysry', 'jwiysry', 'wiysry', 'sry', 'jwiysry', 'y', 'vcjwiysry', 'wiysry', 'jwiysry', 'vcjwiysry', 'y', 'ry', 'sry', 'ysry', 'y', 'iysry', 'sry', 'ysry', 'jwiysry', 'y', 'sry', 'wiysry', 'ysry', 'y', 'cjwiysry', 'cjwiys', 'mvcjwiysry', 'y', 'sry', 'jwiysry', 'mvcjwiysry', 'jwiysry', 'vcjwiysry', 'wiysry', 'sry', 'mvcjwiysry', 'vcjwiysry', 'jwiysry', 'ysr', 'y', 'jwiysry', 'iysry', 'wiysry', 'y', 'sry', 'y', 'cjwiysry', 'jwiysry', 'ry', 'sry', 'iysry', 'iysry', 'jwiysry', 'y', 'sry', 'cjwiysry', 'y', 'sry', 'wiysry', 'sry', 'sry', 'iysry', 'iysry', 'mvcjwiys', 'cjwiysry', 'sry', 'wiysry', 'jwiysry', 'wiysry', 'mvcjwiysry', 'wiysry', 'ry', 'ysry', 'sry', 'cjwiysry', 'vcjwiysry', 'ry', 'vcjwiysry', 'iysry', 'vcjwiysry', 'm', 'iysry', 'y', 'vcjwiysry', 'wiysry', 'ysry', 'sry'], [201, 417, 846, 986, 748, 899, 305, 9, 79, 901, 417, 359, 833, 362, 46, 791, 811, 307, 314, 62, 594, 409, 461, 885, 237, 203, 117, 173, 509, 193, 887, 550, 884, 334, 887, 290, 933, 995, 773, 519, 480, 502, 827, 455, 663, 994, 484, 343, 477, 221, 34, 843, 160, 689, 863, 958, 834, 586, 296, 755, 364, 981, 516, 741, 697, 658, 428, 712, 538, 967, 552, 528, 380, 46, 579, 759, 186, 992, 862, 752, 948, 529, 104, 382, 111, 660, 291, 987, 782, 653, 720, 50, 695, 532, 633, 415, 175, 374, 558, 785]]
    want = 104
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

