"""agents — 四個 agent 各自的**翻譯表**：怎麼找、怎麼 headless 跑、掛鉤裝在哪、技能放哪。

這支在架構裡承重什麼：`adapters/__init__.py` 說共通的是什麼；這裡寫**不共通的那一小撮**。
判斷（`hookpolicy.py`）與收件（`intake/`）都不在這裡——這裡只有格式與路徑。

每一格的證據等級寫在旁邊（技能那一欄：放對位置是 [DOC]；**有沒有真的被列給模型**看
`ops/intake/evidence_20260924/SUMMARY.md` 的「skill listed」欄——那才是量到的）：
- [RUN] ＝ 2026-09-24 在本機用真 binary ＋ 假模型（`ops/intake/mock_model.py`）跑過；
- [DOC] ＝ 官方文件；[SRC] ＝ 讀過 agent 原始碼／型別宣告；[REPO] ＝ 本 repo 既有實測紀錄。

| agent | headless | 每一跑加掛鉤（不動使用者設定） | 常駐安裝（`vacant install`） | 技能 |
|---|---|---|---|---|
| Claude Code | `claude -p … --output-format json` [RUN] | `--settings <檔>`（**只認最後一個**；帶 `disableAllHooks:false`，旗標層勝過專案／本機層）[RUN] | `$CLAUDE_CONFIG_DIR`（預設 `~/.claude`）`/settings.json` 的 `hooks.<Event>[]` 附加帶標記項目 [DOC] | `…/skills/vacant/SKILL.md` [DOC] |
| Codex | `codex exec --json -C <ws> -s workspace-write --skip-git-repo-check …` [RUN] | `-c hooks.<Event>=…`＋`-c hooks.state=…`（信任雜湊自己算）[RUN] | `~/.codex/config.toml` 尾端附加帶標記的掛鉤＋信任區塊 [RUN] | `~/.codex/skills/vacant/SKILL.md` [DOC] |
| OpenCode | `opencode run --format json --dir <絕對路徑> …` [RUN] | `OPENCODE_CONFIG_CONTENT` 併入 `plugin:["file://…/vacant.js"]`（深合併；**不用** `OPENCODE_CONFIG_DIR`）[RUN] | `~/.config/opencode/plugin/vacant.js` [RUN] | `~/.config/opencode/skill/vacant/SKILL.md` [DOC] |
| pi | `pi -p --mode json …` [RUN] | `-e <extension.ts>`／`--skill <dir>` [RUN: `pi --help`] | `~/.pi/agent/extensions/vacant.ts`（自動載入）[RUN] | `~/.pi/agent/skills/vacant/SKILL.md` [DOC] |

⚠ 常駐安裝（`settings.json`）**沒有** `disableAllHooks:false` 守衛：在 `bypassPermissions`
模式下，agent 寫一份 `.claude/settings.local.json {"disableAllHooks":true}` 就能讓互動工作階段
的掛鉤全部停火（agent-claude 對照 T2_tamper_plain）。每一跑的 `--settings` 有那道守衛。
（`ConfigChange` 掛鉤擋得下那次修改——量過，**但這裡沒有實作**。）

⚠ **`--bare`（Claude Code）會關掉所有掛鉤，含 `--settings` 帶進去的**（agent-claude 對照 §2.4）。
`vacant do claude` 拒絕 `--bare`；互動使用者自己打 `--bare` 就是沒有掛鉤——那一次仍然要
經過收件口才能進目的端，只是少了交件前的回饋。
"""
from __future__ import annotations

import dataclasses
import json
import os
import pathlib
import shutil
import sys
import tempfile
from importlib import resources
from typing import Any, Callable

from . import install as INS
from .run import Launch

MARK = INS.MARKER


def hook_argv(agent: str, event: str) -> list[str]:
    """掛鉤要執行的指令。用 `sys.executable -m` ⇒ 不依賴 PATH 上的 `vacant`
    （PyPI 另一個 `vacant` 套件會蓋掉那支指令，README 開頭那一節）。"""
    return [sys.executable, "-m", "vacant_network", "hook", agent, event]


def hook_command(agent: str, event: str) -> str:
    import shlex
    return shlex.join(hook_argv(agent, event)) + f"  # {MARK}"


def skill_text() -> str:
    return resources.files("vacant_network.adapters").joinpath("assets/SKILL.md").read_text(
        encoding="utf-8")


def which(names: tuple[str, ...]) -> str | None:
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    return None


def _marked(p: pathlib.Path) -> bool:
    try:
        return p.is_file() and MARK in p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def persistent_hook_file(agent: str, home: pathlib.Path | None = None) -> pathlib.Path | None:
    """`vacant install` 裝過的常駐掛鉤檔（還在、還帶標記）⇒ 回它的路徑，否則 `None`。

    每一跑的注入要先看這個：常駐的那份會**自己載入**，再注入一份 ⇒ 同一個事件跑兩次
    （pi 兩個不同檔、OpenCode 兩個外掛、Codex 兩個設定層都是加法的）——
    停止檢查跑兩遍、回饋送兩則、輪數一次算兩輪。
    """
    h = home or pathlib.Path.home()
    cand = {"claude": claude_dir(h) / "settings.json",
            "pi": pi_dir(h) / "extensions" / "vacant.ts",
            "opencode": opencode_dir(h) / "plugin" / "vacant.js",
            "codex": codex_home(h) / "config.toml"}.get(agent)
    return cand if cand is not None and _marked(cand) else None


# ── Claude Code ───────────────────────────────────────────────────────

def claude_dir(home: pathlib.Path) -> pathlib.Path:
    """Claude Code 讀 `$CLAUDE_CONFIG_DIR`，沒設才是 `~/.claude`（agent-claude 對照 §2.1）。"""
    x = os.environ.get("CLAUDE_CONFIG_DIR")
    return pathlib.Path(x).expanduser() if x else home / ".claude"


def claude_hooks_doc(*, include_session_end: bool = True) -> dict[str, Any]:
    def entry(ev: str, matcher: str | None, timeout: int) -> dict[str, Any]:
        e: dict[str, Any] = {"hooks": [{"type": "command", "command": hook_command("claude", ev),
                                        "timeout": timeout}]}
        if matcher:
            e["matcher"] = matcher
        return e
    # PostToolUse／PostToolUseFailure／SubagentStop：可究責追緝的病歷（trace/capture.py）——
    # 每一步寫了什麼、輸出是什麼、子 agent 的逐字稿（DECISION_20260924_ACCOUNTABLE_TRACE）
    hooks = {"PreToolUse": [entry("PreToolUse", "*", 30)],
             "PostToolUse": [entry("PostToolUse", "*", 30)],
             "PostToolUseFailure": [entry("PostToolUseFailure", "*", 30)],
             "SubagentStop": [entry("SubagentStop", None, 30)],
             "UserPromptSubmit": [entry("UserPromptSubmit", None, 30)],
             "Stop": [entry("Stop", None, 600)]}
    if include_session_end:
        hooks["SessionEnd"] = [entry("SessionEnd", None, 10)]
    return hooks


def _claude_user_disabled_hooks() -> bool:
    try:
        doc = json.loads((claude_dir(pathlib.Path.home()) / "settings.json").read_text())
        return isinstance(doc, dict) and doc.get("disableAllHooks") is True
    except (OSError, ValueError):
        return False


def claude_run_settings(*, with_hooks: bool = True,
                        force_enable: bool = True) -> dict[str, Any]:
    """每一跑的 `--settings`：掛鉤＋明示 `disableAllHooks:false`（旗標層勝過專案／本機層，
    agent 在工作中改 `.claude/settings.local.json` 關掉掛鉤的那一招因此無效——
    agent-claude 對照 `T2_tamper_explicitfalse`）。常駐安裝還在時只帶守衛、不帶掛鉤
    （掛鉤由使用者層那一份提供，不重複）。"""
    doc: dict[str, Any] = {"disableAllHooks": False} if force_enable else {}
    if with_hooks:
        # SessionEnd 也要：追緝在那一刻封存逐字稿、收尾病歷（交件由 `VACANT_HOOK_NO_SUBMIT` 擋掉，
        # `vacant do` 自己交）
        doc["hooks"] = claude_hooks_doc(include_session_end=True)
    return doc


def claude_build(prompt: str, ws: pathlib.Path, *, hooks: bool = True,
                 extra: list[str] | None = None) -> Launch:
    if extra and "--bare" in extra:
        raise ValueError("--bare disables every hook (including Vacant's); refusing")
    argv = [which(("claude",)) or "claude", "-p", prompt, "--output-format", "json",
            "--permission-mode", "acceptEdits", "--allowedTools", "Bash"]
    cleanup: Callable[[], None] | None = None
    if hooks:
        # 使用者自己在 settings.json 設了 `disableAllHooks: true` ⇒ 尊重它（不替他把
        # 他自己的掛鉤重新打開）；代價是這一跑沒有 Vacant 的掛鉤，收件口照樣把關。
        user_off = _claude_user_disabled_hooks()
        fd, path = tempfile.mkstemp(prefix="vacant-claude-", suffix=".json")
        with os.fdopen(fd, "w") as f:
            json.dump(claude_run_settings(
                with_hooks=persistent_hook_file("claude") is None and not user_off,
                force_enable=not user_off), f)
        argv += ["--settings", path]

        def cleanup(p: str = path) -> None:
            if os.path.exists(p):
                os.unlink(p)
    note = "claude -p"
    if hooks and _claude_user_disabled_hooks():
        note += " (hooks NOT injected: the user's settings.json sets disableAllHooks)"
    return Launch(argv=argv + list(extra or []),
                  env={"VACANT_HOOK_NO_SUBMIT": "1"}, note=note, cleanup=cleanup)


def claude_install(m: INS.Manifest, home: pathlib.Path) -> list[dict[str, Any]]:
    d = claude_dir(home)
    ops = [INS.add_json_hooks(m, "claude", d / "settings.json", claude_hooks_doc())]
    ops.append(INS.put_file(m, "claude", d / "skills" / "vacant" / "SKILL.md", skill_text()))
    return ops


# ── pi ────────────────────────────────────────────────────────────────

#: pi extension：把 pi 的事件轉給 `vacant hook pi …`，讀回 `{"action","reason"}`。
#: 事件名與回傳型別讀自 pi 0.87.1 的 `dist/core/extensions/types.d.ts` [SRC]：
#:   `tool_call` → `{block, reason}`；`agent_before_settle` → `{entries, continue}`
#:   （一次延續；`custom_message` 草稿會成為下一則訊息）；`session_shutdown`。
PI_EXTENSION = r"""// Vacant (vacant-intake) — generated by `vacant install`; remove with `vacant uninstall`.
// Forwards pi events to `vacant hook pi <event>` and applies the decision it prints.
import { spawn } from "node:child_process";

const ARGV = %(argv)s;
const TIMEOUT = { prompt: 30000, pre_tool: 30000, post_tool: 30000, stop: %(timeout_ms)d, session_end: 30000 };

// Asynchronous on purpose: a stop check can take minutes, and spawnSync would freeze
// pi's TUI and streaming for that long. Every handler below is awaited by pi.
function ask(event, payload) {
  return new Promise((resolve) => {
    let out = "";
    let done = false;
    const finish = (v) => { if (!done) { done = true; resolve(v); } };
    try {
      const child = spawn(ARGV[0], [...ARGV.slice(1), event], { stdio: ["pipe", "pipe", "ignore"] });
      const timer = setTimeout(() => { try { child.kill("SIGKILL"); } catch (e) {} finish({ action: "allow" }); },
                               TIMEOUT[event] || 30000);
      child.stdout.on("data", (b) => { out += b; });
      child.on("error", () => { clearTimeout(timer); finish({ action: "allow" }); });
      child.on("close", () => {
        clearTimeout(timer);
        try {
          const line = out.trim().split("\n").pop() || "";
          finish(line ? JSON.parse(line) : { action: "allow" });
        } catch (e) { finish({ action: "allow" }); }   // a broken hook must not kill the agent
      });
      child.stdin.end(JSON.stringify(payload || {}));
    } catch (e) {
      finish({ action: "allow" });
    }
  });
}

function sid(ctx) {
  try { return ctx.sessionManager.getSessionId(); } catch (e) { return undefined; }
}

function mid(ctx) {   // the model pi says it is using (a claim, not an observation)
  try { return ctx.model ? `${ctx.model.provider}/${ctx.model.id}` : undefined; } catch (e) { return undefined; }
}

function text(content) {
  try { return (content || []).filter((c) => c && c.type === "text").map((c) => c.text).join("\n"); }
  catch (e) { return undefined; }
}

export default function (pi) {
  // Accountable trace: the task message (is a wrong value in the answer something the task gave?).
  pi.on("before_agent_start", async (event, ctx) => {
    await ask("prompt", { prompt: event && event.prompt, cwd: ctx.cwd, session_id: sid(ctx) });
    return undefined;
  });
  pi.on("tool_call", async (event, ctx) => {
    const d = await ask("pre_tool", { tool: event.toolName, input: event.input || {},
                                      call_id: event.toolCallId, model: mid(ctx),
                                      cwd: ctx.cwd, session_id: sid(ctx) });
    if (d.action === "deny") return { block: true, reason: d.reason };
    return undefined;
  });
  // Accountable trace: what each step returned (the step's writes are Vacant's own diff).
  pi.on("tool_result", async (event, ctx) => {
    await ask("post_tool", { tool: event.toolName, input: event.input || {},
                             call_id: event.toolCallId, output: text(event.content),
                             is_error: !!event.isError, model: mid(ctx),
                             cwd: ctx.cwd, session_id: sid(ctx) });
    return undefined;
  });
  pi.on("agent_before_settle", async (event, ctx) => {
    const d = await ask("stop", { cwd: ctx.cwd, session_id: sid(ctx) });
    if (d.action === "continue" && d.reason) {
      return { entries: [{ type: "custom_message", customType: "vacant-check",
                           content: d.reason, display: true }], continue: true };
    }
    return undefined;
  });
  pi.on("session_shutdown", async (event, ctx) => {
    // reason: quit | reload | new | resume | fork — only `quit` ends the work
    await ask("session_end", { cwd: ctx.cwd, session_id: sid(ctx),
                               reason: (event && event.reason) || undefined });
  });
}
"""


def pi_extension_text(timeout_ms: int = 600_000) -> str:
    return PI_EXTENSION % {"argv": json.dumps(hook_argv("pi", "")[:-1]),
                           "timeout_ms": timeout_ms}


def pi_build(prompt: str, ws: pathlib.Path, *, hooks: bool = True,
             extra: list[str] | None = None) -> Launch:
    argv = [which(("pi",)) or "pi", "-p", "--mode", "json"]
    cleanup: Callable[[], None] | None = None
    if hooks and (installed := persistent_hook_file("pi")) is not None:
        # 同一個檔再給一次 `-e`：pi 以正規路徑去重（只載一次）[agent-pi 對照 RUN]，
        # 使用者關掉自動探索時仍然載得到。
        argv += ["-e", str(installed)]
    elif hooks:
        d = pathlib.Path(tempfile.mkdtemp(prefix="vacant-pi-"))
        (d / "vacant.ts").write_text(pi_extension_text(), encoding="utf-8")
        argv += ["-e", str(d / "vacant.ts")]

        def cleanup(p: pathlib.Path = d) -> None:
            shutil.rmtree(p, ignore_errors=True)
    return Launch(argv=argv + list(extra or []) + [prompt],
                  env={"VACANT_HOOK_NO_SUBMIT": "1", "PI_SKIP_VERSION_CHECK": "1"},
                  note="pi -p", cleanup=cleanup)


def pi_dir(home: pathlib.Path) -> pathlib.Path:
    return pathlib.Path(os.environ.get("PI_CODING_AGENT_DIR") or (home / ".pi" / "agent"))


def pi_install(m: INS.Manifest, home: pathlib.Path) -> list[dict[str, Any]]:
    d = pi_dir(home)
    return [INS.put_file(m, "pi", d / "extensions" / "vacant.ts", pi_extension_text()),
            INS.put_file(m, "pi", d / "skills" / "vacant" / "SKILL.md", skill_text())]


# ── OpenCode ──────────────────────────────────────────────────────────

#: OpenCode 外掛（`tool.execute.before` 丟例外 ＝ 拒絕 [REPO: AGENT_HOOKS_MEASURED; RUN]）。
#: ⚠ OpenCode 1.18 的外掛 API **沒有任何能讓一回合繼續的掛鉤**（binary 裡的掛鉤名只有
#:   `tool.execute.before/after`、`command.execute.before`、`experimental.chat.*.transform`、
#:   `permission.ask`——後者在 1.18.32 宣告了但**從來不觸發**——與通知型的 `event`），
#:   而 `opencode run` 在第一個 `session.idle` 就結束（v1.18.31 `run.ts:793-797`）。所以：
#:   - 互動 TUI：idle 時沒過 ⇒ 用 SDK client 把回饋當下一則訊息送回（有輪數上限；**未量**）；
#:   - `opencode run`：**沒有交件前的回饋**（2026-09-24 端到端實測：模型沒看到回饋）；
#:   - 工作階段結束：`event` 在 `run` 裡是 fire-and-forget（約 40 ms 後行程就結束），
#:     **`dispose()` 會被 await** ⇒ 交件放在 `dispose`，用 `globalThis` 旗標防重入
#:     （外掛在同一個行程裡可能被初始化不只一次）[agent-opencode 對照 §4]。
#:   - `session.idle` 也會替子 agent 的 session 觸發，而且比父 session 早 ⇒ 用
#:     `session.created` 的 `info.parentID` 記下子 session，idle 時略過。
OPENCODE_PLUGIN = r"""// Vacant (vacant-intake) — generated by `vacant install`; remove with `vacant uninstall`.
import { spawn } from "node:child_process";

const ARGV = %(argv)s;
const TIMEOUT = { pre_tool: 30000, post_tool: 30000, stop: %(timeout_ms)d, session_end: 30000 };

function ask(event, payload) {
  return new Promise((resolve) => {
    let out = "";
    let done = false;
    const finish = (v) => { if (!done) { done = true; resolve(v); } };
    try {
      const child = spawn(ARGV[0], [...ARGV.slice(1), event], { stdio: ["pipe", "pipe", "ignore"] });
      const timer = setTimeout(() => { try { child.kill("SIGKILL"); } catch (e) {} finish({ action: "allow" }); },
                               TIMEOUT[event] || 30000);
      child.stdout.on("data", (b) => { out += b; });
      child.on("error", () => { clearTimeout(timer); finish({ action: "allow" }); });
      child.on("close", () => {
        clearTimeout(timer);
        try {
          const line = out.trim().split("\n").pop() || "";
          finish(line ? JSON.parse(line) : { action: "allow" });
        } catch (e) { finish({ action: "allow" }); }   // a broken hook must not kill the agent
      });
      child.stdin.end(JSON.stringify(payload || {}));
    } catch (e) {
      finish({ action: "allow" });
    }
  });
}

// `opencode run` ends at the first idle: feedback could never be delivered there, so the
// stop check would only add latency. The session-end submission (dispose) still runs.
const NONINTERACTIVE = process.argv.includes("run");

const g = globalThis;
g.__vacantChildSessions = g.__vacantChildSessions || new Map();   // child session id -> parent id
g.__vacantStopBusy = g.__vacantStopBusy || new Set();   // one stop check per session at a time
g.__vacantArgs = g.__vacantArgs || new Map();           // callID -> args (for the post_tool record)

// Who is acting: a child session is a sub-agent; the trace keys the work by the root session.
function who(sessionID) {
  const parent = g.__vacantChildSessions.get(sessionID);
  if (!parent) return { session_id: sessionID };
  let root = parent;
  for (let i = 0; i < 16 && g.__vacantChildSessions.has(root); i++) root = g.__vacantChildSessions.get(root);
  return { session_id: sessionID, parent_session_id: parent, root_session_id: root };
}

export const VacantPlugin = async ({ client, directory }) => {
  return {
    "tool.execute.before": async (input, output) => {
      const args = (output && output.args) || {};
      if (input && input.callID) g.__vacantArgs.set(input.callID, args);
      const d = await ask("pre_tool", { tool: input && input.tool, input: args,
                                  call_id: input && input.callID, cwd: directory,
                                  ...who(input && input.sessionID) });
      if (d.action === "deny") {
        if (input && input.callID) g.__vacantArgs.delete(input.callID);
        throw new Error(d.reason || "blocked by Vacant");
      }
    },
    // Accountable trace: what each step returned (the step's writes are Vacant's own diff).
    "tool.execute.after": async (input, output) => {
      const id = input && input.callID;
      const args = (id && g.__vacantArgs.get(id)) || (input && input.args) || {};
      if (id) g.__vacantArgs.delete(id);
      await ask("post_tool", { tool: input && input.tool, input: args, call_id: id,
                               output: output && output.output, cwd: directory,
                               ...who(input && input.sessionID) });
    },
    event: async ({ event }) => {
      if (!event) return;
      const props = event.properties || {};
      if (event.type === "session.created" && props.info && props.info.parentID) {
        g.__vacantChildSessions.set(props.info.id, props.info.parentID);
      }
      if (event.type === "session.idle" && !NONINTERACTIVE) {
        const id = props.sessionID;
        if (g.__vacantChildSessions.has(id) || g.__vacantStopBusy.has(id)) return;
        g.__vacantStopBusy.add(id);
        try {
          const d = await ask("stop", { cwd: directory, session_id: id });
          if (d.action === "continue" && d.reason && id && client && client.session) {
            try {
              await client.session.prompt({ path: { id }, body: { parts: [{ type: "text", text: d.reason }] } });
            } catch (e) { /* the session has moved on */ }
          }
        } finally {
          g.__vacantStopBusy.delete(id);
        }
      }
    },
    dispose: async () => {
      if (g.__vacantEnded) return;
      g.__vacantEnded = true;
      await ask("session_end", { cwd: directory });
    },
  };
};
export default VacantPlugin;
"""


def opencode_plugin_text(timeout_ms: int = 600_000) -> str:
    return OPENCODE_PLUGIN % {"argv": json.dumps(hook_argv("opencode", "")[:-1]),
                              "timeout_ms": timeout_ms}


def opencode_build(prompt: str, ws: pathlib.Path, *, hooks: bool = True,
                   extra: list[str] | None = None) -> Launch:
    # `--dir` 一定給絕對路徑：相對的 `--dir` 會接在（可能過期的）PWD 後面。
    argv = [which(("opencode",)) or "opencode", "run", "--format", "json",
            "--dir", str(pathlib.Path(ws).resolve())]
    env = {"VACANT_HOOK_NO_SUBMIT": "1"}
    cleanup: Callable[[], None] | None = None
    note = "opencode run"
    merged = opencode_merge_content(os.environ.get("OPENCODE_CONFIG_CONTENT"), "file:///x")
    if hooks and persistent_hook_file("opencode") is not None:
        note += " (hooks: the installed global plugin)"
    elif hooks and merged is None:
        # 使用者自己的 `OPENCODE_CONFIG_CONTENT` 解析不了（例如 JSONC 註解）：
        # 寧可這一跑沒有掛鉤，也不要把使用者的設定換掉。收件口照樣把關。
        note += " (hooks NOT injected: OPENCODE_CONFIG_CONTENT is not plain JSON)"
    elif hooks:
        d = pathlib.Path(tempfile.mkdtemp(prefix="vacant-opencode-"))
        (d / "vacant.js").write_text(opencode_plugin_text(), encoding="utf-8")
        # 加法式注入：`OPENCODE_CONFIG_CONTENT` 是深合併的一層（config.ts:482-490），
        # `plugin` 陣列會去重合併；**併進**使用者原本的值，不覆寫。
        # ⚠ 不用 `OPENCODE_CONFIG_DIR`：它同時改掉全域 AGENTS.md 的讀取位置
        #   （`core/global.ts:64`），使用者的全域規則會從提示裡消失（agent-opencode 對照 §0-3）。
        env["OPENCODE_CONFIG_CONTENT"] = opencode_merge_content(
            os.environ.get("OPENCODE_CONFIG_CONTENT"), (d / "vacant.js").as_uri()) or ""

        def cleanup(p: pathlib.Path = d) -> None:
            shutil.rmtree(p, ignore_errors=True)
    return Launch(argv=argv + list(extra or []) + [prompt], env=env, note=note,
                  cleanup=cleanup)


def opencode_merge_content(existing: str | None, plugin_uri: str) -> str | None:
    """把外掛併進使用者的 `OPENCODE_CONFIG_CONTENT`；解析不了 ⇒ `None`（不注入、不覆寫）。"""
    try:
        doc = json.loads(existing) if existing and existing.strip() else {}
    except ValueError:
        return None
    if not isinstance(doc, dict) or not isinstance(doc.get("plugin", []), list):
        return None
    plugins = list(doc.get("plugin") or [])
    if plugin_uri not in plugins:
        plugins.append(plugin_uri)
    doc["plugin"] = plugins
    return json.dumps(doc, ensure_ascii=False)


def opencode_dir(home: pathlib.Path) -> pathlib.Path:
    x = os.environ.get("XDG_CONFIG_HOME")
    return (pathlib.Path(x) if x else home / ".config") / "opencode"


def opencode_install(m: INS.Manifest, home: pathlib.Path) -> list[dict[str, Any]]:
    d = opencode_dir(home)
    return [INS.put_file(m, "opencode", d / "plugin" / "vacant.js", opencode_plugin_text()),
            INS.put_file(m, "opencode", d / "skill" / "vacant" / "SKILL.md", skill_text())]


# ── Codex ─────────────────────────────────────────────────────────────
#
# Codex 的掛鉤要「受信任」才會跑，而且**不受信任時靜默略過**（agent-codex 對照 §3.3）。
# 信任＝`hooks.state."<來源路徑>:<事件>:<群組>:<處理器>".trusted_hash`，雜湊是對
# `{"event_name", "hooks":[handler], "matcher"?}` 的 canonical JSON 取 sha256——
# 2026-09-24 對照 `codex app-server hooks/list` 的 currentHash 逐位元重現過 [SRC+RUN]。
# ⇒ 每一跑可以用 `-c hooks.*` 加掛鉤、用 `-c hooks.state=…` 同時給信任，不寫任何使用者檔案。
# 常駐安裝：在使用者 `config.toml` 尾端附加一個有頭尾標記的區塊（掛鉤＋信任），
# `vacant uninstall` 整段移除（使用者沒改過就逐位元還原）。

CODEX_SESSION_SRC = "/<session-flags>/config.toml"
#: SessionEnd 在 Codex 被夾在 1–3 秒（`normalize_command_hook`），而且只是建議性的。
CODEX_TIMEOUTS = {"UserPromptSubmit": 30, "PreToolUse": 30, "PostToolUse": 30,
                  "SubagentStop": 30, "Stop": 600, "SessionEnd": 3}
_CODEX_SNAKE = {"UserPromptSubmit": "user_prompt_submit",
                "PreToolUse": "pre_tool_use", "PostToolUse": "post_tool_use",
                "SubagentStop": "subagent_stop", "Stop": "stop", "SessionEnd": "session_end"}
#: 每一跑與常駐安裝都掛的事件（UserPromptSubmit／PostToolUse／SubagentStop／SessionEnd 是追緝的
#: 任務訊息、病歷與逐字稿封存；
#: `-c` 加的掛鉤也到得了子 agent [capture-codex §0-5 RUN]）
CODEX_EVENTS = ("UserPromptSubmit", "PreToolUse", "PostToolUse", "SubagentStop", "Stop",
                "SessionEnd")


def codex_handler(event: str) -> dict[str, Any]:
    return {"type": "command", "command": hook_command("codex", event),
            "timeout": CODEX_TIMEOUTS[event], "async": False}


def codex_hook_hash(event: str, handler: dict[str, Any], matcher: str | None = None) -> str:
    import hashlib
    ident: dict[str, Any] = {"event_name": _CODEX_SNAKE[event], "hooks": [handler]}
    if matcher is not None:
        ident["matcher"] = matcher
    s = json.dumps(ident, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(s.encode()).hexdigest()


def _toml_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def codex_run_overrides(events: tuple[str, ...] = CODEX_EVENTS) -> list[str]:
    args = ["--enable", "hooks", "--disable", "unbounded_connection_retries"]
    state = []
    for ev in events:
        h = codex_handler(ev)
        handler_toml = (f'{{type="command",command={_toml_str(h["command"])},'
                        f'timeout={h["timeout"]},async=false}}')
        args += ["-c", f"hooks.{ev}=[{{hooks=[{handler_toml}]}}]"]
        key = f"{CODEX_SESSION_SRC}:{_CODEX_SNAKE[ev]}:0:0"
        state.append(f'{_toml_str(key)}={{trusted_hash={_toml_str(codex_hook_hash(ev, h))},'
                     f'enabled=true}}')
    args += ["-c", "hooks.state={" + ",".join(state) + "}"]
    return args


def codex_build(prompt: str, ws: pathlib.Path, *, hooks: bool = True,
                extra: list[str] | None = None) -> Launch:
    # 沙箱用 `workspace-write`（exec 的預設其實是 read-only，連工作區都寫不進去）；
    # **不**像舊 gateshim 那樣開 `danger-full-access`——別把別人的圍牆拆掉再量
    # （COMPLETE_MEDIATION §0.1）。`--disable unbounded_connection_retries`：上游死掉時
    # 預設是無限重連（agent-codex 對照 fact 12），launcher 的逾時之外再加一道。
    # 先宣告這個工作區的信任層級：不宣告的話 Codex 每一次 exec 都會自己在使用者的
    # `config.toml` 附加一條 `[projects."<ws>"] trust_level="trusted"`——`vacant do` 每一跑
    # 都是新目錄，使用者的設定檔就一跑長一條（2026-09-24 實測；帶這個 `-c` 就不寫）。
    wsa = str(pathlib.Path(ws).resolve())
    argv = [which(("codex",)) or "codex", "exec", "--json", "--skip-git-repo-check",
            "-C", wsa, "-s", "workspace-write",
            "-c", f"projects={{{_toml_str(wsa)}={{trust_level=\"trusted\"}}}}"]
    note = "codex exec"
    if hooks and persistent_hook_file("codex") is not None:
        # 使用者層已經有我們的掛鉤＋信任：再從 `-c` 加一份 ⇒ 兩個設定層各跑一次。
        argv += ["--enable", "hooks", "--disable", "unbounded_connection_retries"]
        note += " (hooks: the installed config.toml block)"
    elif hooks:
        argv += codex_run_overrides()
    else:
        argv += ["--disable", "unbounded_connection_retries"]
    return Launch(argv=argv + list(extra or []) + [prompt],
                  env={"VACANT_HOOK_NO_SUBMIT": "1"}, note=note)


def codex_home(home: pathlib.Path) -> pathlib.Path:
    return pathlib.Path(os.environ.get("CODEX_HOME") or (home / ".codex"))


def codex_config_block(cfg_path: pathlib.Path, existing: dict[str, Any]) -> str:
    """附加在使用者 `config.toml` 尾端的區塊：三個掛鉤＋它們的信任項目。

    信任鍵裡的群組索引＝使用者自己在同一個檔裡已經有幾組同事件的掛鉤（我們附加在後面）。
    ⚠ 不用 profile：`profile = "vacant"` 在 0.156.1 是**遺留鍵，Codex 直接拒絕啟動**
    （2026-09-24 端到端實測，rc=1）——一個會讓 agent 起不來的安裝比沒裝更糟。
    ⚠ 不設 `[features] hooks`：0.156.1 預設就是 true（`codex features list`），而且使用者
    若已有 `[features]` 表，再附加一個會讓整份檔不合法。
    """
    lines: list[str] = []
    hooks_existing = existing.get("hooks") if isinstance(existing.get("hooks"), dict) else {}
    for ev in CODEX_EVENTS:
        h = codex_handler(ev)
        lines += [f"[[hooks.{ev}]]", f"[[hooks.{ev}.hooks]]", 'type = "command"',
                  f"command = {_toml_str(h['command'])}", f"timeout = {h['timeout']}",
                  "async = false", ""]
    # Codex 用**沒有解析符號連結**的 `$CODEX_HOME/config.toml` 當信任鍵的來源路徑；
    # `~/.codex` 是個連結（dotfiles）時，只寫解析後的那個 ⇒ 三個掛鉤都「不受信任」、
    # 被安靜略過（2026-09-24 對抗審查用 `codex app-server hooks/list` 重現）。兩種拼法都寫。
    spellings = [cfg_path]
    if cfg_path.resolve() != cfg_path:
        spellings.append(cfg_path.resolve())
    for ev in CODEX_EVENTS:
        gi = len(hooks_existing.get(ev) or []) if isinstance(hooks_existing, dict) else 0
        for sp in spellings:
            key = f"{sp}:{_CODEX_SNAKE[ev]}:{gi}:0"
            lines += [f"[hooks.state.{_toml_str(key)}]",
                      f"trusted_hash = {_toml_str(codex_hook_hash(ev, codex_handler(ev)))}",
                      "enabled = true", ""]
    return "\n".join(lines)


def codex_install(m: INS.Manifest, home: pathlib.Path) -> list[dict[str, Any]]:
    import tomllib
    d = codex_home(home)
    cfg = d / "config.toml"
    cur = tomllib.loads(INS.strip_block(cfg.read_text(encoding="utf-8"))) if cfg.is_file() else {}
    ops = [INS.add_toml_block(m, "codex", cfg,
                              codex_config_block(pathlib.Path(os.path.abspath(cfg)), cur)),
           INS.put_file(m, "codex", d / "skills" / "vacant" / "SKILL.md", skill_text())]
    return ops


# ── registry ──────────────────────────────────────────────────────────

@dataclasses.dataclass(frozen=True)
class AgentSpec:
    name: str
    binaries: tuple[str, ...]
    build: Callable[..., Launch]
    install: Callable[[INS.Manifest, pathlib.Path], list[dict[str, Any]]]
    hook_install_note: str


AGENTS: dict[str, AgentSpec] = {
    "claude": AgentSpec("claude", ("claude",), claude_build, claude_install,
                        "hooks in ~/.claude/settings.json + skill"),
    "codex": AgentSpec("codex", ("codex",), codex_build, codex_install,
                       "trusted hooks appended to config.toml + skill"),
    "opencode": AgentSpec("opencode", ("opencode",), opencode_build, opencode_install,
                          "global plugin + skill"),
    "pi": AgentSpec("pi", ("pi",), pi_build, pi_install, "global extension + skill"),
}


def detect() -> dict[str, str | None]:
    return {n: which(s.binaries) for n, s in AGENTS.items()}


def generic_build(template: list[str]) -> Callable[..., Launch]:
    """任何 CLI：`vacant do --cmd 'mytool --task {prompt}'`。沒有掛鉤，只有行程＋工作區。"""
    def build(prompt: str, ws: pathlib.Path, *, hooks: bool = True,
              extra: list[str] | None = None) -> Launch:
        argv = [a.replace("{prompt}", prompt).replace("{workspace}", str(ws)) for a in template]
        return Launch(argv=argv + list(extra or []), note="generic")
    return build
