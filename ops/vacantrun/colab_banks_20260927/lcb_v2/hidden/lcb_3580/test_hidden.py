"""Scoring checks for lcb_3580 -- NOT part of any workspace.

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
    args = ['abcdefg', 'bcdffg']
    want = 1
    got = solution.minStartingIndex(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = ['ababbababa', 'bacaba']
    want = 4
    got = solution.minStartingIndex(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = ['abcd', 'dba']
    want = -1
    got = solution.minStartingIndex(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = ['dde', 'd']
    want = 0
    got = solution.minStartingIndex(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = ['efeff', 'fe']
    want = 1
    got = solution.minStartingIndex(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = ['ffggf', 'gg']
    want = 1
    got = solution.minStartingIndex(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = ['ede', 'd']
    want = 0
    got = solution.minStartingIndex(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = ['pop', 'p']
    want = 0
    got = solution.minStartingIndex(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = ['ijjiii', 'ii']
    want = 0
    got = solution.minStartingIndex(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = ['jj', 'j']
    want = 0
    got = solution.minStartingIndex(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = ['nekkdxvmdpmacigzpwwotldpgncxbpwkkvqebalfovnoeqerptravvkdsjlasqfuzfzsamcdmgiilfrwzlmiwkmcevjqvydrvyozfeiojvyqiqceqvnafwhvbpugapckrompaefpgpskevxjewnzgvagoxhlooanyediqrwaogomntwtxsulwwzlumjimlyevzphghhjcojcjhbkswcspstgcbwwnojhelwvufhbqgedvdnovedoofjcvbumewjwkevwigjkcioderybxfgwmgqqdkpigejgoskfybftzsstanoqbgcmwgjomhxqjejeimmdcmefsklkhovfejyqjabjowkrtgoolejebvvvmasuyehllqyxjxvdaclaonoagrdbwqjqynnfcbgvnlyxajawrclmqjbstonkzjzpojweimxzjvrorwtkekkrkmtduovhckqplpbrgqnpdxpumvljppybzybptgjyxfghgjitezvdecundjlkoghsnubjrkatmbxggscaiknbxgrnycpxiselvhvabdsvcqlgccvwhhhrbcpovfgfgqjgkpflusblkhveebwmvgwvjuadvlutnflfejzbhjnanmoszztrrnlksmgukepuwtjyceohjjyuydfepjdlomkngqenkifzbicgghressdvvxmxyqyqthemchdkosditneckdlivwuauqggrhcwenmmkkarcvwxrtvkoxfxzvrrnepkopxpmjezxbdupslomubxkrenwlahukwhmazrsymkvyrsthnpevyriorbqtmpktujvglgjysvnarqwymabiohgtinzlogffvlbihfunfcretitafqwizrhlufwvyizegpjxccxahegbyxuuqrpydiexagcvtmxgywczfvudoduuyyfsrgmlablgixfiazjyagqjavwhhdbukvjnwopuinptzmsnrnhilezfhprkcsuctxxasgpfnwtcvrfkxdwvfeynrgmlbruqgixywahogxvipzsbqyjvlmwzugmvupmxrbdqqipkjnuduejlurtbgyckmqktruuohmjpvhtmjezdzewklfsxnrkhoqclyjhanvukxpiilzdomgsznlvqjwfdolulmorzympkoetndbpohqmxjvoopnfuxvtfmifoctezjhbyyfqjwffhpnifhyvshkwqzkvtbdxpennbjgchsjambseykgfthyjhlqhfbabqygltxexxmzmvqecrljtxsvvspzddypdzscdfpjnkcwwmkpawwlojxtmptbmdlmgrjfktgdhjwbgmslbamuinfnnyuoqbxkhjyvysxmrejbjlviznoyrougcxqnfmzarlytjzjbkkenqutedultlhncssdnedosontzpdwqlejgrmnuuxaykjdimgblkwkajxdfivlvxvjzjpxaszrmvfhlykswpvttcopflqfebcvzcokddgnsxnehoiokeqjgkkvoweduupjrmtvwufyvsojovlruoglosrbvtxuvuykyfkkoozlnldvjjieatofvccbdmfocfoovaxsytvciwltxukpwidtxziytjpfwdmvtwmwazxxajbjorbhbicktjdvgpoghnhrxltkgtuwcgczjqhgvbhnknxaowmynfmojctzrvrwkfsjsiztlpqsfldplbjsrzybnabzmfjhdomitjotakweqgktydlvuzrqxwsrqivwvcserpblqjhsemvuwjmmtzzuvsqxhcwwmvtgmzjtkhzcsttmipjuykyvelfiafnmfmuquypuaznnanvshvusidhviwmhklpnzlcifysrsxlytwjmzmsryueibwwrrwjrzvgqiolejjtpievtrkuapgxakrcgvhgfavkjvslfxvuqdhuxgrfyhznkdwiapuwshyuiurkgglnkwmjiymhujdbwzjewcnptpwunurzhdfxtjkxruwbfrxhhaolwsjlurogiwixikkelmkgvdmefpyshabeoohjpxkkiucbgbqdwtsduzhovhgoecdmaapaswjufefbwgneuydgtfqkucqorlwsnwjxiombbxpswmfipgfwgdytsbqootpagcdputbopqfipqnpprpslimuuylbzdrcryulalzqegnpdbipebydxfrjbefjqsqkabnmjdfnlgvahdwssabybsbjbaipycvgtqsstufdymcggitndblvqhsathhfaplsylkzyojctulrtugczxgqfbghmzzcirohrifrertvllqxfglhjgnmcvcvvbvdxtmglwfrmvtzwdxyohrtwytxmvajwlitcjmrijxochvuwaxxzvvhnbkyqufbehgxcvprzhiqkalvxgczfeomynrlyckifnmkfzptxgigsdhfemlothkreckqlvfghlqxfyeihpxwlvuoqgtistthdpkiexonsybbvfajjybexewipjolvrgnoaxpgjrdzcmridkaykjuicsbpiiccskmvvkwxfiqiltyxtuitfuvmhymuiwsdvogoartteeyfqpmhgfqrivcemlljyjmxgxhykuidjywqqilrnlsdsbelppyveffwvbkfggfmjflnegwkxykdrwdwnpizfvsmlhbvmanzvvexvyrwrgghfftjdrncurxgttdbjpnyhfkpvtuxtufarkktvutnybnlullsgyxgkzdjslswwpftwkdiqcraqsgkxgfthaizcfhfnjzpvofwpivtajffghpxskggnddpdsojaxckiouqreooobfpcyehfrwfpjtvszyahavcqlnnpcrpcxhpfzkndcmvfdrvokyhvuqpxkprmlhqyesqdnqweeaklhdoobauptkfmkcqlpajrbziltbffaprjjhjxhaawyplxzsluwhdusmopszqtjyxekyihxpbdrseyopiymnathcxzxdrybpblenzsdghvhduwdxedackhryloszlrdfbttybdhskndmioxysmufggrocscncbuowajminkppytwgddvzmblfspmykixoitzcbhrwjfesuwuefcdpvuzgjghwfeeenpmartssotmxeqqxwstalquaxvgnbooflkfgxslwedesbowhwjgtfbaiemwcgwgnsruxlcrnvnwrrguekjioaoogirtcvwozkyadbrncbqwvqagaxtvvbmemjzeprdeyilvsijuxgsaleguawohzinocjpuiomjxzylnasgxwjerqjlznoswdsuppdnjwldjcshdronxyvgysfgwsnanwaeszflmesybaxzhusicaunfjckkvarldgwpgbrjvczsimbdwmrpzzckwmnshoaydswroutcrqcdyunvsncpkwtcwsmqxamyfvurbpdwinmbqhhohfasnqlfslljrzovsizlbixkqtksjsnlhvpvjrfeqeajseyrxsmkrbqffkmgnfbqxegbqltsetfeihcdygfgajefgjgnrlptdquzzhfdqvvwrypiuczijoueqepjutrpxsbgqrllsrflfvvpdxofatkkurvsvvejlupkcnfnebbqywbisyuidlwpnrddtnnvdxuwpcijupinpwxziigdwntvupe', 'qyhgenpgstsdbclvivtivyzrpurgirqwivzlksxiidifxjodsgmsphttclgknmkrllzsebqkfwmgjfjwnrsobmgumvovdpqolofvhngktprykfmcroonmperhsglxvlzqilnuqaxwszzjceldeapsqegarhnvmcfstmnpodxyhfpsupoiizdjjbyukueckvvvxoknzidugvvzaezsvbrkhxfppyimiwlatkzghbckqclxawcpumvgovwfwfqxyxyghwssewwsyqmczeizmkfdvgdvcktdikgavbgavhzzithdortjwlzrauztvqpsullgmrhbmfmyfkflrwmmqqtcfpzsyksptcqcsjtluxditmopdfuiiiqcsnwfrsxcmkpcazhyptvltbmtvthodgvtxwdaswqmgobsanaepdgojewhrddedevfewquaqauexvxkgxpqwcscposlikzjblygfxjnpvafxhsgrobngopyggymytxqhgeeqvfuvcbprjlelxdlqsqldutaztzbpuxbclraypbvsxheyyeapjtbuhlhgornidomodpyjkkdzqfgijwfhydeawixrrzmtrharqtanmjvyazlqhbbwtdluwwfgastxtswfldcilkyvmgpgnupxsgsvqqueesfeqmzpqewmkyooiuftjkjkztjdrjfnireuotyiknggaszuttwhklffuaaikuvvrhtjiztzzewknzmmbdrxwpebtlldsqoyngrefyzaimdqdgupqewnyvagqyeqoipwzwcrolqeixgtflwohdhuwdcsrqivbvfwczctpjnxpbjhirsutrgpiastieuqccfplxrodbvbseocsvzcbonlkvvhggkbacicbxyfdrrcmnktqihrkffmvcdltaqhkmkhsohznrzxgeiddhxujffakgzwtktjmperxoexftfkubrtbmjojzpuxlguqbapmkvcmmtnikwzmkaowdeajbqgifemxjkoarxvcnmlzkwpclkrmyxezltwggxlwjkkrgpjeczegmkkhyvnulxycrehazhhaamsjowfeppcuipcourdkxypbmonwhcxtnovuynsrnxytovijdkpncinomqipjhxwchvgfotcspvujlhtjphtvpdrtwozhxesvltybmwnksdmgowmmdoyupkspicpnimwuzgrvxwxhhamrxoijakhdnlranjtiorbpesvyqpugmzgcvqungldsgtcgsygamlwtoxyeszezbbripkjmqlkzymhniqntnycdkscabmzugjcdrqxtrzzqozobqboaeebjaszmfptcgsdriznylljowtdflmsovaxukiagxyefrmuciyxhhhhnazdsykxscslbpodyajccablxidkxryrsdqchamgjbdrqtdwhljskfmtansmjfrowcsgkebnsmflnqpchykywaruzxnscexqvnbmqlsznbbbfcyyikbjefnnpdpvtvkjzooseoxcjcsextoogvkjmsabvxzixcsulhfvhbkhqaupgzyzeawuqloyfkzmqwtuoribvgqkkkvrnadlvexepususzeohdvqgzzuzvnzwsbsrqxlrijaskwxqoifsuejnwarlrwisvjgelofftxujkzuzcalhmnwwpxynhfbcmkduxwokgzxvxxijkbbfjbsozumzfjipzobqovfkormisjmhylonaobudraeiurdctfgddckrlpxkcvijwqftyufpwapjenlvwbpdpyfdgwxqfrlejnnjvqpohuztlnkqkbvfijxpzkhukcwgnzzvnzuralmbgyziihmtldvwokqwfdxrdsuhnydfghtsinwhgyzahsxogratpnxzdrygtjctvokejpbihwlcoakrgtiphuqmgepwpqezksgmnpeauqorwbpjodhwukansbdwgjmdmpkuigraxosjirqskbxlkavslszevmxpwlsusdstqeablhfxgwfcgksttecatlrfqitxoslmodcdqeejibfrsnzzuuixzcutolfuzsmujuqnzlvrnjqgsssbxxxjbbocrnugkqghdelnnklpsujljyvgclblsuxeqgocfnhwvfxyygjsdtfvjtkhjpfndnxotmxdmwhzspfyytzoumrbnptmlmsembfzkffmpokhnjgcodnoxyniypbijkmaphdbstysmwfsnoaposvhttkxensqoevpjrqmpwznccftusrqffusigkefbkqrqiuoclyfqeomqobxhfwcslcopdfwbzrp']
    want = -1
    got = solution.minStartingIndex(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = ['ccbb', 'bc']
    want = 0
    got = solution.minStartingIndex(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = ['qp', 'q']
    want = 0
    got = solution.minStartingIndex(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = ['ffgg', 'gf']
    want = 0
    got = solution.minStartingIndex(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = ['gghghh', 'hh']
    want = 1
    got = solution.minStartingIndex(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = ['qxafnrwbdjldlim', 'ofjs']
    want = -1
    got = solution.minStartingIndex(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = ['ij', 'j']
    want = 0
    got = solution.minStartingIndex(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = ['ayleslsaqucwdikytqedrcbwsbhzabhcfjwgqespdysddvjjpzxwbcwmvvpvwxisrvvhwsmckerwokpafzaukuznlohtguaghobhugpgeolzayrudhirpxqkkxruwiwcg', 'opiaaydyjjqyvfpidwedsweldxuelgnbxufvbgrzuhlklgxjtygkcbgfquitoqywpjeprdpbqhozdmwuhssojszpgqipfbemilhexajszqfktafiucyvifkxxugsqcndvrywwadnrmhtacoivdqgkijxscrniofjzbapiujnfpifslfgvzdbdgsprrpvycnxcsncypsilkxljhraluraonesqkoemqtnniyzvxiwxbkwiaepoxywlggaaapstzrkbsrdgnukhhjomcaogpsodjvrezapsjcojqkoqfcgswxbayneochhoohhiucooupldggamolcgnzedtnhajflwgfetzazcpdzymkkkvdfnjqvddijobexgwdjfggjjyfschlqpzulpsyrcjwshnnosuaptdmitetkcdztnukebteaagmeoaiobseatezehzeooysetmnxfzthrrmylvxxikgovfthmwkndilzcfkxaytjytaoptxomvnseqkngtdbmgohwbsuzvlsknhiwlnqjmqexdeirnuzqnvfczlkjzaitkbjxnkfrpkxhxpimkyqemfornxykyazkhxnxucrgzyuhcmsufcxklnbbevluoeupeihsrhzjxzvldcomoohyluqppunldhrdhqtkznktyyzwdxmrihtoxejxtmwfghokkepgxsggpxybzepjhytaadsgmylgggclfnlnuvgnpepurjjbiawvdsfqqmxsdizoyyxkvdthgyequolqfosoltgqyjmbokvzgejkiylmzsmsfwtupsdrftgftyxnsjjgxmpapzxtvzalvqvuauubkffjhkkqhkmpvgfnmnbmephxefnjyqifywragrkfosrrvfutrolbjerrxlsywjqtgbcrpophscrqkryyhpaswmorjbrgnxgokalgpttfhehphuvrzvwbqjimbkgnwtlijzzpmctiuljgndfgwnseblrvixjktyhusobpyscoqbpkwddvbousrgouhtoukfkyxweuhimrcevpasfyviowlwcacthodgvuzkgxquasxxloamjvqexlxljyjvfwcnevcwrywrjieorzvmynpjjeyqgxaygchxeotlzmdgajowidgpbvfhmspxnzrrpspuszuiaijdutpxiprkbfjwrmwkngnmuoeiycxouhhvpohuzjxtwevdjotrdvdcxkjogusgtrshvndoqttwxjexauikumttrqasvidnrobxjyljugeodlmrwpbxhikmczikfiaufmjbnxdvpemlcxyqltykspgafdsynodijvkriauwqikdulpmcioebrxbrmqvtqppqwjdaiyplxednodfmdfqjqlpsxirgvlvnjlcykvqndxawaffvbncpozigugjdtecsjnlyzfujkqdqliutxdzqkxxkijbqtkukulfasgznefpzdqdvhscrsagfykknoxwfhtenfhycrpcjcvtixzvvwcfmnbuzetawcqxqskmsbgsqbgalnsyeiozsocsbbxnzsrvgzddjxzzjsskgxigwftixwjifngbfcsvetmlnyljihcflftopkkkizymevzypwryrgjigrrievpsgrjhapusmrwjqvpzbvfhmexnpdwuksvgutfipgewhrztqmyryzejitpbdjwajqlrecgoudedyisrlmbchllkgthsndc']
    want = -1
    got = solution.minStartingIndex(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = ['nnn', 'm']
    want = 0
    got = solution.minStartingIndex(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = ['nmm', 'n']
    want = 0
    got = solution.minStartingIndex(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = ['qqq', 'q']
    want = 0
    got = solution.minStartingIndex(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = ['ffe', 'e']
    want = 0
    got = solution.minStartingIndex(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = ['ef', 'f']
    want = 0
    got = solution.minStartingIndex(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = ['nnn', 'm']
    want = 0
    got = solution.minStartingIndex(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = ['abababababababababab', 'abac']
    want = 0
    got = solution.minStartingIndex(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = ['sbcpzzdqiuvhgkuusphgvhjsdkzwazknqwtfwpbgnhhrrdpatpeyssdbrd', 'pkselhoiqlegt']
    want = -1
    got = solution.minStartingIndex(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_27():
    args = ['uieglepygufpmxkyyqmplgqxjdfgfnqlyznbwkckyfvbppbzcscagubjkwpszvelfyjwrtxbamqzabimtzmpqodaibjwjdollxieoefwggkicevyurmkehasawhmvjyxmbcvuptdurxuogbdjskdinxwkdoayiwpsyqqnxjeosqlyvxzmlmlahojcnwnypwsrsomwxwrnptrihtuggpjdcklzyxeeoazfhnjcpbgadzuuhkgarpgxuuahlajqnglzanobudwhghmozsyxofwkuyxkefafriivsmxptxvhjbvxnmgqzsgjvaovbqrcspaiiwhfcrzjxptmfbyuocttvz', 'nxxcgkakoiizxrewlfctzqdsrkptdcmaeqkjowmwruyobzrpuslrdkywycuuoimednljarwrynazjlxprokiiqzylqrhawnrbofmhcimnqijcdmedoqwjwysfhwmpmfttecrslwjjnqufunrrspwhqatwrssegfraptnfhuhuucliejcmmlyymcjfspaiqq']
    want = -1
    got = solution.minStartingIndex(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_28():
    args = ['no', 'n']
    want = 0
    got = solution.minStartingIndex(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

