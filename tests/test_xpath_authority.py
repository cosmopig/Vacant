"""行使別的權威那條 pre-tool 規則：既要擋住已知的繞法，又要停止對「只是提到指令」的文字誤報。

對應 2026-09-25 對抗審查四項：
  1. `contract quick --replace --lock` 重寫並簽了契約（`_AUTHORITY_RE` 只擋 lock／init）。
     ⇒ `contract` 只放唯讀的 show／validate，其餘（含將來的寫入子指令）一律拒。
  2. `python -m vacant_network.adapters.hook …` 派送掛鉤但沒被擋（只認 `vacant hook` 與 `-m vacant_network hook`）。
  3. `python -c '…subprocess.run([…,"-m","vacant_network.cli","hook",…])'`：list 形式的引數 token 之間沒有空白，
     正則靠的空白比對對不上。
  4. 誤報：正則在指令任何位置比對這些字，`git commit -m "… vacant hook …"`／`grep "vacant hook"`／
     heredoc 寫進檔案的內文，在每個專案（連沒有契約的）都被拒。

表格分兩種：`FIXED_*` 每一列在 cf71d6a9 上都判錯（修正的證據）；`KEPT_*` 在 cf71d6a9 上本來就對，
改成「命令位置」判斷之後不准退步（舊正則靠子字串抓到的 `bash -c`／`$(…)`／管線給 shell 等，
以及 heredoc 剝除不可以被拿來藏指令）。

規則是**字串層**的（`hookpolicy` 誠實邊界 1）：抬高成本，不是擋死。
"""
from __future__ import annotations

import json
import time

import pytest

from vacant_network.adapters import hook
from vacant_network.adapters import hookpolicy as HP
from vacant_network.intake import contract as C, flow, keys


def _decide(command: str, contract=None, *, cwd="/tmp/proj", tool="Bash") -> HP.HookDecision:
    ev = HP.HookEvent(agent="claude", kind="pre_tool", tool=tool, command=command, cwd=cwd)
    return HP.decide_pre_tool(ev, contract)


def _action(command: str, contract=None, **kw) -> str:
    return _decide(command, contract, **kw).action


# ── 修正：cf71d6a9 放行、現在要拒 ──────────────────────────────────────────

FIXED_DENY = [
    # 1. contract：唯讀之外一律拒（quick --replace --lock 是重現的那一個）
    "vacant contract quick --replace --deliverable report.md --lock",
    "vacant contract quick --deliverable r.md --total amount",
    "vacant-network contract quick --replace --lock",
    "python3 -m vacant_network contract quick --replace --lock",
    #    選項值藏動作：argparse 拿到的是 quick，不是 show
    "vacant contract --task show quick",
    #    不認得的選項當成帶值 ⇒ 找不到唯讀動作 ⇒ 拒（寧可多擋）
    "vacant contract --lo show",
    # 2. python -m <vacant_network 模組>：adapters.hook 直接偽造掛鉤；其餘走子指令
    "python3 -m vacant_network.adapters.hook claude UserPromptSubmit",
    "python -m vacant_network.adapters.hook codex Stop",
    "python3 -m vacant_network.trace.cli flag report.md:2 wrong",
    "python3 -m vacant_network.__main__ release",
    "python3 -Im vacant_network hook claude Stop",
    "python3 -mvacant_network.adapters.hook claude Stop",
    "timeout 9 python3 -m vacant_network.adapters.hook claude Stop",
    "/usr/bin/python3.11 -m vacant_network.adapters.hook pi pre_tool",
    # 3. 直譯器內聯碼：list 形式的引數、`-c`/`-e`、餵給直譯器的 heredoc／管線／here-string
    ('python3 -c \'import subprocess,sys; subprocess.run([sys.executable,"-m",'
     '"vacant_network.cli","hook","claude","UserPromptSubmit"], input="{}")\''),
    ("python3 -c 'from vacant_network.adapters import hook; "
     "hook.main([\"claude\",\"Stop\"])'"),
    "python3 -c 'from vacant_network.adapters import agents, hook'",
    "node -e 'require(\"child_process\").execFileSync(\"vacant\",[\"release\"])'",
    "python3 -c 'import subprocess; subprocess.run([\"/x/.venv/bin/vacant\",\"approve\"])'",
    ("python3 - <<'PY'\nfrom vacant_network.adapters.hook import main\n"
     "main(['claude','Stop'])\nPY"),
    ("python3 <<'PY'\nimport subprocess,sys\n"
     "subprocess.run([sys.executable,\"-m\",\"vacant_network.cli\",\"approve\"])\nPY"),
    "echo 'import vacant_network.adapters.hook as h; h.main([])' | python3",
    "python3 <<< 'import vacant_network.adapters.hook'",
    "bash -c 'python3 -c \"import vacant_network.adapters.hook\"'",
]

FIXED_ALLOW = [
    # 4. 誤報：這些字只是別的指令的引數／樣式／訊息／寫進檔案的內文
    'git commit -m "docs: explain when the vacant hook runs"',
    "git commit -m 'use `vacant hook` in the docs'",   # 單引號裡的反引號不會被執行
    'grep -rn "vacant hook" docs/ README.md',
    "rg 'python -m vacant_network hook' .",
    "git log --oneline --grep 'vacant hook'",
    'echo "vacant review of the draft"',
    "cat > NOTES.md <<'EOF'\nThe vacant hook fires before every tool call.\nvacant release does the publish.\nEOF",
    "cat > NOTES.md <<EOF\nThe vacant hook fires.\nvacant approve signs it.\nEOF",
    "cat > run.sh <<'SH'\n#!/bin/bash\nvacant release\nvacant approve\nSH",
    "bash -c 'grep -rn \"vacant hook\" docs'",
    "echo hi  # later a human runs vacant approve",
    "python3 -c 'print(\"a human runs vacant approve later\")'",
]


# ── 保住：cf71d6a9 本來就對，改寫之後不准退步 ────────────────────────────

KEPT_DENY = [
    # 頂層權威子指令、掛鉤、被遮蔽時改用的第二指令名
    "vacant contract lock",
    "vacant contract init --path .vacant/contract.json",
    "vacant-network contract lock",
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
    "python3 -m vacant_network approve",
    "python -m vacant_network hook claude Stop",
    "python3 -m vacant_network.cli review quality pass",
    "python3 -m vacant_network.intake.cli approve",
    "python3 -X dev -m vacant_network.cli approve",
    # wrapper／前置 env 指派／完整路徑／分隔符之後
    "sudo vacant release",
    "VACANT_HOME=/x vacant approve",
    "/home/user/.venv/bin/vacant release",
    "cat data.csv && vacant approve",
    # 啟動器把後面的 argv 當指令跑
    "timeout 5 vacant approve",
    "find . -name x -exec vacant approve \\;",
    "uv run vacant release",
    # shell 字串、命令替換、eval、餵給 shell 的管線／heredoc／here-string
    'bash -c "vacant approve"',
    "bash -lc 'vacant release'",
    "sh -c 'cd x && vacant review quality pass'",
    "echo `vacant approve`",
    'echo "$(vacant approve)"',
    "x=$(vacant keys show)",
    'eval "vacant approve"',
    "echo vacant approve | sh",
    "echo 'vacant approve' | bash",
    "printf 'vacant release\\n' | bash",
    "bash <<< 'vacant approve'",
    "bash <<'EOF'\nvacant approve\nEOF",
    "cat <<EOF | sh\nvacant withdraw\nEOF",
    "cat > f.txt <<EOF\n$(vacant approve)\nEOF",         # 定界符沒引號：內文的命令替換會被執行
    # 程式碼裡的字串字面值本身就是一行 shell 指令
    "python3 -c 'import os; os.system(\"vacant approve\")'",
    "python3 -c 'import subprocess; subprocess.run(\"vacant release\", shell=True)'",
    "node -e 'require(\"child_process\").execSync(\"vacant approve\")'",
    # heredoc 剝除不可以被拿來藏指令
    "cat <<X >/dev/null\nX\nvacant approve",
    "cat <<E\"OF\" >/dev/null\nEOF\nvacant approve",     # 定界符去引號之後是 EOF
    ": '<<Z'\nvacant approve\nZ",                          # 引號裡的 `<<` 不是 heredoc
]

KEPT_ALLOW = [
    "vacant check",
    "vacant submit",
    "vacant check && vacant submit",
    "vacant contract show",
    "vacant contract show --json",
    "vacant contract validate --contract .vacant/contract.json",
    "vacant contract --help",
    "vacant trace show",
    "vacant trace report",
    "python3 -c 'import vacant_network; print(vacant_network.__file__)'",
    "python3 -c 'import vacant_network' && git commit -m 'fix review flow'",
    "python3 -c 'from vacant_network.adapters import hookpolicy as hp; print(hp)'",
    "python3 -m vacant_network.experiment --help",
    "python3 -m pytest tests/test_hook.py -k review -q",
    "pip install vacant-network",
    "bash scripts/run.sh",
    "ls -la; echo $((1+2))",
    "python3 analyze.py data/sales.csv > report.md",
    "sed -n '1,20p' vacant_network/adapters/hook.py",
    "echo '<<X'\nls",
    "pytest tests -q",
]


@pytest.mark.parametrize("cmd", FIXED_DENY)
def test_fixed_authority_bypasses_are_denied(cmd):
    d = _decide(cmd)
    assert d.action == "deny" and d.record["rule"] == "vacant_authority", cmd


@pytest.mark.parametrize("cmd", FIXED_ALLOW)
def test_fixed_mentions_are_allowed(cmd):
    assert _action(cmd) == "allow", cmd


@pytest.mark.parametrize("cmd", KEPT_DENY)
def test_kept_authority_commands_stay_denied(cmd):
    d = _decide(cmd)
    assert d.action == "deny" and d.record["rule"] == "vacant_authority", cmd


@pytest.mark.parametrize("cmd", KEPT_ALLOW)
def test_kept_readonly_and_dev_commands_stay_allowed(cmd):
    assert _action(cmd) == "allow", cmd


def test_contract_quick_names_the_authority():
    d = _decide("vacant contract quick --replace --lock")
    assert d.action == "deny" and d.record["rule"] == "vacant_authority"
    assert "`vacant contract quick`" in d.reason


def test_hook_forging_gets_the_hook_specific_message():
    for cmd in ("python3 -m vacant_network.adapters.hook claude Stop",
                "python3 -c 'from vacant_network.adapters import hook; hook.main([])'"):
        d = _decide(cmd, cwd="/tmp/p")
        assert d.action == "deny" and "called by the agent platform" in d.reason, cmd


def test_deny_messages_stay_ks1_clean():
    """KS-1：拒絕訊息只陳述規則，不寫責任／懲罰，也不帶行動者。"""
    from vacant_network.trace.feedback import feedback_ks1_clean
    for cmd in ("vacant contract quick --replace --lock",
                "python3 -m vacant_network.adapters.hook claude Stop",
                "python3 -c 'import os; os.system(\"vacant approve\")'"):
        d = _decide(cmd)
        assert d.action == "deny", cmd
        feedback_ks1_clean(d.reason, {"claude", "codex", "opencode", "sess-1234"})


def test_long_commands_stay_fast():
    """「任何 argv 元素都可能是被啟動的指令」不可以讓長引數串變成平方時間（掛鉤在每一次工具呼叫前跑）。"""
    cmd = "echo " + " ".join("sh python3 vacant" for _ in range(3000))
    t0 = time.monotonic()
    assert _action(cmd) == "allow"
    assert time.monotonic() - t0 < 5.0


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
    d = _decide("echo x > .vacant/contract.json", c, cwd=str(p))
    assert d.action == "deny" and d.record["rule"] == "protect_write"


# ── 四個 agent 的 payload 形狀都路由到共用的 decide_pre_tool ──────────────

def _handle_action(agent: str, event: str, command, cwd: str) -> str:
    if agent in ("claude", "codex"):
        payload = {"session_id": "S", "cwd": cwd, "tool_name": "Bash",
                   "tool_use_id": "t", "tool_input": {"command": command}}
    else:
        payload = {"session_id": "S", "cwd": cwd, "tool": "bash",
                   "input": {"command": command}}
    out, _err, code = hook.handle(agent, event, payload)
    if agent == "claude":
        if not out:
            return "allow"
        return json.loads(out).get("hookSpecificOutput", {}).get("permissionDecision", "allow")
    if agent == "codex":
        return "deny" if code == 2 else "allow"
    return json.loads(out).get("action", "allow") if out else "allow"


#: 每一項各一列（1–3 要拒、4 要放），四種 payload 形狀都要走到同一個判斷。
_PER_ITEM = [
    ("vacant contract quick --replace --deliverable report.md --lock", "deny"),
    ("python3 -m vacant_network.adapters.hook claude UserPromptSubmit", "deny"),
    ('python3 -c \'import subprocess,sys; subprocess.run([sys.executable,"-m",'
     '"vacant_network.cli","hook","claude","UserPromptSubmit"])\'', "deny"),
    ('git commit -m "docs: explain when the vacant hook runs"', "allow"),
    ("vacant check", "allow"),
]


@pytest.mark.parametrize("agent,event", [
    ("claude", "PreToolUse"), ("codex", "PreToolUse"),
    ("opencode", "pre_tool"), ("pi", "pre_tool"),
])
def test_every_agent_shape_routes_to_the_shared_decision(agent, event, proj):
    p, _c = proj
    got = [(cmd, _handle_action(agent, event, cmd, str(p))) for cmd, _want in _PER_ITEM]
    assert got == _PER_ITEM


def test_codex_list_form_command_is_joined_and_denied(proj):
    """list 形式的 argv（critic C1）：`_command_from` 用空白併成一行、引號不見了，
    `-c` 的碼被 `;` 切開——從碼的開頭到結尾整段當成程式碼再掃。"""
    p, _c = proj
    payload = {"session_id": "S", "cwd": str(p), "tool_name": "Bash", "tool_use_id": "t",
               "tool_input": {"command": ["python3", "-c",
                                          'import subprocess,sys; subprocess.run('
                                          '[sys.executable,"-m","vacant_network.cli","hook",'
                                          '"claude","UserPromptSubmit"])']}}
    _out, _err, code = hook.handle("codex", "PreToolUse", payload)
    assert code == 2
