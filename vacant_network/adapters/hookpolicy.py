"""hookpolicy — **正規化之後的掛鉤事件，由同一份政策判斷**（與 agent 無關）。

這支在架構裡承重什麼：四個 agent 的掛鉤各寫各的（Claude Code `PreToolUse`、Codex
`PreToolUse`、OpenCode `tool.execute.before`、pi `tool_call`），但**要判斷的事是同一件**。
每個 adapter 只負責「翻譯」：把原生 payload 變成 `HookEvent`、把 `HookDecision` 變回
原生回應。判斷邏輯只有這一份。

## 三條規則

1. **工具執行前（`pre_tool`）**：
   - 碰 Vacant 自己的狀態（`$VACANT_HOME`：金鑰、隔離區、帳本）或契約檔／契約釘住的
     輸入（驗收套件、原始資料）的**寫入**⇒ 拒絕。讀契約是允許的（agent 本來就該讀）。
     讀金鑰目錄也拒絕。
   - 契約 `effects.deny_commands` 裡的字串出現在 shell 指令裡 ⇒ 拒絕。
   - 其餘放行。
2. **回合結束（`stop`）**：契約 `hooks.stop_check` 為真時，對專案根目錄跑一次
   `flow.check`（只驗不收）。沒過而且回饋輪數還沒用完 ⇒ 回 `continue`＋失敗摘要，
   讓 agent 在宣告完成之前看到判準（增效那一半）。用完就放行——**放行不等於收件**。
3. **工作階段結束（`session_end`）**：契約 `hooks.submit_on_end` 為真時，把專案根目錄
   交進收件口（`flow.submit`），這一次工作階段因此一定在帳本上有一個裁決。

## 誠實邊界（改碼請保留）

1. **規則 1 是字串層的**：`bash -c "$(echo cm0gLXJmIC52YWNhbnQ= | base64 -d)"` 這種寫法看不出來。
   它擋的是「順手改掉判準」，不是決意的攻擊者。對後者的保護是別處的：輸入以雜湊釘住
   （改了 ⇒ UNKNOWN）、隔離區逐檔驗雜湊（改了 ⇒ 放行拒絕）、收件端的簽章者清單可以在
   另一個帳號。
2. **掛鉤壞掉不可以弄死 agent**：任何例外都放行並落一筆錯誤。這一層是增效與觀測，
   不是保證（`adapters/__init__.py`）。
3. 回饋文字遵守 KS-1：只陳述哪一條主張沒過與原因，不寫「你有責任／會被懲罰」。
"""
from __future__ import annotations

import dataclasses
import json
import os
import pathlib
import re
import shlex
import time
from typing import Any

KINDS = ("session_start", "pre_tool", "post_tool", "stop", "session_end", "other")
ACTIONS = ("allow", "deny", "continue")

#: 寫入型工具（跨 agent 的名字）。shell 類另外處理。
WRITE_TOOLS = frozenset({"write", "edit", "multiedit", "patch", "apply_patch", "notebookedit",
                         "str_replace_editor", "create", "update", "delete"})
SHELL_TOOLS = frozenset({"bash", "shell", "exec", "exec_command", "local_shell",
                         "run_command", "terminal", "unified_exec"})
#: 直譯器程式碼裡的寫入 API（`python3 -c "open(p,'w')"` 這種路徑藏在程式碼字串裡的情況）。
_CODE_WRITE_HINT = re.compile(r"\bopen\(|write_text|write_bytes|writeFile|unlink|remove\(|"
                              r"rmtree|rename|replace\(|truncate|chmod|appendFile")
#: 所有非選項引數都是寫入目標的指令。
_WRITE_ALL_ARGS = frozenset({"rm", "unlink", "shred", "truncate", "chmod", "chown", "chgrp",
                             "tee", "touch", "mkdir", "rmdir", "patch"})
#: 最後一個非選項引數是寫入目標的指令。
_WRITE_LAST_ARG = frozenset({"cp", "mv", "install", "ln", "rsync", "scp"})
_GIT_WRITE_SUB = frozenset({"checkout", "restore", "reset", "clean", "rm", "mv", "apply",
                            "am", "stash"})
_SEPARATORS = frozenset({";", "&&", "||", "|", "&", "(", ")", "|&", ";;", "\n"})
_REDIRECTS = frozenset({">", ">>", ">|", "&>", "&>>", "<>"})
_WRAPPERS = frozenset({"sudo", "env", "command", "nice", "nohup", "time", "exec", "xargs",
                       "builtin", "stdbuf"})

#: 不是工作的結束，只是換一段上下文：在這些時候交件，會把做到一半的專案凍結成一個裁決。
NON_TERMINAL_END_REASONS = frozenset({"clear", "resume", "reload", "new", "fork", "compact"})

FEEDBACK_HEADER = ("The task contract's checks do not pass yet "
                   "(this is feedback from `vacant check`, not a final decision):")


@dataclasses.dataclass
class HookEvent:
    agent: str
    kind: str
    tool: str | None = None
    command: str | None = None
    paths: list[str] = dataclasses.field(default_factory=list)
    cwd: str = ""
    session_id: str | None = None
    stop_hook_active: bool = False
    #: 工作階段結束的原因（Claude `clear|resume|logout|prompt_input_exit|other`、
    #: pi `quit|reload|new|resume|fork`）。只有**真的結束**才交件。
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"unknown hook kind {self.kind!r}")


@dataclasses.dataclass
class HookDecision:
    action: str = "allow"
    reason: str = ""
    record: dict[str, Any] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.action not in ACTIONS:
            raise ValueError(f"unknown hook action {self.action!r}")


def vacant_state_dir() -> pathlib.Path:
    from ..intake.statepaths import state_dir
    return state_dir()


def _protected(contract) -> tuple[list[pathlib.Path], list[pathlib.Path]]:
    """回 `(寫入受保護, 讀取也受保護)`。"""
    write_prot = [vacant_state_dir()]
    read_prot = [vacant_state_dir() / "intake" / "keys"]
    if contract is not None:
        if contract.path:
            write_prot.append(contract.path)
            write_prot.append(contract.path.parent if contract.path.parent.name == ".vacant"
                              else contract.path)
        for name in (contract.raw.get("inputs") or {}):
            try:
                write_prot.append(contract.input_path(name))
            except KeyError:
                pass
        for p in contract.effects.get("protect_paths") or []:
            write_prot.append((contract.base_dir / p).resolve())
    return write_prot, read_prot


def _under(p: str, roots: list[pathlib.Path], cwd: str) -> pathlib.Path | None:
    try:
        q = pathlib.Path(p).expanduser()
        if not q.is_absolute():
            q = pathlib.Path(cwd or ".") / q
        q = q.resolve()
    except (OSError, RuntimeError, ValueError):
        return None
    for r in roots:
        try:
            r = r.resolve()
        except (OSError, RuntimeError):
            continue
        if q == r or r in q.parents:
            return r
    return None


def _tokens(command: str) -> list[str]:
    try:
        lex = shlex.shlex(command, posix=True, punctuation_chars=";&|()<>")
        lex.whitespace_split = True
        lex.commenters = ""
        return list(lex)
    except ValueError:                    # 引號不成對：退回空白切割（寧可多看，不要崩）
        return command.split()


def _segments(tokens: list[str]) -> list[tuple[list[str], list[str]]]:
    """切成簡單指令：`(引數, 重導向目標)`。"""
    out: list[tuple[list[str], list[str]]] = []
    words: list[str] = []
    redir: list[str] = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t in _SEPARATORS:
            if words or redir:
                out.append((words, redir))
            words, redir = [], []
        elif t in _REDIRECTS or (t.endswith(">") and t.rstrip(">").isdigit()):
            if i + 1 < len(tokens) and tokens[i + 1] not in _SEPARATORS:
                redir.append(tokens[i + 1])
                i += 1
        elif t in (">&", "<&", "<", "<<", "<<<"):
            i += 1                        # fd 複製／輸入：不是寫入
        elif re.fullmatch(r"\d*[<>]&?\d*", t):
            pass
        else:
            words.append(t)
        i += 1
    if words or redir:
        out.append((words, redir))
    return out


def _command_word(words: list[str]) -> tuple[str, list[str]]:
    i = 0
    while i < len(words):
        w = words[i]
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", w) or w in _WRAPPERS:
            i += 1
            continue
        return os.path.basename(w), words[i + 1:]
    return "", []


def _write_targets(cmd: str, args: list[str]) -> list[str]:
    plain = [a for a in args if not a.startswith("-")]
    if cmd in _WRITE_ALL_ARGS:
        return plain
    if cmd in _WRITE_LAST_ARG:
        return plain[-1:]
    if cmd == "sed" and any(a == "-i" or a.startswith("-i") or a == "--in-place" for a in args):
        return plain[1:]
    if cmd == "dd":
        return [a[3:] for a in args if a.startswith("of=")]
    if cmd == "git" and plain and plain[0] in _GIT_WRITE_SUB:
        return plain[1:] or ["."]
    return []


def _path_forms(r: pathlib.Path, cwd: str) -> list[str]:
    rs = str(r)
    home = str(pathlib.Path.home())
    forms = {rs}
    if rs.startswith(home + os.sep):
        forms.add("~" + rs[len(home):])
        forms.add("$HOME" + rs[len(home):])
    try:
        rel = os.path.relpath(rs, cwd or ".")
        if not rel.startswith(".."):
            forms.add(rel)
    except ValueError:
        pass
    return [f for f in forms if f and f != "."]


def _in_code(token: str, roots: list[pathlib.Path], cwd: str) -> pathlib.Path | None:
    """路徑以**完整的路徑元件**出現在一段程式碼字串裡（後面接結尾、`/`、引號、空白、括號）。"""
    for r in roots:
        for f in _path_forms(r, cwd):
            if re.search(re.escape(f) + r"(?=$|[/'\"\s),;])", token):
                return r
    return None


def _shell_verdict(command: str, cwd: str, write_prot: list[pathlib.Path],
                   read_prot: list[pathlib.Path]) -> tuple[str, pathlib.Path] | None:
    """`("read", 根)`：碰到讀取也受保護的路徑；`("write", 根)`：寫入受保護的路徑。

    字串層的（見誠實邊界 1）。比的是**路徑元件**，不是子字串：`~/.vacant-work/...`
    不是 `~/.vacant`，`data/sales.csv` 被讀（`python3 x.py data/sales.csv > r.md`）不是寫。
    """
    eff_cwd = cwd or "."
    for words, redir in _segments(_tokens(command)):
        cmd, args = _command_word(words)
        if cmd == "cd" and args:
            nxt = pathlib.Path(os.path.expanduser(args[0]))
            eff_cwd = str(nxt if nxt.is_absolute() else pathlib.Path(eff_cwd) / nxt)
            continue
        for tok in words + redir:
            val = tok.split("=", 1)[1] if tok.startswith("-") and "=" in tok else tok
            hit = _under(os.path.expandvars(val), read_prot, eff_cwd) or \
                _in_code(tok, read_prot, eff_cwd)
            if hit is not None:
                return "read", hit
        for tgt in redir + _write_targets(cmd, args):
            hit = _under(os.path.expandvars(tgt), write_prot, eff_cwd)
            if hit is not None:
                return "write", hit
        for tok in args:
            if _CODE_WRITE_HINT.search(tok):
                hit = _in_code(tok, write_prot, eff_cwd)
                if hit is not None:
                    return "write", hit
    return None


#: agent 的工作階段裡可以 `vacant check`／`submit`，不能行使**別的權威**：
#: 人工審查、批准、放行、撤回、金鑰、重驗、改契約。本機單人模式下那些金鑰就在
#: 同一個帳號裡，agent 一行 `vacant review quality pass` 就能替自己蓋「人工審查」的章
#: （2026-09-24 對抗審查重現）。這條規則跟其他掛鉤規則一樣是**工具層**的（字串比對，
#: 換個寫法就過得去）——真正的分權是把 reviewer／approver 金鑰放到另一個帳號。
#: `vacant`、`vacant-network`（README 教被遮蔽時改用它）、`python -m vacant_network[.cli|.intake.cli]`
_VACANT_CLI = r"(?:\bvacant(?:-network)?|-m\s+vacant_network(?:\.cli|\.intake\.cli)?)"
_AUTHORITY_RE = re.compile(
    _VACANT_CLI + r"\s+(?:(review|approve|release|withdraw|keys|reverify|flag)\b"
    r"|contract\s+(lock|init)\b|intake\s+serve\b)")


def decide_pre_tool(ev: HookEvent, contract) -> HookDecision:
    tool = (ev.tool or "").lower()
    write_prot, read_prot = _protected(contract)
    for p in ev.paths:
        hit = _under(p, read_prot, ev.cwd)
        if hit is not None:
            return HookDecision("deny", f"Vacant: {hit} holds signing keys; agents may not "
                                        f"read or change it.", {"rule": "protect_keys"})
        if tool in WRITE_TOOLS or tool.endswith("write") or tool.endswith("edit"):
            hit = _under(p, write_prot, ev.cwd)
            if hit is not None:
                return HookDecision("deny", f"Vacant: {hit} is part of the task contract or "
                                            f"Vacant's own records; it cannot be modified "
                                            f"from inside the task.", {"rule": "protect_write"})
    cmd = ev.command or ""
    if cmd:
        verdict = _shell_verdict(cmd, ev.cwd, write_prot, read_prot)
        if verdict is not None and verdict[0] == "read":
            return HookDecision("deny", f"Vacant: commands may not touch {verdict[1]} "
                                        f"(signing keys).", {"rule": "protect_keys"})
        if verdict is not None:
            return HookDecision("deny", f"Vacant: this command appears to modify {verdict[1]}, "
                                        f"which is part of the task contract or Vacant's "
                                        f"records.", {"rule": "protect_write"})
        m = _AUTHORITY_RE.search(cmd)
        if m:
            what = m.group(1) or (f"contract {m.group(2)}" if m.group(2) else "intake serve")
            return HookDecision("deny", f"Vacant: `vacant {what}` belongs to the task's owner, "
                                        f"reviewer or approver, not to the session doing the "
                                        f"work. Use `vacant check` to see where the "
                                        f"deliverable stands.", {"rule": "vacant_authority"})
        for pat in (contract.effects.get("deny_commands") if contract else None) or []:
            if pat and pat in cmd:
                return HookDecision("deny", f"Vacant: the task contract does not allow "
                                            f"`{pat}` during this task (effects.deny_commands). "
                                            f"Effects happen through `vacant release` after "
                                            f"acceptance.", {"rule": "deny_commands",
                                                             "pattern": pat})
    return HookDecision("allow")


def feedback_text(res: dict[str, Any], contract) -> str:
    hidden = {c.id for c in contract.claims if c.hidden} if contract else set()
    lines = [FEEDBACK_HEADER]
    for r in res.get("results", []):
        if r["status"] == "PASS" or not r.get("required", True):
            continue
        detail = "" if r["claim_id"] in hidden else f" — {r['detail'][:600]}"
        lines.append(f"- {r['claim_id']}: {r['status']}{detail}")
    if len(lines) == 1:
        lines += [f"- {x}" for x in res.get("reasons", [])[:8]]
    lines.append("Run `vacant check` to re-check before finishing.")
    return "\n".join(lines)


def _rounds_file(session_id: str | None) -> pathlib.Path:
    sid = re.sub(r"[^A-Za-z0-9._-]", "_", session_id or "nosession")[:120]
    return vacant_state_dir() / "intake" / "hooks" / f"rounds_{sid}.json"


def _bump_round(session_id: str | None) -> int:
    p = _rounds_file(session_id)
    n = 0
    try:
        n = int(json.loads(p.read_text()).get("n", 0))
    except (OSError, ValueError):
        n = 0
    n += 1
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"n": n, "t": time.time()}))
    return n


def new_request(session_id: str | None) -> None:
    """人打了一個新的要求 ⇒ 回饋輪數重新算。輪數上限防的是「一個要求之內」agent 被無限推回去；
    互動介面裡前面幾個回合（人只是問問題、還沒要它交件）用掉的輪數，不可以讓之後真的寫錯時
    agent 收不到位置（2026-09-25 互動 TUI 實測時發現）。只有人打的那一則算——呼叫端負責分辨
    （`hook._person_prompt`）。"""
    _rounds_file(session_id).unlink(missing_ok=True)


def decide_stop(ev: HookEvent, contract, *, check_fn, localize=None) -> HookDecision:
    """`localize(res, why_open) -> {"text", "summary", "report", "blames"} | None`：可究責追緝
    （`trace/stopcheck.py`）。給了就用**有位置、有來源**的回饋取代泛用回饋；agent 不會再被要求
    繼續的時候（輪數用完、只剩 agent 改不動的、過了但有提示性問題），未解問題以
    `record["user_message"]` 交給人（Claude Code 顯示成 `systemMessage`），不就此消失。"""
    if contract is None or not contract.hooks.get("stop_check", True):
        return HookDecision("allow")
    res = check_fn(contract, contract.base_dir)
    outcome = res.get("outcome")
    rec: dict[str, Any] = {"outcome": outcome, "coverage": res.get("coverage")}

    def traced(why: str | None) -> dict[str, Any] | None:
        if localize is None:
            return None
        try:
            out = localize(res, why)
        except Exception as e:  # noqa: BLE001 — 追緝壞掉不影響裁決，泛用回饋照送
            rec["trace_error"] = f"{type(e).__name__}: {e}"[:300]
            return None
        if out:
            rec["trace"] = {"findings": len(out.get("blames") or []), "report": out.get("report")}
            if why is not None and out.get("summary"):
                rec["user_message"] = out["summary"]
        return out

    open_any = [r for r in res.get("results", []) if r.get("status") != "PASS"]
    if outcome == "accept":
        # 沒有問題也走一次追緝：之前開著的問題在病歷裡記成「已解決」；人標記的錯處還在
        # （`vacant flag`）⇒ 契約過了也照樣回饋給 agent（有輪數上限）——標記不擋收件
        t = traced("accepted; advisory checks still open" if open_any else None)
        flags = [b for b in (t or {}).get("blames") or []
                 if str(b.get("claim", "")).startswith("flag:")]
        if not flags:
            _rounds_file(ev.session_id).unlink(missing_ok=True)   # 過了 ⇒ 之後的問題有新的輪數
            return HookDecision("allow", "", rec)
        n = _bump_round(ev.session_id)
        rec.update(round=n, flags_open=len(flags))
        if n > int(contract.hooks.get("max_feedback_rounds", 3)) or not (t or {}).get("text"):
            rec["rounds_exhausted"] = True
            traced("feedback rounds used up; places a person marked as wrong are still there")
            return HookDecision("allow", "", rec)
        return HookDecision("continue", str((t or {})["text"]), rec)
    required_open = [r for r in res.get("results", [])
                     if r.get("required", True) and r.get("status") != "PASS"]
    if required_open and all(r.get("status") in ("UNKNOWN", "CONFLICT") for r in required_open):
        # 等人工審查、等獨立證據、審查者意見分歧——agent 改工作區改不動這些。
        # 把它推回去只會燒掉回饋輪數（或讓它試圖自己「補」一個審查）。
        rec["not_agent_fixable"] = True
        traced("waiting on review or evidence the agent cannot supply")
        return HookDecision("allow", "", rec)
    n = _bump_round(ev.session_id)
    rec["round"] = n
    if n > int(contract.hooks.get("max_feedback_rounds", 3)):
        rec["rounds_exhausted"] = True
        traced("feedback rounds used up; the agent stopped with these open")
        return HookDecision("allow", "", rec)
    t = traced(None)
    return HookDecision("continue", (t or {}).get("text") or feedback_text(res, contract), rec)
