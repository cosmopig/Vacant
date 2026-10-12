"""Scoring checks for lcb_3701 -- NOT part of any workspace.

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
    args = ['cdcd']
    want = 'cccc'
    got = solution.minCostGoodCaption(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = ['aca']
    want = 'aaa'
    got = solution.minCostGoodCaption(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = ['bc']
    want = ''
    got = solution.minCostGoodCaption(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = ['kbnaku']
    want = 'kkkkkk'
    got = solution.minCostGoodCaption(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = ['kpxtvdkbfisqmbhcghubfyrjgfdfssagjbdtfgjwfoycykzicxjajoptnvdyacjoskgrcqdmcezwhxiilzomecsrajcjpyflbysemewxhekrxjvncawvviyolklnrllmsndtqrrwkrkhysblfzbpambhrkxljyvrrdzrflytuxzdcjvyijqhtlwnpmupqrylmpdslwqvixtzhrhowkfevkaszbvxyggobywcqsgwkdhewsmajrcvtqaefvbdudvwnmhvtrnnmefofxaqjmkeitdaaqrxsqiooejzaoibnakyyvitdxgxxouogcfsgbtmckrfxcdtssfmelfdlnnrgrpudxgttjcwvkkupukqgihgyscnchrxesvfbqunwgmuhtovnwgbstyzirytffjxmhcwelcdnqwqxtlpbjdidyhgsayraywizdtvocyshvrelkjopgutedumdpsdolyarcnyceutuktqkerafkzamtfyfawuyytifeoulxkuhemswyrmrnkrfqxwjicpdtdyakgpitsvxuympuepduibnlnbmgbknwbbgegthendckydhrtiqfjltfuywehfufruxtfslqniqgfttpggbsinstnriexvhyjfsbectdhwgweunsttvooigwfuphxlj']
    want = 'tttttfffffqqqcccgggggrrrfffsssdddddgggjjjoooyyyiiijjjoooovvvccckkkkqqqddddwwwwiiimmmmrrrcccpppfffmmmmwwwhhhrrrrcccvvvooolllmmmmmnnnrrrrrkkksssfffpppbbbkkklllvvvrrrlllxxxxxdddvvvjjjtttnnnrrrrrllllsssqqqxxxhhhooofffffsssxxxggggssssskkkeeesssccccttteeeddduuuummmtttnnnffffqqqkkkiiiaaarrrrrooojjjbbbbkkkyyyiiixxxxooofffgggmmmmmddddsssffffffnnnnnrrrgggtttvvvkkkppppggggssshhhsssssfffuuuhhhhtttttgggyyyrrrrfffmmmeeedddqqqqqpppdddhhhhgggwwwwwiiitttsssrrrjjjjpppppeeeeeooooorrreeeeeuuuqqqkkkfffmmmmffffwwwwwfffooouuuhhhwwwrrrkkkkwwwiiipppdddiiiitttxxxpppeeeiiinnnbbbbnnnbbbbhhhddddhhhhqqqqjjjjjwwwfffrrruuunnnnnggggtttgggnnnsssiiivvvvjjjccchhhwwwnnnttttooogggppplll'
    got = solution.minCostGoodCaption(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = ['nrcgzb']
    want = 'nnnggg'
    got = solution.minCostGoodCaption(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = ['rbvrbn']
    want = 'rrrnnn'
    got = solution.minCostGoodCaption(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = ['wtcgxq']
    want = 'tttqqq'
    got = solution.minCostGoodCaption(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = ['uidbci']
    want = 'iiiccc'
    got = solution.minCostGoodCaption(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = ['degpwhkuzjknthsqpuvraemuhbrxcqzlsxotikmyhzslpmdwkkpswvbtskmpjrwcthuhjzvcsidbqiuecaarsjzuovxstsdccserxndufcurtqgyqnacvuqlycwjnbmtkclaauhynmzfuucnzindokvzttksesixqrpwcwysmjyigemzsuihgrqprywejmbpgbolrniihvprxdanbcogwohfedvlgaukbvwuxdlylejaokjnjckjttjdynuvowkzuqvbtxnsjbsfchbtvrlbxtgqnlnohuqjnrqhaismrpvnjajhseworcnbczohczbqnhmzhgulpejsxyuuchkfnozdrnorcvtakvhyxeyoxcqofhsdgmhzvbxrilfnrbqxuscdobnqncndrrmsoczyemvomahafldsgvtjkiztytpwsixhgdiyiitfkkugljtltjyjpepjbbzptlpbnwqviuilypvnvtaqiexlcjfiqihccoxpbjvbfznfhbrxoxwhshowzmfxbjjglfxtepacdbqfuggsavtffngcjvhmjbwrytptglhppkuuxobmwjyvauabeviqpcrgvggwlrlwpornfwkfhqs']
    want = 'eeepppuuukkkkkqqquuueeehhhqqqqssstttkkkyyypppmmmkkkvvvssskkkkrrrrhhhhssssdddqqqaaaarrrvvvvvssscccrrrrrddddtttqqqqcccqqqqwwwjjjmmmaaaannnnnuuuunnnkkkkkvvvsssiiirrrpppwwwmmmgggguuuhhhqqqwwwjjjbbbbnnnniiirrrrcccccooooeeeelllbbbbvvvvlllleeekkkkjjjjtttnnnuuuuuuuqqqssssjjjcccctttlllqqqnnnnnqqqqqqhhhrrrpppjjjhhhrrrccccooocccnnnnnhhhjjjjuuuuuffffnnnnooorrrrhhhhxxxxoooooffffhhhvvvvviiinnnnuuuccccnnndddrrrrryyymmmmmaaafffssssjjjyyytttsssgggiiiiiikkkjjjtttjjjpppbbbtttllllvvviiiivvvtttiiilllfffiiicccpppbbbbnnnfffwwwwwhhhwwwmmmjjjgggppppbbbbgggggssssfffffjjjjjjwwwttthhhpppuuummmvvvvbbbbbqqqpppggggrrrpppoooffffqqq'
    got = solution.minCostGoodCaption(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = ['irqykb']
    want = 'qqqkkk'
    got = solution.minCostGoodCaption(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = ['rvezqrxeytgbevraexfgmkbqyzrbecjcgjljzdzufwpurzmconnqwojuuqqlqtaxhghutbstlqbwfrxahkdnawvpulklsnhygtxidkadouaymayxwebekkmbhlzfszwnkqfirjasbrcqrghtgfmvaohlddiorurxcxmdqzhonsemofrsqaaovovqxfzprwnwqtkghnreyxvevysbqjckotiitnsqrmthclymnjqvwuxxcijcthhhislplzbwhgofhkjojvplluseeonfibzolljktykkifawtiikvyryyiuncmrqwllxqclibjecfbiwgtukxcrpgxfztkfbepelwzlajieloibwzqfdxtvukzmoldlgbcoqjxzgnwuaptvkqkqjnjdwhmyysznlzwjndyducvgiucqtskcanipgvynsywmfdcahhdwszpknxjzykgvrcwnmnrualodhzdsqsaxwhimbrnxtvnvwjwwejtbvzknyjdtvvlgygikkdukkzvsxxqbbbmmrjwqdnnttqrjkauecjjbzlinkwwqtvghdgqeuvvgfhafnpbwztzvqghnozfdvuygccmemuwfvzecpcfzqyrvcdklhiyumkyyffxbaynfcbvntptzumvjpbwwhpmnmjfclplrdfoiupkwdmymtyslfpuerqswtiqwocuduuhedtwkmagwpmoxxmmckitwpnzbwjbvxlkpdqfweezijnxbryxkkjtbquusmyikbufxclfoqqchzdvbwqhzhmtiwmcorrjprrhffyevfpivbgjtwqmdkwfpkchugmgnamdmkaggixdxphdardqfnhsgzlvaftniwlrizaibntqidaswicsyhrmcyipbbmzhkoszxzwchqmvwhnbtzyushjhnlkayrfpkoauxvkzklphrkjhecomtphzqojzaczbfxa']
    want = 'rrrrrrtttteeerrrffffkkkkyyycccgggjjjuuuupppuuummmnnnooouuuqqqttthhhtttttlllrrrrhhhddduuuulllnnnttttdddddooommmxxxeeekkkhhhhhwwwnnniiiibbbqqqqgggggmmmllldddrrrrxxxmmmmmoooffffrrraaaqqqqxxxppppttthhhnnnxxxssssjjjkkkiiisssqqqqhhhnnnnnwwwwwiiihhhhhhllllwwwhhhhhjjjjpppssseeeffffoookkktttiiitttiiiyyyyymmmmmrrrlllliiieeeccciiittttpppgggttteeelllwwweeeeiiiiwwwfffuuummmmlllcccoooxxxuuupppppqqqjjjjmmmyyyynnnnnnddduuuggggsssccciiiisssswwwcccchhhwwwnnnxxxxkkkkknnnrrrlllddddssswwwhhhhrrrtttwwwwweeeevvvjjjjvvvllliiiiikkkvvvxxxbbbmmmqqqnnnrrrrjjjeeejjjlllllvvvvvggggggvvvfffffnnnwwwwwnnnnnfffvvvcccmmmvvvvveeeeevvvvvdddiiiuuuyyyffffnnnccctttttuuuujjjwwwmmmmffflllfffooookkkmmmtttlllqqqqtttooooouuuueeetttgggpppxxxkkkkktttttbbbbvvvkkkkeeeejjjnnnxxxkkkqqquuuuuiiiuuufffqqqddddvvvmmmmmtttmmmrrrrrrfffvvviiiigggtttkkkppphhhmmmgggkkkkggggppppdddqqqhhhhhvvvfffllllrrrbbbqqqdddssssssmmmiiibbbmmmoooxxxxhhhvvvhhhuuuuuhhhkkkkppppkkkvvvkkklllkkkeeeoooooqqqqqbbbbfff'
    got = solution.minCostGoodCaption(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = ['qpgiql']
    want = 'ppplll'
    got = solution.minCostGoodCaption(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = ['thhkzv']
    want = 'hhhvvv'
    got = solution.minCostGoodCaption(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = ['ckydtv']
    want = 'kkkttt'
    got = solution.minCostGoodCaption(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = ['jaopnq']
    want = 'jjjppp'
    got = solution.minCostGoodCaption(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = ['zgdkql']
    want = 'ggglll'
    got = solution.minCostGoodCaption(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = ['vwhrqhkjbtolluxuktrdpipgpmeptubfpqmxslqlxoggmnlooillaiviyqbynxlxnvpxsisssguvmuddmgeamghqulhfbvuphkbqbyjuaenebchnxlhkqaqoyoheidlraiuhlbumfdqvokeigzfaymhctlxppjrrtvwqvmvatrnvjbzaxiencskqfljthddqocytbqvuqwnlojamdxlbeicsnsdebdilviiiqcbkulspntmlxycjeridyednoerxtcnowaivzyvpzezlfvrmjrglxbpxqoefktasashhlvuzekkhujlkdutfekbsbgfhiwqkjzaklptxxolbgizrtvoglgdsmhzrwrknchhiiiagihdurlabvkhluhiegmhzhcmkcxkdrwujbiwvwcddntkgartrkykjsuvpsenmeablgtnlpzjgbehnqkkvdktdpfuleydmnhhocqqlkbnzocbzzqkdanxjhjlpslgqvhkjlyvpkdephgsjqcowzwurxseajqzajmdfbivkjabizxvoeteglddsxfjuldpuwqxlopggpysozlsjzqvxczwzgrvsveooxeyflrzzrmiwufpcswrnqwwhbqihzfzitgwttbxhlqnqavivxtdmziwwmzpevtipjzogriuuietizubpxpummovrduenwdvhkceuvpgdpnjoxeewcymxakybdshqoeimuzdskkkmvujsutstlxcfkosmnsqqwyfmhawydtehbwzwckkldzbsceyupzzbgodslxqlxjmzbwwgsuypeawxnjpdshvpxzzzckmdvyycbpqlgbwiegcuuz']
    want = 'rrrrrhhhhlllluuurrriiiiimmmtttfffqqqqooooogggnnnnllliiiiqqqxxxnnnvvvssssssuuuudddeeehhhqqqfffuuuhhhhhuuueeecccnnnkkkqqqoooeeeellliiilllfffqqqiiiffffhhhhtttppprrrvvvvmmmrrrjjjxxxeeeeqqqjjjjdddoooqqqquuuunnnjjjlllccccsssddddllliiiicccsssnnnnxxxeeeiiieeennntttnnniiiyyyvvvffffrrrjjjlllppppfffffssshhhvvvhhhhkkkktttfffbbbggggqqqjjjlllxxxiiiiitttttggggmmmwwwnnnhhhiiigggggrrrbbbkkkkggggmmmhhhhhkkkuuuiiiwwwdddkkkkkrrrkkkksssssmmmbbblllllpppeeeennnkkkkpppllleeemmmhhhqqqkkkkccczzzdddnnnjjjpppqqqjjjjvvveeehhhooooowwwsssseeemmmmmdddjjjjbbbxxxoooeeeeesssllllluuuuooogggsssslllvvvvvzzzsssssoooxxxlllzzzmmmmfffrrrrwwwhhhhhzzziiittthhhhqqqiiivvviiiiwwwwppppjjjoooouuuiiiiuuupppmmmrrreeennnneeeeuuugggnnnneeeexxxdddddooooiiisssskkkkuuusssstttfffoooqqqwwwfffftttteeewwwkkkkdddeeeyyyyyddddqqqqllllwwwwsssseeewwwjjjjjvvvzzzddddyyycccllliiieeeuuu'
    got = solution.minCostGoodCaption(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = ['uqpgmj']
    want = 'qqqjjj'
    got = solution.minCostGoodCaption(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = ['hcqbxi']
    want = 'hhhiii'
    got = solution.minCostGoodCaption(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = ['eevznq']
    want = 'eeeqqq'
    got = solution.minCostGoodCaption(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = ['txhyeg']
    want = 'tttggg'
    got = solution.minCostGoodCaption(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = ['oxarlggdxttzkwzizscncqvldcezlfaqealdgdumqrftwhojhkxvcnxtkwouvpugkdgzxyfrdbxatnghyvdtxtvxpwaokinqwfkqngcmugouqdrdzovwcjokluysxewtmedidawzjvywwpvojceyjuvgstuhledrswjycrlpzurgaxkpcomhwglwcpkrbrlcdnarzahxslcqrjvgmazdefobgfkaizxoqhslhypyajtqkdyyhtrtomclitelmywgmyvvdjlsvkvxvxtdfjvbdllzznnrseegdjjcvvfhfobvxcbnipmswuvrlsukqyutkjaadidvqzznlkdzneyudnxsbiibgwkhrjqfohyhnilklghmxqprzicwjfsxmyixuiflmgdbtlgkpxtheurwsxomdmfxicjklvssjhoxzlgzxlohbhmcpnghdwfxujhfhjuqinmfaedpzkjeyeqyszskmvugwulwabupqtbaganagcashbumsxwkhbvytsuqhoyeofhqpjpingiwnkrynothdztukptqchxklawkjgecjuifikawfqrnkypqicimqeaobgiwlqrpeivopveurpfqtyoflyiykqjeqdhqzspqxpujiyxbpcajbcspdiykmgaxzqphfshpazprnavmkvekfztrdcilhvaqprcvwhnvmnavxauanyodofkjxjxmmrcfejdfrtcdyecscjdaethhtqlegzazvxemlugorln']
    want = 'ooooogggtttwwwwssscccqqqdddllleeedddddqqqqtttjjjjjvvvtttooouuuuggggyyyddddttthhhvvvtttvvvviiiiqqqkkkgggmmmqqqdddvvvvkkkkkuuuummmmdddddvvvvwwwpppeeeuuuusssseeeesssjjjpppuuugggmmmmmhhhlllppplllccccrrrssslllrrrggggeeeffffiiixxxlllllyyyjjjkkkyyytttlllliiimmmmmmvvvjjjsssvvvvvffffflllzzzrrreeeejjjvvvhhhvvvcccmmmuuuurrrqqquuujjjddddvvvvkkkknnnuuusssgggggkkkqqqhhhnnnkkkkhhhrrrrriiiiisssuuuuiiiidddkkkkttthhhssssmmmmffffkkksssjjjxxxxxxhhhhhmmmmggguuuuhhhhqqqmmmddddkkkkkqqqyyymmmuuuuuuubbbqqqbbbaaaccchhhuuuuuhhhvvvsssoooffffppppiiiinnnoooohhhuuupppphhhkkkkkkeeejjjffffqqqnnnqqqiiiiieeegggqqqqiiipppuuuppptttlllyyykkkeeeeqqqqquuujjjpppcccccpppkkkgggqqqqhhhhhhrrrnnnmmmffftttdddhhhhqqqvvvnnnnnvvvaaaooojjjjjxxxmmmeeeeerrrdddddjjjdddhhhqqqeeeexxxlllooonnn'
    got = solution.minCostGoodCaption(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = ['ptaeslaeeuxtdsmkxyomjewenwbfqxuhesxdmxpdvkefqtguxebjkpmcpihgvapyvkjpkgdlhgyzxpdglplaajiqrhfwjbxgvyddjiarkkdjeqmerhhnonkjbeerujgixqcrpiontxlokyxeuziofrhdvhzngnlffhzhzavnmeykvnzpkouzukgqwmkqmhvrtzgtfznfuoryxeukfckxzudpcryjewstpuglfvgisoedjvggbeqcskqwzzlgfkmrhrsqkqewfxcxteedxjbwzczlaipocljfvauscyuaalchyezltekdfjvpllhocphqndrvctvefvpxocmymzzcnwghhtfbjybltsgzkqfyqhauztpcfdhfrqaileilqiwzkcdozabjovpsulyrwcuhropzuxeltgoulftaxstjozjxhzgkgyqvvgsmxzxfibpyjqqwzapujxatuukphmbzresyfgniwbzxvbvqknavhfryjfowuzyhkbaurnfrrxxqpgxjquqltzyxdiuuelqvuajoihksulsfwnhtsplgmlgwburmcetewkzvenexollvbfjpavlcxdmdvtmcfajncjsvhpifdqdjmuevzyntwfqqmshuhxegdbufsfdvwmhrluakyljgbjceoqnlzdrqlcropoeagwugdjirqhjtnhshpppmrptfjxosjfebnccavxwrkkwjvrinqtpzymkqwkgbdromaduraqipymkyoxrkmewrlxeanglsnsga']
    want = 'pppllleeeuuukkkkxxxjjjnnnfffuuuhhhmmmppppfffttttteeemmmhhhhgggvvvkkkkgggggyyyggglllaaaqqqhhhhhvvvvdddddkkkeeemmmhhhnnnneeerrriiiqqqqoootttlllxxxxxiiihhhvvvllllfffzzzmmmmkkkvvvooouuukkkmmmmmmttttgggoooooxxxkkkfffxxxdddjjjjtttttgggggoooeeegggccccqqqzzzgggkkkkqqqqqffftttteeejjjwwwwiiilllllfffuuuuuaaaahhhttteeeepppllllhhhnnnrrrrfffvvvmmmyyyynnnhhhfffjjjssskkkqqqhhhttttfffffqqqiiiilllwwwdddbbboooossswwwhhhpppxxxggggoooffftttjjjjxxxgggvvvvmmmxxxfffppppwwwpppjjjuuukkkkksssssgggiiixxxnnnnnhhhrrrjjjwwwwbbbbrrrrrrxxxjjjjqqqqqyyyiiillluuujjjiiisssshhhhsssllllgggrrreeeevvvveeeooooofffpppllldddtttcccjjjjppppfffjjjmmmyyytttqqqmmmuuuddddsssfffmmmrrrkkkkkeeeeennnnqqqqllloooeeeuuuiiiqqqnnnhhhppppppjjjsssfffcccccwwwkkkvvvqqqqqyyymmmmmdddooodddqqqmmmmmrrrrkkkrrrreeeennnggg'
    got = solution.minCostGoodCaption(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = ['zzqxnofzmupojxdiyvxkcmgjioaehbayoqyeezdrtlfegsskhjhmwqxckuckvdlpcswbkpkirvoddxlbxtblwhrhxknszxniyxtcfhphijdkhcwtgfczdbrrahsgomscxtlnembgzsiyatackxqnsccmpfkylrsgmaqdiwxqnbkdpxvoxnjdrybuejnqqgfwviebzoxxhiianydtbtzjvxsptmcctgvykacstopztbbomwstiuoxuvpvdxjfqphzeposxebnrrmyckhyszlfvotykszullnnagrngbgypztczngwvjeevmgyprykhmttpgzonuprqzaertoidezegzrzynpkarwzlxrfilrhzjbothlfaxieuxzsjzdqyzyuwmjkmirwwtypvgtennuvumrvcjjhqqkgidvbqutawurxlarnakyvvdgneuyrdllomcezxcpkizfawzuxurmkpyonamknkvxohixhhiiwkzvmxoudypyskqyafysmghtcautbapmmqwwotoipujkkuffoaikbadjmsjbuudmydoifexbkdibctjjvteoxgfukhplufbftvrutqoyjxmrkdetpigimzgpnltvlkgwgzhtlcdepsonaewnpxmtdmmsbxategneunwblkoifphsfdgagscbqafamabdaxrguosrdkpttubaqxhhinovrzoqgxgyzyfjikgdjijddxozydtvlefrkrektcqjanjbizvtqeshizecqnctuhagkfvqsqpgxtcbgfchzjnxwssmlboctzwuszktcedxbfowzafsnyzapxswvffhrxqwgkwsqclauakpprugwgwjvagmoileghopejpribopoyfflkmyhybxyizhhyaphkmjetjt']
    want = 'xxxxnnnuuuoooiiixxxkkkiiiibbbbbqqqqeeeerrrfffssshhhhwwwkkkkklllppppkkkkkrrrdddddttttthhhnnnsssssxxxfffiiiiddddtttdddddrrrhhhoootttlllgggssssaaaaqqqqqccckkkrrrrgggiiiqqqqdddvvvvvjjjrrrrjjjqqqvvveeexxxxiiinnndddvvvvvssscccttttcccssstttbbbssssooovvvvvffffppppppssseeerrrrhhhyyylllltttuuulllllnnngggttttnnnvvveeemmmrrrrkkktttnnnnqqqqeeerrreeegggyyyykkkkwwwrrriiirrrjjjlllfffffxxxqqqqqyyyyykkkkkwwwttttnnnnnuuurrrhhhhqqqgggqqqtttuuuulllkkkvvveeeeuuulllleeexxxkkkfffwwwwwmmmpppmmmkkkvvvhhhhiiiwwwvvvoooyyyqqqfffssshhhcccbbbmmmwwwooopppkkkkfffiiibbbjjjjjuuummmmfffkkkccccjjjttttthhhhhpppffftttttoooorrreeepppiiinnnntttkkkwwwllldddpppeeeppptttmmmssseeeggguuukkkiiipppfffgggbbbbfffaaaarrrrrrrkkktttbbbhhhhoooqqqqgggyyyiiiiggggdddxxxxtttfffrrrkkkjjjiiiiivvvqqqhhhhhqqqqqgggggqqqqqtttcccfffnnnwwwmmmcccwwwtttttdddfffwwwfffyyypppvvvfffrrrkkksssccckkkppppgggvvvggglllgggooopppiiipppfffmmmhhhxxxxhhhhkkkjjjttt'
    got = solution.minCostGoodCaption(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = ['owsjeo']
    want = 'sssjjj'
    got = solution.minCostGoodCaption(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_27():
    args = ['ajcaiserelrenxqopoqklxnimxsxdhsndaccgubglpsbepcjylfsrbedeyeahblutguzrnybrjtcujxselyhpwwtqpkyckbynhmslmilnxqkttmxkxvdpuvzowwmnppsmbaugybzctbzjeykpjqheckbylgmqnrccbmovvjmvlfnmlloixhhfdlphckrwjeerdbtwpvjpkrqldlkdfgvsnqmuqlcpovbdvcjljapqkacaxgkmomgsofxwubxmpjcrydshalemfgcrkqpbfgvsxueecomsoqjuflsklaszcfxikrkzqermkyurqrdppkwexlxwuhfspltfebxppfxtdulziinlpccgswztmafafdpqgtbosrypexvqsemyyzmkxbiklophrlyajzhkrnpxsccriprjpnbcekkzbknqcmxipwksacfekqgdehtrqrisounotkatdvamgqtanzbndyqynwygtpmwebixttahsdkhhjl']
    want = 'aaaaiiilllnnnqqqppplllmmmxxxhhhhccccggggpppcccclllrrrdddeeeehhhuuuuurrrjjjtttssslllllwwwppppcccnnnmmmmlllqqqtttvvvvpppwwwwwpppppbbbuuuccctttjjjjpppeeeeellllqqqcccoooommmllllllooohhhlllhhhrrreeeeettttkkkqqqkkkfffsssqqqlllpppccccjjjjpppaaakkkmmmmooowwwmmmjjjrrrrhhhfffffppppfffuuuueeeooooojjjllllsssiiiiiqqqqkkkkuuupppppkkkwwwwwhhhpppeeeppppttttiiiinnncccttttfffdddpppooorrrrrvvvmmmyyymmmiiiiooorrrjjjjjrrrrrcccpppnnnccckkkkkmmmmpppssscccckkkeeerrrrooooookkktttgggqqqqqdddyyywwwpppppeeetttddddjjjjj'
    got = solution.minCostGoodCaption(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

