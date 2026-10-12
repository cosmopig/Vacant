"""零設定第 1 步：模式開關、沒有契約也記錄、最小安裝（DECISION_20260925_ZERO_CONFIG_DESIGN §五）。"""
import json
import pathlib

import pytest

from vacant_network.adapters import cli as acli
from vacant_network.adapters import hook
from vacant_network.adapters import install as INS
from vacant_network.adapters.mode import current_mode
from vacant_network.trace import capture


@pytest.fixture
def env(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    for k in ("VACANT_TRACE", "VACANT_MODE", "CODEX_HOME", "PI_CODING_AGENT_DIR",
              "XDG_CONFIG_HOME", "CLAUDE_CONFIG_DIR"):
        monkeypatch.delenv(k, raising=False)
    return tmp_path


def _manifest(data):
    p = INS.state_root() / "install.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data))


def test_mode_is_off_until_vacant_is_installed(env):
    assert current_mode() == "off"


def test_mode_after_install_is_evidence_even_for_an_old_manifest(env):
    _manifest({"agents": {}})
    assert current_mode() == "evidence"


def test_mode_follows_the_manifest_and_env_overrides_for_tests(env, monkeypatch):
    _manifest({"agents": {}, "mode": "observe"})
    assert current_mode() == "observe"
    monkeypatch.setenv("VACANT_MODE", "off")
    assert current_mode() == "off"
    monkeypatch.setenv("VACANT_MODE", "evidence")
    monkeypatch.setenv("VACANT_TRACE", "0")
    assert current_mode() == "off"


def test_a_contractless_project_is_traced_at_its_git_root_once_installed(env):
    proj = env / "work" / "proj"
    (proj / ".git").mkdir(parents=True)
    (proj / "sub").mkdir()
    assert capture.workspace_for(str(proj / "sub")) is None
    _manifest({"agents": {}, "mode": "evidence"})
    assert capture.workspace_for(str(proj / "sub")) == proj.resolve()


def test_without_a_git_root_the_cwd_is_the_project_and_home_is_never_traced(env):
    _manifest({"agents": {}, "mode": "evidence"})
    d = env / "work" / "loose"
    d.mkdir(parents=True)
    assert capture.workspace_for(str(d)) == d.resolve()
    assert capture.workspace_for(str(pathlib.Path.home())) is None


def test_hook_steps_in_a_contractless_project_land_in_a_chain_only_when_installed(env):
    proj = env / "work" / "p"
    proj.mkdir(parents=True)
    pre = {"session_id": "S", "cwd": str(proj), "tool_name": "Write", "tool_use_id": "t1",
           "tool_input": {"file_path": str(proj / "a.md"), "content": "x"}}
    hook.handle("claude", "PreToolUse", pre)
    (proj / "a.md").write_text("x\n")
    hook.handle("claude", "PostToolUse", {**pre, "tool_response": {}})
    assert not list((env / "vh").rglob("chain.ndjson"))
    _manifest({"agents": {}, "mode": "evidence"})
    hook.handle("claude", "PreToolUse", {**pre, "tool_use_id": "t2"})
    (proj / "a.md").write_text("y\n")
    hook.handle("claude", "PostToolUse", {**pre, "tool_use_id": "t2", "tool_response": {}})
    assert list((env / "vh").rglob("chain.ndjson"))


def test_install_writes_mode_and_no_skill_by_default(env, capsys):
    rc = acli.main(["install", "--agents", "pi", "--force"])
    assert rc == 0
    data = json.loads((INS.state_root() / "install.json").read_text())
    assert data["mode"] == "evidence" and data["schema"] == 2
    home = pathlib.Path.home()
    assert (home / ".pi" / "agent" / "extensions" / "vacant.ts").is_file()
    assert not list(home.rglob("SKILL.md"))
    out = capsys.readouterr().out
    assert "Open your agent as usual" in out and len(out.strip().splitlines()) <= 10


def test_install_keeps_a_mode_the_person_set_and_skill_is_opt_in(env):
    _manifest({"agents": {}, "mode": "observe"})
    assert acli.main(["install", "--agents", "pi", "--force", "--skill"]) == 0
    data = json.loads((INS.state_root() / "install.json").read_text())
    assert data["mode"] == "observe"
    assert list(pathlib.Path.home().rglob("SKILL.md"))


def test_install_with_no_agent_found_says_so_and_skips_are_one_line(env, capsys, monkeypatch):
    from vacant_network.adapters import agents as AG
    monkeypatch.setattr(AG, "detect", lambda: {n: False for n in AG.AGENTS})
    assert acli.main(["install"]) == 1
    out = capsys.readouterr().out
    assert "no supported agent found" in out and "Open your agent as usual" not in out
    monkeypatch.setattr(AG, "detect", lambda: {n: n == "pi" for n in AG.AGENTS})
    assert acli.main(["install"]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert sum("not found on this machine" in ln for ln in lines) == 1
    assert len(lines) <= 4
