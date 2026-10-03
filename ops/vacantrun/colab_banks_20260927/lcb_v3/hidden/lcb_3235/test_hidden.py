"""Scoring checks for lcb_3235 -- NOT part of any workspace.

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
    args = ['abcd', 'acbe', ['a', 'b', 'c', 'c', 'e', 'd'], ['b', 'c', 'b', 'e', 'b', 'e'], [2, 5, 5, 1, 2, 20]]
    want = 28
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = ['aaaa', 'bbbb', ['a', 'c'], ['c', 'b'], [1, 2]]
    want = 12
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = ['abcd', 'abce', ['a'], ['e'], [10000]]
    want = -1
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = ['svqcmtfmmk', 'gckeybwxiv', ['r', 't'], ['e', 's'], [595104, 687994]]
    want = -1
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = ['svqcmtfmmk', 'gckeybwxiv', ['g', 'e'], ['s', 'n'], [639516, 745235]]
    want = -1
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = ['svqcmtfmmk', 'gckeybwxiv', ['l', 'm'], ['u', 't'], [537805, 221140]]
    want = -1
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = ['xwwbq', 'jbbha', ['l', 'g', 'b', 'g', 'v', 'j', 'a', 's', 'w', 'w'], ['h', 'c', 's', 'm', 'k', 'n', 'd', 'p', 'h', 'b'], [55, 22, 15, 16, 29, 43, 46, 100, 47, 68]]
    want = -1
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = ['svqcmtfmmk', 'gckeybwxiv', ['f', 'm', 'k', 's', 'c', 'q', 't', 'v'], ['p', 'w', 'g', 'c', 'o', 'r', 's', 'e'], [78172, 888733, 205010, 47425, 945508, 646126, 800795, 25542]]
    want = -1
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = ['owjhjlkskb', 'fiiistchug', ['z', 'z', 'v', 'i', 'l', 'm', 'l', 'z', 'n', 'k'], ['q', 'g', 'i', 'c', 'k', 's', 'g', 'e', 'z', 'e'], [273165, 487946, 918483, 356362, 895609, 968808, 480774, 42600, 473983, 947825]]
    want = -1
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = ['sxnvpozkxwwvhijlcywbeutnkehbqlxikrcsdixctwajckygpxesbupfvpflsbjxtfzhrkycutkcbxwtiirnsjwezjafigvsqugm', 'slatzlmbzcbrkbvoalwwklvwijgoufmvkuyysvvyvkaidukbheexgewmzlqfqecoatpnboqrmeonincfnlggxzijmfhcdgwporgk', ['r', 'w', 'i', 'e', 'f', 'l', 'u', 'b', 'g', 'r'], ['k', 's', 't', 'n', 'd', 'r', 'z', 's', 'u', 's'], [933811, 232967, 870813, 299993, 860883, 9047, 365080, 465467, 968998, 293486]]
    want = -1
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = ['jgqfqdxvmqgvezvueuwsckhhyaoeztviyvevdzphurhezpjtszhphewljvmcpxggxqhemrtggpqenjasrgvydedooeeuaainmfqi', 'izyjfohigvxqygdpzyvhyvzacgploycdqgvbwrrcurwereggcrdjxessizccvsezmxqhgiiekubhrawocsfocsnmxeiwfyfobonh', ['a', 'm', 'k', 'u', 'q', 'j', 'v', 'p', 'l', 'o', 'f', 'x', 'g', 'e', 'n', 'w', 'z', 'r', 'c', 'd', 'i', 'h', 's', 'y', 't'], ['h', 'l', 'i', 'v', 'p', 'z', 'u', 'a', 'a', 'm', 'd', 'g', 'p', 'u', 'm', 'j', 'j', 'x', 'o', 'l', 'c', 'e', 'w', 's', 'd'], [895977, 730406, 609770, 44855, 854756, 529983, 505019, 543482, 502635, 846880, 623371, 847699, 907864, 523705, 716002, 386994, 883916, 922839, 498971, 715519, 903522, 303276, 535910, 831339, 675789]]
    want = -1
    got = solution.minimumCost(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

