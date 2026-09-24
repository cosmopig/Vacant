"""四個 agent 的翻譯表（`vacant_network/adapters/agents.py`）＋`vacant hook` 的格式翻譯。

不需要 agent 的 binary：這裡驗的是「我們寫出去的設定合法、使用者的東西留著、
原生 payload 翻得對、回應格式是那個 agent 認得的」。真 binary 的量測在
`ops/intake/e2e_four_agents.py`（L-fake，四個 agent 都跑過，見裁決 §七）。
"""
from __future__ import annotations

import json
import pathlib
import tomllib

import pytest

from vacant_network.adapters import agents as A
from vacant_network.adapters import hook as H
from vacant_network.adapters import install as INS
from vacant_network.intake import contract as C


@pytest.fixture()
def fakehome(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vhome"))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.delenv("PI_CODING_AGENT_DIR", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    return home


def _seed_user_config(home: pathlib.Path) -> dict[pathlib.Path, bytes]:
    files = {
        home / ".claude" / "settings.json":
            b'{"permissions":{"allow":["Read"]},"hooks":{"Stop":[{"hooks":'
            b'[{"type":"command","command":"user-stop"}]}]}}',
        home / ".codex" / "config.toml":
            b'model = "m"\n\n[mcp_servers.docs]\ncommand = "docs"\n\n'
            b'[[hooks.Stop]]\n[[hooks.Stop.hooks]]\ntype = "command"\ncommand = "user-stop"\n',
        home / ".config" / "opencode" / "opencode.json": b'{"mcp":{"docs":{"type":"local"}}}',
        home / ".pi" / "agent" / "models.json": b'{"providers":{}}',
    }
    for p, b in files.items():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b)
    return files


def test_install_all_four_then_uninstall_restores_every_user_byte(fakehome):
    before = _seed_user_config(fakehome)
    m = INS.Manifest()
    for name, spec in A.AGENTS.items():
        spec.install(m, fakehome)
    m.save()
    # Claude: 使用者自己的 Stop hook 還在，我們的附加在後面
    cs = json.loads((fakehome / ".claude" / "settings.json").read_text())
    assert cs["hooks"]["Stop"][0]["hooks"][0]["command"] == "user-stop"
    assert INS.MARKER in json.dumps(cs["hooks"]["Stop"][1])
    assert cs["permissions"] == {"allow": ["Read"]}
    # Codex: 整份 TOML 合法、使用者的 MCP 與 Stop hook 還在、信任鍵的群組索引跳過使用者那一組
    cx = tomllib.loads((fakehome / ".codex" / "config.toml").read_text())
    assert cx["mcp_servers"]["docs"]["command"] == "docs"
    assert cx["hooks"]["Stop"][0]["hooks"][0]["command"] == "user-stop"
    keys = list(cx["hooks"]["state"])
    assert any(k.endswith(":stop:1:0") for k in keys)
    assert any(k.endswith(":pre_tool_use:0:0") for k in keys)
    # 自己的檔
    assert (fakehome / ".pi" / "agent" / "extensions" / "vacant.ts").is_file()
    assert (fakehome / ".config" / "opencode" / "plugin" / "vacant.js").is_file()
    for d in (".claude", ".codex", ".pi/agent", ".config/opencode"):
        assert list((fakehome / d).rglob("SKILL.md")), d
    # 解除安裝 ⇒ 使用者的檔逐位元回來、我們的檔不見
    m2 = INS.Manifest()
    for name in list(A.AGENTS):
        INS.uninstall(m2, name)
    m2.save()
    for p, b in before.items():
        assert p.read_bytes() == b, p
    assert not (fakehome / ".pi" / "agent" / "extensions" / "vacant.ts").exists()
    assert not list(fakehome.rglob("SKILL.md"))


def test_codex_hash_matches_the_measured_formula():
    """公式出自 agent-codex 對照 §3.3（對 `hooks/list.currentHash` 逐位元重現）。"""
    h = {"type": "command", "command": "x", "timeout": 30, "async": False}
    ident = {"event_name": "pre_tool_use", "hooks": [h], "matcher": "^Bash$"}
    import hashlib
    want = "sha256:" + hashlib.sha256(json.dumps(ident, sort_keys=True, separators=(",", ":"))
                                      .encode()).hexdigest()
    assert A.codex_hook_hash("PreToolUse", h, "^Bash$") == want


def test_codex_run_overrides_are_valid_toml_values():
    args = A.codex_run_overrides()
    assert args[:2] == ["--enable", "hooks"]
    for i, a in enumerate(args):
        if a == "-c":
            key, _, val = args[i + 1].partition("=")
            tomllib.loads(f"v = {val}")          # 每個 -c 的值都是合法 TOML
    state = [a for a in args if a.startswith("hooks.state=")][0]
    assert "/<session-flags>/config.toml:pre_tool_use:0:0" in state


def test_claude_run_settings_keep_hooks_alive_against_project_disable():
    s = A.claude_run_settings()
    assert s["disableAllHooks"] is False
    # 追緝的病歷要 PostToolUse(Failure)／SubagentStop／SessionEnd（DECISION_20260924_ACCOUNTABLE_TRACE）；
    # SubagentStart：背景子 agent 還在做時不驗收
    assert set(s["hooks"]) == {"PreToolUse", "PostToolUse", "PostToolUseFailure", "SubagentStart",
                               "SubagentStop", "UserPromptSubmit", "Stop", "SessionEnd"}


def test_claude_refuses_bare():
    with pytest.raises(ValueError):
        A.claude_build("p", pathlib.Path("."), extra=["--bare"])


def test_generated_js_embeds_a_runnable_hook_argv():
    for text in (A.pi_extension_text(), A.opencode_plugin_text()):
        assert "vacant_network" in text and '"hook"' in text and INS.MARKER in text


# ── vacant hook: 原生 payload ↔ 原生回應 ───────────────────────────────

def _contract(tmp_path, deny=("git push",)):
    proj = tmp_path / "p"
    (proj / ".vacant").mkdir(parents=True)
    raw = C.scaffold("t")
    raw["effects"]["deny_commands"] = list(deny)
    (proj / ".vacant" / "contract.json").write_text(json.dumps(raw))
    return proj


def test_claude_pretool_deny_uses_permission_decision(tmp_path, fakehome):
    proj = _contract(tmp_path)
    out, err, code = H.handle("claude", "PreToolUse", {
        "hook_event_name": "PreToolUse", "tool_name": "Bash",
        "tool_input": {"command": "git push origin main"}, "cwd": str(proj)})
    d = json.loads(out)
    assert code == 0 and d["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert d["hookSpecificOutput"]["permissionDecisionReason"]


def test_codex_pretool_deny_is_exit_2_with_nonempty_stderr(tmp_path, fakehome):
    proj = _contract(tmp_path)
    out, err, code = H.handle("codex", "PreToolUse", {
        "hook_event_name": "PreToolUse", "tool_name": "Bash",
        "tool_input": {"command": "git push"}, "cwd": str(proj)})
    assert code == 2 and err.strip()


def test_pi_and_opencode_get_our_json(tmp_path, fakehome):
    proj = _contract(tmp_path)
    for agent in ("pi", "opencode"):
        out, _, code = H.handle(agent, "pre_tool", {"tool": "bash",
                                                    "input": {"command": "git push"},
                                                    "cwd": str(proj)})
        assert json.loads(out) == {"action": "deny", "reason": json.loads(out)["reason"]}
        assert code == 0


def test_no_contract_is_a_fast_allow(tmp_path, fakehome):
    out, err, code = H.handle("claude", "PreToolUse", {"tool_name": "Bash",
                                                       "tool_input": {"command": "git push"},
                                                       "cwd": str(tmp_path)})
    assert (out, err, code) == ("", "", 0)


def test_apply_patch_paths_are_extracted():
    patch = "*** Begin Patch\n*** Update File: .vacant/contract.json\n@@\n-a\n+b\n*** End Patch"
    ev = H.normalize("codex", "PreToolUse", {"tool_name": "apply_patch",
                                             "tool_input": {"input": patch}, "cwd": "/w"})
    assert ev.paths == [".vacant/contract.json"]


def test_hook_main_never_crashes_the_agent(monkeypatch, capsys, fakehome):
    import io
    monkeypatch.setattr("sys.stdin", io.StringIO("{not json"))
    assert H.main(["claude", "PreToolUse"]) == 0


def test_per_run_hooks_are_not_doubled_when_the_persistent_install_is_present(fakehome,
                                                                            monkeypatch):
    """常駐安裝會自己載入；每一跑再注入一份 ⇒ 同一事件跑兩次（停止檢查兩遍、輪數算兩輪）。"""
    monkeypatch.delenv("OPENCODE_CONFIG_CONTENT", raising=False)
    ws = fakehome / "ws"
    ws.mkdir()
    # 沒裝 ⇒ 每一跑自己帶
    fresh = {n: A.AGENTS[n].build("p", ws) for n in A.AGENTS}
    try:
        assert "OPENCODE_CONFIG_CONTENT" in fresh["opencode"].env
        assert any(a.startswith("hooks.state=") for a in fresh["codex"].argv)
        pi_ext = fresh["pi"].argv[fresh["pi"].argv.index("-e") + 1]
        assert not pi_ext.startswith(str(fakehome))
    finally:
        for la in fresh.values():
            if la.cleanup:
                la.cleanup()
    # 裝了 ⇒ 不重複
    m = INS.Manifest()
    for spec in A.AGENTS.values():
        spec.install(m, fakehome)
    m.save()
    for n in A.AGENTS:
        assert A.persistent_hook_file(n) is not None, n
    oc = A.opencode_build("p", ws)
    assert "OPENCODE_CONFIG_CONTENT" not in oc.env and "installed" in oc.note
    cx = A.codex_build("p", ws)
    assert "--enable" in cx.argv and not any(a.startswith("hooks.") for a in cx.argv)
    pi = A.pi_build("p", ws)
    assert pi.argv[pi.argv.index("-e") + 1] == str(A.persistent_hook_file("pi"))
    cl = A.claude_build("p", ws)
    try:
        doc = json.loads(pathlib.Path(cl.argv[cl.argv.index("--settings") + 1]).read_text())
        assert doc == {"disableAllHooks": False}
    finally:
        if cl.cleanup:
            cl.cleanup()
    # 拆掉 ⇒ 又自己帶
    m2 = INS.Manifest()
    for n in list(A.AGENTS):
        INS.uninstall(m2, n)
    m2.save()
    assert all(A.persistent_hook_file(n) is None for n in A.AGENTS)


def test_opencode_merges_into_user_content_and_never_replaces_unparseable_content(
        fakehome, monkeypatch):
    user = {"provider": {"x": {"name": "x"}}, "plugin": ["file:///user/p.js"]}
    merged = json.loads(A.opencode_merge_content(json.dumps(user), "file:///v/vacant.js"))
    assert merged["provider"] == user["provider"]
    assert merged["plugin"] == ["file:///user/p.js", "file:///v/vacant.js"]
    assert A.opencode_merge_content('{"plugin": "not-a-list"}', "file:///v.js") is None
    jsonc = '{ // my provider\n "provider": {} }'
    assert A.opencode_merge_content(jsonc, "file:///v.js") is None
    monkeypatch.setenv("OPENCODE_CONFIG_CONTENT", jsonc)
    la = A.opencode_build("p", fakehome)
    assert "OPENCODE_CONFIG_CONTENT" not in la.env      # 使用者的值原封不動（由繼承的環境帶）
    assert "NOT injected" in la.note
    # `--dir` 永遠是絕對路徑（相對的會接在過期的 PWD 後面）
    rel = A.opencode_build("p", pathlib.Path("."))
    assert pathlib.Path(rel.argv[rel.argv.index("--dir") + 1]).is_absolute()
