"""adapters 的共通件：掛鉤政策、可逆安裝、`vacant do` 的行程＋工作區層。

與任何一個 agent 都無關——四個 agent 的模組只做格式翻譯，判斷在這裡。
"""
from __future__ import annotations

import json
import sys

import pytest

from vacant_network.adapters import hookpolicy as HP
from vacant_network.adapters import install as INS
from vacant_network.adapters import run as RUN
from vacant_network.intake import contract as C, flow


@pytest.fixture()
def vhome(tmp_path, monkeypatch):
    h = tmp_path / "vhome"
    monkeypatch.setenv("VACANT_HOME", str(h))
    return h


def _proj(tmp_path, *, deny=None, inputs=None):
    proj = tmp_path / "proj"
    (proj / ".vacant").mkdir(parents=True)
    (proj / "data").mkdir()
    (proj / "data" / "facts.csv").write_text("amount\n1\n")
    raw = C.scaffold("t-hook", deliverable=["out.txt"], destination="dir:published")
    raw["claims"] = [{"id": "has_out", "verifier": "text",
                      "params": {"path": "out.txt", "must_contain": ["^done$"]}}]
    raw["inputs"] = inputs or {"facts": {"path": "data/facts.csv"}}
    raw["effects"]["deny_commands"] = deny or ["git push", "npm publish"]
    (proj / ".vacant" / "contract.json").write_text(json.dumps(raw))
    flow.lock(proj / ".vacant" / "contract.json")
    return proj, C.load(proj / ".vacant" / "contract.json")


# ── pre_tool policy ────────────────────────────────────────────────────

def test_reading_the_contract_is_allowed_writing_it_is_not(tmp_path, vhome):
    proj, c = _proj(tmp_path)
    cwd = str(proj)
    read = HP.HookEvent("claude", "pre_tool", tool="Bash",
                        command="cat .vacant/contract.json", cwd=cwd)
    assert HP.decide_pre_tool(read, c).action == "allow"
    write = HP.HookEvent("claude", "pre_tool", tool="Bash",
                         command="echo '{}' > .vacant/contract.json", cwd=cwd)
    assert HP.decide_pre_tool(write, c).action == "deny"
    edit = HP.HookEvent("claude", "pre_tool", tool="Edit",
                        paths=[str(proj / ".vacant" / "contract.json")], cwd=cwd)
    assert HP.decide_pre_tool(edit, c).action == "deny"


def test_pinned_inputs_and_vacant_state_are_protected(tmp_path, vhome):
    proj, c = _proj(tmp_path)
    ev = HP.HookEvent("pi", "pre_tool", tool="write", paths=["data/facts.csv"], cwd=str(proj))
    assert HP.decide_pre_tool(ev, c).action == "deny"
    keys = HP.HookEvent("codex", "pre_tool", tool="shell",
                        command=f"cat {vhome}/intake/keys/verifier/identity.key", cwd=str(proj))
    d = HP.decide_pre_tool(keys, c)
    assert d.action == "deny" and d.record["rule"] == "protect_keys"
    ordinary = HP.HookEvent("opencode", "pre_tool", tool="write", paths=["out.txt"],
                            cwd=str(proj))
    assert HP.decide_pre_tool(ordinary, c).action == "allow"


def test_contract_deny_commands(tmp_path, vhome):
    proj, c = _proj(tmp_path)
    ev = HP.HookEvent("claude", "pre_tool", tool="Bash", command="git push origin main",
                      cwd=str(proj))
    d = HP.decide_pre_tool(ev, c)
    assert d.action == "deny" and "effects.deny_commands" in d.reason


def test_no_contract_means_only_vacant_state_is_protected(tmp_path, vhome):
    ev = HP.HookEvent("claude", "pre_tool", tool="Bash", command="git push", cwd=str(tmp_path))
    assert HP.decide_pre_tool(ev, None).action == "allow"


# ── stop: feedback is bounded and KS-1 clean ──────────────────────────

def test_stop_feedback_rounds_are_bounded(tmp_path, vhome):
    proj, c = _proj(tmp_path)
    ev = HP.HookEvent("claude", "stop", cwd=str(proj), session_id="s1")
    seen = []
    for _ in range(5):
        d = HP.decide_stop(ev, c, check_fn=flow.check)
        seen.append(d.action)
    assert seen == ["continue", "continue", "continue", "allow", "allow"]
    fb = HP.decide_stop(HP.HookEvent("claude", "stop", cwd=str(proj), session_id="s2"), c,
                        check_fn=flow.check).reason
    assert "has_out" in fb
    from vacant_network.memory import assert_ks1_clean
    assert_ks1_clean(fb)


def test_stop_allows_when_the_contract_passes(tmp_path, vhome):
    proj, c = _proj(tmp_path)
    (proj / "out.txt").write_text("done\n")
    ev = HP.HookEvent("pi", "stop", cwd=str(proj), session_id="s3")
    assert HP.decide_stop(ev, c, check_fn=flow.check).action == "allow"


def test_hidden_claims_give_status_without_detail(tmp_path, vhome):
    proj, _ = _proj(tmp_path)
    cp = proj / ".vacant" / "contract.json"
    raw = json.loads(cp.read_text())
    raw["claims"][0]["hidden"] = True
    cp.write_text(json.dumps(raw))
    c = C.load(cp)
    res = flow.check(c, proj)
    fb = HP.feedback_text(res, c)
    assert "has_out: FAIL" in fb and "must_contain" not in fb and "does not contain" not in fb


# ── installer: key-level, reversible, keeps user edits ────────────────

def test_json_hooks_install_uninstall_keeps_user_edits(tmp_path, vhome):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"permissions": {"allow": ["Read"]},
                                    "hooks": {"Stop": [{"hooks": [{"type": "command",
                                                                   "command": "user-hook"}]}]}}))
    m = INS.Manifest()
    ours = {"hooks": [{"type": "command", "command": f"vacant hook claude stop # {INS.MARKER}"}]}
    INS.add_json_hooks(m, "claude", settings, {"Stop": [ours], "PreToolUse": [ours]})
    INS.add_json_hooks(m, "claude", settings, {"Stop": [ours], "PreToolUse": [ours]})  # 冪等
    m.save()
    data = json.loads(settings.read_text())
    assert len(data["hooks"]["Stop"]) == 2 and len(data["hooks"]["PreToolUse"]) == 1
    # 使用者在安裝之後自己加的東西
    data["env"] = {"FOO": "1"}
    data["hooks"]["Stop"].append({"hooks": [{"type": "command", "command": "later-hook"}]})
    settings.write_text(json.dumps(data))
    out = INS.uninstall(INS.Manifest(), "claude")
    assert out and all("error" not in o["result"] for o in out)
    after = json.loads(settings.read_text())
    assert after["env"] == {"FOO": "1"}
    assert [h["hooks"][0]["command"] for h in after["hooks"]["Stop"]] == ["user-hook",
                                                                          "later-hook"]
    assert "PreToolUse" not in after["hooks"]


def test_file_op_keeps_modified_files(tmp_path, vhome):
    m = INS.Manifest()
    p = tmp_path / "skills" / "vacant" / "SKILL.md"
    INS.put_file(m, "pi", p, "ours\n")
    p.write_text("user changed it\n")
    res = INS.uninstall(m, "pi")
    assert res[0]["result"].startswith("kept") and p.read_text() == "user changed it\n"


def test_toml_block_is_validated_and_removable(tmp_path, vhome):
    cfg = tmp_path / "config.toml"
    cfg.write_text('model = "x"\n[mcp_servers.docs]\ncommand = "docs"\n')
    m = INS.Manifest()
    INS.add_toml_block(m, "codex", cfg, "[features]\nhooks = true\n")
    assert "hooks = true" in cfg.read_text()
    with pytest.raises(Exception):
        INS.add_toml_block(m, "codex", cfg, "[mcp_servers.docs]\ncommand = \"dup\"\n")
    INS.uninstall(m, "codex")
    assert cfg.read_text() == 'model = "x"\n[mcp_servers.docs]\ncommand = "docs"\n'


# ── vacant do: process + workspace, with a stand-in agent ─────────────

def _fake_agent(script: str) -> RUN.Launch:
    return RUN.Launch(argv=[sys.executable, "-c", script])


def test_do_runs_in_an_isolated_workspace_and_submits(tmp_path, vhome):
    proj, c = _proj(tmp_path)
    task = flow.open_task(c)
    res = RUN.do(task, agent="fake", prompt="write out.txt",
                 build=lambda p, ws: _fake_agent("open('out.txt','w').write('done\\n')"))
    assert res["outcome"] == "accept"
    assert not (proj / "out.txt").exists()            # 原專案不動
    assert res["attempts"][0]["workspace_escape"] is False
    assert flow.release(task)["released"] is True
    assert (proj / "published" / "t-hook" / "out.txt").read_text() == "done\n"


def test_do_detects_writes_to_the_original_project(tmp_path, vhome):
    proj, c = _proj(tmp_path)
    task = flow.open_task(c)
    esc = f"open({str(proj / 'escaped.txt')!r},'w').write('x')"
    res = RUN.do(task, agent="fake", prompt="p", build=lambda p, ws: _fake_agent(esc))
    assert res["attempts"][0]["workspace_escape"] is True
    evs = [e for e in task.ledger.events() if e["type"] == "attempt_ended"]
    assert evs[-1]["workspace_escape"] is True


def test_do_agent_that_claims_success_but_is_wrong_is_rejected(tmp_path, vhome):
    proj, c = _proj(tmp_path)
    task = flow.open_task(c)
    res = RUN.do(task, agent="fake", prompt="p", build=lambda p, ws: _fake_agent(
        "open('out.txt','w').write('almost\\n'); print('Done! All requirements met.')"))
    assert res["outcome"] == "reject"
    assert res["attempts"][0]["rc"] == 0              # agent 自己說成功
    assert flow.release(task)["released"] is False


def test_do_feedback_attempts(tmp_path, vhome):
    proj, c = _proj(tmp_path)
    task = flow.open_task(c)
    seen_prompts = []

    def build(prompt, ws):
        seen_prompts.append(prompt)
        body = "done" if "has_out" in prompt else "nope"
        return _fake_agent(f"open('out.txt','w').write({body!r} + '\\n')")
    res = RUN.do(task, agent="fake", prompt="p", build=build, attempts=2,
                 feedback=lambda r: HP.feedback_text(r, c))
    assert [a["outcome"] for a in res["attempts"]] == ["reject", "accept"]
    assert seen_prompts[0] == "p" and "has_out" in seen_prompts[1]


def test_do_spawn_failure_is_void_not_dropped(tmp_path, vhome):
    proj, c = _proj(tmp_path)
    task = flow.open_task(c)
    res = RUN.do(task, agent="ghost", prompt="p",
                 build=lambda p, ws: RUN.Launch(argv=["/nonexistent/agent-binary"]))
    assert res["void"] is True
    assert flow.status(task)["state"] == "void"


def test_uninstall_restores_original_bytes_when_user_changed_nothing(tmp_path, vhome):
    settings = tmp_path / "settings.json"
    original = '{"permissions":{"allow":["Read"]},"hooks":{}}'   # 非標準排版、沒有結尾換行
    settings.write_text(original)
    m = INS.Manifest()
    ours = {"hooks": [{"type": "command", "command": f"x # {INS.MARKER}"}]}
    INS.add_json_hooks(m, "claude", settings, {"Stop": [ours]})
    assert settings.read_text() != original
    INS.uninstall(m, "claude")
    assert settings.read_text() == original


def test_ledger_write_before_open_task_still_registers_the_signer(tmp_path, vhome):
    """2026-09-24 端到端抓到的競態：掛鉤先寫帳本（建了鑰匙卻沒登記），收件端拒絕放行。"""
    from vacant_network.intake import keys
    from vacant_network.intake.ledger import Ledger
    Ledger("race-task").append("hook_event", {"k": 1})
    t = keys.Trust.load()
    pub = keys.pub_hex(keys.load_or_create("verifier"))
    assert t.name_of("verifier", pub) is not None
    ok, why = Ledger("race-task").verify(t)
    assert ok, why
