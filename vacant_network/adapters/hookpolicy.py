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
   另一個帳號。**行使別的權威那條規則（見下）同樣是字串層的**：它看的是命令位置的 vacant CLI／
   `python -m <vacant_network 模組>`（含 `$(…)`、`bash -c`、`eval`、餵給 shell 的 heredoc／管線），
   以及直譯器內聯碼（`-c`／`-e`、餵給直譯器的 heredoc／管線）裡同時引到模組與權威詞、或字串字面值
   本身就是一行權威指令的情況——**抬高成本，不是擋死**（base64／變數組裝出來的指令、寫成外部
   腳本再跑、`ssh host '…'`／`watch '…'` 這類把整串當一個引數交出去的啟動器，都繞得過）。
   反過來它也會多擋：沒加引號的 `grep vacant hook` 會被當成在叫 `vacant hook`。
   真正的分權還是把 reviewer／approver／owner 金鑰放到另一個帳號——掛鉤擋下的指令，
   在掛鉤外面（同一個帳號、同一把 owner 金鑰）照樣跑得動。
2. **掛鉤壞掉不可以弄死 agent**：任何例外都放行並落一筆錯誤。這一層是增效與觀測，
   不是保證（`adapters/__init__.py`）。
3. 回饋文字遵守 KS-1：只陳述哪一條主張沒過與原因，不寫「你有責任／會被懲罰」。
"""
from __future__ import annotations

import dataclasses
import hashlib
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
#: 人工審查、批准、放行、撤回、金鑰、重驗、標記、掛鉤、寫契約、開收件口。本機單人模式下
#: 那些金鑰就在同一個帳號裡，agent 一行 `vacant review quality pass` 就能替自己蓋「人工審查」的章
#: （2026-09-24 對抗審查重現）。這條規則跟其他掛鉤規則一樣是**工具層**的（見誠實邊界 1）
#: ——真正的分權是把 reviewer／approver 金鑰放到另一個帳號。
#:
#: 判斷靠的是「vacant CLI／`python -m <vacant_network 模組>` 出現在一段簡單指令的**命令位置**」
#: （用 `_segments`／`_command_word`，跟殼層寫入規則同一組切詞器），不是「這些字出現在指令裡的任何地方」。
#: 所以 `grep "vacant hook" docs/`、`git commit -m "… vacant hook …"`、heredoc 寫進檔案的內文都放行——
#: 那些字只是別的指令的引數／樣式／檔案內容，不是在叫 Vacant。
#: 「命令位置」包括：分隔符之後、wrapper／環境指派之後、**獨立的一個 argv 元素**（`timeout 5 vacant
#: approve`、`find -exec vacant approve`、`uv run vacant approve`：啟動器把後面的 argv 當指令跑）、
#: 命令替換 `$(…)`／反引號（在單引號外面就會被執行）、`bash -c`／`eval` 的字串、餵給 shell 的
#: heredoc／here-string／管線。代價（誠實邊界 1）：沒加引號的 `grep vacant hook` 會被當成在叫
#: `vacant hook`——字串層分不出「啟動器」與「普通指令的兩個引數」，這邊選擇寧可多擋。
#: 頂層權威子指令（`contract` 除外，見下）：
_AUTHORITY_SUB = frozenset({"review", "approve", "release", "withdraw", "keys", "reverify",
                            "flag", "hook", "intake"})
#: `contract` 只有唯讀的兩個放行；其餘（`lock`／`init`／`quick`／將來任何會寫的子指令）一律拒絕，
#: 這樣新增一個會改契約的子指令不會自動開一個洞（2026-09-25 審查：`contract quick --replace --lock` 重寫並簽了契約）。
_CONTRACT_READONLY = frozenset({"show", "validate"})
#: `vacant contract` 裡**不帶值**的選項（其餘選項都當成吃掉下一個 token）：找動作時用。
#: 不認得的選項當成帶值 ⇒ 動作可能被跳過 ⇒ 找不到唯讀動作 ⇒ 拒絕（寧可多擋）。
_CONTRACT_FLAGS = frozenset({"--lock", "--replace", "--json", "-h", "--help"})
#: `python -m vacant_network.adapters.hook` 直接就是掛鉤（不需要子指令詞）；其他 `vacant_network[.…]`
#: 模組（`vacant_network`、`.cli`、`.intake.cli`、`.trace.cli`、`.__main__`…）照子指令判斷。
_HOOK_MODULE = "vacant_network.adapters.hook"
_VACANT_CLI_NAMES = frozenset({"vacant", "vacant-network"})
_PY_RE = re.compile(r"(?:python|pypy)[0-9.]*$")
#: python 的選項裡會吃掉下一個 token 的（`-X dev -m …`、`-W error -m …`）。
_PY_VALUE_OPTS = frozenset({"-X", "-W", "--check-hash-based-pycs"})
#: 直譯器：`-c`／`-e` 的內聯碼、以及餵給它的 heredoc／管線，都當成「一段程式碼」再掃一次。
_SHELL_RE = re.compile(r"(?:bash|sh|zsh|dash|ksh|mksh|fish)$")
_INTERP_RE = re.compile(r"(?:python[0-9.]*|pypy[0-9.]*|node|nodejs|deno|bun|ruby|perl|php)$")
#: 非 shell 直譯器的內聯碼選項（`-c`、`-Ic`、`-e`、`-pe`、`--eval`…）。
_INLINE_FLAG_RE = re.compile(r"-[A-Za-z]*[ceE]|--eval|--print|-p|-r")
#: 內聯碼裡當成「權威詞」的字串字面值／裸識別字（唯讀的 show／validate 不算）。
_CODE_AUTHORITY = frozenset({"review", "approve", "release", "withdraw", "keys", "reverify",
                             "flag", "hook", "intake", "serve", "lock", "init", "quick"})
_CODE_MOD_RE = re.compile(r"\bvacant_network\b")
_CODE_CLI_RE = re.compile(r"""['"](?:[^'"\s]*/)?vacant(?:-network)?['"]|\bvacant-network\b""")
#: 引到掛鉤模組：`vacant_network.adapters.hook`（點路徑／屬性）或 `from vacant_network.adapters import … hook …`。
_CODE_HOOK_RE = re.compile(
    r"vacant_network\.adapters\.hook\b"
    r"|vacant_network\.adapters\s+import\s+(?:\(\s*)?(?:[\w\s,]*,\s*)?hook\b")
_CODE_TOKEN_RE = re.compile(r"""['"]([\w-]+)['"]|([A-Za-z_][\w-]*)""")
#: 程式碼裡的字串字面值（`os.system("vacant approve")`）：各自再當成一行 shell 判斷。
_CODE_STR_RE = re.compile(r""""((?:[^"\\\n]|\\.)*)"|'((?:[^'\\\n]|\\.)*)'""")
_HEREDOC_OP_RE = re.compile(r"<<(-?)[ \t]*([^\s;&|<>()]+)")
_MAX_DEPTH = 4


def _python_module(cmd: str, args: list[str]) -> tuple[str, list[str]] | None:
    """`python[3] -m <模組> <其餘…>` ⇒ `(模組, 其餘)`；不是 `-m` 形式（跑腳本／`-c`）⇒ None。"""
    if not _PY_RE.match(cmd):
        return None
    i = 0
    while i < len(args):
        a = args[i]
        if a == "-m" or re.fullmatch(r"-[A-Za-z]*m", a):        # `-m`、`-Im`
            return (args[i + 1], args[i + 2:]) if i + 1 < len(args) else None
        if re.fullmatch(r"-m\S+", a):                            # `-mvacant_network`
            return (a[2:], args[i + 1:])
        if a in _PY_VALUE_OPTS:
            i += 2
            continue
        if a.startswith("-") and a != "-":
            i += 1
            continue
        return None                       # 第一個非選項不是 `-m`：在跑一支腳本（或 `-` 讀標準輸入）
    return None


def _contract_action(args: list[str]) -> str:
    """`contract` 之後的引數 ⇒ argparse 會拿到的動作（第一個位置引數）；找不到 ⇒ ""。"""
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--":
            return args[i + 1] if i + 1 < len(args) else ""
        if a.startswith("-"):
            i += 1 if (a in _CONTRACT_FLAGS or "=" in a) else 2
            continue
        return a
    return ""


def _authority_of_sub(sub: list[str]) -> tuple[str, str] | None:
    """一串子指令引數 ⇒ `(rule, what)`：`("hook", …)` 偽造掛鉤事件、`("authority", 名字)` 別的權威；否則 None。

    頂層子指令只看**第一個位置引數**（CLI 本來就是看 `argv[1]` 派送），跳過選項。"""
    words = [a for a in sub if not a.startswith("-")]
    if not words:
        return None
    head = words[0]
    if head == "hook":
        return ("hook", "hook")
    if head == "contract":
        rest = sub[sub.index("contract") + 1:]
        act = _contract_action(rest)
        if act in _CONTRACT_READONLY:
            return None
        if not act and any(a in ("-h", "--help") for a in rest):
            return None
        return ("authority", f"contract {act}".strip())
    if head == "intake":
        return ("authority", "intake serve")
    if head in _AUTHORITY_SUB:
        return ("authority", head)
    return None


def _cli_hit(cmd: str, args: list[str]) -> tuple[str, str] | None:
    """命令位置上的 `vacant …`／`vacant-network …`／`python -m vacant_network… …`。"""
    if cmd in _VACANT_CLI_NAMES:
        return _authority_of_sub(args)
    mod = _python_module(cmd, args)
    if mod is None:
        return None
    module, rest = mod
    if module == _HOOK_MODULE or module.startswith(_HOOK_MODULE + "."):
        return ("hook", "hook")
    if module == "vacant_network" or module.startswith("vacant_network."):
        return _authority_of_sub(rest)
    return None


def _maybe_command(word: str) -> bool:
    """這個 argv 元素可能是被啟動器跑起來的指令（vacant／python／shell／直譯器／eval／wrapper）。"""
    if word in _WRAPPERS or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", word):
        return True
    base = os.path.basename(word)
    return (base in _VACANT_CLI_NAMES or base == "eval" or bool(_PY_RE.match(base))
            or bool(_SHELL_RE.match(base)) or bool(_INTERP_RE.match(base)))


def _close_paren(s: str, i: int) -> int:
    """`$(` 之後從 `i` 起找對應的 `)`（略過引號裡的括號）；找不到 ⇒ `len(s)`。"""
    depth = 1
    while i < len(s):
        c = s[i]
        if c == "\\":
            i += 2
            continue
        if c in "'\"":
            j = s.find(c, i + 1)
            i = len(s) if j < 0 else j + 1
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return len(s)


def _shell_scan(command: str) -> tuple[str, list[tuple[str, bool, str]], list[str]]:
    """照殼層的引號規則掃一趟字元，回傳 `(指令, heredoc 們, 命令替換們)`。

    - 指令：拿掉 heredoc 的**內文與結束定界符**、拿掉註解；heredoc 的開頭那一行留著
      （`cat > f <<EOF` 的命令位置還是 `cat`）——寫進檔案的內文就算有 `vacant release` 也不是指令。
    - heredoc：`(內文, 定界符有沒有引號, 開頭那一行)`；定界符沒引號時內文裡的 `$(…)` 會被執行。
    - 命令替換：單引號外面的 `$(…)` 與反引號的內文（雙引號裡照樣會被執行）。
    `<<` 只在引號外面才算 heredoc：`echo "<<X"` 不會把後面的指令藏成「內文」。
    結束定界符找不到 ⇒ 內文到指令結尾為止（bash 也是這樣讀，那些行不會被執行）。"""
    out: list[str] = []
    heredocs: list[tuple[str, bool, str]] = []
    substs: list[str] = []
    pending: list[tuple[str, bool]] = []
    line_start = 0                        # 目前這一行在 `out` 裡的起點（以 list 長度計）
    in_dq = False
    i, n = 0, len(command)
    while i < n:
        c = command[i]
        if c == "'" and not in_dq:
            j = command.find("'", i + 1)
            j = n - 1 if j < 0 else j
            out.append(command[i:j + 1])
            i = j + 1
            continue
        if c == "\\":
            out.append(command[i:i + 2])
            i += 2
            continue
        if c == '"':
            in_dq = not in_dq
        elif c == "$" and command.startswith("$(", i) and not command.startswith("$((", i):
            j = _close_paren(command, i + 2)
            substs.append(command[i + 2:j])
            out.append(command[i:j + 1])
            i = j + 1
            continue
        elif c == "`":
            j = i + 1
            while j < n and command[j] != "`":
                j += 2 if command[j] == "\\" else 1
            substs.append(command[i + 1:j])
            out.append(command[i:j + 1])
            i = j + 1
            continue
        elif not in_dq and c == "#" and (i == 0 or command[i - 1] in " \t\n;&|()"):
            j = command.find("\n", i)     # 註解：到行尾為止都不是指令
            i = n if j < 0 else j
            continue
        elif not in_dq and command.startswith("<<", i) and not command.startswith("<<<", i):
            m = _HEREDOC_OP_RE.match(command, i)
            if m:
                word = m.group(2)
                pending.append((re.sub(r"[\"'\\]", "", word), bool(re.search(r"[\"'\\]", word))))
                out.append(m.group(0))
                i = m.end()
                continue
        elif c == "\n" and not in_dq and pending:
            line = "".join(out[line_start:])
            out.append("\n")
            pos = i + 1
            for delim, quoted in pending:
                body: list[str] = []
                while pos < n:
                    e = command.find("\n", pos)
                    e = n if e < 0 else e
                    ln = command[pos:e]
                    pos = e + 1
                    if ln.strip() == delim:
                        break
                    body.append(ln)
                heredocs.append(("\n".join(body), quoted, line))
            pending = []
            line_start = len(out)
            i = pos
            continue
        if c == "\n" and not in_dq:
            line_start = len(out) + 1
        out.append(c)
        i += 1
    return "".join(out), heredocs, substs


def _shell_inline(args: list[str]) -> str | None:
    """`bash -c STR`／`bash -lc STR` ⇒ STR；沒有 `-c` ⇒ None。"""
    seen_c = False
    for a in args:
        if not seen_c:
            if re.fullmatch(r"-[A-Za-z]*c[A-Za-z]*", a):
                seen_c = True
            continue
        if not a.startswith("-"):
            return a
    return None


def _reads_stdin(args: list[str]) -> bool:
    """直譯器沒有給腳本、也沒有 `-c`／`-m`：程式碼從標準輸入來（管線、heredoc、here-string）。"""
    return not [a for a in args if not a.startswith("-") or a == "-m"] or args[-1:] == ["-"]


def _code_hit(code: str, depth: int) -> tuple[str, str] | None:
    """一段內聯碼（`-c`／`-e` 字串、餵給直譯器的 heredoc／管線）是否在行使權威。

    規則：引到 `vacant_network.adapters.hook`（或從 `vacant_network.adapters` import hook）⇒ 偽造掛鉤；
    否則要同時引到 vacant_network 模組或 vacant CLI **且**有一個權威詞以獨立的字串字面值／識別字出現
    （例：`subprocess.run([sys.executable,"-m","vacant_network.cli","hook",…])` 裡逗號隔開的
    `"vacant_network.cli"` 與 `"hook"`）；或者碼裡有一個字串字面值本身就是一行叫 Vacant 權威的
    shell 指令（`os.system("vacant approve")`）。誠實邊界 1：這抬高成本，不是擋死。"""
    if _CODE_HOOK_RE.search(code):
        return ("hook", "hook")
    if _CODE_MOD_RE.search(code) or _CODE_CLI_RE.search(code):
        for m in _CODE_TOKEN_RE.finditer(code):
            w = m.group(1) or m.group(2)
            if w in _CODE_AUTHORITY:
                return ("authority", "intake serve" if w in ("intake", "serve")
                        else f"contract {w}" if w in ("lock", "init", "quick") else w)
    for m in _CODE_STR_RE.finditer(code):
        lit = m.group(1) if m.group(1) is not None else m.group(2)
        if lit and not lit.isidentifier():
            hit = _authority_verdict(lit, depth + 1, launchers=False)
            if hit is not None:
                return hit
    return None


def _authority_verdict(command: str, depth: int = 0, *,
                       launchers: bool = True) -> tuple[str, str] | None:
    """指令是否在行使別的權威 ⇒ `(rule, what)`；否則 None。字串層（誠實邊界 1）。

    `launchers=False`：只看每一段的命令位置，不把後面的 argv 元素當成被啟動的指令
    （用在程式碼的字串字面值上：`print("run vacant approve later")` 不是在叫 Vacant）。"""
    if depth > _MAX_DEPTH or not command:
        return None
    stripped, heredocs, substs = _shell_scan(command)
    for s in substs:                      # `$(…)`／反引號：在哪個位置都會被執行
        hit = _authority_verdict(s, depth + 1)
        if hit is not None:
            return hit
    toks = _tokens(stripped)
    shell_bodies: list[str] = []
    code_bodies: list[str] = []
    stdin_kinds: set[str] = set()
    for words, _redir in _segments(toks):
        for k in range(len(words) if launchers else min(1, len(words))):
            if k and not _maybe_command(words[k]):
                continue                  # 只有看起來像被啟動的指令才重算（長引數串不變成平方時間）
            # 被啟動的指令只看它後面的一小段 argv（子指令、`-c` 碼都在前面）
            cmd, args = _command_word(words[k:k + 64] if k else words)
            if not cmd:
                continue
            hit = _cli_hit(cmd, args)
            if hit is not None:
                return hit
            if cmd == "eval":
                shell_bodies.append(" ".join(args))
            elif _SHELL_RE.match(cmd):
                code = _shell_inline(args)
                if code is not None:
                    shell_bodies.append(code)
                elif k == 0 and _reads_stdin(args):
                    stdin_kinds.add("shell")
            elif _INTERP_RE.match(cmd):
                codes = [args[j + 1] for j, a in enumerate(args[:-1])
                         if _INLINE_FLAG_RE.fullmatch(a)]
                for code in codes:
                    code_bodies.append(code)
                    # 沒加引號的內聯碼（例：list 形式的 argv 被併成一行）會被分隔符切開：
                    # 從碼的開頭到指令結尾整段當成程式碼。有引號時只看那一個引數。
                    if not re.search("['\"]" + re.escape(code[:24]), stripped):
                        at = stripped.find(code[:24])
                        code_bodies.append(stripped[at:] if at >= 0 else stripped)
                if not codes and k == 0 and _reads_stdin(args):
                    stdin_kinds.add("code")
    # heredoc：餵給 shell／直譯器的內文照樣判斷；寫進檔案的只看它會被展開的命令替換
    for body, quoted, line in heredocs:
        if not quoted:
            for s in _shell_scan(body)[2]:
                hit = _authority_verdict(s, depth + 1)
                if hit is not None:
                    return hit
        for words, _redir in _segments(_tokens(line)):
            cmd, args = _command_word(words)
            if _SHELL_RE.match(cmd) and _reads_stdin(args):
                shell_bodies.append(body)
            elif _INTERP_RE.match(cmd) and _reads_stdin(args):
                code_bodies.append(body)
    # here-string（`bash <<< "…"`）：字面值就是直譯器讀到的程式碼
    for j, t in enumerate(toks[:-1]):
        if t == "<<<":
            seg = _segments(toks[:j])
            cmd = _command_word(seg[-1][0])[0] if seg else ""
            if _SHELL_RE.match(cmd):
                shell_bodies.append(toks[j + 1])
            elif _INTERP_RE.match(cmd):
                code_bodies.append(toks[j + 1])
    # 管線（`echo "…" | sh`、`printf '…' | python3`）：前面那些字面值就是直譯器讀到的程式碼
    if "shell" in stdin_kinds:
        shell_bodies.extend(t.replace("\\n", "\n") for t in toks
                            if t not in _SEPARATORS and any(ch.isspace() for ch in t))
    if "code" in stdin_kinds:
        code_bodies.append(stripped)
    for body in shell_bodies:
        hit = _authority_verdict(body, depth + 1)
        if hit is not None:
            return hit
    for body in code_bodies:
        hit = _code_hit(body, depth)
        if hit is not None:
            return hit
    return None


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
        verd = _authority_verdict(cmd)
        if verd is not None and verd[0] == "hook":
            # 掛鉤是 agent 平台自己呼叫的；在工作的那一方自己呼叫一次＝偽造病歷裡的一個事件
            # （例：一則「人打的」提示）。字串層：擋直接的寫法，擋不住繞路（誠實邊界 1）
            return HookDecision("deny", "Vacant: `vacant hook` is called by the agent platform "
                                        "itself, not from inside the session. Use `vacant check` "
                                        "to see where the deliverable stands.",
                                {"rule": "vacant_authority"})
        if verd is not None:
            what = verd[1]
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


def _rounds_file(session_id: str | None, contract=None) -> pathlib.Path:
    """輪數檔的鍵＝工作階段＋**這一份契約**：別的目錄裡一個過了的驗收不可以把這個專案的輪數歸零
    （2026-09-25 審查 loop#4：偽造一次別處的 Stop 就能重置）。"""
    sid = re.sub(r"[^A-Za-z0-9._-]", "_", session_id or "nosession")[:120]
    where = str(getattr(contract, "path", "") or "")
    tag = hashlib.sha256(where.encode()).hexdigest()[:12] if where else "nocontract"
    return vacant_state_dir() / "intake" / "hooks" / f"rounds_{sid}_{tag}.json"


def _bump_round(session_id: str | None, contract=None) -> int:
    p = _rounds_file(session_id, contract)
    n = 0
    try:
        n = int(json.loads(p.read_text()).get("n", 0))
    except (OSError, ValueError):
        n = 0
    n += 1
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"n": n, "t": time.time()}))
    return n


def new_request(session_id: str | None, contract=None) -> None:
    """人打了一個新的要求 ⇒ 回饋輪數重新算。輪數上限防的是「一個要求之內」agent 被無限推回去；
    互動介面裡前面幾個回合（人只是問問題、還沒要它交件）用掉的輪數，不可以讓之後真的寫錯時
    agent 收不到位置（2026-09-25 互動 TUI 實測時發現）。只有人打的那一則算——呼叫端負責分辨
    （`hook._person_prompt`）。
    ⚠ 分辨靠的是掛鉤事件的內容：agent 在殼層裡自己呼叫一次 `vacant hook …` 偽造一則「人打的」，
    同樣會重置（字串層的 `vacant hook` 擋得住直接的寫法、擋不住繞路，誠實邊界 1 那一類）。
    重置的後果是 agent 被多推回去幾輪，不會讓任何東西被收下。"""
    _rounds_file(session_id, contract).unlink(missing_ok=True)


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
            _rounds_file(ev.session_id, contract).unlink(missing_ok=True)   # 過了 ⇒ 新的輪數
            return HookDecision("allow", "", rec)
        n = _bump_round(ev.session_id, contract)
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
    n = _bump_round(ev.session_id, contract)
    rec["round"] = n
    if n > int(contract.hooks.get("max_feedback_rounds", 3)):
        rec["rounds_exhausted"] = True
        traced("feedback rounds used up; the agent stopped with these open")
        return HookDecision("allow", "", rec)
    t = traced(None)
    return HookDecision("continue", (t or {}).get("text") or feedback_text(res, contract), rec)
