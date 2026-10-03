"""Scoring checks for lcb_3356 -- NOT part of any workspace.

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
    args = [['cab', 'ad', 'bad', 'c']]
    want = ['ab', '', 'ba', '']
    got = solution.shortestSubstrings(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = [['abc', 'bcd', 'abcd']]
    want = ['', '', 'abcd']
    got = solution.shortestSubstrings(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = [['bbybxbbxb', 'byxxbxxx', 'yxxyx', 'xby', 'yyy', 'xyxyyyyxbyyyyyxyyxx', 'xxyybbbbxxb', 'y', 'ybbybyxxyxbbbxxybxyy', 'yyxbybbbyyx', 'xbbyybbybxbx', 'xby', 'yxxybbbbbybb', 'ybbxyxyxbx']]
    want = ['bbxb', 'xxx', '', '', '', 'byyy', 'bxxb', '', 'yby', 'byyx', 'bxbx', '', 'xybb', 'bbxy']
    got = solution.shortestSubstrings(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = [['aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab', 'aaaaaaaaaaaaaaaaaab']]
    want = ['', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '']
    got = solution.shortestSubstrings(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = [['gfnt', 'xn', 'mdz', 'yfmr', 'fi', 'wwncn', 'hkdy']]
    want = ['g', 'x', 'z', 'r', 'i', 'c', 'h']
    got = solution.shortestSubstrings(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = [['oooyyyooyyyoyooyoy', 'oyoyyyyyyyoo', 'y', 'oyoooooyoooyyooyooy', 'oyyoyyoyyyyyyyoyoy', 'yyyyoyyooo', 'ooyyoyoyyoo', 'oyyyyoyyyyyyyy', 'oyoooyyyyyyo', 'yyyyoooy', 'oyyooyooo', 'ooyyoooooyooyyyoyooo', 'yyyoyyoyyyoyyyyyo', 'yoo', 'oyyoyoyoo', 'yyyoyyyyyyyyyyy', 'oy', 'oyyyyyoyyyoyyyyyoyo', 'yyyy', 'ooyyyyoyoyyyyo', 'ooyoyy', 'oyoooyoo', 'oyoooyooyo', 'yooyyyyooyyoyyy', 'oyoooyoyy', 'oyyy', 'oooyyoyooyoooyo', 'oyyyyoooyo', 'ooyoyyyyyoyyyyooy', 'yoy', 'yoyyyoyyoyyoyo', 'oooy', 'oyyoyooyooyyyyo', 'oyoyyoyoooyyyyooo', 'yyoyoooyo', 'yyyyyyoyooyoyoyoy', 'yooyyoyy', 'oooooyyy', 'ooyooyoooyyoooyyyoo', 'yoyoooyyoyyyyyyooooy', 'yoooooooyooo', 'ooyoyoooyyy', 'oooyooyoyoyooyoyy', 'oyyoyooyooyoyoyy', 'yoyooyoyyooooy', 'yyoyyyooyyyooy', 'yyooyyoyoy', 'yoyoo', 'yoooyooyyoyoy', 'oyyy', 'oyyyyooyoyyoyooy', 'yyoyyoyyo', 'oyoyoyy', 'oyoyoyyooyoyoyyyoooy', 'oooooyyyyoyyyoyyyoyy', 'oooyyyoyyoyyoyoooyoy', 'yoyooyoyooyooooooyoy', 'ooyoyoooooyy', 'yyyoyooy', 'yoy', 'ooyoyooyoyyoyoooyoyy', 'yyoooooyyyyyoooooyyo', 'yyoyyyooyy', 'ooyyoyoyy', 'yyooyyoyyooyyyooooo', 'ooyyyooyoyyo', 'oyyoooyo', 'oyyoyyyyoooooyy', 'ooooyyoyyo', 'yyooyyooo', 'oooooyooyy', 'o', 'oyoyyyyoyyyoyyoo', 'yyooyooyyooyyy', 'yyyoyyoyooyyoyo', 'ooo', 'yoooyoyoooooyoyy', 'yyyyooooyoyy', 'o', 'o', 'y', 'yoyoyyo', 'oyyoooyo', 'yoyyooyyoy', 'yoyoy', 'yyyoyoyyyoyooyoyy', 'yo', 'oo', 'y', 'o', 'yoooyyyooyoyoo']]
    want = ['ooyyyooyy', 'oyoyyyyyy', '', 'oooyoooy', 'oyyoyyoyy', 'yyoyyooo', 'yyoyoyyo', 'oyyyyoyyyy', 'ooyyyyyy', '', 'yyooyooo', 'ooyyoooo', 'oyyoyyyo', '', 'yyoyoyo', 'yyyyyyyyy', '', 'oyyyyyoyo', '', 'oyyyyoyo', '', '', 'oyoooyooy', 'yyyooyyo', '', '', 'oooyyoyo', 'yyyoooyo', 'ooyoyyy', '', 'yoyyyoyyoy', '', 'oyooyyyy', 'oooyyyyoo', '', 'yoyoyoy', '', '', 'yyoooyy', 'yoooyyoy', 'ooooooo', 'oyoyoooy', 'oyoyoyoo', 'yooyooyo', 'ooyoyyoo', 'yooyyyooy', 'yyooyyoyo', '', 'oooyooyyo', '', 'yyyyooyo', '', '', 'oyoyoyyo', 'ooooyyyyo', 'oooyyyoy', 'ooyoooo', 'oyoooooyy', '', '', 'ooyoyooyoy', 'oooooyyo', '', '', 'ooyyyooo', 'oyyyooyoyy', '', 'oyyoyyyyo', 'ooooyyoy', 'yooyyooo', '', '', 'yoyyyyoy', 'ooyyooyy', 'yoyooyy', '', 'oooyoyo', 'yooooyo', '', '', '', '', '', 'oyyooyyo', '', 'oyoyyyoy', '', '', '', '', 'yyooyoyoo']
    got = solution.shortestSubstrings(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = [['ymymyymyym', 'ymymmmmmmyymmmm', 'ymyymmmmymy', 'm', 'ymmymyyyymmyyyymy', 'yymyymyyyymy', 'mmymmymyyyyyym', 'mymmymm', 'yyyyyyyyyy', 'mmyyymmymmmmmmymyyy', 'mmyymyyyymmymmymyy', 'mmyymmymyyymyy', 'yyymmm', 'ymyy', 'mmymmmmmmmmymyymmmy', 'myyymm', 'mmmy', 'myyyymyyymymmymmyyyy', 'yymyymm', 'mymmyyyyym', 'ymymmmmmmyyymymm', 'y', 'yymmmmymyymy', 'myymmmmmmm', 'myymymmymymmmm', 'mmymyymymymyyy', 'myyyymyymm', 'myymmyyy', 'ymmyyyyymyym', 'mymmymyymyyyymmmmmm', 'ymymyymymymmmmymmy', 'mmmymyyyyyyymy', 'myymmymmmmm', 'yymmmmymmmmmyyyymy', 'myymmmyymymyymmy', 'ymmyyymmm', 'ymymymmmmyyyyy', 'mmyyyymmmmmyymmmy', 'mm', 'mmymmmmyymmmmy', 'mmy']]
    want = ['myymyym', 'mmmmmmyym', 'ymyymmmm', '', 'yyymmyy', 'yymyymy', 'myyyyyym', '', 'yyyyyyyy', 'myyymmy', 'mmyymyy', 'mmyymmy', '', '', 'mmmmmmmm', '', '', 'mmymmyy', '', 'mymmyyyyy', 'mmmyyym', '', 'mmmymyymy', 'myymmmmm', 'mmymym', 'mymymy', 'yyymyymm', 'myymmyy', 'myyyyymy', 'ymmymyym', 'mmmymmy', 'myyyyyyy', 'myymmymm', 'mmmymmm', 'ymmmyy', 'myyymmm', 'mmmyyyyy', 'mmyymmmy', '', 'mmymmmmy', '']
    got = solution.shortestSubstrings(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = [['samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'ggdetgcvmqffsyrbrxdh']]
    want = ['', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', 'b']
    got = solution.shortestSubstrings(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = [['ijyacbmcipsdjgpvttwf', 'jvryaugpixtzjsjmzdis', 'uktzsnrmvmxmprqrnejy', 'xtnjrsgwikfiupjlbxpk', 'lyyrffbrbuctbhlicvmn', 'grwfxpufulavdbcjzczn', 'gqpgqusbmadlcrpeoglb', 'xdtklkscnotxmbqthqmp', 'ysarziridkwtygqjobdh', 'mqukampmtkftiigixaba', 'zrbxsndxhhtirqlyfbtm', 'bhggmvqbxpztiwlkcdui', 'apeqopbwruylxgzuhjjk', 'mfhsojafwekcanaeihuq', 'cufzvooffoupmsklyoyp', 'nvjyahastihhlweixvcs', 'hvtennybgovocilarttk', 'uckovrnknchdsigyrpei', 'ymupfanztguviplimswp', 'sjonygcuybcgxcesfefo', 'kcgwnaiixrmngfegnznv', 'xmprkzvtxvbpalhopprs', 'enszmifuxvcgkliwfcjy', 'vkuylrcuiycarcqpciwa', 'lcbzkkqbakahhqqeiyjb', 'ellfzksmxdexfpvvqivb', 'firowbkeecivhmmyfciy', 'jdkktkfupxzexlwzdlxv', 'fppvytqvuznbwnxcchjr', 'uwllrqbjwiaqijieprfv', 'ahoyh', 'cdgmdqzlsorzzxxdvwma', 'wdswwverzjuyjhnywbdz', 'dkdsjbgemlpslsjllzeu']]
    want = ['ac', 'au', 'ej', 'ik', 'br', 'av', 'ad', 'bq', 'dh', 'ab', 'bt', 'du', 'ap', 'ae', 'of', 'as', 'go', 'ck', 'fa', 'ce', 'ai', 'al', 'gk', 'cq', 'ak', 'de', 'bk', 'jd', 'cc', 'aq', 'yh', 'dg', 'dz', 'em']
    got = solution.shortestSubstrings(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = [['abcde', 'abced', 'abdce', 'abdec', 'abecd', 'abedc', 'acbde', 'acbed', 'acdbe', 'acdeb', 'acebd', 'acedb', 'adbce', 'adbec', 'adcbe', 'adceb', 'adebc', 'adecb', 'aebcd', 'aebdc', 'aecbd', 'aecdb', 'aedbc', 'aedcb', 'bacde', 'baced', 'badce', 'badec', 'baecd', 'baedc', 'bcade', 'bcaed', 'bcdae', 'bcdea', 'bcead', 'bceda', 'bdace', 'bdaec', 'bdcae', 'bdcea', 'bdeac', 'bdeca', 'beacd', 'beadc', 'becad', 'becda', 'bedac', 'bedca', 'cabde', 'cabed', 'cadbe', 'cadeb', 'caebd', 'caedb', 'cbade', 'cbaed', 'cbdae', 'cbdea', 'cbead', 'cbeda', 'cdabe', 'cdaeb', 'cdbae', 'cdbea', 'cdeab', 'cdeba', 'ceabd', 'ceadb', 'cebad', 'cebda', 'cedab', 'cedba', 'dabce', 'dabec', 'dacbe', 'daceb', 'daebc', 'daecb', 'dbace', 'dbaec', 'dbcae', 'dbcea', 'dbeac', 'dbeca', 'dcabe', 'dcaeb', 'dcbae', 'dcbea', 'dceab', 'dceba', 'deabc', 'deacb', 'debac', 'debca', 'decab', 'decba', 'eabcd', 'eabdc', 'eacbd', 'eacdb', 'eadbc', 'eadcb', 'ebacd', 'ebadc', 'ebcad', 'ebcda', 'ebdac', 'ebdca', 'ecabd', 'ecadb', 'ecbad', 'ecbda', 'ecdab', 'ecdba', 'edabc', 'edacb', 'edbac', 'edbca', 'edcab', 'edcba']]
    want = ['abcde', 'abced', 'abdce', 'abdec', 'abecd', 'abedc', 'acbde', 'acbed', 'acdbe', 'acdeb', 'acebd', 'acedb', 'adbce', 'adbec', 'adcbe', 'adceb', 'adebc', 'adecb', 'aebcd', 'aebdc', 'aecbd', 'aecdb', 'aedbc', 'aedcb', 'bacde', 'baced', 'badce', 'badec', 'baecd', 'baedc', 'bcade', 'bcaed', 'bcdae', 'bcdea', 'bcead', 'bceda', 'bdace', 'bdaec', 'bdcae', 'bdcea', 'bdeac', 'bdeca', 'beacd', 'beadc', 'becad', 'becda', 'bedac', 'bedca', 'cabde', 'cabed', 'cadbe', 'cadeb', 'caebd', 'caedb', 'cbade', 'cbaed', 'cbdae', 'cbdea', 'cbead', 'cbeda', 'cdabe', 'cdaeb', 'cdbae', 'cdbea', 'cdeab', 'cdeba', 'ceabd', 'ceadb', 'cebad', 'cebda', 'cedab', 'cedba', 'dabce', 'dabec', 'dacbe', 'daceb', 'daebc', 'daecb', 'dbace', 'dbaec', 'dbcae', 'dbcea', 'dbeac', 'dbeca', 'dcabe', 'dcaeb', 'dcbae', 'dcbea', 'dceab', 'dceba', 'deabc', 'deacb', 'debac', 'debca', 'decab', 'decba', 'eabcd', 'eabdc', 'eacbd', 'eacdb', 'eadbc', 'eadcb', 'ebacd', 'ebadc', 'ebcad', 'ebcda', 'ebdac', 'ebdca', 'ecabd', 'ecadb', 'ecbad', 'ecbda', 'ecdab', 'ecdba', 'edabc', 'edacb', 'edbac', 'edbca', 'edcab', 'edcba']
    got = solution.shortestSubstrings(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = [['skgotnumlesjeymirlke', 'xlyeqbnammbqjrnaifzx', 'qefbbfbspwzjospolqeh', 'tuxahptmnuexqhycmjhx', 'vroaashtveogwztpqfhw', 'axewiqomydmycuqevkse', 'uarhpupdtlyirzbecugn', 'umdozswfdrmmmqozafpn', 'mmnphkrbnxpjztkvvvhi', 'kjvsmeubllqfgjshbanj', 'elipmutddmzwbhnyprpz', 'tatuazdgespanvgmckkm', 'bkegvkirewwltghmzegb', 'cfyrymwvjwhmykmeqixu', 'fkogulpevtkbbiuipqxc', 'rztebxhwljqvcwjwgrlf', 'bthsyaepzohfjuwlzvfb', 'oqyisxqjwemmgeluvscu', 'aygcyeuurdkjjcudsxcr', 'vdpbgttympdmcmshiyes', 'bozijcgphlkxmvkkhinm', 'raayovgjtuswlvjhmuww', 'ihffnvxlvfrparxhdxca', 'gdstuwedltdnqeffyoll', 'ztwms', 'xqddadumrtsgkwxfhloq', 'onrofyjvtuacpfzdibwf', 'ymqrmwqcgeguxfmfkmie', 'pgspxiphgabjzsngydsg', 'tagvywudlzogytunnuew', 'qydtxdcgggevzfklvfsw', 'dhxerphxfvjwrlfsbwbz', 'hkeiucdodqprtokckahv', 'ohcaakkavkxrmzjmcwdi', 'mrivoezsvikvbhjavlrl']]
    want = ['ey', 'ai', 'bf', 'ex', 'as', 'ax', 'be', 'af', 'kr', 'ba', 'hn', 'at', 'bk', 'cf', 'bi', 'bx', 'ae', 'em', 'cr', 'bg', 'bo', 'jt', 'dx', 'dn', 'tw', 'ad', 'ac', 'fm', 'ab', 'ag', 'dc', 'bz', 'cd', 'ak', 'ez']
    got = solution.shortestSubstrings(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = [['vggvgg', 'vvvgg', 'g', 'vv', 'gvvvgvggggvv', 'vvg', 'vv', 'ggvv', 'gvvgvgggvgggvvvggvg', 'vvgvvvv', 'ggggvgg', 'vgvgvvgv', 'gggggvgvgvgvv', 'gvgvgvgvvvgvgvgvvg', 'vggvvvvvgvvg', 'vgvggvggvvgvvgvvg', 'vvgvgggvgv', 'ggvggvggggggvggggvvv', 'vgvvgvvvg', 'vvvvvg', 'vgvvgvvvv', 'ggggggvvgggvg', 'gvggvgvgv', 'vgvvggg', 'gvvggvvvgggggvggggv', 'vgvvgvvvvvg', 'vv', 'gvvggvvvvggvg', 'vvggvvvvvvvgvvgvggv', 'gvgvgvgvgvgvvggggvg', 'gggg', 'vvgvvvvgvggggvv', 'g', 'vvggvvvvvv', 'vgvvgvv', 'gvgvgggvgg', 'ggvvvv', 'vggvgvvvgv', 'ggvvvgvvvvggvvg', 'vgg', 'v', 'vvggvvvvggvvgvg', 'vvgvgvgvgvggvggvvv', 'v', 'gvgvgg', 'ggggggvv', 'gvvvv', 'ggvgggvg', 'vvggggvgg', 'vgvgvvgvvgvg', 'vvggv', 'vvgggvgggvvvgv', 'vgvgggvvvgvvgvvg', 'gvv', 'gv', 'vgg', 'vvvvvgggvgvvggv', 'gv', 'gvggggvvggvgv', 'vvv', 'gggvgvvgvvg', 'gvv', 'gvvvggvggvggvvggg', 'ggvvv', 'ggvggvgvgv', 'ggv', 'vggvvvvvgggvvggv', 'gvgvgvggvggvgvgvggvv', 'vggggvvvgvgvg', 'vgvgvgvgvvv', 'ggvvgvvv', 'vvvg', 'gvvgvvvgggv', 'vvgvv', 'gvvggvgggvvgggvvvvvv', 'vvvvggvgvggvggvvvvgv', 'gg', 'v', 'vvgvvvgg', 'gvvgv', 'ggvvgggvgvvgvgvvggg', 'gvvvvvgvvvggvggvvvgv', 'vvgggggvgvvvvggv', 'gggvgvgvggvvvgggvv', 'gvvgvggvg', 'ggvggvgvvvv', 'vgvvgvvggggvvvgvv']]
    want = ['', '', '', '', 'gvvvgvgg', '', '', '', 'gggvvvgg', '', '', '', 'ggggvgvg', 'vgvgvvvg', 'ggvvvvvgv', 'ggvvgvvg', 'gvgggvgv', 'gvggggg', 'vgvvgvvvg', '', '', 'gggggvvg', '', '', 'vvvgggg', 'vgvvvvv', '', 'gvvggvvvv', 'vvvvvvg', 'gvgvgvvgg', '', 'vvvvgvg', '', '', '', 'gvgvggg', '', 'ggvgvvvg', 'gvvvgvvv', '', '', 'ggvvgvg', 'vgvgvgvgg', '', '', '', '', 'ggvgggvg', 'vggggvgg', 'gvvgvvgvg', '', 'vvgggvgg', 'gvvvgvvg', '', '', '', 'vgvvggv', '', 'ggvvggvg', '', 'ggvgvvgvv', '', 'vggvvgg', '', '', '', 'gvvvvvgg', 'gvggvggvg', 'ggvvvgvg', 'vgvgvgvgvvv', 'ggvvgvvv', '', 'vgvvvggg', '', 'gggvvvv', 'ggvgvgg', '', '', '', '', 'gvvgvgv', 'vggvvvgv', 'ggggvgvv', 'vgvggvvv', 'vvgvggvg', 'gvggvgvv', 'vvgvvgg']
    got = solution.shortestSubstrings(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = [['samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'qklrnnsglkcfmvzppnzb']]
    want = ['', '', '', '', '', 'b']
    got = solution.shortestSubstrings(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = [['baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa', 'baaaaaaaaaaaaaaaaa']]
    want = ['', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '']
    got = solution.shortestSubstrings(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = [['ssfouawlkomtoeradjne', 'albmvymnumbckrlhkhjp', 'qycmgqqaomufduzvaaax', 'olnqmjrqnrockirmopjf', 'ksrjhrqpszxcbthgwgya', 'qewdemeyfvguxhfprezt', 'ovopozaoequklkygzban', 'yngmxgqdpxnspzvccriz', 'gruvugbsboytxsivfomp', 'razgfhejcujkxggjjtpn', 'qdbjnxftprdmgyobtjax', 'rryowhczrrawntwgfmiz', 'hrurkzwdfhuhgrpetssi', 'colaeezdsmrujysiyrqc', 'udbacbbxggjrhpwlklgm', 'zxidvbbrofofjybnmlml', 'diosurrcpjflotyzmlbz', 'gggqhfkacjryionhoufb', 'zzbyeusxbaojdyhpffvv', 'tyqcuoobnhjzhdjtfrxs', 'cohkcutyqdzgdtgbskpl', 'qsdbnemqhqtaxhpcdmwn', 'wuyfqciknoruyeuciiyi', 'dyfzgbiduwexkzaainby', 'kacvlyinjqnblexarqcb', 'pzgwcgtedsrfzbrxirud', 'kwuolabdmgkbixqoyrgu', 'rgjfrdlgxhtsjwvmjhtm', 'pkganfdsnclqhxawxxbw', 'sfopiyligxmhlydylykj', 'lheanxxbdcsafbozoefq', 'vkdwhqrwzprurdunrdse', 'imgkcontjuizogvlmckn', 'ytsyrenkljppzicdkfow', 'atnquredkgypugwpjgvp', 'tovqcghrrryqdvsgumrl', 'hkelhheptnpozmzvmlau', 'cccxyrmfwaozyccvblpr', 'mkdomywpbdjkypmidrcf', 'tabteiwkngliimgkhyqo', 'npgdfyfxlxmcmlbxedco', 'zwmtjrzkwptuadklfpbc', 'gqenjitahcofqzjwesba', 'ntjoydjphjjhxevswvlv', 'nziuddfiodishklwfjee', 'uzmubglagujvxyaumlvb', 'ulitqaefcqrtimskmzdz', 'sfxtiwnmtlguosqtbnba', 'tbmbxjpeymjswulnwnij', 'ztbvwjjoajuwdiwhonqr', 'vcpybsgmirtoaiezauhd', 'yahujfeaarrjurkxzllq', 'csquvwtyuzywuztynpcl', 'rlbgbzywmbalkdxuxwoj', 'alhsdqwtgggtsnjasiwi', 'grqvoludknkvjfagvkcj', 'bexjkepshqndngszthca', 'lziwhodmgklitmihvvrf', 'taeoezuywxkqircqtdjy', 'gevxsifwhdbakpblfsmj', 'oiiscmnebxhguhhttxth', 'kpcvmiuizpeoeeiuxgca', 'drwzpzucwprtyzwyabjv', 'pbvyegofjjfohdzlhspj', 'ttjqwhbarowkzlmobfai', 'vbakqrxxdtsciropjdxe', 'poqqw', 'wcehwltoskbwmrrnrzum', 'vunmnqnwyyvsvlpklwdv', 'vfkndinkutmfkxtscksu', 'ubcfeqqppkchqdbrpcxn', 'sfferknpujarmcpwotpd', 'yzgpwhujbwcgedhfvomi', 'pzbvoyojiqouabfqoucm', 'ccisanbywxyaopogqury', 'qsqxgrzjivfslmuligyz', 'kjnlafyrntbgiiegdzpq', 'armltfakmjnyexbyswwe', 'qpvbdpywzebqzyharofj', 'diwgrxkrqbvgzzumqjww', 'jljwwgrdmwrikqkihoio', 'lahenxjcvwdfsygjfgxq', 'keyxwtjfutsnntiljozw', 'pqkdukaerqhddlwpvmtf']]
    want = ['ko', 'mv', 'qy', 'oc', 'xc', 'de', 'aoe', 'cr', 'mp', 'az', 'ft', 'cz', 'et', 'aee', 'rh', 'bbr', 'fl', 'acj', 'pf', 'jz', 'pl', 'axh', 'no', 'aai', 'le', 'brx', 'ix', 'sj', 'ga', 'hl', 'afb', 'dw', 'ckn', 'ic', 'at', 'gh', 'el', 'wa', 'do', 'hy', 'lx', 'tu', 'es', 'ph', 'fi', 'agu', 'fc', 'tl', 'ij', 'aj', 'aie', 'll', 'yu', 'xu', 'as', 'kv', 'be', 'hv', 'qi', 'if', 'bxh', 'gc', 'cw', 'go', 'hb', 'xd', 'oq', 'ce', 'sv', 'ku', 'ch', 'pd', 'dh', 'iq', 'anb', 'qx', 'gi', 'ny', 'bq', 'qb', 'jl', 'fg', 'fu', 'aer']
    got = solution.shortestSubstrings(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = [['gxgwgxgwggggg', 'gwwwgw', 'gwwwxxggwxwx', 'w', 'ggwwwxwxwgxgxw', 'xgggxxw', 'xggggxggxwgw', 'xggxxxwwxwwgww', 'gxwxwwxg', 'wwwxwgwwggxxxgxx', 'wwgwxg', 'gwwgxxwgx', 'wwwwx', 'gwgxwxwxxgwgxgwgxw', 'xxxg', 'xwgwwggwx', 'wgwgwgggg', 'gx', 'xxxwxxxxw', 'wwxxxw', 'ggwgggwxwg', 'xggwxgg', 'gggxwxwxwwgxwxggwgwx', 'gwwxwgxwgxgx', 'wgggwgwxgxggxgxgwxw', 'wgggxwgxwwgwwwwgwww', 'wwgggwgxgxgxxw', 'wxgwxw', 'xxxw', 'gxwxxxwxgxwxwgw', 'gx', 'wxxxxx', 'wgg', 'xxxgxwgwgwww', 'gxxgwxxggwwgggxggww', 'xxgwwwx', 'ggwwgxw', 'gxxg', 'wxwgxgwxwggxwwwggwx', 'wxxwg', 'wxgxwwggggxgwggwgw', 'xwwxwgww', 'xgw', 'xwwggxwww', 'ggxwgxwwggwxwwg', 'xxggwxgggggx', 'ggwxxgwxwggxwxwxxgg', 'gwgw', 'xggxwggxwx', 'gxgwgggxxwwgw', 'wxw', 'gwgwwxxgxg', 'ggwwxgw', 'g', 'wwgggwww', 'ggxwxwgxwxgx', 'wgwwxwggxwgxxwwwwxg', 'gwxgwxxxxx', 'xwgggxgwgxgwgxwxxgg', 'ggwwxxx', 'xggwggwxxggggggw', 'wggw', 'gwwwxwwgggxwgxxx', 'xxwxxxggxxwgxggwwg', 'gxxwgxwxgggxwgxwx', 'xwwggwggxwwwwwggw', 'xwxggw', 'wwww', 'ggwxwxxwwgwxwwwx', 'wxxxgggwwwgwgwx', 'wwggw', 'xwgwxwggxgxgxgxgxgxg', 'xxxxxxwxgwxwxxxw', 'xxxwwgwxgxwgg', 'xxwxwxxwwxgww', 'xxwwxggggwg', 'wxxxgwxwwwxxwwxxw', 'ggggggwg', 'wxxwxxgwgx', 'ggxwggxwxggg', 'gwxx', 'wwwxxggg', 'wgxxwgwgww', 'g', 'gg', 'ggxxxgxwxxgwxw', 'gggwxxgwx', 'wxwwggx', 'gxgxggxx', 'gxgwgwwwgwxxwxwgwx', 'gggw', 'wggwxg', 'wgwxgx', 'gwwxxwxxgwxxxwgww']]
    want = ['wggggg', '', 'gwwwxx', '', 'gxgxw', 'xgggxx', 'ggxggx', 'gxxxw', 'wxwwx', 'wggxx', '', 'wwgxx', '', 'wgxwxw', '', 'gwwggw', 'gwgwg', '', 'wxxxxw', 'wwxxxw', 'gggwxw', '', 'xwwgx', 'wgxwg', 'wxgxg', 'gwwww', 'ggwgx', '', '', 'gxwxxx', '', '', '', 'gxwgwg', 'gxxgw', 'xgwww', 'ggwwgx', '', 'xwwwg', 'wxxwg', 'xgxww', 'xwwxwg', '', 'wwggxw', 'ggwxww', 'gggggx', 'wggxwxw', '', 'xggxwgg', 'ggxxww', '', 'wxxgx', 'gwwxg', '', 'wgggww', 'gxwxgx', 'wwwxg', 'gwxgw', 'xwggg', 'ggwwxx', 'ggwggw', '', 'wgxxx', 'wgxgg', 'wxgggx', 'gwggx', '', '', 'wgwxww', 'wwgwg', '', 'wggxg', 'xwxgw', 'gwxgxw', 'wxgww', 'wwxgg', 'xwwxx', 'gggggwg', 'xxwxxgwg', 'ggxwxg', '', 'wwxxggg', 'gxxwgw', '', '', 'xgxwxx', 'gggwxx', 'wxwwggx', 'gxggxx', 'gwxxw', '', 'wggwxg', '', 'xxxwg']
    got = solution.shortestSubstrings(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = [['ygjqmagoa', 'dktccxwzvm', 'mmmjmjm', 'wiznn', 'bxtqhg', 'emknytby']]
    want = ['a', 'c', 'jm', 'i', 'h', 'e']
    got = solution.shortestSubstrings(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = [['tygnlmptzntgogtutjmw', 'izmnvrnymebvhgbqsnrl', 'ssxqycmssedrnbqjymbx', 'opypgzeozmpdsmqklgix', 'mdzobdanmrhpzuvtgdzf', 'lulftoisfctchxdycluq', 'gcihcackxhfsnvsmclal', 'pymsqxgvrrltmhwtwnrk', 'ishpaxhknjwgslszvked', 'vhrmwhdnnxzvpynfwcca', 'odhhgkcwdmjzrtudyjft', 'yrduwcsgewhmyxomnjua', 'kbcyjmlaidycureqgwlc', 'fryzbwjelpesruznafnx', 'xokwyoxeqbnhgtbhbsvw', 'cslegcwijrhbumpfgbcc', 'yjwxrlvnbkfvxzermtik', 'mhtnaudrpxaxrxrzgmzv', 'nalshfombthmbevhhwvk', 'hpwyglkqmytvmxpbkqpo', 'qasdoonetcvohxjnuctt', 'xackwizrmqzqzyfhdlci', 'mlfqdcjyyqxkotiramqb', 'chcejpjcfivpsgnastul', 'ggdxxvjdgvojzvvxcrcr', 'xfhlaelhwlhskaviuire', 'duduzffulyzupsesbvxc', 'nkjflosakchoibqqrxup', 'ksurnxhgqfmtpeahincr', 'amzrvpsmzulfhcheikqu', 'egpjzufnfgizehmnjkxq', 'zeefnimjfloqpqvhqjdf', 'zovojhlmclinnixncrak', 'dicbjtzfoxsodiedjjtm', 'vwtxizfpedkfhbwrofyd', 'jpngpivgkuhkxtipxojy', 'qysvcssxolcjwueuksms', 'dtqefvkgtxajdnihznci', 'wksftpvhwklaopapcuva', 'cyfah', 'byfzmenkthlkvhrlfhvg', 'nqvgakziszijlceeiqbs', 'ipnlhjmedzkswjpyqpzc', 'snzvpufuctrurmcowshg', 'bgcesbcwzhdfsexvvmlc', 'djafaxrnmxdbbzvmqclf', 'noejgrlfdpmrhvwniozo', 'lanthtxpcbkgiidiasyr', 'gugvkyjkibhuvolonpoy', 'wyfoljkbhfrihasykcuv', 'mmowegvipoefkrdcyopy', 'zlcheyovypqqsxqjbrpl', 'oejjegjowcgqgimjmuvr', 'kxpocfllyeywmjmldcci', 'hpkteqvmgojmsfqezytt', 'qydhgboadpbrvpujnsbz', 'spssqxbgrnfajonkklow', 'difbytgdysicqpxzbidc', 'smcnlotlawodcmfwutrj', 'djcgokkfnypcogkdecud', 'gprndabubaqovttugxht', 'wxmsuyldlrxorqbhskux', 'wmjhhnoadjuredkyyarx', 'rcgtfmrhiwqnstpycmxj', 'ikgjgcbaybtyzyteyvxk', 'umyxyzbehworpacfcxbs', 'scpbslhyntxunsjunqkp', 'ixzaajgopfwojmvopsls', 'ugacmjeykdqxqlywyxfh', 'wksbzsqmojqbxvxxrejb', 'sgkclldubparxeugbdsz', 'ngokzdertutddguonltl', 'vfyyqmvpiylcaeczfxcq', 'unpxeugpuufsjpjwmuen', 'dbkvhkkshcmmosqblhav', 'lzwcmvyooiwpzctcdmkd', 'xglmayibnztjimngcduk', 'iktlhxxvnphhmozxzfjc', 'qractoiymxbddklsjqgo', 'fuqnbwkibwimywyjtkjq']]
    want = ['pt', 'eb', 'bqj', 'eo', 'md', 'lu', 'vs', 'rk', 'gs', 'cca', 'wd', 'ew', 'ai', 'lp', 'nh', 'jr', 'lv', 'au', 'ev', 'pw', 'cv', 'qz', 'ko', 'fi', 'dx', 'iu', 'ff', 'ho', 'ea', 'qu', 'egp', 'hq', 'li', 'bj', 'fp', 'uh', 'vc', 'dt', 'ao', 'cyf', 'fz', 'iq', 'hj', 'ws', 'ex', 'bb', 'fd', 'ia', 'hu', 'lj', 'fk', 'pl', 'cgq', 'oc', 'ez', 'bo', 'sp', 'bi', 'aw', 'cgo', 'ab', 'lr', 'hn', 'tf', 'yb', 'cx', 'cp', 'aa', 'dq', 'zs', 'bp', 'td', 'cz', 'uu', 'bl', 'lz', 'ji', 'fj', 'act', 'tk']
    got = solution.shortestSubstrings(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = [['ewewweeeewewww', 'eeeweeewwewwwwe', 'wwwwwwewwwee', 'eewewweweeweewewewwe', 'w', 'eeewwe', 'we', 'wwewwwewee', 'eeeewewewee', 'wee', 'weew', 'ewweeee', 'weeeweewwweweewwwwew', 'ww', 'w', 'ew', 'weeeeeeewweeeweewww', 'wweewwwewewewwwew', 'w', 'ewew', 'eew', 'wew', 'weewwwweeww', 'ew', 'weweeww']]
    want = ['weeeew', 'eweee', 'wwwww', 'weewe', '', '', '', 'wewwwewe', 'ewewee', '', '', '', 'ewwwwew', '', '', '', 'eeeee', 'wwewew', '', '', '', '', 'wwweew', '', '']
    got = solution.shortestSubstrings(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = [['samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'pekuisjjxtlotcxbxtun']]
    want = ['', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', 'b']
    got = solution.shortestSubstrings(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = [['kseqxoevihbhmtfjvvtt', 'rnvex', 'xhjmkefmzvkxfipfdnlh', 'cpmaplzxljcxnxxklkqp', 'saabcnjufgqgesfokkul', 'sqzehjzehyqrzpbccgcd', 'fjmyksogioywvypjunnl', 'mamgifvtvpdvvrypcjyn', 'rchklnyblaabkhahyixs', 'kiyghkhtakzffsmtxzge', 'dnsgauqisjwfbnhjqtcf', 'mtofjodojpsnlhkhnnlz', 'wgivokhpybijkdbprnyj', 'ppepjsiqgdmldiwjitjd', 'ipxhdbqyjguetvvvqire', 'dmjmzqfsyqkgqpvionlu', 'hyyujrsphsuxcpjzzvyw', 'qlfijfduvcmtcxkxiuxs', 'bfadnuegspkitlkeogog', 'curthnaosbeyliixbijc', 'onlkaeeopmxwfwjztijq', 'bbqwthksbsgpwyhdqern', 'fvtvuqnhddabqizlynxx', 'kdvkbidqufdokxdtcovu', 'ndduxubutituvrtauznj', 'nhiqcukbswhzuwhiqred', 'vtnjtligefgzqdbahyir', 'ivktdhgqyylcyfiancab', 'mhluwnxcxhplxrtkiiql', 'btyuofvghdqzjotmmtco', 'lozdkgmjpvvwwduorafh', 'wzjyyjzfrarfemupqhgx', 'kovtzyefvfqucawetkry', 'wicgawnclghytnthpotg', 'xhlzciaxckdzkcdyvkuq', 'vjzfqmdeyrhwnjvdxmwy', 'imuwfyvoimbqnydmqwfg', 'onrprvbwsutspkvnufgi', 'qutwcotqkfraukqsutxe', 'rafzdbrundhociduetib', 'ybrwpixqdxcpjkczcflw', 'qxreidtsxkoeelfpbgjs', 'gnvxrxcnoayxncnfiiqm', 'wequewsubcgpdhehjukg', 'prsbgcuercvwrsseiqjh', 'moovkcwpbgkldbypmybo', 'wfkgtvieauntajndhcoc', 'tozbysaexrwvuedozfzl']]
    want = ['bh', 've', 'fm', 'ap', 'es', 'cc', 'oy', 'am', 'bk', 'ak', 'bn', 'od', 'bp', 'di', 'gu', 'qf', 'hs', 'cm', 'ad', 'ao', 'fw', 'bb', 'da', 'xd', 'bu', 'hi', 'ba', 'an', 'lx', 'bt', 'dk', 'ar', 'kr', 'cl', 'ax', 'de', 'fy', 'bw', 'kf', 'ho', 'cz', 'el', 'ay', 'ew', 'cv', 'bo', 'aj', 'ys']
    got = solution.shortestSubstrings(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = [['elrlrlleereerlr', 'rr', 'eereerrrrlrrrerelrll', 'erlrrlelerlelr', 'rer', 'eerleeeleeeerr', 'reelrererrerlrell', 'elerllerl', 'eeee', 'lererllereeerereerr', 'elleeerrrllrrrlrlrrl', 'rrlrrr', 'elrelrellller', 'elrrrrl', 'er', 'lrleerlrlelrrl', 'eeel', 'eerree', 'eeeerllrrrrlerlrle', 'le', 'rrelllrrreeelerlrlr', 'lrrelrrlerrrllle', 'lelleerel', 'lerllrerlrlllelreel', 'r', 'lrreerr', 'eeerlrrereleleeree', 'reerrrerellrlleerer', 'eellreee', 'rrerrellrelelrer', 'lllrlrerler', 'rlrlrrel', 'eerlreeerr']]
    want = ['elrlr', '', 'elrll', 'erlel', '', 'eelee', 'eelr', 'llerl', '', 'lere', 'leeer', '', 'llll', 'elrrr', '', 'leerl', '', 'eerre', 'eerll', '', 'eeler', 'lerr', 'lell', 'llel', '', 'lrree', 'eleer', 'ellrl', 'eell', 'elelr', 'erler', 'lrlrre', 'rlree']
    got = solution.shortestSubstrings(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = [['ojjoojojojjojjo', 'oojjoojjj', 'oojjjoojojjjo', 'ooooojojjooo', 'jojoojjjjjojo', 'joojjojooo', 'jjoo', 'jojjjjoooojjjoojoo', 'o', 'jjojjjjojooojojjj', 'ooojojjoj', 'ojjojooojooojj', 'jjjooooooooooo', 'joojjjjojjojojojoj', 'joooojoojooo', 'jjoooojojojooooj', 'ojjojojjjj', 'jjojoojoojojjj', 'oojjjj', 'jjjjjjo', 'jjjojojojjj', 'ojooooojojjojj', 'jojjjojjj', 'jjojjojoo', 'jojjoooojjooj', 'ojj', 'jjoojoojooooj', 'ojojoojjooojjojoo', 'ojjjojoojjjojojj', 'oojjjojjjoj', 'joooooooooojoojjoo', 'ooojojjo', 'ooj', 'oojoo', 'ojoooojjooooojjjojj', 'ojooojj', 'jjojjjoojjojo', 'oojjooojojojjo', 'joooojoojjjjo', 'jjjooj', 'joojooj', 'ojjjjojj', 'ooo', 'ojjooojo', 'oojjojjojojoojoojo', 'jjoojojoojjjojo', 'jojooojooojojjjjjjoj', 'jjjjjojjoj', 'ooojjjjjoojjojooojo', 'oj', 'jjjjojjoo', 'jjooojjjojjjj']]
    want = ['ojjoojo', 'jjoojjj', 'ojojjjo', 'ojojjoo', 'jjjjjojo', '', '', 'jjjjooo', '', 'jjjjojoo', '', 'oojooojj', 'jjjooooo', 'jojojojo', 'ooojoojo', 'jojoooo', 'jjojojjj', 'ojoojoj', '', '', 'jjjojojo', 'ojooooo', 'jojjjojj', 'jojjojoo', 'jojjoooo', '', 'oojoooo', 'jooojjo', 'jjjojojj', 'jjjojjjo', 'ooooooj', '', '', '', 'ooooojj', '', 'jojjjoo', 'jjooojoj', 'oojoojjj', '', '', '', '', '', 'oojjojj', 'oojojoo', 'jojjjjj', 'jjjjjojj', 'jjjjjoo', '', 'jjojjoo', 'jooojjj']
    got = solution.shortestSubstrings(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = [['zkcxrvlhjdmppgcmdrpk', 'eodlctdheqazttpibcaa', 'mabsjbyafdpcdkszemyk', 'fpiiaszbmghipwvuqnlg', 'bvxcbnndwrhgzzhyuoxb', 'wpujzjqepgtiwryodwtk', 'miqnjieblcphlbdzpzmv', 'enbzgjafwmabdwmtsqgv', 'pqmrfoegbrarybpmskve', 'npxpxxlssprcirmqgiwc', 'bflxvwoehrylkxrplevm', 'chgnawlfauvkbwsgtjms', 'zkgodhaojsmhknjndgyt', 'oulbawpgjnmougnsdoxw', 'vorqjjixtpjnzrewojoz', 'rgnoqgyumtgwwzozryqb', 'udfcwenarbuvsyjyoyos', 'kxylmvksfznefhvqmcuo', 'luejh', 'dtvfgwvpuylordrovamv', 'lyldtvxixkdmrxatjhwq', 'wchgmxmlrozfqgetoqrb', 'xbvwquyjtgkcdpaymksy', 'qdhwjwbigilitkurvatn', 'totvwkcwroviwlcsezgb', 'egnrsnuogiqzmosbgexh', 'nuqnfgkygxpvwvavbqim', 'qkbyixuuncuggrrwolbo', 'ojbdkfriaddfmayvoptc', 'qlxrirsylnedcyydieve', 'dqrqtcgswgrmxginzjml', 'jutncfwmqgcxyliueabd', 'arymuhbeezsmiapkckym', 'pqcqzbulvvavxmcglotv', 'gcazmcuhlqedhblrmqwq', 'dewyzcxilefyzocrkcay', 'byvljlketycervtipzoi', 'jlyyhpjooeenwllnshxb', 'nnualdqhdltubbiflgud', 'ytercfqibblogmhqnreh', 'qnhxddyifmswhlaszenn', 'vdkcnfddxjinmlopmqat', 'mjpussflvujpshhlwswa', 'kvokwjlodqnoscrovvtr', 'vyiqxednlnzvwjzvwznj', 'gnffguzebeaeihiojiqv', 'iajcsvbmroxyninvtsln']]
    want = ['cm', 'aa', 'bs', 'fp', 'bn', 'ep', 'cp', 'bz', 'bp', 'ci', 'bf', 'au', 'ao', 'ba', 'jj', 'qb', 'fc', 'fh', 'ej', 'am', 'kd', 'zf', 'jt', 'ig', 'se', 'bg', 'bq', 'bo', 'ad', 'cy', 'gs', 'iu', 'ap', 'cq', 'lq', 'de', 'ce', 'hp', 'al', 'hq', 'dy', 'cn', 'hh', 'kw', 'dn', 'ae', 'aj']
    got = solution.shortestSubstrings(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = [['samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'samestring', 'yngsyulxemsgufamprsx']]
    want = ['', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', 'f']
    got = solution.shortestSubstrings(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = [['dbdnnndbndbbbbdbb', 'nnbbbndbb', 'dbdbbnbnnbnnddd', 'bnbbdbnbbbdnddnd', 'dnbnddbdbb', 'bbbbdnndb', 'dnn', 'dddddbndd', 'bbdbdbbdnbbnnbn', 'dbdnbbbndbbbnd', 'n', 'dndnd', 'bbnndnbdbbnnnbdn', 'bndddndbnnbbdndbnnd', 'bndnnnn', 'dbnddnbb']]
    want = ['nnnd', 'nnbbb', 'bbnb', 'bdbn', 'ddbd', 'dnnd', '', 'ddbn', 'bdbd', 'dbbbn', '', 'dndn', 'nbd', 'dbnn', 'bndn', 'ddnb']
    got = solution.shortestSubstrings(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

