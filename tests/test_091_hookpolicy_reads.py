"""0.9.1 回歸：hookpolicy 把「只讀 Vacant 狀態資料夾」的內聯程式碼誤判成寫入。

承重什麼：`_CODE_WRITE_HINT` 曾把任何 `open(`／`replace(` 當成寫入，連唯讀的
`python3 -c "import json;print(json.load(open('~/.vacant/adapters/install.json')))"` 都擋。
第一版修法解析 open() 的模式（黑名單），對抗審查一再找到寫入漏洞（`p.open('w')`、`shelve.open`、
`dbm.open(p,'c')`、perl `open(F,'>',p)`、`open(p,'\\167')`）⇒ 改回 09cc052f 的提示（裸 `open(`、
`replace(` 都算寫），只開白名單豁免：`python -c` 裡裸的 `open('字面值'[, r|rb|rt|br|tr])`、沒有其他
寫入提示、受保護路徑只出現在這些字面值裡。另一個決定：`_in_code` **不加左邊界**（加了會讓 `os.getcwd()+'/.vacant/…'` 這類
執行時組出來的路徑讀到私鑰、寫到被鎖的契約）；cwd==HOME 時 `proj/.vacant/…` 被多擋，接受。
誠實邊界：仍是字串層；白名單之外一律算寫入（含 `s.replace('a','b')`、`open(p, mode='r')`）。
豁免只作用在寫入保護；讀金鑰在豁免之前就拒絕。
"""
from __future__ import annotations

import json

import pytest

from vacant_network.adapters import hookpolicy as HP
from vacant_network.intake import contract as C
from vacant_network.intake import flow


@pytest.fixture()
def env(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("VACANT_HOME", str(home / ".vacant"))
    monkeypatch.delenv("VACANT_WORK", raising=False)
    proj = home / "proj"
    (proj / ".vacant").mkdir(parents=True)
    raw = C.scaffold("t-091", deliverable=["out.txt"], destination="dir:published")
    raw["claims"] = [{"id": "c", "verifier": "text",
                      "params": {"path": "out.txt", "must_contain": ["^done$"]}}]
    (proj / ".vacant" / "contract.json").write_text(json.dumps(raw))
    flow.lock(proj / ".vacant" / "contract.json")
    return home, proj, C.load(proj / ".vacant" / "contract.json")


def _act(c, cmd, cwd):
    ev = HP.HookEvent(agent="claude", kind="pre_tool", tool="Bash", command=cmd,
                      paths=[], cwd=str(cwd))
    return HP.decide_pre_tool(ev, c).action


def _cases(state):
    p = f"{state}/adapters/install.json"
    return [
        ("incident read", f"python3 -c \"import json;print(json.load(open('{p}')))\"", "allow"),
        ("open r", f"python3 -c \"print(open('{p}','r').read())\"", "allow"),
        # 白名單只收位置引數的模式字面值；mode= 關鍵字不在白名單 ⇒ 照 09cc052f 算寫
        ("open mode kw r", f"python3 -c \"print(open('{p}', mode='rb').read())\"", "deny"),
        ("open w", f"python3 -c \"open('{p}','w').write('x')\"", "deny"),
        ("open mode kw a", f"python3 -c \"open('{p}', mode='a')\"", "deny"),
        ("open unknown mode", f"python3 -c \"m='w';open('{p}',m)\"", "deny"),
        ("open nested path join w", f"python3 -c \"open(os.path.join('{state}','x'),'w')\"", "deny"),
        ("write_text", f"python3 -c \"import pathlib;pathlib.Path('{p}').write_text('x')\"", "deny"),
        ("Path.open w", f"python3 -c \"pathlib.Path('{p}').open('w')\"", "deny"),
        ("os.remove", f"python3 -c \"import os;os.remove('{p}')\"", "deny"),
        ("os.replace", f"python3 -c \"import os;os.replace('/tmp/a','{p}')\"", "deny"),
        ("Path.replace", f"python3 -c \"pathlib.Path('/tmp/a').replace('{p}')\"", "deny"),
        ("node writeFile", f"node -e \"require('fs').writeFileSync('{p}','x')\"", "deny"),
        ("node read", f"node -e \"console.log(require('fs').readFileSync('{p}','utf8'))\"", "allow"),
        # 決定：`replace(` 照 09cc052f 一律算寫（字串層分不出 str.replace 與 Path.replace）
        ("str.replace", f"python3 -c \"print('{p}'.replace('a','b'))\"", "deny"),
    ]


def test_inline_code_table(env):
    home, proj, c = env
    bad = []
    for name, cmd, want in _cases(str(home / ".vacant")):
        got = _act(c, cmd, proj)
        if got != want:
            bad.append((name, want, got))
    assert not bad, bad


def test_cwd_home_relative_state_name_is_conservative(env):
    """沒有左邊界：cwd==HOME 時 `proj/.vacant/…` 也算狀態資料夾（多擋，安全優先）。"""
    home, proj, c = env
    assert _act(c, "python3 -c \"open('.vacant/x','w')\"", home) == "deny"
    assert _act(c, "python3 -c \"open('./.vacant/x','w')\"", home) == "deny"
    assert _act(c, "python3 -c \"open('proj/.vacant/contract.json','w')\"", home) == "deny"


_KEY_REL = ".vacant/intake/keys/owner/identity.key"

#: 對抗審查 probe.py 的重現（cwd==HOME 讀私鑰、cwd=proj 寫被鎖的契約）：全部必須 deny。
_RUNTIME_PATH_DENY = [
    ("key read cwd+concat",
     f"python3 -c \"import os;print(open(os.getcwd()+'/{_KEY_REL}').read())\"", "home"),
    ("key read .//", f"python3 -c \"print(open('.//{_KEY_REL}').read())\"", "home"),
    ("key read fstring",
     f"python3 -c \"import os;print(open(f'{{os.getcwd()}}/{_KEY_REL}').read())\"", "home"),
    ("key read PWD",
     f"python3 -c \"import os;print(open(os.environ['PWD']+'/{_KEY_REL}').read())\"", "home"),
    ("key read plus", f"python3 -c \"print(open('x'+'{_KEY_REL}').read())\"", "home"),
    ("key read node cwd",
     f"node -e \"console.log(require('fs').readFileSync(process.cwd()+'/{_KEY_REL}','utf8'))\"",
     "home"),
    ("contract write cwd concat",
     "python3 -c \"import os;open(os.getcwd()+'/.vacant/contract.json','w').write('{}')\"", "proj"),
    ("contract write fstring",
     "python3 -c \"import os;open(f'{os.getcwd()}/.vacant/contract.json','w').write('{}')\"",
     "proj"),
    ("contract write .//", "python3 -c \"open('.//.vacant/contract.json','w').write('{}')\"", "proj"),
    ("contract write plain", "python3 -c \"open('.vacant/contract.json','w').write('{}')\"", "proj"),
]


@pytest.mark.parametrize("name,cmd,where", _RUNTIME_PATH_DENY,
                         ids=[x[0] for x in _RUNTIME_PATH_DENY])
def test_runtime_built_paths_denied(env, name, cmd, where):
    home, proj, c = env
    assert _act(c, cmd, home if where == "home" else proj) == "deny"


def _state_write_cases(S):
    return [
        ("Path.open(m) var", f"python3 -c \"m='w';import pathlib;pathlib.Path('{S}/x').open(m)\""),
        ("Path.open(*a)", f"python3 -c \"import pathlib;pathlib.Path('{S}/x').open(*['w'])\""),
        ("Path.open(mode var kw)",
         f"python3 -c \"m='w';import pathlib;pathlib.Path('{S}/x').open(mode=m)\""),
        ("Path.open(**kw)",
         f"python3 -c \"import pathlib;pathlib.Path('{S}/x').open(**{{'mode':'w'}})\""),
        ("open(*a)", f"python3 -c \"open(*['{S}/x','w'])\""),
        ("open(p, **kw)", f"python3 -c \"open('{S}/x', **{{'mode':'w'}})\""),
        ("open r+w concat", f"python3 -c \"open('{S}/x','r'+'w')\""),
        ("open conditional mode", f"python3 -c \"open('{S}/x', 'r' if 0 else 'w')\""),
        ("node openSync", f"node -e \"require('fs').openSync('{S}/x','w')\""),
        ("node copyFileSync", f"node -e \"require('fs').copyFileSync('/tmp/a','{S}/x')\""),
        ("node cpSync", f"node -e \"require('fs').cpSync('/tmp/a','{S}/x')\""),
        ("os.symlink", f"python3 -c \"import os;os.symlink('/tmp/a','{S}/x')\""),
        ("Path.touch", f"python3 -c \"import pathlib;pathlib.Path('{S}/x').touch()\""),
        ("os.makedirs", f"python3 -c \"import os;os.makedirs('{S}/x')\""),
        ("os.mkdir", f"python3 -c \"import os;os.mkdir('{S}/x')\""),
        ("Path.replace alias",
         f"python3 -c \"from pathlib import Path as P;P('/tmp/a').replace(P('{S}/x'))\""),
        ("shutil.move", f"python3 -c \"import shutil;shutil.move('/tmp/a','{S}/x')\""),
        ("open w comma in path", f"python3 -c \"open('{S}/a,b','w')\""),
        ("open w double quotes", f"python3 -c 'open(\"{S}/x\",\"w\")'"),
        ("triple quote mode", f"python3 -c \"open('{S}/x', " + "'''w''')\""),
        ("mode kw after buffering", f"python3 -c \"open('{S}/x', buffering=-1, mode='w')\""),
        ("file= mode=", f"python3 -c \"open(file='{S}/x', mode='w')\""),
        ("ruby File.write", f"ruby -e \"File.write('{S}/x','y')\""),
        ("ruby File.open w", f"ruby -e \"File.open('{S}/x','w'){{|f|f.puts 1}}\""),
        ("io.open w", f"python3 -c \"import io;io.open('{S}/x','w')\""),
        ("open r+", f"python3 -c \"open('{S}/x','r+')\""),
        ("open uppercase W", f"python3 -c \"open('{S}/x','W')\""),
        ("open then .write", f"python3 -c \"f=open('{S}/x');f.write('a')\""),
        ("open bytes mode", f"python3 -c \"open('{S}/x',b'wb')\""),
        ("perl open >", f"perl -e \"open(F,'>{S}/x')\""),
    ]


def test_state_writes_denied(env):
    home, proj, c = env
    bad = [n for n, cmd in _state_write_cases(str(home / ".vacant"))
           if _act(c, cmd, proj) != "deny"]
    assert not bad, bad


def test_read_only_modes_allowed(env):
    """刻意的 deny→allow（相對 09cc052f）只有白名單裡的唯讀 open。"""
    home, proj, c = env
    p = f"{home}/.vacant/adapters/install.json"
    for cmd in (f"python3 -c \"print(open('{p}','rt').read())\"",
                f"python3 -c \"print(open('{p}','rb').read())\"",
                f"python3 -c \"print(open('{p}', 'br').read())\"",
                f"python3.11 -c \"import json;print(json.load(open('{p}')))\"",
                f"python -c \"import json, pprint;x=open('{p}');pprint.pprint(json.load(x))\""):
        assert _act(c, cmd, proj) == "allow", cmd
    rel = "python3 -c \"import json;print(json.load(open('.vacant/adapters/install.json')))\""
    assert _act(c, rel, home) == "allow"


def test_outside_allowlist_denied(env):
    """白名單之外照 09cc052f 算寫（多擋可以，漏寫不行）。"""
    home, proj, c = env
    S = f"{home}/.vacant"
    p = f"{S}/adapters/install.json"
    for cmd in (f"python3 -c \"print(open('{p}','rU').read())\"",
                f"python3 -c \"print(open('{p}').read().replace('a','b'))\"",
                f"python3 -c \"print(open('{p}').read().replace(str(1),str(2)))\"",
                f"python3 -c \"print(open('{p}','R').read())\"",
                f"python3 -c \"print(open(r'{p}').read())\"",
                f"python3 -c \"print(open(f'{p}').read())\"",
                f"python3 -c \"print(open('{p}','r',1).read())\"",
                # 只有 open 是讀，但受保護路徑還出現在別處
                f"python3 -c \"open('/tmp/a');print('{S}/x')\"",
                f"python3 -c \"open('{p}');__import__('os').system('rm {S}/x')\"",
                f"python3 -c \"import subprocess;open('{p}');subprocess.run(['rm', '{S}/x'])\"",
                f"python3 -c \"import os;open('{p}')\"",
                f"python3 -c \"exec(\\\"open('{S}/x','w')\\\")\"",
                f"python3 -c \"open('{p}','r');open('/tmp/y','w')\"",
                # 豁免只給 python -c
                f"pypy3 -c \"print(open('{p}').read())\"",
                f"ruby -e \"puts open('{p}').read\"",
                f"perl -e \"open(F,'{p}');print <F>\""):
        assert _act(c, cmd, proj) == "deny", cmd


#: 對抗審查第二輪（/tmp/claude-0/adv2-hookpolicy/r.py）：黑名單式模式解析漏掉的寫入，全部必須 deny。
def _adv2_cases(S):
    return [
        ("var.open('w')", f"python3 -c \"import pathlib;p=pathlib.Path('{S}/x');p.open('w')\""),
        ("var.open('a')", f"python3 -c \"import pathlib;p=pathlib.Path('{S}/x');p.open('a')\""),
        ("shelve.open", f"python3 -c \"import shelve;shelve.open('{S}/x')\""),
        ("dbm.open c", f"python3 -c \"import dbm;dbm.open('{S}/x','c')\""),
        ("dbm.open n", f"python3 -c \"import dbm;dbm.open('{S}/x','n')\""),
        ("mode \\u0077", f"python3 -c \"open('{S}/x','\\u0077')\""),
        ("mode \\167", f"python3 -c \"open('{S}/x','\\167')\""),
        ("perl 3arg >", f"perl -e \"open(F,'>','{S}/x');print F 1\""),
        ("perl 3arg >>", f"perl -e \"open(F,'>>','{S}/x')\""),
        ("ruby File.open mode kw", f"ruby -e \"File.open('{S}/x', mode: 'w')\""),
        ("py open r opener", f"python3 -c \"open('{S}/x','r',opener=lambda p,f:"
                             f"__import__('os').open(p,1))\""),
        ("node fs.open w", f"node -e \"require('fs').open('{S}/x','w',()=>0)\""),
        ("bare open dbm-like c", f"python3 -c \"open('{S}/x','c')\""),
        ("open literal path + mode w unicode-ish", f"python3 -c \"open('{S}/x','rw')\""),
    ]


@pytest.mark.parametrize("idx", range(14))
def test_adv2_writes_denied(env, idx):
    home, proj, c = env
    name, cmd = _adv2_cases(str(home / ".vacant"))[idx]
    assert _act(c, cmd, proj) == "deny", name


def test_reading_private_key_still_denied(env):
    home, proj, c = env
    key = home / ".vacant" / "intake" / "keys" / "owner" / "identity.key"
    assert _act(c, f"cat {key}", proj) == "deny"
    assert _act(c, f"python3 -c \"print(open('{key}').read())\"", proj) == "deny"
    assert _act(c, f"python3 -c \"print(open('{key}','rb').read())\"", proj) == "deny"
    assert _act(c, "python3 -c \"print(open('.vacant/intake/keys/owner/identity.key').read())\"",
                home) == "deny"


def test_round3_adversary_bypasses_denied(env):
    """第三輪對抗審查重現的繞法（`/tmp/claude-0/adv3-*`）：全部要擋。

    豁免是 tokenize 白名單：名字、屬性、運算子都要在表上，路徑要是正規形式、不能組，
    整個指令只能是單獨一段 `python -c`。
    """
    home, proj, c = env
    S = f"{home}/.vacant"
    p = f"{S}/adapters/install.json"
    key = f"{S}/intake/keys/owner/identity.key"
    for cmd in (
            # 非正規路徑讀私鑰（`..`、`.`、`//`）
            f"python3 -c \"print(open('{S}/intake/adapters/../keys/owner/identity.key').read())\"",
            f"python3 -c \"print(open('{S}/intake/./keys/owner/identity.key').read())\"",
            f"python3 -c \"print(open('{S}/intake//keys/owner/identity.key').read())\"",
            f"python3 -c \"print(open('{S}/adapters/../intake/keys/owner/identity.key').read())\"",
            f"python3 -c \"print(open('{key}').read())\"",
            # 黑名單漏掉的反射／全形識別字
            f"python3 -c \"import pprint; open('{p}'); pprint._sys.modules['o'+'s'].system('touch {S}/x')\"",
            "python3 -c 'import json; open(\"" + p + "\"); \uff47\uff45\uff54\uff41\uff54\uff54\uff52(json,\"x\")'",
            # 09cc052f 就漏的兩種寫法
            f"python3 -c \"open ('{S}/x','w')\"",
            "python3 -c \"\uff4f\uff50\uff45\uff4e('" + S + "/x','w')\"",
            # 唯讀開檔之後拿 handle 寫
            f"python3 -c \"f=open('{p}');f.write('x')\"",
            f"python3 -c \"import json;json.dump(1,open('{p}'))\"",
            f"python3 -c \"print(1,file=open('{p}'))\"",
            # 路徑在執行時組出來
            f"python3 -c \"print(open('{S}'+'/x').read())\"",
            # 整個指令不只一段 python -c
            f"python3 -c \"print(open('{p}').read())\" `touch {S}/x`",
            f"python3 -c \"print(open('{p}').read())\" > {S}/x",
            f"python3 -c \"print(open('{p}').read())\" | tee {S}/x",
            f"python3 -c \"print(open('{p}').read())\"; touch {S}/x",
    ):
        assert _act(c, cmd, proj) == "deny", cmd
