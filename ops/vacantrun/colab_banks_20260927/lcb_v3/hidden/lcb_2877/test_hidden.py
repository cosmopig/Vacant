"""Scoring checks for lcb_2877 -- NOT part of any workspace.

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
    args = ['abc', 'bca', 'aaa']
    want = 'aaabca'
    got = solution.minimumString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_02():
    args = ['ab', 'ba', 'aba']
    want = 'aba'
    got = solution.minimumString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_03():
    args = ['o', 'x', 'd']
    want = 'dox'
    got = solution.minimumString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_04():
    args = ['pmg', 'jv', 'e']
    want = 'ejvpmg'
    got = solution.minimumString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_05():
    args = ['hc', 'lhiv', 'hd']
    want = 'hchdlhiv'
    got = solution.minimumString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_06():
    args = ['tah', 'vq', 'gcrw']
    want = 'gcrwtahvq'
    got = solution.minimumString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_07():
    args = ['pxp', 'o', 'zjfacmb']
    want = 'opxpzjfacmb'
    got = solution.minimumString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_08():
    args = ['nlgqdguu', 'gm', 'e']
    want = 'egmnlgqdguu'
    got = solution.minimumString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_09():
    args = ['jb', 'rgyxglb', 'koa']
    want = 'jbkoargyxglb'
    got = solution.minimumString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_10():
    args = ['mrmzito', 'nssds', 'k']
    want = 'kmrmzitonssds'
    got = solution.minimumString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_11():
    args = ['sln', 'nmrfbbumy', 'cxqnl']
    want = 'cxqnlslnmrfbbumy'
    got = solution.minimumString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_12():
    args = ['kklsvpeqxegqskwgbwxreuprkgjgwuagxyhxvnakucehmmxnnxttedmwkungsutmizitclkjldjoxiajdeddkttmlfdqtoyiprzh', 'ttedmwkungsutmizitclkjldjoxiajdeddkttmlfdqtoyiprzhslqbktwmbvjrkhaimwddwmxrtnsigrqfptklmkqvmnjujgguqk', 'vbufbcdirblienjdlksffbtipttedmwkungsutmizitclkjldjoxiajdeddkttmlfdqtoyiprzhldtbwjdzcecsslgdbneqqkkes']
    want = 'kklsvpeqxegqskwgbwxreuprkgjgwuagxyhxvnakucehmmxnnxttedmwkungsutmizitclkjldjoxiajdeddkttmlfdqtoyiprzhslqbktwmbvjrkhaimwddwmxrtnsigrqfptklmkqvmnjujgguqkvbufbcdirblienjdlksffbtipttedmwkungsutmizitclkjldjoxiajdeddkttmlfdqtoyiprzhldtbwjdzcecsslgdbneqqkkes'
    got = solution.minimumString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_13():
    args = ['wovhrtfykmytnachvglbfqnrogibwopkalnrhzfmuorkixoauvofrhcqonlushhhdfhuzhytumfwdwemokrobmh', 'muednoskclbzjudiostwrtbkvmqlwogwhbdeiipdktuedbdoygruyogbaaswlevdkdpeykofxweajqnngjxsxqffssmjn', 'oqldwomhdtonzsqbwkzgcjiollhwnyfqkwxzoauhiekoydsmagthdfkcgctahibyygezclmcwbifgtdxndurwebupglfoyamux']
    want = 'muednoskclbzjudiostwrtbkvmqlwogwhbdeiipdktuedbdoygruyogbaaswlevdkdpeykofxweajqnngjxsxqffssmjnoqldwomhdtonzsqbwkzgcjiollhwnyfqkwxzoauhiekoydsmagthdfkcgctahibyygezclmcwbifgtdxndurwebupglfoyamuxwovhrtfykmytnachvglbfqnrogibwopkalnrhzfmuorkixoauvofrhcqonlushhhdfhuzhytumfwdwemokrobmh'
    got = solution.minimumString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)


def check_case_14():
    args = ['raejtnpndbrnfkvhwtpuuyvcimdjqkqbsjryknxgsvbrxzvdjyrvlbjmaqpjftwbakdcvgevlzykeztlfzddexzhsouxybbbkoua', 'wqfebyibylvqhwmksjovneujfievgcbsfcsqdiwgbcwagfispvzkciclkijfguwjoxudodbyesanvzipjerdimtwhmtmfzkrshir', 'lohdppbqkqdgaygemcaspusswrgyuiszpjmcjhozpcmfxfzggfrfkyprjwfsjbumiggqnejxvevumlydqassfjhgmjgocejruoax']
    want = 'lohdppbqkqdgaygemcaspusswrgyuiszpjmcjhozpcmfxfzggfrfkyprjwfsjbumiggqnejxvevumlydqassfjhgmjgocejruoaxwqfebyibylvqhwmksjovneujfievgcbsfcsqdiwgbcwagfispvzkciclkijfguwjoxudodbyesanvzipjerdimtwhmtmfzkrshiraejtnpndbrnfkvhwtpuuyvcimdjqkqbsjryknxgsvbrxzvdjyrvlbjmaqpjftwbakdcvgevlzykeztlfzddexzhsouxybbbkoua'
    got = solution.minimumString(*args)
    assert _aeq(got, want), "args=%r got=%r want=%r" % (args, got, want)

