"""Scoring checks for lcb_3638 -- NOT part of any workspace.

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
    args = ['acab']
    want = 1
    got = solution.makeStringGood(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = ['wddw']
    want = 0
    got = solution.makeStringGood(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = ['aaabc']
    want = 2
    got = solution.makeStringGood(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = ['becda']
    want = 0
    got = solution.makeStringGood(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = ['ooffjjfj']
    want = 1
    got = solution.makeStringGood(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = ['dxxmggddbbbyxddbzgbqdmgbmgydqmwxgmdzxdxwxgzxxdmxzgmmbdggmmwbxzgxxbxdzggzggggxwgdbgddmmxxgxxmgmxzbssdzmbdgdgdgggqyxdmgxbbdxsddgyzdwsxybxssxxdmgxbgwsmxggxmdwgdxzdyzdgbzzwqxzbbdoowxsgbgzxxzmxybxgbwxmsgzmozgbgqzbgbzmxxgozxmdbxqqddbmmxwdbdbmwzmdgxmbdxxwxgbbsxgggzmbdgdzbmzbmmmxdzsmbzmxgdmqdwdgxdgdgxbdxbgzmbdwggmzdxxgdzzogdxmqdxdddgbbxwgxmbmxdbzbdbxmddxdxwddzqgbxgdgqgddmgqzdzdzzbdbsdzobddzyxddxwxxbgqddmdsmggbzbogxdmbbgbdxzgzbxzswgbgxgzdggbdxymzbdddzxdbddbzzbdxggdddxdgdggdxmdxwdxmdggxbqdxddwgdqmmgsgbzddzgdbwdzzxydmgxdgmqxdbddqbgsdgsxmggmzzzxmdmxxddxbzgzdgsmdmgzgddmbbgdmdgmbdzmgddzbzmwmszzdsxdzzdgggzbxbxqbzzdsgxgxbqxxdmxmxzxdbgbwgzdbmgzbdggmgqxzxgbzgmbxdxygdmzmggdxgzdzgmmmdxmzyxzgsxxxxgdzggwgdzdxmqbgggdqbxwmxdggzgdddqggzbdzbdosdqygsdxbggdxgqdmxxgggdmdwdgxzzgxmdgzqddbygydmxdwbdbmxsxzdbmqxxddzxdxggxmmzzgdgmzmbzdgdxogbbzddmmgddbddgqxgmxzsgbggqxwzgbyoddgddbxgzmggqdsbxxxxzsgxogwzybzwbdbzsgdggddbmxxbsgbbsbzgzxbxmqbbbgbgzgwgdgmmbbxgxgdxgzxxzdxmzdgmxgdzbdogbgsbggddxbwdzzdddgdzxxszdbdxzdzddgdxmddxmgxmzqdzxbbbdggbdzbzbdxdwbxzxbbwmysxmmxmyzgxymwmmbxmwdwxgzggxgbxdqdzddggbwbggwmxmxgxbxzzxbgxxszmsbbxxddxdgxsbgxxgzzogsddzmydxyddxgzxddwmgygxbxxgsxmxgdgbzssgqxbgqxgdzddddxzggdzgxgmyzbddbymbsgzggbgsdxxddmgzxgobdqyzdxmxgxwdgbdbzwgxbmgdbxdzgmmxzxoxbgmgdgxdgqzmydbwzxxbzgzddggodxbmoxxxmwbgxmywdgzxdsgmdsbzgxzzmxgggbdgdsxzgxxxxqwwgwgyggdzwbxdbdxxmdogbbxdzxzggdxxgbzggqdmdmxmwbgdgbmxdddwdxdgmdgzbzqmxxdddgoxzbwxgmggwszdbxgddsgdgzbzqmmgbzwzdgqdbdxxszdzgzdbzszbzgyzxgbbmgbxgxbbmyxxmboxdswbwzmxgggbmwxxdwxzbxbgxbqqbbymwxdqmbxxdxgdzzsxbxqgmzdxqddgxxgwyqdxdxdzgdmbdxdggmmgxzmdgdodgqbgyqxxbysmbxbgxgggozxddmzqxdmxbgbbxbzgdgbdwmbxgdbzqxdxswdzdwzgdggggbsxddzdxmdgdbxggxdddxxxxwwdmdxbxmzsmqbzbbgdzqsdgzwdzgdsdgggzbqmxmwgsbgwdgmdgxmzxxzxdmggxzxdxqdzgdgmxxxdbgddmgomgwxbzmxxgbgbmqsdggzwyxxmxdxgyzwxzmdmzgwxbzqbgybxzgbdmxxbddqzggbgdommxgbozgggdddmbgydggmxzxxzsbggzdgxxxgxgxdbdgdzgzdgmbggomqdzxdgmxgxmmgxygdgbbdxqmdzxdgzbdqsygzgzwqxgddxzdqgdmzxwmzxxmmgdbszydgdxbgqbdggzsgsddddgxgdzmdmxddxbzdgzozmgbdmxddxgxmbqdzombxxbzgbxdybgmxddbxzbdzxxxysbdzmmxxdgxoybxbmbxqqgwqwzgdobxmsgdzgxmxgmdmqxbwddozxddxdbdxgzgmxmzdddbxxsxmzgqxgggoxgyxmbqzxzzdgdbzmbxmzdgdzyddzdgddmxdgzxdmwmwxbxmzdzgmdbdgdzgwsddxxmgxzsxqgogxdogbddxbdddxbbgxdmgzwdmxzdgmdgxgdbxzsxmbbxsggmgdzgmzddxdgdgdbzxxzxbmgzgggozbzdxsqddzgxxddbsgxmwdwbzmyxwdmbddqwgbddmxbzggxbxqgmdxzxbxbmzdzbdgxgwxdmqbbwoyzzgbbqqgddxbybgdssdggbxgbxzsdxxzxqsxbbmddxmbgmggzbodgxsqzxmxdgdxmgmmxgzxdbggxddbdwzdxgggdbxgdxxgmgmdddxmsdgzbmbqxwdgddqmdxbbgmgdbxgmxdszzzddxgmxxzmdzzbxgmgxgsqmbgzxxmdmggzgdysdxbdmdgxsygzgzqxzmmbxzgzxgxbdgxxbxdmbmbxbdmzmddxdwydwmgzqdzqmggdzbgdqgxxqzdbxdosoygybdydmdqywzddmsdggxzbzmxzdmgbbogbzgbzmgwdggxddgdxgbbgdzqgxzsmxdzdxgddxbddgddddwxgzosdzzbddgbgbmbzmmbgdzzdxzwxgzbzdbxybdwzwgxdwgsxdbdybxmxmwmzmgzgzdmsxmdzgdyzbbgxdzbgdgzdxmqdydzbqxddxdgxdggxqzdqdgqddmwybxqwsddzwdgbsmgzzbbzoggggbgxbgggdxxgggdddxxdsgdxxbmsxsxqodbbddxbbzdbxzbddodxxgyzmbdxodzmdgbgzydzxmbmmgbxxdgmxdgxdzggmmqdbbgwxzxgdbddxdgzdgwdbdqwdxgxxswmmxbmqgxgzxwgzxgmdmgdxdbwggmddombbdxdxgybdzdbzbgxgdbbxgmzxxbdsdgxddwggdmbdmxxbbgxzzzsmbgzmxgbgwgzxggmmbsobmmgqdbbmmybxgbgdmdbzdggdgxgzydzgzxqxxgwxgmmgxgogzmxdbxdzggsmmmbmxdzgbgzdgxdzgmxmdoxmgmxddbgdxdxgxydmsgdddgbmmdbwdgygdbgddxgzwdgdxdgxgxgsxxddgxdbbxgbsgqxzzwbgqyzdqmxzggxybyzmmgwmsgssbmgzgdxgzbbdzdxxdxqxbdbbggzxzmdgdzdgmddbmdzxgoxdgdxgxzyxqgddbsbdbxxdbgbzqddswzmzdmxbsbbddddwbzdgmzggxoxddgdgzxggddgzxxdsggosggmggdyxydmdszgqdbxxybzsddbxzxmgzgsdwwgzbydzdgdgzxxdbogxsxgzgxdgmdxgsdggddxgdzzgbggxygbmgxqbmxgxdgmxdddxgdqggdsdswgzdogwdbxmsmmzgxggzdggxzmbbysgzygbgmgxmdgbmxdwbmmzmmggbxwgdmxdwmgzgxgdxsdxdbbxggmqggmxmdgzmzmddddmmmmzgdbmbgbxxmdbdgxgdxbzxdwddxmmwxbxxdxddgbmyxzgbmxgdqmxxzmdbxxbzsbgxgbmgdbgdxdmgxsbgdxmmddggmgywgzoxbdygmwdgxxdxgbmzzbsbbzqdxgmdxmgqzobzddgwyqgdxzxdodmgzbbsdxxdsbmzdmgbqmdqxddmmgdbbbxwgydwyzgdxxxgddmdbxdzzoszgdbdwdbqzyxgxzbbxdwxzbbdgdddgwzmsgbxgdgbxggbdbddbgxqmwggmgbgxydddwbgsxwgqdbzymgbbzgsmgggxzdmxdmxxddgyxybgdzgxqwmddomxxxxggzozzyddqygsdxdzggmgxgxgddddbgbmmygzmbggqbdgzgmzxdygzszbdgxzgqmbdxmgdbmmbxxgbxmggmddggxxzgsgmbzzdygbzsodgwdsddwbxygwzzqbdbxymxgxddmxywwdmwggzxgxgdgzgwxbqwgdzzdzxxbzsgbgggwodyxdddmdmgdgmgdozmgdmdgdzbbzwmsdmgbwgmybzbbbzddxxbdxddggdmdyqodgzdxbgggzbzgggggggbxyxbddddygxgzggbdbggbqmqgxbdbbbgmwsbgggmgbbddsdmggqmgzymqxxxddxzddgxdsggzgmxmxgzgzbmdgddbqbgzgmxdgxxdgxxbbgxdxqbgzbdxxzgdygwxbbgzdxbsgdswggdqbzszxgboxzgxmdgwdgxgmdddwdgxdgggqgmdbbgdyydddddbgxddbsgzdzxzbgdxgxdxzwbddwxbwdyszdzgyyzbbmxzyddqxsgyobgxdmbxbdxxbdbyoygbgdgmbgwdyqmggxsbmggsyzbzdxzgdxbxgyggdmzzgqbqxgxzgyoxmgbdbdxzbyxdgzxdmgbzmqmdymgdbxbbdggxoxmggbzbbgxymgbxdozmdmxwgmbxdgbwmqyywbzbdmmzxmwdqgxgxygmdgxzbxxgxbddgwmgozdmmmddxdzdxdybgdxxxzgmdgydmxmyzdmxddgmzbgdygzzdgzggbxxgdbgdsyxzdzmddybwqgbygzzddbxxmxmzybmggmbzgxbzbdgbgwzggwgmdxbmbgwzgdxxzbmgdmsmgdxggwxddmdxbzdwbmmggxdgxmbzddxddxmymmgsbxggzzz']
    want = 1538
    got = solution.makeStringGood(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = ['bba']
    want = 1
    got = solution.makeStringGood(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = ['kdyyrkkdykkdyrr']
    want = 3
    got = solution.makeStringGood(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = ['zzzzsz']
    want = 1
    got = solution.makeStringGood(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = ['apop']
    want = 1
    got = solution.makeStringGood(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = ['accdddddbebbabbe']
    want = 5
    got = solution.makeStringGood(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = ['aaaabbaaaaba']
    want = 3
    got = solution.makeStringGood(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = ['eususueuss']
    want = 2
    got = solution.makeStringGood(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = ['misazhyzmhslfyafzrsmyyazfffcfbfyhhrsmmhhbammfslzhszyfmyhfzfzrclfshrcrhfiyyrcfzmbssafcsbrhmsshmmmichhrsrbcshamymsmhhzhfmsmyyshhszhmbiimsyilfcmylzryccifmcyslhchiycbffhylzfibimhymrfizmclzifrymsaibyzcciyghsffzhfzymffssccsyhifyzrylllssihhfimhchmsfzhmsmzhfhclrsrirbhryglzycfrzyfhazyfsmlraisahyhihifrciiymfyzyzmmsshfyhfshmhzzshmhzcaiychhmiziyrmhmamrrrimhifszsrmfzhacyrzraysyzsysiichhizrcrzhzibfchfyhfzzyhsiymhcyshmbrrzhbsrrlcmmrhsffyylmhmbyfshmhmhcyymrzfmfzzcyhsrhhshymrmsmhzyriifhmziyahcyrzrszaizrfyzrhscimmyzcircmsyrsmysrlsrbsaysahhfcsfyhsszalzyhharsssrmhfrbsshisihfbzmharzfymschrfmyrghziifszzsfzshmmhhyyscmrafshshmhifyzmfmrzyhhriiscimhzsmcclfmhmmmsryiblaiizymaamzifssarhsmysyyiifzzahizbhfihrzyfyiimmrmzzfmfcymzhrscfhfcfyziyicmmrhshbmrslimhhcffhsyyhcfhylhrihffmcyzhlfalaryymslsyffihyfyiyrzffczrmffbalzasammzciysiryzizrchaiszrhhirfcfzysibfrsyzyfzmbsssrzhzirrizyzyiryimfiihsmmzmcyhrfmmhlyrcsfmsifmmlysfhyhbryhmhyzlshrrfrszhsiszmrmfhhbmzrfrzmzhhzrymfyzrzcfmclzyflymhlfscfslhhfafiyfysfyrhlyyihmyahizizlaccyhcmicfmffchhmhzgrhlmysbymsshrasicisyhszlzlcysaamhmhmilsmrhyrfmybyfzmsfffhyyffhzciilylfsffhcrhfycyssihhfyhyrfchfhbmszyshimissshzrfifcmhzzrsryfzzihihmasfrhchzhhfrzmhacmfzrirchzfyzzhsyhsyhfrhzhzzzzfscsmazsyihsizasizzfcmisszrhhiiizaszyhlsaffhsmychsfrhisiaazmfzasmlhiraiyhzzclfyzyhyhzryysfhimszsmiirmfghriyafhlfcrzhsahcgsiymmzyfsizmzmlmrlymyahzhrircmcamfbzaiymzmflzahzmimysryhmhrhzhfrhccfshrfrlryhfzfhyrzsfsciyfhfmhrscfzmylccmhmclizfcihychrhhzflhzhifmhfzmyzmflhhbzmilciyzrzbbmhhcyfrhfsmsryzrcfhczrasyrmslhhhifymzsyyfhbyyyybmayazcchmbyshhismishirficcrhhmzzmsfhmrihyblahzmlymyaymclmyyffbbzyzmbisyciiyfirzrmbzmhmhfzifhcyismlyybmrshfyffyzmhcmbisffrmyryrhhysymizsslyrzhizsmrzshszmiishhhhbccmslbmfhscmirsfhlcyzshbfzzsiasyfyhrmcyymyhmfzsscbhmiafzsifycybbahfsfhhiyszhmsyssffzhaymffymfimryhsycziyzrmmihsmfiymylyssbfhmhzirifrmhrhsrzmmymlfmsifhrihzbzmfsiimifzzaryyssizfirhihcssrsizffhfyrihzcymyczfysyrrfrhhyhryhmcmyisyscmfmyzahyyfssmslsahhlymzcmfhyiszrrssrlrmzlfssscylfhazirmmchyrhlsbirayriszhhyhyyrbyimfhmyisirymzhcsfslrisyzgzfym']
    want = 385
    got = solution.makeStringGood(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = ['uctcxxc']
    want = 2
    got = solution.makeStringGood(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = ['zcttzt']
    want = 2
    got = solution.makeStringGood(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = ['pbppppp']
    want = 1
    got = solution.makeStringGood(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = ['ehhe']
    want = 0
    got = solution.makeStringGood(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = ['qaqmtqudtdqmesrewaaasjrqtjiitdttrimrrqshmaqmaaxiarxtsciihstijdqjmmjsedhmsrtmathhqesdijnthqmeivqhamdjtwsiemgtiacqiwqnqhhwtrtmwqdqqwctismrtsesehtaqqrsrrmutujhcsqadvujaahahgdgdiiquqhtqgasjaihmiqaiqshnmqdeiamitsarmsiatucjmnsatiamsitvhiawrmxaesstaasugtxsigqsqqmexvhdwdniermhhiiiwwriaimrvsqjtthddslcqwwqrwcausarittvmaejmtdiiqammtqmvtuqdieiaiamqrjueativigssmriiirvqmnaniimttteslxdsjaiwstxarswlswgsxjrmsnwteiwxahanavmtihdhdjstamaeismhevutimatrqewjqngxlsgcvsiuwihnasarmgtstdjxaridnqlqdjdhdmdrdasqiixjqjdqtihrrmnmtxqcxsehqtaqsrttsmsdvsmceihqaahadmatieaqaihqqacqirrejatardmhavmucmwrjasmwchqidwmeihdqtarqxssaisasiiistnhhxmqmtsqiidvamvxaihqgrqagihvqltttdddnihheurteratjtvsiicmjaeiwjahteqahrqnjmntqwjsnhhathimadasmdchthjtdhiqqmtqqiqawimhdixsidcmmiidjasqismhqjritmmqiarhwmstvamiqhideesxvxamimhshhqhrsedaeeiqxhmshiamrsqasdtrqaaxqejtmaxmieahsgdjjxcqjmiaiwdqdtmehhwtrjdseieqtntaqthiqajsurqjrmelsridhxjqgqqeetijhqljtwidhsnttnidexmtttjvesnqamasadaqdshaassnvwriaqiadagqgawrmmlhdqsdanmwqteititmctatqmqaadaciqsqacjreemrjradejivgqiqsjuslxmtjqmeaaawwsvwmierqimmqqahtscaeitittisqdtwdtacsjimhnhtaqruswaaqmsjhaatqihmmsisqwtmwaqhjtwwslhxhwrtaqwjdrmetqardmevaiatasqaarigeistmqjatmeiqadmhtgmtrvsqqsgaxihmiijxsidsiidiuaaaiamrtveewqmtliaeqiquqmcmhmsresrxmhsrsawwjvaeehdciqqirdcagwlrtuhsmijamtmhswitteriqswassidrsxeshliimhsmmtihttsdxjeehgaehadrmmemeqqamihashqxmseindteiimtsqaeqansvdqhqtddmvidhamuemurqaasamvitrmiqaiiimeawrerevtxhvumwatadtshmasrvaanxrwvmarmnwrdirsqsiaalialmdtgwuaaeqjhxamdntsmqerdttcutidsvlsdwiqsiawltsjxsjmarddhidhaituimqqqvaaiijnqiijvmgieijilcxtxnmnrlheuggqvqqqausmxhdmwhtjtaimxaaesqmjmtaemmixidtwwhwtgqrxwjalmtaejitmtsrrqwquaqiqtmdtqdqrtqhqstuwrirhthxtitqavetasmddsisqnxidhheihdinessashmmvnhwisstsasqjuslrdsmetdsxmxcdriqishiilmeidwthrqmisthwtmvsaqsxqiidmttasishjssdmmraqsiaajijrjmrmgdhmaeiahiimihejhadwtiwmcsndwsimjsqmjmdwanasitijrqmlhtitjtcswjjtqehdqxadrcshamisimjtsltemnamaqetgqvchrdjihqdmeewaatiiaqvqhjsaimqitidwrhjiwduhjsmuwqnhsranmuuqqqdhntmmrhtrqtmmsrxtevdtvhddqmaarjqqtrwhqismarsiqieamrhqqthxmtsmincqttahrqteajuimdjlctwtqqtamgjaitdsxsimiqjhixgijqxeasndiwaaanviidmmqjmiaxegthdadujertaaqhqdijsgqciaasdqmaithitemswqhhegtlridadlmiqimctijvjetessmhqtttwhhnijhawqmmjqwdstqrqgdimeqqaahlrvtrgxqgdjdjaxwiaxqxtqhremqersdvetmwvqsjsmeejqmtidmiddrnqnqmhctqiqavjqmqqsqwhiaxtghatidmihewhjiveaqtimvqtqqdegishmwaaaanhxqsmtraxsnawethjvhjindssqqxsasmevhesiatdeismawetrvqmndnwrrwmtdgmhwxqvaaqxihsrndtqeqamaimtmismmtsttdqdvevraaediidtdtiwsaqasimcqtqadtarwjhaartgjitsdttiidqrinvmmnaaaavaaedwinqitsideavmminmahatirethsmtqqdtmmrevhqttqriimiehjjqrqiarmavtdawwctiweiiiqvrxeijdqmwaiqsxedviivatdearreqmesiuhaarmqtiwsirdthetmmdwmwiqiwhiqiawmqmiaiimniasmrthixrhcsstitxdhtaanmqrqhqhcnrawejtisutsmjniaettixrqusgiimxhiaqqttwmtssqsthtimqahaeaeuqidqhidjaxsmeairatjaigiatsmtiqsaqaiiqhhsqdgaqhelhmwistjahqdhsdtdmxmmdadscdqajsrdxremcaxaicarssatiercqqsthsaqtihsnhgqcsqhitjsdqmaahrtsmhviitmqtqtmlsmqqrxsehqstahjalmjdhtrqqqwggwqnmacmhhmqghumtedwvssjsimsqnwmxcsqjdigjiaaaqwsdchaedtraqqniwaixsjthsmaxmmawmiwdrilhxhthdqmjvmhwiwthimqhaeimuhmdithagiiianihvatqwsrmmjqtinestwisagisqlaansimaqanaatdtrttqrmalsxijqevatvjmltjsdiaaahtiqiejhmjivtixwiimwmmarrmarxswtdrmmlaeessimtdtwhwhdhtqdshjiiiirwriwuseiiajavnjqrjjmnqtvnmackvxmetsqdahjiaqjmtmagwdmacdsettjmvdxaittjiwdnmsetqqhrnaxqjnqthgsiialcmedmexatawaemjwsdtatsatrsqimtrvaeihwqjgieahsdxasnhdttlmdssiivsxxwstdrhiedwditjsivjijuhemasatilaxremtcjetsmnssdiwsqiscldnshsixhamsndhameseatlmiaqihxmmldhtdtwrhdestmcdtsrwhaiirxhmhrmlquitketmisljniwahvhaxeidsvsmnqitiihhqjatqjrqtmreqtmiiaqdtqieiqgrqisteaamiujtasaituixqrjqhtajsdrmdaicwdidsivqqaqqimcqrimwanistjmtrjjvqqusjdectmmuqittujsautdxctthremeqmsmiaqhghrrmvdsnsvdnmiajgsamsvudrttqtqrsdqidqmhmduahwarjulsahgmqgttmjcavjriwawrjidqnvtgutaixrvihnrtithaihdrlaqamiqjrssrqwvxqhtimhtuttjuehssrsxtsaqiiimmwusqwajsmqsmtuaithmhjieqrejjhumijvaqrqhdwiucthhqrhhmjhxssqhntdqtthnidjmethdattqrnhwaiiquqltvamriqhwhimnihedqgmivihaahqatmjwuimdtrewdjgnhiumwemarhqitihjtraqsgqsssemqmdqweaaswcutiridmqecejhlstiiqxirvcmrdrutqeiqdwiqhtthahtqtjqmstshqijdarhajjwtmqvqirexewqamnxqsmtdqiteumqgctawmsvqgwintqqssiaqrihqqstiaicssnvlhutjeqivasrtsqxihijmdhrewamiuxgdamwmtssehaiitawjjtdiithqatshmmsqqihsraxattsqmjtddqqqimitwavshddselhqtjiwjeaqnqmiqeanjdqhidmqtvlhdtqvhmteitjrtnhjtnhimcieqsiirhusihhhhihdhtaqnnrrqxqhsqtettgrmdmdijtcnrqqrdhhtdtqatmqvmmwwdhrqaihnhlimditmawshismjraqltttiwttxtjqhsaihniadmerqmtwmvrehatsddstajamvqawriaqtvciemwahniiqsamswatrqtaqdlartqqieatmnirqnrasmgmlqridnsmetihasaijdqqqimjlqsntddiwqnrqqjveiivjiittesdsdmrmaadqwtwttimwnimimxvieiqeseciexircqtiajqtdhmdhciijmduaqsrestssjaeenseaqajiqmtmjisuevijsariqtetseadclitrinqhxnttqnitqhewrsddarrqaahqjhimaqhqqaghsqadimttdeqhisxmihmqriuihmchltwhhhjirtsvdstsitmciajelimiitlqrujhjtsatahtjeictaivuiqqragtaawldqsstumqieitmdggmiamrihleditxwiiiitvcixdatciturqalnhhugjtxxiinwqielhmartqmvqmtigrmhtumqtaacqumrdeqhqaacwqlvhqhsaadjqvdrhetqimwiwmjqtseiderlvaqiiriwnsthjiiagttaliaeddashituqhrmgsiadtdqamiiwsdmjmjummdnwqimmttimqtshaindaiqiewqairmjgicewqdsiqriiritmmmxsqevrqrcmqqqgmamaaqeqasissrqtqtcjaaijraaijhkmjirsdaiqmhaiaqmmmhtthrttdqvwemmadhherqanqarqiqejqqsttuqvuegqteaixqtiwuqtwicawqwuadeheqqejsmhhemtijhmgiwsnqaitiwqhmmqsvsaaaaarawmmnasiaseitwmtqiildimuiashvhwwqsivnarhdvsscihsqqjtqjsncdnqujqrevamaciqsqmewjjqdsiqdjhaqcghmsqughdxshsatigdjrqhqjvhteqhjxhrmisimqmqwjxhmdwaraiittimijsjtwvhsdsttjneisartmjiditsijhajqgstadjashithiitihinhaxtexqmmaajimcmtrmimnemwiqxdsultdgaddataevdshdcaadqissmuhimidsdtmcaihaaqradmrujqatmsdtrmherqajaiiadaadqwtsetesvrdiqmqqacdhdqthactshdhhtjlmsiiasqnmeadmqhtijaahxhtasttiidwudm']
    want = 1569
    got = solution.makeStringGood(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = ['ereehem']
    want = 3
    got = solution.makeStringGood(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = ['jpmph']
    want = 1
    got = solution.makeStringGood(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = ['xgxggxgbgxggx']
    want = 3
    got = solution.makeStringGood(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = ['hgichzieejihqggwcigaqhiiheihhhhhewnhnzaznzreriqhngeaweeiemnginwwinhrhgerzwqhqjegiaamgiwaejkcmaehewiqhjeaherazicgihwweewawjieiihjzwjhwmgzhearnckgirhmmijneieaeaezhhnqwiceagmhzzremmehjgmwewaeegrhjacrhwghhichqicaawjeeasisihiiirweareihzrahhhmeimeriznwcizzhziaccairkeriaghiwhgceehaeinawggraieszewgergeehenjiiaiwiiiezwzgzjjemenjkzghiaehgiingzhjrrhmhaziizwijhighgihaihinrejwginkwacsiwwiweiimhghcrwhgaiweeeaaihrihjwkeeihahgzmgammznierizmgicjkkigreahchcaciwqkiwjwiihziiqheiiheirgwgccgewgekmewghwanihiwzgchzgciazmgicwhjrnqirkiegwwzihgaaiggheiraengnnagmgmiheihejwimrizimmrnewhahaehiiehawicwiwnicwjchiheichirrzgkwzcmigegiweghgzkiganhjkgweeejrrcjhjwwgenhrrmmiaemnjwqignhezirzrrmieczehhmwkzhagimiqehgizgggzcmiawrjgrhhaghrgahawcrgghwzrghhnhewcheijgergerwmwrgwecnjwgmmewziwkqkijasegieeaanchmziiimkkgkwzahgsereekrhhaciwhhceeikeggmiizhrinweackhjhawaehemiwiegmngnhiimehaijwcahgeejwgegqerhmjwehchwhgmniihinercircgwhnrhreihehghjeakearjhhqizqizmnrgiereegmaggwcgcermiajaaahigrwwikhwhngjgrzaeageggmagchegriihicgeeiinwwirkaaaeraiirwmeijwhigecccakkaessheghncnmwewesiaghigawanhigiaerzkiaqccgainianiigririgraiwnwrezgeeiwheigiigeamweaighczeehgmhjigwiiihczqgjgjhekrmgzrhhigheizhngiikcciigijirqhwhwwkchqiikwkamjgwiichrigzrmrrgmiqnhhiwmwehergzwgighegangiwjiarwghikihhihkiieirgwzehaiekkwrngencaiiewzchzqhaiaiaqmewczesgimrzeizgearcaigjigghghgkeewzigzzaraeneeawacwegkeegggghrehmrgiecwnagaignmjeghaieeimegcwmqmiqehemiaewigrirzmgehezrjmraijqaieegnnearigcchehezchhjimmigaemehhnwghggaejnhhhhrcinzwahghqhigeashieighcceaimhzheaeehqigzerihgnzzizwagewarrehcjazcrwnwwhjgeggiwghieihhchhrchaqwikgwkcwkhhghwrhgrreehkgjiaikahinarhiiiejhrecgeiaawghgghgeriejrziizjgiejcjgzzgzgqhzjzqigieisqieeewriajeiihreahggjzzawrnjhgaiijiigeewnmhrwzrwwsagagjhrisjwhgmqgmghragwijhgeiagkehiceeezreeheracagqagieiwghmhcmjnecigiinrkhswwiginziqhciiqijnihrihenciigarnzjeehwcszrmwgjgqhigahhzzenhshhgehargjciakheihgzcrzijwargacmhieghwieejrhwieqamgergwwjiqgzcikiihzmgwawegzawiaicizgzwawizwaczhhewjncghezecgijmkashgcrjizrkkiwinrigriqwjghiisiahjhigchhigcejnhheeierjmmhkcgrnrmgmggregiqrehsmmgehwrwzgwcizgkriwwrizncirhihiwhhqhhkhrisrericeewwirhmnzrmgzcimgriishweiaahezemhgghjwgzgwzhegianrhrwzajmwrgcmahirkhhraccjmeaweeewcgerwhwemacarhreijhweemewggshaheqgiegneaaewjhggqhciiqkijwegmcsereeihehawgghjrehzimahirwahnamgggeeriqirzjzaiehhqgwzewgkhhgheeiaeangghniwrcgrgrzcrimnigeanirzgqhjjeigiwgraiewwinagjenwzihihgmjrjhgheqwiheigichriwkrjcirhiawkhgrhhesrecehmwiegaheehwzwkigzzghhjhseniacnhcwhrjrjezwgwhiiiemgikewkhwgrgemngiagggnheghzihciieahijehgwgrnhnkgreehhgrjwawmmcrmewqgzmhhqagrhwhiqizhghmwghchaejiwjhahghwwheihnghcagrzsigcjawrgeaknwecghrgiwzceacwmgwezweecrcegqkegrghehehmkrecegwggjzmegggagwkrzerzghhghiwneimeakieniarqiazgjgenmhwaimgwwmiwajmagzsinrmneehgwjgmhikwghggejiziikzzgigzwzgwzriiizachhrhemgeaimrhhehzehwggjmeaqjjngggieizaeaihehhiiggggghanhrjeqrsiwrghnirhgehiirerrgchracegsqrmzgjngwihmgecwqiehwahggiherniqgizirrezaaekigngniighhnnaqharerhgezgwgiairiagnizgcwrezhmzhgjgirwmznhrrzrwgjiwjzmekhhmwarirnciahzcjmircagcmniiemehrcagiaginzwmzhnecehggrgkrgeigzejghierahageiieecaigieirnaehgwazngqggghrigzggragwjjheehnergeiwrajwnrzghjhcswjieigeenwhegneihheahwwihiiehhrarhwwrhiiwaqcwwgwijznigchnkzmzhiighrh']
    want = 1084
    got = solution.makeStringGood(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = ['nennneeeennnnne']
    want = 3
    got = solution.makeStringGood(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = ['geeeegeggggegge']
    want = 1
    got = solution.makeStringGood(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = ['ruuu']
    want = 1
    got = solution.makeStringGood(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_27():
    args = ['muummkmkkuu']
    want = 1
    got = solution.makeStringGood(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

