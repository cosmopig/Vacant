"""0.9.1 回歸：hookpolicy 把「只讀 Vacant 狀態資料夾」的內聯程式碼誤判成寫入。

承重什麼：`_CODE_WRITE_HINT` 曾把任何 `open(`／`replace(` 當成寫入。
對抗審查之後的決定：`_in_code` **不加左邊界**（加了會讓 `os.getcwd()+'/.vacant/…'` 這類
執行時組出來的路徑讀到私鑰、寫到被鎖的契約）；cwd==HOME 時 `proj/.vacant/…` 被多擋，接受。
誠實邊界：仍是字串層；拿不準（模式不是字面值、`*` 展開）一律算寫入。`s.replace('a','b')` 不算寫，
`Path(p).replace(x)`／`os.replace` 算。讀金鑰照樣拒絕。
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
        ("open mode kw r", f"python3 -c \"print(open('{p}', mode='rb').read())\"", "allow"),
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
        # 決定：str.replace（兩個引數）只是字串操作，路徑出現在字串裡不是寫入 ⇒ 放行
        ("str.replace", f"python3 -c \"print('{p}'.replace('a','b'))\"", "allow"),
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
    """刻意的 deny→allow：看得到的唯讀模式字面值、str.replace。"""
    home, proj, c = env
    p = f"{home}/.vacant/adapters/install.json"
    for cmd in (f"python3 -c \"print(open('{p}','rt').read())\"",
                f"python3 -c \"print(open('{p}','rU').read())\"",
                f"python3 -c \"print(open('{p}').read().replace('a','b'))\"",
                f"python3 -c \"print(open('{p}').read().replace(str(1),str(2)))\""):
        assert _act(c, cmd, proj) == "allow", cmd


def test_reading_private_key_still_denied(env):
    home, proj, c = env
    key = home / ".vacant" / "intake" / "keys" / "owner" / "identity.key"
    assert _act(c, f"cat {key}", proj) == "deny"
    assert _act(c, f"python3 -c \"print(open('{key}').read())\"", proj) == "deny"
    assert _act(c, f"python3 -c \"print(open('{key}','rb').read())\"", proj) == "deny"
    assert _act(c, "python3 -c \"print(open('.vacant/intake/keys/owner/identity.key').read())\"",
                home) == "deny"
