"""Scoring checks for lcb_3451 -- NOT part of any workspace.

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
    args = ['abcde']
    want = '1a1b1c1d1e'
    got = solution.compressedString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = ['aaaaaaaaaaaaaabb']
    want = '9a5a2b'
    got = solution.compressedString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = ['qmbfuevafdcgoiryrfqrbaipgpqijrfjgxnyyenlsfjnrceflnupvirtvulbfscozbqkxztvsbkdcgcsizaubkfvjubgnrheitvf']
    want = '1q1m1b1f1u1e1v1a1f1d1c1g1o1i1r1y1r1f1q1r1b1a1i1p1g1p1q1i1j1r1f1j1g1x1n2y1e1n1l1s1f1j1n1r1c1e1f1l1n1u1p1v1i1r1t1v1u1l1b1f1s1c1o1z1b1q1k1x1z1t1v1s1b1k1d1c1g1c1s1i1z1a1u1b1k1f1v1j1u1b1g1n1r1h1e1i1t1v1f'
    got = solution.compressedString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = ['bowwti']
    want = '1b1o2w1t1i'
    got = solution.compressedString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = ['eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee']
    want = '9e9e9e9e9e9e9e9e9e9e9e6e'
    got = solution.compressedString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = ['bbbbbbbbbbbbbbbbbb']
    want = '9b9b'
    got = solution.compressedString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = ['qaxeokukoojiwirvvdsclmxinrasahykgsegvmbjpqcahrvfthedcvlxzatovkhbwnduxusawqbjoxeuvcjhvenokfrlpkdnfyfinsqnmtsdhkhnxguarvfglzhfjmxcglgofhaefusxxplnwxgzuwblwdzyytdiysxohxtpkcmzqxbewxcqjyphemjtmmdirnwqfxguufxxbdvrxcwxjksssubnbiekgkgpxnausxxambskspkhcwjeszxgaoppoo']
    want = '1q1a1x1e1o1k1u1k2o1j1i1w1i1r2v1d1s1c1l1m1x1i1n1r1a1s1a1h1y1k1g1s1e1g1v1m1b1j1p1q1c1a1h1r1v1f1t1h1e1d1c1v1l1x1z1a1t1o1v1k1h1b1w1n1d1u1x1u1s1a1w1q1b1j1o1x1e1u1v1c1j1h1v1e1n1o1k1f1r1l1p1k1d1n1f1y1f1i1n1s1q1n1m1t1s1d1h1k1h1n1x1g1u1a1r1v1f1g1l1z1h1f1j1m1x1c1g1l1g1o1f1h1a1e1f1u1s2x1p1l1n1w1x1g1z1u1w1b1l1w1d1z2y1t1d1i1y1s1x1o1h1x1t1p1k1c1m1z1q1x1b1e1w1x1c1q1j1y1p1h1e1m1j1t2m1d1i1r1n1w1q1f1x1g2u1f2x1b1d1v1r1x1c1w1x1j1k3s1u1b1n1b1i1e1k1g1k1g1p1x1n1a1u1s2x1a1m1b1s1k1s1p1k1h1c1w1j1e1s1z1x1g1a1o2p2o'
    got = solution.compressedString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = ['gtjtngvhfpaenctblrvwyncofmklstgdepcgtylwqhspranoehzlsyhdxeoi']
    want = '1g1t1j1t1n1g1v1h1f1p1a1e1n1c1t1b1l1r1v1w1y1n1c1o1f1m1k1l1s1t1g1d1e1p1c1g1t1y1l1w1q1h1s1p1r1a1n1o1e1h1z1l1s1y1h1d1x1e1o1i'
    got = solution.compressedString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = ['yqfjfggxumwuvjukdpuecqgyhvkyikysdqethxohkszmkgoipvqgplucrkgywxtwxfmenvnrzkoccmbtdicnkdoitwdnewxfedum']
    want = '1y1q1f1j1f2g1x1u1m1w1u1v1j1u1k1d1p1u1e1c1q1g1y1h1v1k1y1i1k1y1s1d1q1e1t1h1x1o1h1k1s1z1m1k1g1o1i1p1v1q1g1p1l1u1c1r1k1g1y1w1x1t1w1x1f1m1e1n1v1n1r1z1k1o2c1m1b1t1d1i1c1n1k1d1o1i1t1w1d1n1e1w1x1f1e1d1u1m'
    got = solution.compressedString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = ['d']
    want = '1d'
    got = solution.compressedString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

