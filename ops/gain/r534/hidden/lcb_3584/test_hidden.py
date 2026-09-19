"""Scoring checks for lcb_3584 -- NOT part of any workspace.

⚠ 這個檔案是計分用的 GT。它住在 ops/gain/r534/hidden/ 這棵**另外的樹**裡，
  永遠不複製進 agent 的工作區；任何把它的內容（含失敗訊息）回饋給模型的路徑
  都是 R534 的紅線。

case 組成 ＝ 題庫的 `visible_tests` ＋ `hidden_tests`（超集），與
vacant/codebench.py::LiveCodeBenchLoader 的 `hidden_check` 逐字同一組，
所以算出來的分子與 runs/g_r460_harness_lcb2_*／runs/g_r532_lcb2_* 的
`meets_demand` 是同一把尺。
"""

import solution

def _aeq(a, b):
    """與 vacant/codebench.py::_lcb_check_code 的 __aeq 同一套判等（逐行對應）。"""
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
    args = ['vbcca', 'abc']
    want = [0, 1, 2]
    got = solution.validSequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = ['bacdc', 'abc']
    want = [1, 2, 4]
    got = solution.validSequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = ['aaaaaa', 'aaabc']
    want = []
    got = solution.validSequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = ['abc', 'ab']
    want = [0, 1]
    got = solution.validSequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = ['ccbccccbcc', 'b']
    want = [0]
    got = solution.validSequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = ['gzyjrdzkvnnszvpgaoojvhctsozvazuadzyljshehevyglaffsskdahxtaragpztxfsbwztkzhifqmifcvjylyltrgpvxpnhcdejmxzssbxwziarxhbhjimhvtzloaegllcuqkogutgknxtohcrjjweyzcaqmfafcwmoclqkpjuzpvrqqsjzekderkusauqvlrhxgllyfqmchxjmejsqliekulcdyxlfksuslwbugptaqcrmhrhailzcldsplogqzasezrvjcfutdoiullhisoxeqjcfcojspcnsukvcwivqztxuvpkvkyxmxhitvqotsecgcppsyyygsmnjftbjkmswgtswbbyuoowztrpbgwidjbstrmiarcttodqgjcdbyzgxtdqombsblcuwoxkfouqhpygxbnqeqboboatojuhrejyhnfjrdeylwtkxsujgsiceuiwnuphjigiqhmkwfyyjqdzsonggeuiaqrxmpnqzxerkvdcrxunpctijbiqwulmiqzrzqoitzmhdixcjubfpsggmobvorkruvxflsbuhrftqlmcozlzwyvyflxngigaqxdzotjfjojwrxsbnecrujmetorurysaxioptassejkyimfcmnimeqakaxvxccmhtgojrtauymqipvbpclprhlwpfhjdhbzolqvwnftkljxgfedxrxgwfjfdtlhibwsvaqhpvweexizbazkxvkcyuanwrhjhpzaxxsmgpsiywysghohylwufaynugjmvgctovfaoormgnctrcqhjenzliuxdsokcomrodsekggdgrgwzneovybvteyxpiteknofpnpsapvnwqdlugnhhvhuksxprzisfkjojtrodudxdjiouummxlmenfkneqrhhgvsvpwaifjvorcvdjovstqkrsqmnnamsalugrydqvimkhvnrgifcrfwmdkkuasfqhbwdkrkjkceesvdipdolrcsldflykbyujzrzzwyls', 'gzyjdknnszvgaoojhctozzuayseyglaskdahtpfbzkzfqmifjyytrvpndejsxwzbhjmvtoegqtgkxthrjezaqfafcwoclqkjvqqsjdrkuauqglyqmmsiekucdyxsspqaizdspoqjutoiisoxcfcopcskivztxvvkxxiotsysmjtbwgtwuoztpgwdbmrttgbyzqobsuofuqygxnqebobtorjyfjrdeywjgieuhiqhmkfyyjqdzngarxedcrxunpcjbiwqzrqoitzhdicjubfpggmobvorkruvlhftlcozwyyggaotjfjjwxsjetrraxipakyimkvxcmtumqipclhlfhzovtjgfdxwfdliwaeizbzxvyuzxxmgsywyghoylwufujmvvaoomceluxokcomdkggrzneovtexpiepanwqduhhhusisfktrodxioummenfnqrwafjovdstqrqmnsardqimkniffwdkuasfheddrcllybzzwysz']
    want = []
    got = solution.validSequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = ['nmm', 'm']
    want = [0]
    got = solution.validSequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = ['tjnrxgfeuxbmpggtzlenboeyddhwaafangmrleqaqcjupladlwflfuwukqienrqtuouwplkuamwtgnwfafztmgdupfaxtzbzstxdoolddnkvfmadvicbpczdbfihyqpsxzzbjxwdwaofenvtrlcejozbmvbzsjqzaxttdxtgwhapoojtrtuobabjooam', 'qftjbhfqwipsiaohdneupjnsdsrszrfvamcx']
    want = []
    got = solution.validSequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = ['lzhyp', 'ue']
    want = []
    got = solution.validSequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = ['gfffgggggfff', 'ff']
    want = [0, 1]
    got = solution.validSequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = ['ffggfggg', 'f']
    want = [0]
    got = solution.validSequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = ['ibupbgdqmokainxusqyvxhqpzfbxzcjqetrumvobgxzfsiccrescxpvlmtifgjjqzishxtgqagyftcpnqrrtkuobwyodbfojmqimkyvohefvdvrahmnrofliadlbwqdchvkicvwwqvuevolooydjrsdnlrmaiwbcugvtlflryxukdlrockhaoyjxwhysgkaesorgudnyydejoukitjsvypwwwowbrnilsldtodhtyltvvwhlgjyebndyybhssxdynfehsovmqumzkofiwqzqaamagrwgmhvwgofqrxbsgplsanovlvnrntkdbzgmnbrbsldrctelruvsgqxmtdbltfhlywnhmjzogljroiwirootqvvneckrpkycuxihuyobxtrrphvizqgfnoczjprhkjevtxssiozjpbxixuvlexgwzenvneamjwioewwdsfcktngjjbepejppqewgoqcgrsnodgbajorxewniqqdwwcpctboegdkatgzslgmmlzulzcvpfbeqbkcpfnrwrkxtkboljscsejbqbmxsivhzqsibdjyanawxoftteotvmrawdjjgqjviqsrplrlwadayqsymowgpqzwvakjttapoohzurdgfckbckccnbeerqhpkientbyxcfdimappyafxmnzmpvsgaymulvkktfgqsiqtwjjhofstkelzxeepouitvrnujiqkystubijfyvuqxbuuwzbbrldcdjioxxhizjonfgoycbzmwyudblicqhmtwzbfwgjwqdgclpptkjfboqhgsrhnmodzzahnnllgiimnpuvvksjtljxzjjsumrlyyaflixgrlhpougrxcylsudknqredgdzevlnmljlwsyowtfpxzahjrzyvqykozjmblgplaxwhlshcesaezrkjizvfxsedwoeiauzqvpwtszkruhcigotxgiqpxzkyivzrnpnrvgldtevaeiwebmoudxlbpyzjxathdwhyclfwfanzegwlemiqaltfwaomjmzschdipvypecldrgfqmvpvqawgoqcatctlokaaznnbmhywhmzvgnsjxxfsbfagbeixgyzvkdbdsvwagxbnfkihlxhxmtvxundllgenebtxvmmweipbzdwqmtmsrhjzqkjorajkrvmzthkihlghonjipuztxthqevpkzpffvhndlqriysmbfqdvfvivygqmmijzxjprzdvlzdgiswyvwjzfiiltvsnebtdzyzoojupkgbbigqlpudefvlrkucnimkatfyqmy', 'zshghknxtoxtesuleghpnezfczcozpztdwhclnlfnhfkkdlzzguiihuoubjnjsyyeuaohvmuiybdwnkazcobxnhpgfshrkjwcarwiddyqjlsrwvhflvqkicskjzvxfynutpadysmoamyumgssygubwnqktvlrfxjpzpfyshggajqmesimeemlvydjsqveixxyunpaquxmuhfthnuejncfuupxksjhigfpfwbhqouvsqzxpvrjkxnyxlokmgyjbpgtayfnqijnmkgctihjakwdyjhovczisvfdbkqxvdkkqlnwerukvxjilyrlfistiptsprodedalyksljsnnlwrgeynccabxotwdxhmnmkmhzysnqibedqizumsknldpdyswdpqheqeruaohttgevpvbxrxuvycarjjrcougrfdlszavnlzbjdefnyqnvznodiglmhqehsrtvvqzaxejrsdzdzjjcgsoqrutoyvpjthqxsjrsuktreavrpwgacqkayplvrvalyoflpxtpahlosrvpkhjcpabuxpgatmjbcfhblrmgzxlyavmwhidemxeiajovgbdecnizrsvhxpyusimeujbuituuzlqyznhlhjmdqcsqaasprbryyvohgwbwvhedsfzathxtrxgtsxaetummtzodukesofqnsnglfzsbxrkitplmzeiuezotqxriiajryywuipdthwrytdnrthygcgipecegqblrnornohdzevdopdzyykjicruvrhgluewjwetejohclej']
    want = []
    got = solution.validSequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = ['nnnnmmnnmn', 'm']
    want = [0]
    got = solution.validSequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = ['eeefff', 'e']
    want = [0]
    got = solution.validSequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_15():
    args = ['njmbopldieslpqhlhhiexnptvvvhglzyzqzrymwfntbprdcestxzbeqmlhufttuptqwszwheqmeikkhmjcfxqlpzdbmhscbtdmsuxgfqkjcwsdvtpxwdvzrgcuudmuhvmanklgovskizulluxsdvfdeaalbwksalqnajtbmmwqptjnmjftjrphmjwpedzyrmnqvlckwtnyvmhkcoktwihurjltxedwgrsbibaleropvpghkksnegmdcatwljjgqjvjryzjsojjzvmvbezjywmyclbvffxegoyrpltoxskiurnbcpkckohjnpwfpgtuprnepvebopikoedebmuuogfaxbcevrcpicwzpgtjytentjionwavfvttgixjdezrxnyalspdwauvbyyvrdiqciihwlsfylnssrzulfghoobvyqkcnizmcdocloclpfldrxflybirtgqzzgpuebeuuojtiebjbkkvigtnvzgfrsdcbvdxzivqolkfdqfjvitfaijutyrndawkktdzeztqnkcyrupndcrvjrbewlblfhljqwqdvsjcivdwdsgckuzkyhqywaoygyzrvkjidpkethkvuey', 'hctklhdxriwbmbihgqtclmutuyyfnhmztptlfwvvdvwrynxbanobrrqhtgacfuacvxfktjcpoiiagqzhsquietxdctvftntlkeleoxctbwtzavcdwdmfyqgoucbtkvkkdabsdtvibrxqovrczyykpntoroeywsuxtuyzalbtfpftmqdktbldvzngjmidulkqulmkttxfqhwhljnmqnvbb']
    want = []
    got = solution.validSequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_16():
    args = ['eeddeeeeee', 'dd']
    want = [0, 2]
    got = solution.validSequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_17():
    args = ['eeffeeeeefeeffe', 'ee']
    want = [0, 1]
    got = solution.validSequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_18():
    args = ['klkklll', 'k']
    want = [0]
    got = solution.validSequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_19():
    args = ['ababababab', 'aaaaa']
    want = [0, 1, 2, 4, 6]
    got = solution.validSequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_20():
    args = ['ffeeefee', 'e']
    want = [0]
    got = solution.validSequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_21():
    args = ['kkkkjkkj', 'j']
    want = [0]
    got = solution.validSequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_22():
    args = ['iihihhi', 'h']
    want = [0]
    got = solution.validSequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_23():
    args = ['vynsazctfwgvagtgdwjexisqlybaepcnkluxbtlgzcxtuywpgjegogchtkhpakuxklivtwceyedyhxgedtvbdxaikckluapqhjxddpwaxfnkuducuicnxsapclosisnpfebgmyoplkvoiyhmznedmwhkkuktoxxjkdtihadspbsrusvwqlbuadkueykdfpylccwqhexokxlfaqrqrecutvbpjmumjaxnuxxsjxmwfuntcpedtmxnytokxqedotwrwgfgprgeokuxllxqdksqnevzgbkdmkjhozydqrqpwnmtcdymvbbpfwgppmzkmldanjlycsvhskvgivrierawamqcxglssbqlenninpikevuypfpqloqhowwihusksqhzvbainmmehntfeomnzxlgjqvrilqtoavdfaxquclhnafrvaprwcumjeyctjslmyaabowqnpnbcfrmsopeaoescccbtzgkoteitcknorpknjctobgtqvvzrivfptndvbbazwizatfdkvzkssmfyolyugjbqyyphkrujxflixwvfzpebdwzrjizaweuiobephqcnktknzsxyqlwdqvxiekqzvkopxjfvwhbawwmfvwvdpfmjtqktvxohiklwxorpbhmlbwlrlvsmrdddsnlgxfnrpebignyhdhnercmwttorcwtjhsfyishxhppltkxbkhtnvqyzimwvmuadgnwveajrgwovohdiymxdysdsrziqweyyaclfllevzpmdpgazfefxzoovhjugfodfdeinacedajktctvsxclyynpoilbpnupparbkguuujqmsmaiyeqvnktmwyvmxdymyllrhngxycyjxkzaafzjgaypjutelckasreafhhlqqbosqbshdkevohwguboljblbdnnqcoyvnjpqdyzluqrgcxozeqvbwvsibyrqcwlsevihdfwiadlknccushggizcgootivifsrpeavfkwmewhrrcdoyvzgjbpagdprdrpfgamgzkimccxbioentjyvuzafeekpftddhqcosjytbwtqasqqkwhihvtanhcfoqdohuolnchoapnnjinprcbqggqgmvwtchseoeflzrkhcfseosnfuyhigmejarvfawvgzelsdfswfqvguustytirxzexpgnwhkwnbobwiykwwrrpeelrogczjwsiwauoshvbcliwazdiaouboknyiowblwnufieptzlormjgybqlzdornxajhrzzfgixuuapdpfrxyabrdymprpbgvjahzrwdpeiuqwxklhlwttixtbfzexaxdcomwglzxdryzohvaqkyzhirrwrjntvvdavkhbnxntoyhrvqlsxqshtxppnipigkbzjfyokaasdnghjzkoisxgrpsdynqidkgfvjbnkoojmnindibflxpqowmasewxvejqxkgdxhiutfvfnczvnfvxmmwexsygcjafmvhjekesfgsyxbxaznpoinanfmgqkrbdicfxnjorqwsjgrrmoymczemaazykqukghpmvgsyuqfiausxkjaqedcveytolknezixvfsssnsyfvksyjyibfqvpfzqnmivuheptupzyapyzsjhhabzmyhvkwcyelqtxcekphoedkenifbozmbozpzxrvevavogkhvlcnrbykksvyqjufinrhddgygedbwgnlxgpnawedvjaayojsjybyexvnmiasrrrbamubowoujbcazotrixqcitvgbaxwakflrzmclsxjdtbcyoqlnyfghntggtbmjzniajtcywswcqrgphixlulkhpduflihezdz', 'zqbuzujrezlwssycnvnsuumqjgtulwtamkdsmwmtnuyurtqvnawosshleayomnhbbprfkgmjtmrcqwadchhelzetgjetsmbmwgtkryhptubosfxalpmxhbksivbpwayxqxyavpkqoyobvicpnmpgbkuipkqgzeyfwuugsxqamqjltgdmemqbgdrauxnywvfpstdprxsqnmphycosxzwxcsstasuvcbeeuxpajtcclbqgdskyssblmrmueeumencezvwiwgkbhmkffsgrvvsmofecagufnbgfydriavocbvbmdfiipxpqtncpuyzhkfkncxjuohbevftzadwwolfmfxmikmwmeueiznxriigjptrkiypshczraebsqrphwaqoepvenbvflusljqihmlqpjwkdyqrsvttrgxyunxdtpjgrrwgnfqfrnzuvfkjpktirxzqvgsigjbxrjldknzyqrngruuakwhttongkdozrstfntnwngnpgomaxvwnyixazmzbszalujiauatljsgummizhgbdabjzfthvoeqbyvaxtpmnnkenfujywjavcfkrtlisbvnncwsarbztmnktqinhlbsyhxmdndvojyuksqdlciscesibptdtyok']
    want = []
    got = solution.validSequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_24():
    args = ['wskhknlfuhef', 'splu']
    want = [1, 2, 6, 8]
    got = solution.validSequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_25():
    args = ['fvqfencfukgvjwkebzslzrgtfdrzikloxtwvmpnqcigzfxudbiypyxlydmzoondmurzrbfxuxtqsbevfrqbioawrbcqolmeqfresjvyarywzckkzyddsvuycwvjnlssmodkehshhwfviqyzqfqlrxbyvufapumhkukvqiajjrajpffaqmirokhvulcoszrkfznvkpjslfkwspmknbxlmzryvylfrhguhwadrecxdniuqjwazstsdncwewjehmygdjshbpknjfqzsmmkdhtedijbtligrvgpfhzhbdmsjpphsqrhujlutuuudynjpazepvatwlumhsfgbqkvbaknvlkoffcyxbwfpbuhrwiiwxguxxyzulvbmeghmdovuyzkkxkywenjsdjiscelfferkmoxubwnuygwaruqsiyssqamqengfvpjtygpiqtfxhrucindjszhrxqbiotvgabnizilgkgjvpaygobhbkkdzehcihgbmswfeaetyfrqgojeggwmayiuqqwfywrkgnunpjdcczklumjgvvhxqdoiftlqrkoybstlhgyzpfwmebjapumzrgtrhdbekiqwlayucgqgkrntquywhhejfhffzaipdwhzgbsrricbfqpqpwemtfpvyrqukiboiqeowbqqptkhsaygmgctihhxnjfdwfrqvhlvqzvkpaoxdijyakbekeoppuhrqninnyjfidhhlvzykaiolychzdjzhidsavxguvobmgpwitjqbfwkihwluplhmoeopdynbshblbgkoycnzahgmjpaflgfkdnwqywmoaoynshutoevithgketgbukspzckmnumxlvwjvzxvvrckgqtpdktpfxfvwgywgcjulfpctuvgtdnhhsbppgwcicizajuoknlqslnlwhnkbwhgfxpwoiawclasjkivguigtfjiygygugupcmklmweqmsfqxadidayucdszmdthbiukmcmxcrophrvhskzvhxwlzvpucxalylbogchbbrfefmsflnhqprpkgipvvvtsuksylavajfbgsupnwyckbwsczdaiozziqkhomrjmplevvmddihybamfrqiipzpswaurbrykjybhvufazlsiwecbveyyacotnlbmeztxposeugdyytrhgdjmqqkxgnhocnllgnrqdtadqlkvnpjjmchpdrukgcvtoskmjeoquerprompmeunkfegjtkximzczywjdjtphcoyoiwbjthmfrnkqgshdhvrrzbqgddnrgfemfvffrzkljqoybofescvfxunmeduiwxawkjzsymfrksvkzdqyidclbxbbplucjlvcbfyemenriqdhdysssknujtrpkchqbobdwbaeqajrsfnikpyjnbasteoltggwjbxtgozrkgbjbhchbrlbrmuvvrnvnwbejhrgzgomjnshwqezslftcwolikhoncajczoyxoozohxcbxfdqtcrvjugrqruiwaudfvaxfroazxrgcfawuiuigklkyndgujehdwmasybvptccxkgjzaisiczkaoettnbdfvhhlhlmkjrncwqbzhagmztpshbnncvsghvappcqjtufjnzwpbrrtztkdtmdykeyawbunfxhmlodicvvvmnnhxjciscfqtwvecqxcwanfqmrqfbuzugkbtqrslpacndhqieynchmoxruanraaxfpfdwtpztqehuhcxtrxbszqmzuqlnvzgjefkunlxnwaperzzkkgdvpyptuenzpxwwqrwureunxpsvyixnztpxszbffzbryqdqresmrugrqhazhudynkkosuteedzsfvylggwwcgptbfyjuaoznijodaxdomfggcugwvlnlbnysuvwjigungwwricrgsfraifixgucyilmzjyk', 'nnrsxxkajgfpctlgzlsuxityspmuqdyafuluvffsrktwlhgcvzamykyyuunquzmurvdhpnoqwrqdlhzhgwbhsekhlydxymfxozcfkobaezobgowflmtjsjjnudwuigeonjqjiyqfkoraumqrlcvlrtjgwakutnnkgilplaoplgouxojqmiqypiqzddgksasajvjdkhpfysqxjaforsuffuudslduumwpzgxwswjjiefuqgzilxyvpwdiqmpvadmezrcvnmnntqklfeingsipzuaobtkcjwhmfwcijaqgxqidhmsauoglurlfqybsrmyobioltuhztfuymijfaayltbmrvbkdtgcgnbbunpywszjgsrtqomvyxavtaalyvkbpdpecfawicmqlkfamcnyrkelobvcdjvqoaaesukypuwkqomyswwsnechshvvcuqtxaptfxebjwyktflyqkkhrwenpvjydbwoylowmbuzkmloatbcriezmfbvarslpefjyweofurkzprldiydpgyfevjxuuqkxuwwiclgmexuysntrofppaxehankenmydndbvmrorrzwepngafafctuvwbouttawzdxmqxebpyatzqqnztwzubtzjpgfyibnxftlkqcsovhoapupxnhuzfkkqchmddgqrzvpzulydzzcrfzcsvgwxofqjgkudsvqzdmcfoketnkfqmooycbzxhkycgtkaytxtvtzoogpryxvacoacaozlpaguhaqxydthbcudxcrazkrtnvpqtzhibzeophymzwefymwweaxmxyxqikfumjzzundq']
    want = []
    got = solution.validSequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_26():
    args = ['cdddddddd', 'c']
    want = [0]
    got = solution.validSequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_27():
    args = ['fzycnvstvycjdawgzfnmydwnhthfjszugydotgqysfllgvtiijrepcqdfpxchqfhprcfgkhzynxgmmqnnvnjmixkzexmuwjaefoclholgmiqjznsdgrmxkrmjiagrkobyhivhflocexqslrqbpwgteshxecoehssxqxmswyzkhvrkzofjpocruzlluarrbpgwnrltcmvrqcauwqyuuslwhkvsvtotarksrdkqmdqyenpunqawzdonlqdzvcjyluhwexrjmzoufumkuccugkbkdpddfbjjhjcvqoukuvgijzolukwpmuauaahexheyqkzjutbujcfzdonwtcabcounvsgtwijdhqysnzecjwqmlqygvzczkvdkbkjnbnyliptfsnczgsnuarmhkoxqnexdpictfmjjyeaypgxhbrivdwwlzrjnohifldjbeaghgdmvdsuznchvpmjdkguvljecdyfyjtpjnnhealogxkbbaxhniextbjsftjlyqawkxcuttkyyppmzogwaptmavxldollfpcjwaejhmqqtpvxfffiqowjcksiqkmkfnxglnjzkydijutcfthoipfydsjvxwtoqrefeuoqeqncadnirxzmpdal', 'sngglycfoljmsxqmnwwteceyilyjkgrrwqwmodjpykstobxhpzvfwalvlkpdxifqdsqhowtmoemkzxmqnwwttttbsyucypccyewlzkhsarvipjqcsaukktveeowoljlmclinenmosemwaiulsiygbdrglcerakpwkkvroigzfdpzdkpgsuaosqhpcxcxkaslvififkgzfyridqoaksoyaaptbq']
    want = []
    got = solution.validSequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_28():
    args = ['eeefeefeff', 'e']
    want = [0]
    got = solution.validSequence(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

