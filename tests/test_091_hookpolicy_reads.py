"""0.9.1 回歸：hookpolicy 把「只讀 Vacant 狀態資料夾」的內聯程式碼誤判成寫入。

承重什麼：`_CODE_WRITE_HINT` 曾把任何 `open(`／`replace(` 當成寫入；`_in_code` 的相對路徑
沒有左邊界（cwd==HOME 時 `.vacant` 會吃到 `proj/.vacant/…`）。
誠實邊界：仍是字串層；拿不準（模式不是字面值）一律算寫入。`s.replace('a','b')` 不算寫，
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


def test_cwd_home_relative_state_name_needs_left_boundary(env):
    home, proj, c = env
    assert _act(c, "cat proj/.vacant/contract.json", home) == "allow"
    assert _act(c, "python3 -c \"print(open('proj/.vacant/contract.json').read())\"", home) == "allow"
    assert _act(c, "python3 -c \"print(open('foo.vacant/x').read())\"", home) == "allow"
    assert _act(c, "python3 -c \"open('.vacant/x','w')\"", home) == "deny"
    assert _act(c, "python3 -c \"open('./.vacant/x','w')\"", home) == "deny"


def test_reading_private_key_still_denied(env):
    home, proj, c = env
    key = home / ".vacant" / "intake" / "keys" / "owner" / "identity.key"
    assert _act(c, f"cat {key}", proj) == "deny"
    assert _act(c, f"python3 -c \"print(open('{key}').read())\"", proj) == "deny"
    assert _act(c, f"python3 -c \"print(open('{key}','rb').read())\"", proj) == "deny"
    assert _act(c, "python3 -c \"print(open('.vacant/intake/keys/owner/identity.key').read())\"",
                home) == "deny"
