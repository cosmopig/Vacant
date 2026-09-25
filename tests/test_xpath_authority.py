"""行使別的權威那條 pre-tool 規則：既要擋住已知的繞法，又要停止對「只是提到指令」的文字誤報。

對應 2026-09-25 對抗審查四項：
  1. `contract quick --replace --lock` 重寫並簽了契約（`_AUTHORITY_RE` 只擋 lock／init）。
  2. `python -m vacant_network.adapters.hook …` 派送掛鉤但沒被擋（只認 `vacant hook` 與 `-m vacant_network hook`）。
  3. `python -c '…subprocess.run([…,"-m","vacant_network.cli","hook",…])'`：list 形式的引數 token 之間沒有空白，
     正則靠的空白比對對不上。
  4. 誤報：正則在指令任何位置比對這些字，`git commit -m "… vacant hook …"`／`grep "vacant hook"`／
     heredoc 寫進檔案的內文，在每個專案（連沒有契約的）都被拒。

規則是**字串層**的（`hookpolicy` 誠實邊界 1）：抬高成本，不是擋死。判斷靠命令位置＋直譯器內聯碼。
"""
from __future__ import annotations

import json

import pytest

from vacant_network.adapters import hook
from vacant_network.adapters import hookpolicy as HP
from vacant_network.intake import contract as C, flow, keys


def _action(command: str, contract=None, *, cwd="/tmp/proj", tool="Bash") -> str:
    ev = HP.HookEvent(agent="claude", kind="pre_tool", tool=tool, command=command, cwd=cwd)
    return HP.decide_pre_tool(ev, contract).action


# ── 要拒的：vacant CLI／python -m 在命令位置行使別的權威 ──────────────────

DENY = [
    # 1. contract：唯讀之外一律拒（含將來會寫的子指令；quick --replace --lock 是重現的那一個）
    "vacant contract quick --replace --deliverable report.md --lock",
    "vacant contract lock",
    "vacant contract init --path .vacant/contract.json",
    "vacant contract quick --deliverable r.md --total amount",
    "vacant-network contract lock",
    # 2. python -m <派送模組>：adapters.hook 直接偽造掛鉤；其餘走子指令
    "python3 -m vacant_network.adapters.hook claude UserPromptSubmit",
    "python -m vacant_network.adapters.hook codex Stop",
    "python3 -m vacant_network approve",
    "python -m vacant_network hook claude Stop",
    "python3 -m vacant_network.cli review quality pass",
    "python3 -m vacant_network.intake.cli approve",
    "python3 -m vacant_network.trace.cli flag report.md:2 wrong",
    # 3. 直譯器內聯碼：list 形式的引數、`-c`/`-e`、餵給直譯器的 heredoc
    ('python3 -c \'import subprocess,sys; subprocess.run([sys.executable,"-m",'
     '"vacant_network.cli","hook","claude","UserPromptSubmit"], input="{}")\''),
    ("python3 -c 'from vacant_network.adapters import hook; "
     "hook.main([\"claude\",\"Stop\"])'"),
    "node -e 'require(\"child_process\").execFileSync(\"vacant\",[\"release\"])'",
    # 既有：頂層權威子指令、掛鉤、被遮蔽時改用的第二指令名
    "vacant review quality pass --reason ok",
    "vacant approve",
    "vacant release",
    "vacant withdraw",
    "vacant keys init",
    "vacant reverify",
    "vacant flag report.md:2 wrong",
    "vacant hook claude Stop",
    "vacant intake serve --contract .vacant/contract.json",
    "vacant-network review quality pass --reason ok",
    "vacant-network release",
    # 包在 wrapper／有前置 env 指派／完整路徑，命令位置照樣抓得到
    "sudo vacant release",
    "VACANT_HOME=/x vacant approve",
    "/home/user/.venv/bin/vacant release",
    "cat data.csv && vacant approve",
]

# ── 要放的：這些字只是別的指令的引數／樣式／檔案內容，或唯讀子指令 ────────
ALLOW = [
    # 4. 誤報：這些字出現在別的指令的引數／樣式／訊息裡
    'git commit -m "docs: explain when the vacant hook runs"',
    'grep -rn "vacant hook" docs/ README.md',
    "rg 'python -m vacant_network hook' .",
    "git log --oneline --grep 'vacant hook'",
    'echo "vacant review of the draft"',
    "cat > NOTES.md <<'EOF'\nThe vacant hook fires before every tool call.\nvacant release does the publish.\nEOF",
    # 唯讀／被允許的 vacant 子指令
    "vacant check",
    "vacant submit",
    "vacant contract show",
    "vacant contract validate",
    "vacant trace show",
    "vacant trace report",
    # python -m 但不是派送模組，或只是讀取（沒有權威詞）
    "python3 -c 'import vacant_network; print(vacant_network.__file__)'",
    "python3 -m vacant_network.experiment --help",
    # 一般開發指令
    "python3 analyze.py data/sales.csv > report.md",
    "pytest tests -q",
]


@pytest.mark.parametrize("cmd", DENY)
def test_authority_commands_are_denied(cmd):
    assert _action(cmd) == "deny", cmd


@pytest.mark.parametrize("cmd", ALLOW)
def test_mentions_and_readonly_commands_are_allowed(cmd):
    assert _action(cmd) == "allow", cmd


def test_deny_record_rule_is_vacant_authority():
    ev = HP.HookEvent("claude", "pre_tool", tool="Bash",
                      command="vacant contract quick --replace --lock", cwd="/tmp/proj")
    d = HP.decide_pre_tool(ev, None)
    assert d.action == "deny" and d.record["rule"] == "vacant_authority"


def test_hook_forging_gets_the_hook_specific_message():
    for cmd in ("python3 -m vacant_network.adapters.hook claude Stop",
                "python3 -c 'from vacant_network.adapters import hook; hook.main([])'"):
        d = HP.decide_pre_tool(
            HP.HookEvent("claude", "pre_tool", tool="Bash", command=cmd, cwd="/tmp/p"), None)
        assert d.action == "deny" and "called by the agent platform" in d.reason, cmd


# ── heredoc 內文的兩面：餵給直譯器 vs 寫進檔案 ────────────────────────────

def test_heredoc_fed_to_interpreter_is_scanned():
    cmd = ('python3 <<\'PY\'\nimport subprocess,sys\n'
           'subprocess.run([sys.executable,"-m","vacant_network.cli","approve"])\nPY')
    assert _action(cmd) == "deny"


def test_heredoc_written_to_a_file_passes_even_with_authority_words():
    cmd = ("cat > run.sh <<'SH'\n#!/bin/bash\nvacant release\nvacant approve\nSH")
    assert _action(cmd) == "allow"


# ── 有契約時（規則 1 的保護仍在），命令位置判斷不變 ──────────────────────

@pytest.fixture()
def proj(tmp_path, monkeypatch):
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("VACANT_WORK", raising=False)
    monkeypatch.delenv("VACANT_TRACE", raising=False)
    (tmp_path / "home").mkdir()
    keys.init_local()
    p = tmp_path / "proj"
    (p / ".vacant").mkdir(parents=True)
    (p / "data").mkdir()
    (p / "data" / "sales.csv").write_text("amount\n1\n")
    raw = C.scaffold("t-auth", deliverable=["out.txt"], destination="dir:published")
    raw["claims"] = [{"id": "has_out", "verifier": "text",
                      "params": {"path": "out.txt", "must_contain": ["^done$"]}}]
    raw["inputs"] = {"sales": {"path": "data/sales.csv"}}
    (p / ".vacant" / "contract.json").write_text(json.dumps(raw))
    flow.lock(p / ".vacant" / "contract.json")
    return p, C.load(p / ".vacant" / "contract.json")


def test_with_a_locked_contract_the_same_rule_holds(proj):
    p, c = proj
    assert _action("vacant contract quick --replace --lock", c, cwd=str(p)) == "deny"
    assert _action('grep "vacant hook" docs/', c, cwd=str(p)) == "allow"
    # 保護規則仍在：寫契約檔照樣拒（不是被權威規則擋，是被 protect_write）
    d = HP.decide_pre_tool(HP.HookEvent("claude", "pre_tool", tool="Bash",
                                        command="echo x > .vacant/contract.json",
                                        cwd=str(p)), c)
    assert d.action == "deny" and d.record["rule"] == "protect_write"


# ── 四個 agent 的 payload 形狀都路由到共用的 decide_pre_tool ──────────────

def _handle_action(agent: str, event: str, command, cwd: str) -> str:
    if agent in ("claude", "codex"):
        payload = {"session_id": "S", "cwd": cwd, "tool_name": "Bash",
                   "tool_use_id": "t", "tool_input": {"command": command}}
    else:
        payload = {"session_id": "S", "cwd": cwd, "tool": "bash",
                   "input": {"command": command}}
    out, err, code = hook.handle(agent, event, payload)
    if agent == "claude":
        if not out:
            return "allow"
        return json.loads(out).get("hookSpecificOutput", {}).get("permissionDecision", "allow")
    if agent == "codex":
        return "deny" if code == 2 else "allow"
    return json.loads(out).get("action", "allow") if out else "allow"


@pytest.mark.parametrize("agent,event", [
    ("claude", "PreToolUse"), ("codex", "PreToolUse"),
    ("opencode", "pre_tool"), ("pi", "pre_tool"),
])
def test_every_agent_shape_routes_to_the_shared_decision(agent, event, proj):
    p, _c = proj
    assert _handle_action(agent, event, "vacant approve", str(p)) == "deny"
    assert _handle_action(agent, event,
                          "python3 -m vacant_network.adapters.hook claude Stop", str(p)) == "deny"
    assert _handle_action(agent, event, 'grep "vacant hook" docs/', str(p)) == "allow"
    assert _handle_action(agent, event, "vacant check", str(p)) == "allow"


def test_codex_list_form_command_is_joined_and_denied(proj):
    """list 形式的引數（critic C1）：`_command_from` 併成一行字串再判斷。"""
    p, _c = proj
    payload = {"session_id": "S", "cwd": str(p), "tool_name": "Bash", "tool_use_id": "t",
               "tool_input": {"command": ["python3", "-c",
                                          'import subprocess,sys; subprocess.run('
                                          '[sys.executable,"-m","vacant_network.cli","hook",'
                                          '"claude","UserPromptSubmit"])']}}
    _out, _err, code = hook.handle("codex", "PreToolUse", payload)
    assert code == 2
