"""Scoring checks for lcb_3403 -- NOT part of any workspace.

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
    args = ['fabccddg']
    want = 3
    got = solution.minimumSubstringsInPartition(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = ['abababaccddb']
    want = 2
    got = solution.minimumSubstringsInPartition(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = ['ddyytpzzgvvffyipsbgueslllapkkbdlnaanmaaxzhhhhxwwedttghyyuebxtvvoleesflitnwnawyxyeebbabqkxnnnnutzpppwwpeyyyrjdpqhyybrrhqnbjnciseoscrmjqqwgtazvwjqziyyhhjjjylhhdxvwicctwwqqvrnmkkvgdpvocvyyijdyzwtnboxllddhhbbvvvxyknutbgdiiefxxhinieerrrggpdlllqrqqdfzfyynnndddmzskppshmdwxdjjabkykwxzsoozzddjiiasgiijffpnqqgotbdxiiauuggwwwzpyopstxwfgfggxgffrghotuulmusnlllhggfglvppaaqqipqqqolmdkcorstrrhgmztttnrqhrpyzozzzeknfpnzxfhfepnaaaenhpgkddbzggnvaabjlsgaaafmydodtddddsqqxjomzyncjjolhnaffmwdnjjljnhqjklkrqwoxbtubbgfiiamnjuuxsqtmiiexzffflffqqwccjtysgdipawzjdujkhgzzzossssjifennvxdimaimgftffeslpoffjhhxuzcdxlllzooqluiivddanoddnzjpppjibsdsjjgcgggsshggfmnsbgziffxxoklkjsmmmafgdusszzzxokdnwneeeuvlbjjjnvttggalattwvoyxjkppjwxkkwpsjdnbibcaonlifcswurruassszvxxymmlocdlnjbkkliifppwavdsususgqprrqqpyidjogxmmmlwxkxpbjmekmmcbiirwwxxxjkcqaxebrjzzsknmeyzpccealowsllklcoodddjpoktltddimtdiozzumkkvbtnssggiccyyiisvvpvvddepooprldhvtrnuxyllfddauvhuwsxtttgtbyyggowrrqssuuohiiivjazsvhfpixjaavaazttvtpiieiirhrrstzvuaawvmnnnllbdegfniuukjmjls']
    want = 247
    got = solution.minimumSubstringsInPartition(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = ['eeddccaabb']
    want = 1
    got = solution.minimumSubstringsInPartition(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = ['fkrvfrcccesypomxdrbdflhlrcncusmedpjtnpudcsmirpmfhpqadkoehwsykjwrbcoxupinfoldellujemyrunftuhanyeaewanlrryocgfwsaxejszcmlazbwcmxvcdujibsvzbnjfjlvqxuaipvkzgkrqvlfnpozkpqrrnfkxeykzijvuwdyulvejqinlzqurvcfhgqdfbjdodbzoubtwbovwhhbnjqhrlnkcvqyaagnqzjwsqekcyokquzbwgdjppvkujgxkpzxotohwpdbxxxmroeybrwwmvlrslhqhtswhkfbhskivqkewgevgirhiwdduvxheuzcxyklkvqbizcboydleegmdivsoadjcbdlozpihcgdrjmnmlaxmjqmprfvkunstuetehuqiwyhfzbfkdnzkevxcuxefsfqxboyngshzrflgxehagsjsynyjqqbijtfwklufquoctomfmjswdvlvttlhhjbdrsieouebsslk']
    want = 85
    got = solution.minimumSubstringsInPartition(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = ['poppppopooppwwwwwuulmcffeebcbcstvsrcqqpiihkedxxxxonmdwwwwkhhkjbamnnmmmzdoooooaallllllllllllhhffffffffbbbbzzzzcccccccheoockkifffqqfmkwwwwtttttmmwwwwwjjkiikpnpurouplvnbcggklldutsuubfcebpoqvtvddddogffgfffffhhnnmaaaaasqoskponnqqnqlkpnljqppdkkkkkkkkkpppqqqqnokljnnggkxxxxxonpooqzjkkkuwstsvppppppgigggigghhhighigkkddlohpkqqifqnfhqhifffjfjhfifhjiononlpnoinikkikuugeeesrzzzzzaaaaajjjjooooooooooooooooonuuijjijiijjkkylqooqocadddnnnticgladlksalcsfijikfkiiiicddefdddddddddddddtqqporiiiiiittlnlnmqqqqqqhhhhhhhhhhhhddddddsqqprsqoqoqstttxxxrsrhhhhffxyttrrrppppppppppgfmmcbppppppprrtppppaaawssssoqqoppwwwbbbbbbbbbbbbywxffiffgiiigzzzzllllttqsqbbjjkklljpjbbwvvhfffeffeggiiiiipphiffffddeeddttssstkkzzzzrrrrrrtllllllllllbbeelsbakkkkkkkwqoqvvxymxwlxsoiiiiiiiiiiiiiijkjjjkrbbbbbbzzzzzzeyyyygfgggfmkjlvjjwfjumnfugldlvhhurgjlqmeokfeqklhpldnglpfeceaaaaklnnnnmmnnmnmnjjjiiihfjjfhjiijxstttbbbbbbbbbbbbkkkkrrrrgeemmffghdddddzzjihhihhiffffifrxxxxxxxxxxisssbrqttttttttttttteeghhbvvsssssspqqrrdcwxwvvvvvvvdcwxwxxwwxrrccdafcdfb']
    want = 232
    got = solution.minimumSubstringsInPartition(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = ['cnsxvivgtfeqdlqppsoxjuhcsofpuaeaywuevkpcuhgbotrzefgczspdsdorrerizzhqtsbnyedospgmxuklzbygtmnsacibjniwttrpkxytumhupxslojjxxfckimxboxxcuqxtprqoxkxuhueekvgblkcdgbermtjjvpvpnzgbjvdfvynxbmepnhjaqzrubpyoiohhozmlpduholsqcuvtmidyjgdsgswtbhtsktwqjbxcwscoqbwdxozmznmasnopaykgokengewzcobrxfrttwmmylazfalkyjyddaqqjpwmbyjcjryffobloxbibhunlqxsklmgasozivqbdylefgevpkryioxfngwaacjwhlchsupvowimktoobcifrebpqsaayybpteqqktlghxvacthabalealgqowicpwymrnsejrravnrybbmczjcdzoaflbkpfbdrwvwrdwphszglrrhewzancxqsxsfxlbpdomlownvrskzpixdkundstgahqrhmymxrmqhljnyvqzhaagyoncsqabtntawcenpsbxaqrcyyeodgonhtfzxlurbgegpkrgivrrnhgczqzowgxykhvenjdqopjuwiaetwzlxfeqezegydomjzkmttupwkemjhemzdinugigaopnqxtwvmvubqhvzmdzpvndxljlfiarabsjzirojhwmqidfdnegubhsmlliphdkkauvpecierkzaasecrmlylnuioqsbzpnomzepntarbwlzkpysjfsprihjgwwbwvncmlfmqqvffenwgmthfulkoubzmxetwtrbwsirwxxcxqfxzwyrgpeipwrfuilnlpvitkioeonhjbwazqwfmixmjafgarovmtogierzgquyenycyakhnqonoctwqolfzurvmpnjwzykkivplcarhkjrtlvwauzevcsyrtrrawnqteyhriwovpjwzqkcaprsobnfqlayntsisvyjqksjybzji']
    want = 157
    got = solution.minimumSubstringsInPartition(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = ['bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa']
    want = 1
    got = solution.minimumSubstringsInPartition(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = ['qkxqeflf']
    want = 3
    got = solution.minimumSubstringsInPartition(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = ['njlewlnfuofenutcaadpibowedebvulgdqhbxymafbhczktdutzguzeofscnlggqzrpqsgthqhrwmayqvbrlwqrzqqrqkorcyoww']
    want = 18
    got = solution.minimumSubstringsInPartition(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = ['dyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyyeyydyy']
    want = 500
    got = solution.minimumSubstringsInPartition(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = ['gursoptiqnczfrxtcoqftlagegivxudanyxubswgnphzzunieenxonraijjelhmbnzzqrssqawijlhyskkzkmtawqzfxlaxufzplaladdflksozxxmjxmojewuznydccpmqdkxqbgsjqwgxlhhxzwbbxbonfqtnnzmewxbrxjuqsiwwhdqqpzgpbpargtwqybmadedadmnhddnumtnkpanpgrrqpisixefxmdzxjymaakmuvkixlwambpdpzyeywnmapvvojapjsvmmspccdaccqxrrljjdqjrailaniixcdfpumirpeujayqtieigfrfkeuxydyjnykoakkcbagmspmtqqfgfpsdmlvddderaaglcimvkqulqhgvzpkhkvgzumwwwywfsrigbnwspvypdcdqhvehtnlkgsdcirxrdxrrzeakrgylvviojjcncuukefctefoyrrjmgllagxzzhhtltaddpptuykzzsprhwcoletbjlhqjyswyqvsgzyvftwajzgydrrescyihmbirmegdpbaqdlhiuxeypadytzfabssactdphxltxbqrsgmbjjaqqmdfssmjvdtdttfpyaquhhsonhjcvzcscifsxaivvhixjkffwweajhllyvwzfbtzvhigjlbdrwwwaimpryszxpvzauutxznnjnmqxutqmltjmiirykdummqnutroopvjllhoiimmkwxzgxuqopellmhwgrjtmomnxwtbxwqylxbarsgloomphawnptvpuyfiwfesayhzyakkssgatzuutvbyutppmilamoebyygqcqvgcfzpgttlxairepzjtkhjvoakkziucktadbazmlhhspkftbyjhrhyfgciceihuyznebkgkkgkggeatlfccqvlccmpwxjuokkktclvbwqtmzdopoonzjgfmcinnkojhxakgypfbekkxwvprcbyeauurbcaztnuolphitzfctilsxxdddtdqbqysyl']
    want = 189
    got = solution.minimumSubstringsInPartition(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = ['abbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabbabb']
    want = 334
    got = solution.minimumSubstringsInPartition(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = ['uhqitvwrtvzyhswiuyqcbhbdobnhrjsxp']
    want = 5
    got = solution.minimumSubstringsInPartition(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = ['ipoavffcgqgoncxovweeypechcrgohkcuzsdcfnfifvppdrzonpaxahymwtwoaaxfbdiquhxragvygeablsghmfcwvshdrqbqcrjghgikgmwnwxtxazklccvraipucuhxfzchvhmexxiqwomqsmhqrfwfegqobesrvcvpdxxdimlcygigfehixfuoonbinmqassmgpcazhqebfjcdtcymfxosakwrqbvevpuqobwdocmouqfdsqzhjrsnofpkgvcrgxqzwcpscfnrmcoiguwrcoplhxmepqrodzaisiimiabaqbzimumgefyjldwkgbievvuwmzeotgsmvowyuiwxbyxrkyxhalctowqzwwsmxgsudpceisbmekvrwekccozhdfmsyjpwgulfgvvahsybdxndgugopjrhksnkirgqylfrdetisoykknmpedyrjzotbqdezdskczefnncwgkbrtyzbmhjjuffarkjqjpeqsgdabevdgvwkzedzlrnmqtqvvcwkgkwvuwcawxqhkoothsewnzqoouktvcaiznbgfysvqmtdayyyttasttlhkqrpgiaxaeaicclsqrolxhsjdxfdxvjqrayglajrwsfbdugokuejitfngidhosshktdycbcxbibrbexcyptebsmdbfcvtdcltjxsrdvlidbppqolvcuocwbgirmgniidnrhtfyeodbnjcxyvkaarsdluzmzrqcftqhodhmamhdgeqcvzeddpudvwpvbkarsiscktwmkhrmniglbqggxblsrzacmiomwmnmpepxzkdluusptjwtgmcdismzbbiufrglelznzzopjiueyjedbcmrzzqtshofqqvhckopdyhzeftcvpneoslpmqdctdmkrziuapcqccscqbqsfvhxcokdurmgnkizkbncaymypxzrxrxjxawripraaztzwbuejnwpigjndhmbsbkcdvnbuvenhccteczoclcaelleiusdv']
    want = 169
    got = solution.minimumSubstringsInPartition(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = ['shesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshesheshe']
    want = 1
    got = solution.minimumSubstringsInPartition(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = ['c']
    want = 1
    got = solution.minimumSubstringsInPartition(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = ['pwalyrfqfkvrjdfkwottpxhcfzkknsmazubgdpaljdspmojflqcjgxwmwoypykgvmyxxovjgqvhzlpzvwnrvmdbvj']
    want = 16
    got = solution.minimumSubstringsInPartition(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = ['gpgfkexfrz']
    want = 3
    got = solution.minimumSubstringsInPartition(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = ['gggggmmmmmrrrrrdddddbbbbbeeeeeaaaaahhhhhffffftttttooooosssssnnnnnccccckkkkklllllqqqqqiiiiipppppjjjjj']
    want = 1
    got = solution.minimumSubstringsInPartition(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = ['rztdjnhcdwhmvngftrnkbbwrwtqswwtlhueomkcqdbdecstfhslgdwlqwuhgpibteaursximejpvjfkemggmhufpzdldadohworfcvdwqxnbbcxchfflvzjpxuudzffgfhzhfqymlvevrqgaejnltgjsazitwsqwpdlqnhqilpgqxarzrtsbdcsnupfyrbahcrokxfddnfpbxntmuyxkhmellhsptovlovwhnqowggudwkzrbjscbyictuzvvkmlhjvontiremwyxyaoolxtmprqptkseebozryohoadjacgzawnchwjoghwxjkbxogtiyyiargjeiftoqntjbplmzxlnklokmooqdlallyydmeodsnpytxiwmbksvpcolzjgdhvimejzqzcejexycrqwwtonttlklkhfohcbgctbswiqwssdxsnujvzqgbjkxxrskwlvwrlhyoajymmlliqflglnnfdgosulwkgdvpcxvettreeaptcsevmvwqhjxyeuxlnrjjqscwwjjgfutqclcpmfsuqhoqsmetoukmrkwlueflmmitmeotvuqxegvaznrtfantinlqhwocikmabttfrykyvsowsbpwdjicszfhlijjnfhyavncldrlslewawqkroopvkizawugddmyxkvyattbvyylwiutefhkwxgkkzgvzwrudfhwaunykrxcnvvvsinqoweyjyadrmgewdwunoskksjmqpbhulegwfinrbaxbtsfqcmprmahewkungyvsqcfrgvzzvaltzsccfxqikrtamayxzfquooovupkjhjpjplgtxvufngnchmjvpauzhtpduddshjgkoralrynudtyzwykehcqboprmnshznbruzgsbqyfkefjetdxcfgkdxpaxbcfbohpntcwyqtuthcqubmlobyqcodiinuifbmftnifoqxhhtbdyzhoqzdpnusuaphzccrtnkbgiifoixvqcwkzijrwuzlac']
    want = 165
    got = solution.minimumSubstringsInPartition(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = ['aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaabc']
    want = 2
    got = solution.minimumSubstringsInPartition(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = ['htwyixiqisumgsufnmpznxjjvqntwsivxjgqjtcvtqaiooryczuakhbcaztsmsiaemlzynyadrxedmwqubajkfjqtmkeuuqdkghplmfynmmzqwgingjjsrzupjydurioshfcwjlhgnispaiocdyrqaheqzsdqijfnrrblktyrdfhtfppxrsrqraarbkmrwnuggihvtwecvofwqizhtiehtoaekedphiucpndqkdtpwflfvrmvagwaqeauxowdvjxjyizsdrlvnvycxnlibkossosefgligujguwahfziahiowqjcaqseiu']
    want = 51
    got = solution.minimumSubstringsInPartition(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = ['aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaabbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbabababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababab']
    want = 1
    got = solution.minimumSubstringsInPartition(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = ['abababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababababab']
    want = 1
    got = solution.minimumSubstringsInPartition(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = ['lllyyybbbiiiooouuuyyymmmvvvkkksssccceeetttjjjiiicccffffffkkkwwwtttwwwpppyyylllffftttcccxxxeeeyyycccbbbrrrddddddooohhhffftttccczzzqqqvvvuuuqqqjjjuuunnnzzzoooxxxfffooollliiiwwwlllssshhhccchhhbbbqqqvvvkkkuuuuuunnnbbbvvvrrrgggxxxuuuggguuufffrrrnnnqqqlllttteeemmmwwwlllhhhgggyyykkkllluuucccyyygggaaammmoooooolllfffbbbyyyrrrxxxkkkssssssqqqxxxsssmmmdddhhhcccyyycccyyywwwvvvbbbtttuuutttiiixxxtttooovvvwwwxxxzzzuuuwwwbbbjjjtttaaadddkkkqqqvvvmmmeeefffuuulllnnnmmmlllhhhlllyyylllmmmyyyyyyjjjmmmttttttlllkkkcccxx']
    want = 29
    got = solution.minimumSubstringsInPartition(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

