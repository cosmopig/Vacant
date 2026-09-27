"""Scoring checks for lcb_3540 -- NOT part of any workspace.

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
    args = ['abcd', 2]
    want = 'bf'
    got = solution.stringHash(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = ['mxz', 3]
    want = 'i'
    got = solution.stringHash(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = ['m', 1]
    want = 'm'
    got = solution.stringHash(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = ['lgylscqqzbddgjwnkraiwtiapriuxgjjxqdisohsahaezejtgyyupwrazloggeejpbojecnxhmbh', 38]
    want = 'rs'
    got = solution.stringHash(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = ['cz', 1]
    want = 'cz'
    got = solution.stringHash(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = ['dhonjghyiq', 1]
    want = 'dhonjghyiq'
    got = solution.stringHash(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = ['iw', 1]
    want = 'iw'
    got = solution.stringHash(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = ['na', 1]
    want = 'na'
    got = solution.stringHash(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = ['i', 1]
    want = 'i'
    got = solution.stringHash(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = ['qoockasapxojrnoyppzsyipawnfrhwwvbdymyrrzhyzjaiqjtxryysucuysviobfqrhroemcpanjzpkrgsytejrnftrlguaywsuhmctiblgfbhooocwtegezspletgaeogcbxywnkirbgaqpfwlczqhnmitacqpqltngivgbjsfzjjcmuqbsxatpoanrszvznxnkbkwhjtffanckgwhtmywehddvcwycyqzyudasigqznvkxpdymagogattjakmdpkzqlqszxskwwsacqvtckriydfljwqrzrmgjjghszdbyezyatgdhjxrwakqqkbbeiqdndjsgztdokfcjwgsexbdyqrhyaewtlwwmoerswqmbsydwvpzrtgeakbsdhtklocbnqyneprhlxrjrtwsojetzdehvflnkzwqixfsijupinmvwsfnukkcqisozrgstjjvhbcluqcvfugedxckbloutxbiccbjfahaqzebiscgttvcfhpdwfxaebvtrlrvibzdfrjapeurqhkcdywvpthuitrrrsrthpdnlulcyohehawuyjgaujsarehbuszobsvildxjrdtdolonidnamrbicnqdryqkugohhidimfawagpyiafnssylxizypeyvzimsufziujihbzpzwgnsfbxmwrlwqappmnblx', 13]
    want = 'wykyjuwnqcnzncijwkaotlzbxshicjkpitddlqxtyczfpyaogvrw'
    got = solution.stringHash(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = ['guhzumdrlchoohhexgfnxmeznrqdqxdcrajsdynmfugndaqpjjgwulvgptvarzwyuthtxuwqcrcupmmuodwyofziwcislroebekmzajydvikqteikyoreivikcawmilitccgeajwxcmaybqovmgqunpuckojgrasovmqtgjinetzleuuwziriedoyuogtpmsszaggsma', 2]
    want = 'aggunvvldsjdetnfrbbzztdfscfbivqunarmtwbgruthyacsfwzhysjmifmdmwutviefzmzehwhjmxxsjczrrspovzmrsuiergym'
    got = solution.stringHash(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = ['ei', 1]
    want = 'ei'
    got = solution.stringHash(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = ['aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 52]
    want = 'aaaaa'
    got = solution.stringHash(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = ['wanvaycxwugryzwqmrbpjazhhmlwdwfgdhdgujdpfsltuzwbmhgojildbqucxjwrmlyudcuvmlpsqdsyhpxbuqyudtddnwwutygfpamlgbrawdzwtxnikxhlygimduheomxognzdupmezmqfzztrbzxuvqjjqqywjoyuanbdcdwxdzawcfsdzxdzsomvhmslsmpsxccspheapvxabjtmgdwrsytrxdytgujtlydipojmkglyixxqqtdpyqzgkhbzowreietrswdvymjlvtsqpjmsgjwjivhvqwmnqsjonldcibujgyrdpocxcrstbewtimsmtvajzhufcwpwxuspwgqfcohdbqvpmxjodjbtuzzxdgvozrsujvkoriytsxefmmaercxnybfdkwkaewlrrixtfkrezivkglusqgphgnfljqquagohxbvvnrahhxjqcfwvnhvhfegqpuvufxvclryfaxybcynsuclxfnhhghszscniixermzxvfraqsdvppkhfogutptikpowuzaqttucgpnwgldqficrccsyoagulfhnhnsisxgandychukjxefngymjhlvgagmundkyuoizozureeopkosqowkkbqyjubrnnqhypkcwsahlqbvpmpuemkvmvnxsrcbgqmnxhkpockokoiotsbfjwccpyqxzmptccdlwbqqhefgzwphnybncxlmbvebaojzzqpzzdboylbtppknktctziztjtnjdlgjnrsdensowdgwmlvwbamwqcjjeasibghvpvlakajojzmiqszvckaaghmyicrrmpwbdkrunsypefoqewcodbvkvegtbwaoksavtpsskcqjkgdbkzixsr', 36]
    want = 'itwvgdwfbtlqzmjyqanxxlyz'
    got = solution.stringHash(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = ['ekupuxwkxyxfvyvrmrljvsvdhsmecgbhcaoagjkdpyxysnlejuiipbnrfbepxvmqifqqiyskiflwcauprosvyyonbuvxxhzvniqkrfldyonoelcwfkanoccqwqnhshzdkvnkbomggcjugazejyfvvgmoajwbbletoohwozyyudshvtailovuixqvjbxpoaqhqauxnglqlaahqrjlopusxsfmihoojglghazbwysfsjzdglgyfgfznwoemelrpojvvfiushtcsytsmvbgozkvrqroyojrdsfiyvacwdmgabgchkjrbrjzafcyfndidgmhhyerqtqiypeblgbplfaspnbxezzpkelraytgyhuzsorgysvwzgorlumasqomqkskfztxrvqpvqwzrzbcijktwqdbrfcotwuhaivvltibqafaanusqkryovkbblceksgcehwnvwcjelstnzrjljrtfndphjvxaujyijdgwlxxrdgjoxqgewfxekcjoqrvcswfxtmeanizdbnkgfrtmoasnggnmpgdqdgpgqawnixdklacgwfrywnuugxmbispysiwrfvapkrabbikalgktjdltddthhqihzaxhxbndjmfrmuqhxpmakhrfkfaedredorfcsofyofyfphmohwrstdeyyuoguibskqvxclaunffbnigpakerpgdlcnbqyntgeswrajohhgmpu', 51]
    want = 'osqzjiipvefnrb'
    got = solution.stringHash(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = ['ib', 1]
    want = 'ib'
    got = solution.stringHash(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = ['fukiqyzlwhtfmijrinyxkcfgdqnlqonrjklistgzmdqmpgvylpdyyzwdqdapsnsifxkegayudfrrzvqovizsbcalsanqfiainoxetqogghiocvjjgtmnaakoqhpwzhsxnxtmksfvrazywybzfgjmcdhmgrnddoomlexgfftbmjiacvgflcndqdgocwmdobvxxnzmkpparehwjalslanzygzscwlgfjtfextwgjwteluywfjggmtchiktjminkxhkjkuopmtkodosophgedbnplkwatdjwmskbabswqmsalfgdhcneqgftwmoelmlmikozlllcnwirztinermjnwgnsuvahhrlksbwfuiumcmgtkffexwhinbeqqaoexhhrzaveudfhoayiyuvjmbhlrpkqpzulqweqahtxzikbavyzwzeqihnwigewmkrvfxgnhgdsvwclmovxwcjzgqndbopnwxxffhgmfgqjhybttxedeorvabdotxoiexmorhqdzbgrlajjqnvbgiwjqnfgmxclhkiixdtywpyypomckmjzzbsorzyqcupgblztwjmokrljwcquifupdfbviqnvknqtmwvzubzrarluwueotfummgrvdryjomldgdormddvnqgwsuudsrhckpmorogpbmqywqklolaprhppdgeugojkoxyssoipmozejoawxtthyhbiizjhvoiedvdbquvpjiircgqgiwdlpylzkktqidprvstcuqthzgfumlriblinikqdjgnvbprelqhahejaptzulmzcprpsuhztzrtqdwxfmbxidxppjvkebeogreklktucuzjorlrnbd', 2]
    want = 'zsokdyuavvmltyeettlfpcvtabxztpfacogsiiuedrdlsdnibbjunwxszzayxlgpkfcarxualvftxqrapdkuvixlnqtuyppsklzpvdjdlmeryroybppppsbpsvpdvvhrtibdrgdnhoagtmicbtmellkpulpapxuykwpeqbrdwcfphyvtbcgozpjtpouqseyzzxmogsensgaofmuhqhlvxvupjoawmctnvrnasyiwqpctcmslzfuqhsmbrqwbaytaxlsdwofdljnrqarlwdowiagqowvmsfabuyknjiwyixjiuvqrfqsygsmuhaojfpydcmxjjzafvnomvzpyejyutlqgxadxwqafjhqjmyekkrziweonkujlgnvkafzxzmvstpiqvbhljitxbghbsqjzcnfaeeofuvvdwtxcee'
    got = solution.stringHash(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = ['vlcyfhchuilgqqiygvxd', 5]
    want = 'lsfz'
    got = solution.stringHash(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = ['ztiotwlctz', 2]
    want = 'swpns'
    got = solution.stringHash(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = ['ehqhchweboikualekqiqpgmcyfdqnhdbrpwfmwyitcljaozlmlapjdpvzexzpqoupjzvvfutpxkbkavluwmholncxdvctebjokvbwizevpwqkvggwnzcjlorknotecawwmkcjarftihyafrovtzdolgieokaimzjcziafrpgupbuxqbrqzqeppqvwwqhgpuuhieokuvskzqjmtofzzsfnusvhprylqbvbdsjjvzgeurkzoapxurbcczxtxaazieobyiimptpceuogrlauqpbkubiabwpnyluyqgvcyxarskcfwgephtcjlhbtmenpwylrxbaoibdpvefvquiypgbmsoxwdmpwoaueesdmrxzauywttyezpxzuquxtasuuixcaypptsgjlbgclqbqwcbijisnqaooegdksdewfmofxrkjarlxxnsiorpnifqwwlsjbwytnheqxrjcyqldeogwymlogmqzhawercbmtfmfpxweorrsoszhcedqxypvyhxhdmobmramevmppafqtrvrkjliqeluaumeriuxuzsltewcfxnmryxcmwtdzfhfugnwbthgifiapblbudjjkviovhvqsxegkumjlbvkvctzeghfdofbyqfnatqrqsqilzalqnriwkdgdookkqthhhhcgnuunejeznrecjxyvcgzjfbqduwamcozvrnpvransofypimsjpezwraarzdbpfssmmfhiwoqrzmdpzowobgvhzuosrkecufvgefr', 40]
    want = 'dzycdsfdkhubnjyedec'
    got = solution.stringHash(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = ['h', 1]
    want = 'h'
    got = solution.stringHash(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = ['w', 1]
    want = 'w'
    got = solution.stringHash(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = ['azazazazazazazazazazazazazazazazazazazazazazazazazazazazazazazazazazazazazazazazazazazazazazazazazaz', 25]
    want = 'onon'
    got = solution.stringHash(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = ['abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijkl', 20]
    want = 'iscmwgqakueoyiscmwgqakueoyiscmwgqakueoyiscmwgqakue'
    got = solution.stringHash(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = ['feukbsiekceczfgbezseuecefhmeqwrivpclcnvefpuvgzxcxsrndndajhkpdpilwccwpqhwwdqtazxqayuldcjylxukoztosmvubhkqtavijrxremfwnujviwclielgumnwxuntslksqsyxlqnpnxcndqenajymlcveilfkkhhfsk', 87]
    want = 'kj'
    got = solution.stringHash(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = ['ht', 1]
    want = 'ht'
    got = solution.stringHash(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

