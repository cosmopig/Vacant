"""adapters／帳本的對抗審查回歸（2026-09-24，`decisions/DECISION_20260924_UNIVERSAL_INTAKE.md` §十一）。

- 殼層指令的保護規則用子字串比對 ⇒ 擋掉正常工作（`~/.vacant-work` 裡的每一個寫入、
  `pytest tests`、`python3 x.py data/sales.csv > report.md`）
- Codex／OpenCode 的 apply_patch 真實形狀沒被讀到 ⇒ 改契約的修補放行
- `/clear`、resume 也觸發交件；等審查的 hold 被當成要 agent 修
- `CLAUDE_CONFIG_DIR` 被忽略；`~/.codex` 是連結時信任鍵寫錯路徑
- 安裝把連結換成普通檔、0600 變 0644；重裝蓋掉備份；撤銷失敗卻忘了；結尾標記壞掉就刪到檔尾
- `vacant do` 被中斷留下孤兒 agent、帳本沒有終態；`.git/hooks` 植入不算逃逸；
  hold 也重試；`VACANT_HOME` 在專案裡時金鑰被複製進工作區
- 放行之後交一個被退的版本，狀態就變 rejected（目的端上明明還是放行的那一版）；
  從沒放行過的任務被「撤回」之後永遠放不出去；一個壞掉的帳本讓整份報表消失
"""
from __future__ import annotations

import json
import os
import pathlib
import signal
import stat
import subprocess
import sys
import time

import pytest

from vacant_network.adapters import agents as A
from vacant_network.adapters import hook as HK
from vacant_network.adapters import hookpolicy as HP
from vacant_network.adapters import install as INS
from vacant_network.adapters import run as RUN
from vacant_network.intake import contract as C
from vacant_network.intake import flow
from vacant_network.intake.ledger import report as ledger_report


@pytest.fixture()
def vhome(tmp_path, monkeypatch):
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vhome"))
    monkeypatch.delenv("VACANT_WORK", raising=False)
    return tmp_path / "vhome"


def _proj(tmp_path, claims=None, *, attempts=1, name="proj"):
    proj = tmp_path / name
    (proj / ".vacant").mkdir(parents=True)
    (proj / "data").mkdir()
    (proj / "data" / "sales.csv").write_text("amount\n1\n")
    (proj / "tests").mkdir()
    (proj / "tests" / "test_x.py").write_text("def check_x():\n    pass\n")
    raw = C.scaffold("t-hard", deliverable=["out.txt"], destination="dir:published")
    raw["claims"] = claims or [{"id": "has_out", "verifier": "text",
                                "params": {"path": "out.txt", "must_contain": ["^done$"]}}]
    raw["inputs"] = {"sales": {"path": "data/sales.csv"}, "suite": {"path": "tests"}}
    raw["attempts"] = {"max": attempts}
    (proj / ".vacant" / "contract.json").write_text(json.dumps(raw))
    flow.lock(proj / ".vacant" / "contract.json")
    return proj, C.load(proj / ".vacant" / "contract.json")


def _pre(c, command=None, *, tool="Bash", paths=None, cwd=None):
    ev = HP.HookEvent(agent="claude", kind="pre_tool", tool=tool, command=command,
                      paths=paths or [], cwd=str(cwd or c.base_dir))
    return HP.decide_pre_tool(ev, c).action


# ── 殼層指令規則：路徑元件，不是子字串 ─────────────────────────────────

@pytest.mark.parametrize("cmd", [
    "python3 analyze.py data/sales.csv > report.md",
    "pytest tests -q 2>&1 | tail -5",
    "cp data/sales.csv /tmp/work.csv",
    "echo hi > metadata_tests_notes.txt",
    "cat .vacant/contract.json | python3 -c 'import sys; print(1)' > c.txt",
])
def test_normal_work_is_not_blocked(tmp_path, vhome, cmd):
    _, c = _proj(tmp_path)
    assert _pre(c, cmd) == "allow"


def test_writes_inside_the_vacant_work_directory_are_allowed(tmp_path, vhome):
    _, c = _proj(tmp_path)
    ws = RUN.work_root() / "t" / "r" / "ws"
    assert _pre(c, f"cd {ws} && python3 gen.py > {ws}/report.md", cwd=ws) == "allow"


@pytest.mark.parametrize("cmd", [
    "echo x > data/sales.csv",
    "sed -i s/1/2/ data/sales.csv",
    "cp /tmp/evil.csv data/sales.csv",
    "rm -rf tests",
    "cd data && echo 9 >> sales.csv",
    "python3 -c \"open('.vacant/contract.json','w').write('{}')\"",
    "git checkout -- data/sales.csv",
    "tee .vacant/contract.json < /tmp/x",
])
def test_writes_to_the_contract_and_pinned_inputs_are_denied(tmp_path, vhome, cmd):
    _, c = _proj(tmp_path)
    assert _pre(c, cmd) == "deny"


def test_reading_signing_keys_is_denied_even_inside_code(tmp_path, vhome):
    _, c = _proj(tmp_path)
    key = HP.vacant_state_dir() / "intake" / "keys" / "owner" / "identity.key"
    assert _pre(c, f"cat {key}") == "deny"
    assert _pre(c, f"python3 -c \"print(open('{key}').read())\"") == "deny"


@pytest.mark.parametrize("cmd", ["vacant review quality pass --reason ok",
                                 "python3 -m vacant_network approve", "vacant release",
                                 "vacant contract lock", "vacant keys init"])
def test_the_session_cannot_exercise_other_authorities(tmp_path, vhome, cmd):
    _, c = _proj(tmp_path)
    assert _pre(c, cmd) == "deny"
    assert _pre(c, "vacant check") == "allow" and _pre(c, "vacant submit") == "allow"


# ── apply_patch 的真實形狀 ─────────────────────────────────────────────

PATCH = ("*** Begin Patch\n*** Update File: .vacant/contract.json\n@@\n-  \"max\": 1\n"
         "+  \"max\": 10\n*** End Patch\n")


@pytest.mark.parametrize("agent,payload", [
    ("codex", {"hook_event_name": "PreToolUse", "tool_name": "apply_patch",
               "tool_input": {"command": PATCH}}),
    ("opencode", {"tool": "apply_patch", "args": {"patchText": PATCH}}),
])
def test_native_apply_patch_to_the_contract_is_denied(tmp_path, vhome, agent, payload):
    proj, _ = _proj(tmp_path)
    event = "PreToolUse" if agent == "codex" else "pre_tool"
    ev = HK.normalize(agent, event, {**payload, "cwd": str(proj)})
    assert ev.paths == [".vacant/contract.json"] and ev.command is None
    out, err, rc = HK.handle(agent, event, {**payload, "cwd": str(proj)})
    if agent == "codex":
        assert rc == 2 and err
    else:
        assert json.loads(out)["action"] == "deny"


# ── 工作階段結束的原因；等審查不是 agent 的事 ─────────────────────────

def test_clear_and_resume_do_not_submit(tmp_path, vhome, monkeypatch):
    proj, _ = _proj(tmp_path)
    calls = []
    monkeypatch.setattr(HK, "_spawn_submit", lambda *a: calls.append(a) or 1)
    for reason in ("clear", "resume"):
        HK.handle("claude", "SessionEnd", {"hook_event_name": "SessionEnd", "reason": reason,
                                           "cwd": str(proj)})
    HK.handle("pi", "session_end", {"cwd": str(proj), "reason": "reload"})
    assert calls == []
    HK.handle("claude", "SessionEnd", {"hook_event_name": "SessionEnd",
                                       "reason": "prompt_input_exit", "cwd": str(proj)})
    assert len(calls) == 1


def test_stop_does_not_push_back_what_the_agent_cannot_fix(tmp_path, vhome):
    proj, c = _proj(tmp_path, [{"id": "quality", "verifier": "review"}])
    (proj / "out.txt").write_text("done\n")
    ev = HP.HookEvent(agent="claude", kind="stop", cwd=str(proj), session_id="s1")
    d = HP.decide_stop(ev, c, check_fn=flow.check)
    assert d.action == "allow" and d.record.get("not_agent_fixable")


# ── 安裝 ──────────────────────────────────────────────────────────────

@pytest.fixture()
def fakehome(tmp_path, monkeypatch, vhome):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    for k in ("CODEX_HOME", "PI_CODING_AGENT_DIR", "XDG_CONFIG_HOME", "CLAUDE_CONFIG_DIR",
              "OPENCODE_CONFIG_CONTENT"):
        monkeypatch.delenv(k, raising=False)
    return home


def test_claude_config_dir_is_honoured(tmp_path, fakehome, monkeypatch):
    cfg = tmp_path / "claude-cfg"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(cfg))
    m = INS.Manifest()
    A.claude_install(m, fakehome)
    assert INS.MARKER in (cfg / "settings.json").read_text()
    assert not (fakehome / ".claude" / "settings.json").exists()
    assert A.persistent_hook_file("claude") == cfg / "settings.json"


def test_codex_trust_keys_cover_a_symlinked_codex_home(tmp_path, fakehome):
    real = tmp_path / "dotfiles" / "codex"
    real.mkdir(parents=True)
    (real / "config.toml").write_text('model = "m"\n')
    os.symlink(real, fakehome / ".codex")
    m = INS.Manifest()
    A.codex_install(m, fakehome)
    import tomllib
    keys = list(tomllib.loads((real / "config.toml").read_text())["hooks"]["state"])
    assert any(k.startswith(str(fakehome / ".codex" / "config.toml")) for k in keys)
    assert (fakehome / ".codex").is_symlink()


def test_install_writes_through_symlinks_and_keeps_the_mode(tmp_path, fakehome):
    real = tmp_path / "dotfiles" / "settings.json"
    real.parent.mkdir(parents=True)
    real.write_text('{"env": {"API_KEY": "sk-secret"}}')
    os.chmod(real, 0o600)
    (fakehome / ".claude").mkdir()
    os.symlink(real, fakehome / ".claude" / "settings.json")
    m = INS.Manifest()
    A.claude_install(m, fakehome)
    m.save()
    link = fakehome / ".claude" / "settings.json"
    assert link.is_symlink() and INS.MARKER in real.read_text()
    assert stat.S_IMODE(real.stat().st_mode) == 0o600
    m2 = INS.Manifest()
    INS.uninstall(m2, "claude")
    m2.save()
    assert link.is_symlink() and real.read_text() == '{"env": {"API_KEY": "sk-secret"}}'
    assert stat.S_IMODE(real.stat().st_mode) == 0o600


def test_installing_twice_still_restores_the_original_bytes(tmp_path, fakehome):
    p = fakehome / ".claude" / "settings.json"
    p.parent.mkdir()
    original = b'{\n    "permissions": {\n        "allow": ["Read"]\n    }\n}\n'
    p.write_bytes(original)
    for _ in range(2):
        m = INS.Manifest()
        A.claude_install(m, fakehome)
        m.save()
    m = INS.Manifest()
    INS.uninstall(m, "claude")
    m.save()
    assert p.read_bytes() == original


def test_a_failed_undo_is_remembered_and_reported(tmp_path, fakehome, capsys):
    from vacant_network.adapters import cli as ACLI
    p = fakehome / ".claude" / "settings.json"
    p.parent.mkdir()
    p.write_text("{}")
    m = INS.Manifest()
    A.claude_install(m, fakehome)
    m.save()
    good = p.read_text()
    p.write_text("// a comment makes it unparsable\n" + good)
    assert ACLI.main(["uninstall", "--agents", "claude"]) == 1
    assert INS.Manifest().ops("claude")                     # 還記得，下次可以再試
    p.write_text(good)
    assert ACLI.main(["uninstall", "--agents", "claude"]) == 0
    assert INS.MARKER not in p.read_text()


def test_a_damaged_end_marker_is_refused_not_deleted_to_eof(tmp_path, fakehome):
    cfg = fakehome / ".codex" / "config.toml"
    cfg.parent.mkdir()
    cfg.write_text('model = "m"\n')
    m = INS.Manifest()
    A.codex_install(m, fakehome)
    m.save()
    text = cfg.read_text().replace(INS.BLOCK_END, "# edited end marker")
    cfg.write_text(text + "\n[mcp_servers.newserver]\ncommand = \"x\"\n")
    res = INS.uninstall(INS.Manifest(), "codex")
    assert any(r["result"].startswith("error:") for r in res)
    assert "[mcp_servers.newserver]" in cfg.read_text()


# ── vacant do ─────────────────────────────────────────────────────────

def _agent(script: str) -> RUN.Launch:
    return RUN.Launch(argv=[sys.executable, "-c", script])


def test_git_hook_implants_in_the_original_project_count_as_escape(tmp_path, vhome):
    proj, c = _proj(tmp_path)
    subprocess.run(["git", "init", "-q", str(proj)], check=True)
    task = flow.open_task(c)
    implant = (f"import os; p={str(proj / '.git' / 'hooks' / 'post-checkout')!r}; "
               f"open(p,'w').write('touch /tmp/pwn'); os.makedirs({str(proj / 'empty')!r}); "
               f"open('out.txt','w').write('done\\n')")
    res = RUN.do(task, agent="fake", prompt="p", build=lambda p, ws: _agent(implant))
    a = res["attempts"][0]
    assert a["workspace_escape"] is True
    assert ".git/hooks/post-checkout" in a["escaped_paths"] and "empty/" in a["escaped_paths"]


def test_hold_is_not_retried(tmp_path, vhome):
    proj, c = _proj(tmp_path, [{"id": "q", "verifier": "review"}], attempts=3)
    task = flow.open_task(c)
    res = RUN.do(task, agent="fake", prompt="p",
                 build=lambda p, ws: _agent("open('out.txt','w').write('done\\n')"))
    assert res["outcome"] == "hold" and len(res["attempts"]) == 1 and res.get("stopped")


def test_vacant_home_inside_the_project_is_not_copied_into_the_workspace(tmp_path, monkeypatch):
    proj = tmp_path / "proj"
    monkeypatch.setenv("VACANT_HOME", str(proj / ".vh"))
    monkeypatch.delenv("VACANT_WORK", raising=False)
    _, c = _proj(tmp_path)
    task = flow.open_task(c)
    for _ in range(2):                                  # 第二跑不可以遞迴複製
        res = RUN.do(task, agent="fake", prompt="p",
                     build=lambda p, ws: _agent("open('out.txt','w').write('done\\n')"))
        ws = pathlib.Path(res["workspace"])
        assert not list(ws.rglob("identity.key"))
        assert res["attempts"][0]["workspace_escape"] is False


def test_sigterm_kills_the_agent_and_leaves_a_terminal_record(tmp_path, vhome):
    proj, c = _proj(tmp_path)
    pidfile = tmp_path / "agent.pid"
    driver = f"""
import sys, pathlib
sys.path.insert(0, {str(pathlib.Path(__file__).resolve().parents[1])!r})
from vacant_network.adapters import run as RUN
from vacant_network.intake import flow
task = flow.open_task({str(c.path)!r})
script = "import os,time; open({str(pidfile)!r},'w').write(str(os.getpid())); time.sleep(120)"
RUN.do(task, agent="fake", prompt="p",
       build=lambda p, ws: RUN.Launch(argv=[sys.executable, "-c", script]))
"""
    proc = subprocess.Popen([sys.executable, "-c", driver], env=os.environ.copy())
    for _ in range(100):
        if pidfile.exists() and pidfile.read_text():
            break
        time.sleep(0.1)
    agent_pid = int(pidfile.read_text())
    proc.send_signal(signal.SIGTERM)
    proc.wait(timeout=30)
    time.sleep(0.5)
    with pytest.raises(ProcessLookupError):
        os.kill(agent_pid, 0)
    evs = flow.open_task(c).ledger.events()
    assert any(e["type"] == "infra_void" and e.get("stage") == "interrupted" for e in evs)


# ── 帳本的狀態與報表 ───────────────────────────────────────────────────

def _submit(task, tmp_path, name, text):
    ws = tmp_path / name
    ws.mkdir()
    (ws / "out.txt").write_text(text)
    return flow.submit(task, ws, source="t")


def test_a_later_reject_does_not_hide_the_live_release(tmp_path, vhome):
    _, c = _proj(tmp_path)
    task = flow.open_task(c)
    _submit(task, tmp_path, "a", "done\n")
    assert flow.release(task)["released"] is True
    assert _submit(task, tmp_path, "b", "nope\n")["outcome"] == "reject"
    st = flow.status(task)
    assert st["state"] == "released" and st["newer_candidate"]["state"] == "rejected"
    rep = ledger_report()
    assert rep["by_state"]["released"] == 1 and rep["destination_live"] == 1


def test_withdrawing_a_never_released_task_is_a_noop(tmp_path, vhome):
    _, c = _proj(tmp_path)
    task = flow.open_task(c)
    w = flow.withdraw(task, reason="oops")
    assert w.get("noop") is True
    _submit(task, tmp_path, "a", "done\n")
    assert flow.release(task)["released"] is True


def test_one_unreadable_ledger_stays_in_the_denominator(tmp_path, vhome):
    _, c = _proj(tmp_path)
    task = flow.open_task(c)
    _submit(task, tmp_path, "a", "done\n")
    other = task.ledger.path.parent / "broken-task.ndjson"
    other.write_text('{"not": "a chain entry", "trunc')
    rep = ledger_report()
    assert rep["n_tasks"] == 2 and rep["by_state"]["unreadable"] == 1


def test_submit_does_not_freeze_the_in_project_destination(tmp_path, vhome):
    raw_claims = [{"id": "e", "verifier": "exists", "params": {"paths": ["out.txt"]}}]
    proj, c = _proj(tmp_path, raw_claims)
    raw = json.loads(c.path.read_text())
    raw["deliverable"]["include"] = ["**"]
    c.path.write_text(json.dumps(raw))
    flow.lock(c.path)
    task = flow.open_task(c.path)
    (proj / "out.txt").write_text("done\n")
    flow.submit(task, proj, source="t")
    assert flow.release(task)["released"] is True
    res = flow.submit(task, proj, source="t")
    m = task.store.load_manifest(res["artifact_sha256"])
    assert not [f for f in m["files"] if f["path"].startswith("published/")]
