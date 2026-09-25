"""blame — **追到造成錯誤的那一步**：錯的值 → 寫下它的那一步 → 重跑證明 → 它是從哪裡讀來的。

這支在架構裡承重什麼（`decisions/DECISION_20260924_ACCOUNTABLE_TRACE.md` §三、§4.5、§4.8 K7–K10；
LOOP §二-2）：

輸入是一個位置（`locate.py`：檔案、行、錯的值）與病歷（`recorder.py` 的簽章鏈）。步驟：

1. **誰把它寫進去的**：有行號時，把那一行沿著這個檔案的版本（每一步與每個缺口的前後版本）
   用逐行對齊往回追，找到**那一行**第一次帶著這個值出現的轉變（同一個值在別行出現、被別人加過又刪掉，
   都不算）；沒有行號時，找最後一次讓這個值的出現次數增加的轉變。它可能是一步、一個缺口
   （沒被記錄的改動），或是「第一次看到的時候就在了」。
2. **它從哪裡來**：那一步的行動者**在那之前觀察到**的東西裡找這個值——工具輸出（讀到的檔、指令輸出、
   搜尋結果、抓到的網頁、子 agent 的回覆）、它自己之前寫的內容、任務訊息、指令檔（`CLAUDE.md`、
   `AGENTS.md`：每一次請求都送給模型）。找到就往上追。殼層指令直接寫檔而指令字串裡沒有這個值 ⇒
   值是算出來的：看它用到的檔（資料裡有 ⇒ 追資料；腳本是這個工作階段寫的 ⇒ 寫腳本的那一步；
   腳本本來就在 ⇒ 輸入；跑了程式卻認不出是哪一支 ⇒ 推論層，不給事實層）。
3. **重跑**：直接寫下它的那一步，在重建出來的前後狀態上重跑同一條主張；之後不過、而且錯的值
   **就在那一行**、之前那一行沒有 ⇒ 事實層的證據。
4. **分級**（兩層，K9）：`provable`（事實層）／`lineage_exact`／`lineage_internal`／`heuristic`／`gap`；
   **過錯類別**另外標（K10）：`agent`／`input`／`unattributable`。結果狀態（K8）：
   `located`／`candidate_set`／`UNOBSERVED`／`UNKNOWN`。另外記「對的值那時候看不看得到」
   （`correct_value_seen`）：錯的值哪裡都沒有、對的值也沒看過，和「對的值看過了還寫錯」不是同一件事，
   報告分開寫（批判 §1.2 的 2×2）。

## 誠實邊界（改碼請保留）

1. 讀取是**下限**（DECISION §4.2）：「沒在觀察到的讀取裡找到來源」**單獨**永遠不構成 `provable`；
   `provable` 還要重跑翻轉，而且只給**直接寫下它**的那一步。往上追出來的都是推論層。
2. 值比對是逐字（數字依數值）：同一個值從兩個地方都讀得到時，取**最近**觀察到的那一個；
   巧合相同的值會被誤認成來源——所以往上追的結論都是推論層，不接任何重罰。
3. 平行的步驟、`post` 沒來的步驟、沒有 `pre` 的步驟、唯讀工具期間出現的寫入：寫入不確定是誰的 ⇒
   `candidate_set`。
4. 殼層指令執行中讀了哪些檔看不到；這裡只看**指令字串裡點名的**檔。
5. 模型上下文裡的其他東西（系統提示、記憶、之前的對話、工作區外的指令檔）看不到或只能事後讀
   現在的內容；使用者訊息只在平台有給（`UserPromptSubmit`）或 `vacant do` 自己送出時才看得到。
"""
from __future__ import annotations

import dataclasses
import difflib
import json
import os
import pathlib
import re
import shlex
import shutil
import tempfile
from typing import Any

from . import locate as L
from . import workspace as W
from .recorder import Recorder
from .tools import READ_ONLY, tool_kind

MAX_DEPTH = 8

_INTERPRETERS = {"python", "python3", "node", "bash", "sh", "zsh", "ruby", "perl", "deno", "bun",
                 "rscript", "php", "lua", "awk", "source", ".", "tsx", "ts-node", "npx", "uv",
                 "pipx", "poetry", "pytest", "make", "julia", "go", "cargo"}
_SCRIPT_EXT = {".py", ".js", ".mjs", ".cjs", ".ts", ".sh", ".bash", ".rb", ".pl", ".r", ".php",
               ".lua", ".jl", ".awk", ".sql"}
_REDIRECT = {">", ">>", "1>", "2>", "&>", "1>>", "2>>", "tee", "-o", "--output"}
#: 從網路抓東西的指令：值若來自它們抓回來的內容，是外部來源，不是 agent 自己算出來的
_NET_FETCH = {"curl", "wget", "http", "https", "xh", "aria2c", "httpie"}
#: 和抓網頁的指令接在一起也不會**造出**新值的過濾器（`grep -c`、`wc` 會算數，不在這裡）
_PASSTHROUGH = {"head", "tail", "grep", "egrep", "fgrep", "cat", "tee"}
#: 段首可以略過的前綴（環境變數設定另外處理）
_PREFIX_CMDS = {"sudo", "command", "env", "time", "nohup", "exec"}
#: 這些抓網頁的選項後面跟的是值，不是要抓的網址（代理、來源頁、標頭、上傳的內容…）
_FETCH_OPT_ARGS = {
    "-x", "--proxy", "-e", "--referer", "-H", "--header", "-A", "--user-agent", "-u", "--user",
    "-b", "--cookie", "-c", "--cookie-jar", "-d", "--data", "--data-raw", "--data-binary",
    "--data-urlencode", "--data-ascii", "--json", "-F", "--form", "--form-string", "-o",
    "--output", "-T", "--upload-file", "-w", "--write-out", "--resolve", "--connect-to", "-K",
    "--config", "-m", "--max-time", "--connect-timeout", "-X", "--request", "-r", "--range",
    "--retry", "--cacert", "--cert", "--key", "-E", "--interface", "--dns-servers",
    "--proxy-user", "-U", "--noproxy", "-O", "--output-document", "--output-file",
    "--post-data", "--post-file", "--body-data", "--body-file", "--execute", "-P",
    "--directory-prefix", "-t", "--tries", "--timeout", "--method", "--header-file",
    "--user-agent", "--load-cookies", "--save-cookies"}
_SEPARATORS = {";", "&&", "||", "|", "&", "|&", "(", ")"}
_VERSIONED_INTERP = re.compile(r"^(python|pypy|node|nodejs|ruby|perl|php|lua|julia|g?awk|mawk|"
                               r"nawk|deno|bun)[0-9.]*$")
#: 每一次請求都送給模型的指令檔（批判 §0-8：CLAUDE.md 在 8/8 次請求裡）
INSTRUCTION_FILES = ("CLAUDE.md", ".claude/CLAUDE.md", "CLAUDE.local.md", "AGENTS.md",
                     "GEMINI.md", ".cursorrules", ".github/copilot-instructions.md")
_GLOBAL_INSTRUCTIONS = (".claude/CLAUDE.md", ".codex/AGENTS.md", ".config/opencode/AGENTS.md",
                        ".pi/agent/AGENTS.md")
_FILE_LINE_RE = re.compile(r"([A-Za-z0-9_./-]+\.[A-Za-z0-9]+):([0-9]+)")


def _texts(obj: Any) -> list[str]:
    """JSON 形狀的工具輸出攤平成文字（字串與數字的葉子）。`json.dumps` 會把換行存成 `\\n`，
    行首或 tab 後的數字就配不到了（2026-09-24 審查 blame#2）。"""
    out: list[str] = []
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, bool) or obj is None:
        pass
    elif isinstance(obj, (int, float)):
        out.append(str(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            out += _texts(v)
    elif isinstance(obj, list):
        for v in obj:
            out += _texts(v)
    return out


def _as_text(raw: str) -> str:
    s = raw.strip()
    if s[:1] in ("{", "[", '"'):
        try:
            return "\n".join(_texts(json.loads(s)))
        except ValueError:
            pass
    return raw


@dataclasses.dataclass
class Step:
    seq: int
    n: int
    id: str
    actor: dict[str, Any]
    tool: str
    input_blob: str | None
    output_blob: str | None
    writes: list[dict[str, Any]]
    pre_index: str | None
    post_index: str | None
    error: str | None
    ambiguous: list[str]           # 為什麼寫入不確定是它的（空＝確定）
    conc: list[str] = dataclasses.field(default_factory=list)

    @property
    def ctx(self) -> tuple[str, str, str]:
        a = self.actor
        return (str(a.get("platform")), str(a.get("session")), str(a.get("agent") or ""))

    def brief(self) -> dict[str, Any]:
        return {"n": self.n, "step": self.id, "tool": self.tool, "actor": self.actor}


@dataclasses.dataclass
class Transition:
    seq: int
    kind: str                      # step｜gap
    step: Step | None
    before: str | None
    after: str | None
    paths: set[str]
    gap: dict[str, Any] | None = None


class Trace:
    """病歷的唯讀視圖：步驟、缺口、任一狀態的任一檔案內容。"""

    def __init__(self, rec: Recorder):
        self.rec = rec
        self.transitions: list[Transition] = []
        self.steps: list[Step] = []
        self.prompts: list[dict[str, Any]] = []
        self._idx: dict[str, W.Index] = {}
        self.initial: str | None = None
        self.scan_disabled: str | None = None
        #: 第一次完整觀察之前就有步驟在跑（專案太大、在背景看）：那時已經在的值不能說是「本來就在」
        self.unobserved_start = False
        #: 第一次看改到背景、還沒看完：到目前為止什麼都沒看到
        self.first_look_pending = False
        #: 讀不回來的狀態（版本庫被改過或壞了）：碰到它的追緝一律不歸給任何人
        self.unreadable: set[str] = set()
        seen_steps: set[str] = set()
        for e in rec.events():
            t = e.get("type")
            if t == "step":
                sid = str(e.get("step"))
                if sid in seen_steps:
                    # 掛鉤在「寫進鏈」與「存狀態」之間被砍 ⇒ 同一步之後又被收尾一次；留第一筆
                    continue
                seen_steps.add(sid)
                writes = e.get("writes") or []
                if e.get("writes_blob"):
                    try:
                        writes = json.loads(rec.blobs.get(e["writes_blob"]))
                    except (OSError, ValueError):
                        pass
                amb = []
                if e.get("concurrent_with"):
                    amb.append("concurrent with " + ", ".join(map(str, e["concurrent_with"])))
                if e.get("post_missing"):
                    amb.append(f"no post-tool event ({e['post_missing']})")
                if e.get("pre_missing"):
                    amb.append("no pre-tool event")
                if e.get("baseline_missing"):
                    amb.append("no earlier view of the workspace")
                kind = tool_kind(str(e.get("tool") or ""))
                if writes and kind in READ_ONLY:
                    amb.append(f"files changed while a read-only tool ({e.get('tool')}) ran")
                if writes and kind == "agent":
                    amb.append("files changed while a sub-agent ran, outside its recorded steps")
                s = Step(seq=int(e["seq"]), n=int(e.get("n") or 0), id=sid,
                         actor=dict(e.get("actor") or {}), tool=str(e.get("tool") or "?"),
                         input_blob=e.get("input_blob"), output_blob=e.get("output_blob"),
                         writes=list(writes), pre_index=e.get("pre_index"),
                         post_index=e.get("post_index"), error=e.get("error"), ambiguous=amb,
                         conc=[str(x) for x in e.get("concurrent_with") or []])
                self.steps.append(s)
                if self.initial is None and s.pre_index:
                    self.initial = s.pre_index
                if s.writes and not e.get("denied"):
                    self.transitions.append(Transition(s.seq, "step", s, s.pre_index,
                                                       s.post_index,
                                                       {str(w["path"]) for w in s.writes}))
            elif t == "unrecorded_change":
                changes = e.get("changes") or []
                if e.get("changes_blob"):
                    try:
                        changes = json.loads(rec.blobs.get(e["changes_blob"]))
                    except (OSError, ValueError):
                        pass
                if self.initial is None and e.get("before_index"):
                    self.initial = e["before_index"]
                self.transitions.append(Transition(
                    int(e["seq"]), "gap", None, e.get("before_index"), e.get("after_index"),
                    {str(c["path"]) for c in changes},
                    gap={"seq": e["seq"], "observed_at": e.get("observed_at"),
                         "paths": sorted({str(c["path"]) for c in changes})[:20]}))
            elif t == "prompt":
                self.prompts.append(e)
            elif t == "coverage" and e.get("scan_disabled"):
                self.scan_disabled = str(e["scan_disabled"])
            elif t == "coverage" and e.get("baseline_deferred"):
                self.first_look_pending = True
            elif t == "coverage" and isinstance(e.get("baseline"), dict):
                self.first_look_pending = False
                bl = e["baseline"]
                if bl.get("after_unobserved"):
                    self.unobserved_start = True
                if self.initial is None and bl.get("index"):
                    self.initial = bl["index"]
            elif t == "session_closed" and self.initial is None and e.get("final_index"):
                self.initial = e["final_index"]
        self._credit_delegated_writes()

    def _credit_delegated_writes(self) -> None:
        """委派呼叫（Agent／task／spawn…）自己不寫檔。它的前後差異裡若有一個版本，是另一個**真正的步驟**
        寫出來的同一個版本（平行的另一個子 agent 還在跑、比這個委派晚收尾），那個檔歸那一步，不歸委派呼叫
        （2026-09-24 情境 I：平行委派時，先結束的那個委派把兄弟子 agent 的寫入掃進了自己的差異）。"""
        # 只認「委派之後才收尾、而且做了**一模一樣**的改動（同一個路徑、同一個前版本、同一個後版本）」的步驟：
        # 只比後版本的話，一個剛好回到舊版本的改動（編輯器復原、沒被記到的步驟）會被接到很早以前寫過那個版本的
        # 步驟上，版本鏈就被接錯——後來無辜的步驟背「可證明」（2026-09-24 審查 credit#5–7）
        written: dict[tuple[str, str | None, str], list[Step]] = {}
        for s in self.steps:
            if tool_kind(s.tool) == "agent":
                continue
            for w in s.writes:
                if w.get("after") and w.get("after") != w.get("before"):
                    written.setdefault((str(w["path"]), w.get("before"), str(w["after"])),
                                       []).append(s)
        if not written:
            return
        for tr in self.transitions:
            d = tr.step
            if tr.kind != "step" or d is None or tool_kind(d.tool) != "agent":
                continue
            s = d
            claimed = {str(w["path"]) for w in s.writes
                       if any(x.seq > s.seq for x in written.get(
                           (str(w["path"]), w.get("before"), str(w.get("after"))), []))}
            if not claimed:
                continue
            tr.paths -= claimed
            s.writes = [w for w in s.writes if str(w["path"]) not in claimed]
            if not s.writes:
                s.ambiguous = [a for a in s.ambiguous
                               if not a.startswith("files changed while a sub-agent ran")]
        self.transitions = [tr for tr in self.transitions if tr.paths]

    # ── content access ───────────────────────────────────────────────
    def index(self, sha: str | None) -> W.Index:
        if not sha:
            return {}
        if sha not in self._idx:
            try:
                self._idx[sha] = self.rec.load_index(sha)
            except (OSError, ValueError):
                # 讀不回來 ≠ 空的工作區：記下來，追緝碰到它就不歸給任何人（審查：竄改一個關鍵幀
                # 曾經讓 provable 從真正寫的人移到後來的人身上）
                self.unreadable.add(sha)
                self._idx[sha] = {}
        return self._idx[sha]

    def file_text(self, index_sha: str | None, path: str) -> str | None:
        e = self.index(index_sha).get(path)
        if e is None or ":" in e.sha256:
            return None
        return self.blob_text(e.sha256)

    def blob_text(self, sha: str | None) -> str | None:
        if not sha:
            return None
        try:
            return self.rec.blobs.get(sha).decode("utf-8", "replace")
        except (OSError, ValueError):
            return None

    def input_text(self, s: Step) -> str:
        return _as_text(self.blob_text(s.input_blob) or "")

    def input_obj(self, s: Step) -> Any:
        try:
            return json.loads(self.blob_text(s.input_blob) or "")
        except ValueError:
            return {}

    def output_text(self, s: Step) -> str:
        return _as_text(self.blob_text(s.output_blob) or "")

    def latest_index(self) -> str | None:
        for t in reversed(self.transitions):
            if t.after:
                return t.after
        for s in reversed(self.steps):
            if s.post_index:
                return s.post_index
        return self.initial

    def materialize(self, index_sha: str | None, dest: pathlib.Path,
                    contract: Any = None) -> list[str]:
        """重建某一步的狀態。給契約 ⇒ 只重建繳付物（include／exclude）——收件口的驗證器也只看得到
        這些（`flow._verify_manifest` 只放 manifest 裡的檔）；整個工作區重建曾經讓 `command`
        類主張在追緝時看得到收件時看不到的檔，而且 4 萬個檔的專案每條主張要寫 8 萬個檔。"""
        idx = self.index(index_sha)
        if contract is not None:
            # 和 `artifact.collect` 同一套規則：符號連結不進隔離區、那幾個目錄永遠跳過
            from ..intake.artifact import ALWAYS_SKIP_DIRS, glob_to_regex
            inc = [glob_to_regex(p) for p in contract.include]
            exc = [glob_to_regex(p) for p in contract.exclude]
            idx = {r: e for r, e in idx.items()
                   if not e.sha256.startswith("link:")
                   and not ALWAYS_SKIP_DIRS.intersection(r.split("/")[:-1])
                   and any(x.match(r) for x in inc) and not any(x.match(r) for x in exc)}
        return W.materialize(idx, self.rec.blobs, dest)


# ── lineage ──────────────────────────────────────────────────────────

@dataclasses.dataclass
class Origin:
    kind: str       # agent｜input｜pre_existing｜external｜gap｜ambiguous｜unresolved｜unknown
    step: Step | None = None
    source: dict[str, Any] | None = None
    note: str = ""
    candidates: list[Step] = dataclasses.field(default_factory=list)


class Blamer:
    def __init__(self, trace: Trace, contract: Any = None):
        self.t = trace
        self.contract = contract
        self.inputs: dict[str, tuple[str, pathlib.Path]] = {}   # 工作區相對路徑 → (名字, 絕對路徑)
        self.intro_line: dict[str, int | None] = {}             # 「引入」的那個轉變之後，那一行在哪
        ws = trace.rec.workspace
        if contract is not None:
            for name in (contract.raw.get("inputs") or {}):
                try:
                    p = contract.input_path(name)
                except KeyError:
                    continue
                try:
                    rel = p.resolve().relative_to(ws).as_posix()
                except ValueError:
                    rel = str(p.resolve())
                self.inputs[rel] = (name, p)

    # 1. 誰把值放進這個檔 ------------------------------------------------
    def _versions(self, path: str, before_seq: int | None
                  ) -> list[tuple[Transition | str, str | None]]:
        out: list[tuple[Transition | str, str | None]] = [
            ("initial", self.t.file_text(self.t.initial, path))]
        for tr in self.t.transitions:
            if before_seq is not None and tr.seq >= before_seq:
                break
            if path in tr.paths:
                out.append((tr, self.t.file_text(tr.after, path)))
        return out

    def introducer(self, path: str, value: str, before_seq: int | None = None,
                   line: int | None = None) -> Transition | str | None:
        """回傳引入它的轉變；`"initial"`＝第一次看到時就在；None＝那時候不在。
        給 `line`（1 起算，最後一個版本裡的行號）⇒ 追**那一行**（逐行對齊往回）。"""
        vers = self._versions(path, before_seq)
        if line is not None:
            got = self._line_introducer(vers, value, line - 1)
            if got is not None:
                return got
        # 沒有行號（或行號對不上）：最後一次讓出現次數增加的轉變
        prev = len(L.occurrences(vers[0][1], value)) if vers[0][1] is not None else 0
        intro: Transition | str | None = "initial" if prev else None
        for tr, txt in vers[1:]:
            now = len(L.occurrences(txt, value)) if txt is not None else 0
            if now > prev:
                intro = tr
            elif now == 0:
                intro = None
            prev = now
        return intro

    def _line_introducer(self, vers: list[tuple[Transition | str, str | None]], value: str,
                         idx: int) -> Transition | str | None:
        last_txt = vers[-1][1]
        if last_txt is None:
            return None
        cur = last_txt.splitlines()
        if not (0 <= idx < len(cur)) or not L.contains(cur[idx], value):
            return None
        for k in range(len(vers) - 1, 0, -1):
            prev_txt = vers[k - 1][1]
            tag = vers[k][0]
            key = tag.seq if isinstance(tag, Transition) else -1
            self.intro_line[f"{key}"] = idx + 1
            if prev_txt is None:
                return tag
            prev = prev_txt.splitlines()
            mapped = None
            for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=prev, b=cur,
                                                               autojunk=False).get_opcodes():
                if not (j1 <= idx < j2):
                    continue
                if op == "equal":
                    mapped = i1 + (idx - j1)
                elif op == "replace":
                    # 那一行改過：舊區塊裡對應位置附近有這個值 ⇒ 值早就在，只是那一行被改寫
                    cands = [i for i in range(i1, i2) if L.contains(prev[i], value)]
                    if cands:
                        want = i1 + (idx - j1)
                        mapped = min(cands, key=lambda i: abs(i - want))
                break
            if mapped is None:
                return tag
            cur, idx = prev, mapped
        return "initial"

    # 2. 它從哪裡來 -------------------------------------------------------
    def sources(self, s: Step) -> list[tuple[str, Step | None, str, Any]]:
        """`s` 的行動者在 `s` 之前觀察到的東西，最近的在前：(種類, 步驟, 文字, 參照)。"""
        from ..adapters.hook import _paths_from
        out: list[tuple[str, Step | None, str, Any]] = []
        first_of_ctx: int | None = None
        for j in self.t.steps:
            if j.seq >= s.seq:
                break
            if j.ctx == s.ctx and first_of_ctx is None:
                first_of_ctx = j.seq
            if j.ctx != s.ctx:
                continue
            kind = tool_kind(j.tool)
            inp = self.t.input_obj(j)
            ref: Any = None
            if kind in ("read", "fetch", "write"):
                ps = _paths_from(inp)
                ref = ps[0] if ps else (inp.get("url") if isinstance(inp, dict) else None)
            elif kind == "shell":
                ref = _command(inp)
            out.append((kind, j, self.t.output_text(j), ref))
            if kind == "write":
                # 行動者自己之前寫的內容也是它「看過」的（blame#4）
                out.append(("own_write", j, self.t.input_text(j), ref))
        if s.actor.get("agent"):
            # 子 agent 的任務說明＝父 agent 叫它的那個工具呼叫的輸入
            exact = self._spawning_step(s) if any(
                p.get("agent") == s.actor.get("agent") and "spawned_by" in p
                for p in self.t.prompts) else None
            if exact is not None:
                out.append(("spawn_input", exact, self.t.input_text(exact), None))
            elif not any(p.get("agent") == s.actor.get("agent") and "spawned_by" in p
                         for p in self.t.prompts):
                for j in self.t.steps:
                    if j.seq >= (first_of_ctx or s.seq):
                        break
                    if tool_kind(j.tool) == "agent" and j.ctx[:2] == s.ctx[:2] and not j.ctx[2]:
                        out.append(("spawn_input", j, self.t.input_text(j), None))
        for p in self.t.prompts:
            if int(p.get("seq", 0)) >= s.seq:
                continue
            if str(p.get("session")) not in ("*", str(s.actor.get("session"))):
                continue
            src = str(p.get("source") or "user")
            if src not in _TASK_SOURCES:
                # Vacant 自己的回饋（引了錯值與應有的值）、agent 自己排的提示（它自己的話）、別的工作階段
                # 送來的訊息：都不是「任務說的」——當成來源就等於替 agent 洗掉錯（2026-09-25）
                continue
            if src == "parent_agent" and not s.actor.get("agent"):
                continue
            if src == "parent_agent" and p.get("agent") and p.get("agent") != s.actor.get("agent"):
                continue                       # 另一個子 agent 收到的任務說明
            kind = {"subagent_result": "subagent_result",
                    "parent_agent": "spawn_prompt"}.get(src, "prompt")
            fake_seq = int(p.get("seq", 0))
            out.append((kind, None, self.t.blob_text(p.get("text_blob")) or "",
                        {"seq": fake_seq, "tool_use_id": p.get("tool_use_id")}))
        out.sort(key=lambda x: -(x[1].seq if x[1] is not None else
                                 (x[3] or {}).get("seq", 0) if isinstance(x[3], dict) else 0))
        return out

    def _rel(self, ref: Any, cwd: str | None = None) -> str | None:
        if not ref or not isinstance(ref, str):
            return None
        ws = self.t.rec.workspace
        p = pathlib.Path(ref)
        base = ws / cwd if cwd else ws
        try:
            return (p if p.is_absolute() else base / p).resolve().relative_to(ws).as_posix()
        except (ValueError, OSError):
            return None

    def _referenced_files(self, s: Step) -> tuple[list[str], list[str], bool]:
        """指令字串點名的工作區檔案：`(讀的, 執行的, 有沒有跑程式)`。重導向的目標不算；
        `cd <dir> &&` 與工具輸入的 `workdir` 會改變相對路徑的基準；腳本＝直譯器／執行器的引數、
        `./x`、或副檔名／可執行位元像程式的檔（blame#1）。"""
        inp = self.t.input_obj(s)
        cmd = _command(inp) or ""
        cwd = inp.get("workdir") if isinstance(inp, dict) and isinstance(inp.get("workdir"),
                                                                        str) else None
        if cwd:
            cwd = self._rel(cwd)
        try:
            toks = shlex.split(cmd, posix=True)
        except ValueError:
            toks = cmd.split()
        idx = self.t.index(s.pre_index)
        reads: list[str] = []
        scripts: list[str] = []
        runs_code = False
        prev = ""
        after_interp = False
        for i, tok in enumerate(toks):
            base = pathlib.PurePosixPath(tok).name.lower()
            if base in _INTERPRETERS or _VERSIONED_INTERP.match(base):
                runs_code = True
                after_interp = True
            if tok in ("&&", ";", "||", "|"):
                after_interp = False
            if prev == "cd":
                cwd = self._rel(tok, cwd) or cwd
                prev = tok
                continue
            if prev in _REDIRECT or tok.startswith(">"):
                prev = tok
                continue
            for piece in tok.replace("=", " ").split():
                # `curl -d @draft.md`／`-F f=@draft.md`：上傳的是這個檔（審查 curl#4）
                rel = self._rel(piece.strip("'\"<>|;&()").lstrip("@"), cwd)
                if not rel or rel not in idx or rel in reads or rel in scripts:
                    continue
                e = idx[rel]
                is_script = after_interp or piece.startswith("./") or e.exec or \
                    pathlib.PurePosixPath(rel).suffix.lower() in _SCRIPT_EXT
                if is_script:
                    scripts.append(rel)
                    runs_code = True
                else:
                    reads.append(rel)
            if tok.startswith("-") or base in _INTERPRETERS:
                prev = tok
                continue
            prev = tok
            if i and after_interp and not tok.startswith("-") and base not in _INTERPRETERS:
                after_interp = False
        return reads, scripts, runs_code

    def _fetch_of(self, s: Step) -> dict[str, Any] | None:
        """這一步是不是**只是**抓網頁：每一段的指令字都是抓網頁的指令或不造新值的過濾器，而且至少有一段
        是抓網頁的。回 `{"urls": [...], "local": bool, "outputs": [...]}`；不是 ⇒ None。
        只看得到指令字串：代理、DNS、hosts 檔把名字指到哪裡看不到（誠實邊界）。"""
        cmd = _command(self.t.input_obj(s)) or ""
        try:
            lex = shlex.shlex(cmd.replace("\n", " ; "), posix=True, punctuation_chars=";&|()<>")
            lex.whitespace_split = True
            lex.commenters = "#"
            toks = list(lex)
        except ValueError:
            return None
        segs: list[list[str]] = [[]]
        for tok in toks:
            if tok in _SEPARATORS:
                segs.append([])
            else:
                segs[-1].append(tok)
        urls: list[str] = []
        outputs: list[str] = []
        local = False
        fetched = False
        for seg in segs:
            words = list(seg)
            while words and (re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0])
                             or words[0] in _PREFIX_CMDS):
                words.pop(0)
            if not words:
                continue
            head = pathlib.PurePosixPath(words[0]).name.lower()
            rest = words[1:]
            for i, w in enumerate(rest):                  # 重導向的目標
                if w in (">", ">>") and i + 1 < len(rest):
                    outputs.append(rest[i + 1])
            if head in _PASSTHROUGH:
                if head in ("grep", "egrep", "fgrep") and any(
                        w.startswith("-") and not w.startswith("--") and "c" in w
                        or w == "--count" for w in rest):
                    return None                           # 數出來的是新值
                # 過濾器自己讀了檔（`cat 筆記; curl …`）：輸出不全是抓回來的（審查 curl#1c）
                plain = [w for w in rest if not w.startswith("-") and not w.isdigit()
                         and w not in (">", ">>") and w not in outputs]
                allowed = 1 if head in ("grep", "egrep", "fgrep") else 0
                if head != "tee" and len(plain) > allowed:
                    return None
                continue
            if head not in _NET_FETCH:
                return None                               # 別的指令可能自己造出這個值
            fetched = True
            skip = False
            for i, w in enumerate(rest):
                if skip:
                    skip = False
                    continue
                if w in (">", ">>", "<"):
                    skip = True
                    continue
                if w in _FETCH_OPT_ARGS:
                    if w in ("-o", "--output", "-O", "--output-document") and i + 1 < len(rest):
                        outputs.append(rest[i + 1])
                    if w in ("--resolve", "--connect-to"):
                        local = True                      # 名字被指到別處：看不出是不是本機
                    skip = True
                    continue
                if w.startswith("-"):
                    if w.split("=", 1)[0] in ("--resolve", "--connect-to"):
                        local = True
                    continue
                urls.append(w)
        if not fetched or not urls:
            return None
        local = local or any(_is_local_url(u) for u in urls)
        return {"urls": urls, "local": local, "outputs": outputs}

    def _own_file_with(self, j: Step, value: str) -> str | None:
        """這個行動者在第 j 步之前自己寫過、而且那時含有這個值的檔（有的話）。"""
        for tr in reversed(self.t.transitions):
            if tr.seq >= j.seq or tr.step is None or tr.step.ctx != j.ctx:
                continue
            for p in sorted(tr.paths):
                txt = self.t.file_text(j.pre_index, p)
                if txt is not None and L.contains(txt, value):
                    return p
        return None

    def _last_writer(self, path: str, before_seq: int) -> Transition | None:
        last = None
        for tr in self.t.transitions:
            if tr.seq >= before_seq:
                break
            if path in tr.paths:
                last = tr
        return last

    def _pinned_ok(self, rel: str, index_sha: str | None) -> bool:
        """這個輸入在那個狀態下，是不是委託者釘住的那一版。"""
        if self.contract is None or rel not in self.inputs:
            return False
        pin = self.contract.input_pin(self.inputs[rel][0])
        e = self.t.index(index_sha).get(rel)
        return bool(pin and e is not None and e.sha256 == pin)

    def value_origin(self, path: str, value: str, chain: list[dict[str, Any]], *,
                     before_seq: int | None = None, depth: int = 0,
                     line: int | None = None) -> Origin:
        if depth > MAX_DEPTH:
            return Origin("unknown", note="lineage too deep")
        intro = self.introducer(path, value, before_seq, line=line)
        if intro is None:
            return Origin("unknown", note=f"{value!r} is not in {path} at that point")
        if intro == "initial" and self.t.unobserved_start:
            chain.append({"via": f"{path} already had it when Vacant first managed to look"})
            return Origin("gap", source={"observed_at": "baseline"},
                          note="steps ran before the first full view of the workspace")
        if intro == "initial":
            src = {"kind": "file", "path": path, **self._line_of(self.t.initial, path, value)}
            if path in self.inputs:
                name, _p = self.inputs[path]
                if self._pinned_ok(path, self.t.initial):
                    return Origin("input", source={**src, "kind": "input", "name": name},
                                  note="the pinned input already says this")
                return Origin("input", source={**src, "kind": "input", "name": name,
                                               "observed": False},
                              note="the input already said this when first seen, but it is not "
                                   "the pinned version")
            return Origin("pre_existing", source=src,
                          note="present before the first recorded step")
        assert isinstance(intro, Transition)
        if intro.kind == "gap":
            chain.append({"via": f"{path} changed with no recorded step", "gap": intro.gap})
            return Origin("gap", source=intro.gap, note="changed outside any recorded step")
        s = intro.step
        assert s is not None
        chain.append({**s.brief(), "via": f"wrote {path}"})
        if s.ambiguous:
            return Origin("ambiguous", step=s, note="; ".join(s.ambiguous),
                          candidates=[s, *self._concurrent(s)])
        return self.step_origin(s, value, chain, depth=depth, path=path)

    def _concurrent(self, s: Step) -> list[Step]:
        return [j for j in self.t.steps if j.id != s.id and (s.id in j.conc or j.id in s.conc)]

    def _line_of(self, index_sha: str | None, path: str, value: str) -> dict[str, Any]:
        txt = self.t.file_text(index_sha, path) or ""
        occ = L.occurrences(txt, value)
        return {"line": occ[0][0]} if occ else {}

    def step_origin(self, s: Step, value: str, chain: list[dict[str, Any]], *,
                    depth: int, path: str | None = None) -> Origin:
        if depth > MAX_DEPTH:
            return Origin("unknown", note="lineage too deep")
        typed = L.contains(self.t.input_text(s), value)
        if tool_kind(s.tool) == "shell" and not typed:
            # 值不在指令字串裡：可能是指令算出來的，也可能只是編碼過（`base64 -d`）——
            # 後者和直接打字一樣，往下看行動者之前觀察到什麼
            o = self._shell_origin(s, value, chain, depth, fallback=False, into=path)
            if o is not None:
                return o
        for kind, j, text, ref in self.sources(s):
            if not L.contains(text, value):
                continue
            if kind == "prompt":
                chain.append({"via": "the task message"})
                return Origin("input", source={"kind": "prompt"},
                              note="the value is in the task message")
            if kind == "subagent_result":
                return self._from_subagent_result(ref, value, chain, depth)
            if kind == "spawn_prompt":
                chain.append({"via": "the task the sub-agent was given"})
                parent = self._spawning_step(s)
                if parent is not None:
                    return self.step_origin(parent, value, chain, depth=depth + 1)
                return Origin("unresolved", note="the sub-agent's task carries it; the parent "
                                                 "call that gave it was not recorded")
            assert j is not None
            if kind == "own_write":
                chain.append({**j.brief(), "via": "its own earlier write"})
                return self.step_origin(j, value, chain, depth=depth + 1)
            if kind == "read":
                return self._from_read(j, ref, value, chain, depth)
            if kind == "fetch":
                chain.append({**j.brief(), "via": f"fetched {ref}"})
                return Origin("external", source={"kind": "url", "ref": ref, "step": j.n},
                              note="the fetched content says this")
            if kind == "agent":
                chain.append({**j.brief(), "via": "a sub-agent's reply"})
                sub = self._subagent_step(j, value)
                if sub is None:
                    return Origin("unresolved", source={"kind": "subagent_reply", "step": j.n},
                                  note="the sub-agent's reply carries it; its steps don't show "
                                       "where it came from")
                chain.append({**sub.brief(), "via": "the sub-agent's step that produced it"})
                return self.step_origin(sub, value, chain, depth=depth + 1)
            if kind == "spawn_input":
                chain.append({**j.brief(), "via": "the task the sub-agent was given"})
                return self.step_origin(j, value, chain, depth=depth + 1)
            if kind == "shell":
                chain.append({**j.brief(), "via": "a command's output"})
                if L.contains(self.t.input_text(j), value):
                    return self.step_origin(j, value, chain, depth=depth + 1)
                return self._shell_origin(j, value, chain, depth, in_output=True) or \
                    Origin("agent", step=j, note="the command itself produced the value")
            if kind in ("search", "write"):
                # 搜尋結果／寫檔工具的回覆：值其實來自工作區裡的某個檔
                f = self._file_with(j.pre_index, value, text)
                chain.append({**j.brief(), "via": f"the output of {j.tool}"})
                if f is not None:
                    return self.value_origin(f, value, chain, before_seq=j.seq, depth=depth + 1)
                if kind == "write":
                    return self.step_origin(j, value, chain, depth=depth + 1)
            else:
                chain.append({**j.brief(), "via": f"the output of {j.tool}"})
            return Origin("external", source={"kind": "tool_output", "tool": j.tool,
                                              "step": j.n},
                          note=f"{j.tool} returned it")
        inst = self._instruction_source(s, value)
        if inst is not None:
            chain.append({"via": f"the instruction file {inst['path']}"})
            return Origin("input", source=inst, note="an instruction file the agent is always "
                                                     "given says this")
        for rel, (name, p) in self.inputs.items():
            txt = self.t.file_text(self.t.initial, rel) if self._pinned_ok(rel, self.t.initial) \
                else None
            if txt is not None and L.contains(txt, value):
                return Origin("input", step=s, source={"kind": "input", "name": name,
                                                       "path": rel, "observed": False},
                              note="a pinned input has this value, but no recorded read "
                                   "shows it being read")
        return Origin("agent", step=s, note="no recorded read contains this value")

    def _from_read(self, j: Step, ref: Any, value: str, chain: list[dict[str, Any]],
                   depth: int) -> Origin:
        rel = self._rel(ref)
        chain.append({**j.brief(), "via": f"read {ref}"})
        if rel is not None:
            # 釘住的輸入也先看寫入歷史：agent 自己改過它，就不是「輸入說的」（blame#6）
            o = self.value_origin(rel, value, chain, before_seq=j.seq, depth=depth + 1)
            if o.kind != "unknown":
                return o
            if rel in self.inputs:
                name, _p = self.inputs[rel]
                return Origin("input", source={"kind": "input", "name": name, "path": rel,
                                               "observed": False},
                              note="the read shows it, but the recorded versions of the input "
                                   "do not")
            return o
        # 工作區外的檔：這個工作階段有沒有哪一步寫過它
        for w in reversed([x for x in self.t.steps if x.seq < j.seq]):
            if tool_kind(w.tool) != "write":
                continue
            from ..adapters.hook import _paths_from
            if isinstance(ref, str) and ref in _paths_from(self.t.input_obj(w)):
                chain.append({**w.brief(), "via": f"wrote {ref}"})
                return self.step_origin(w, value, chain, depth=depth + 1)
        return Origin("input", source={"kind": "file", "path": ref},
                      note="a file outside the workspace says this")

    def _file_with(self, index_sha: str | None, value: str, text: str) -> str | None:
        """搜尋結果裡點名的工作區檔案中，那時候真的含有這個值的那一個。"""
        idx = self.t.index(index_sha)
        for m in re.finditer(r"([A-Za-z0-9_./-]+\.[A-Za-z0-9]+)", text):
            rel = self._rel(m.group(1))
            if rel and rel in idx:
                txt = self.t.file_text(index_sha, rel)
                if txt is not None and L.contains(txt, value):
                    return rel
        return None

    def _instruction_source(self, s: Step, value: str) -> dict[str, Any] | None:
        for rel in INSTRUCTION_FILES:
            txt = self.t.file_text(s.pre_index, rel)
            if txt is not None and L.contains(txt, value):
                return {"kind": "instructions", "path": rel, **self._line_of(s.pre_index, rel,
                                                                              value)}
        home = pathlib.Path(os.path.expanduser("~"))
        for rel in _GLOBAL_INSTRUCTIONS:
            try:
                txt = (home / rel).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if L.contains(txt, value):
                return {"kind": "instructions", "path": f"~/{rel}", "observed": False}
        return None

    def _shell_origin(self, j: Step, value: str, chain: list[dict[str, Any]],
                      depth: int, *, fallback: bool = True,
                      in_output: bool = False, into: str | None = None) -> Origin | None:
        """殼層指令產生的值從哪裡來。`in_output`＝這個值出現在這一步**有紀錄的輸出**裡；
        `into`＝正在追的那個檔（這一步寫了它，值不在指令字串裡）。"""
        reads, scripts, runs_code = self._referenced_files(j)
        for f in reads + scripts:
            txt = self.t.file_text(j.pre_index, f)
            if txt is not None and L.contains(txt, value):
                chain.append({**j.brief(), "via": f"the command read {f}"})
                return self.value_origin(f, value, chain, before_seq=j.seq, depth=depth + 1)
        for f in scripts:
            tr = self._last_writer(f, j.seq)
            if tr is not None and tr.kind == "step" and tr.step is not None:
                chain.append({**tr.step.brief(), "via": f"wrote {f}, which the command ran"})
                if tr.step.ambiguous:
                    return Origin("ambiguous", step=tr.step, note="; ".join(tr.step.ambiguous),
                                  candidates=[tr.step])
                return Origin("agent", step=tr.step,
                              note=f"{f} (written at step {tr.step.n}) computed the value")
            if tr is not None and tr.kind == "gap":
                chain.append({"via": f"{f} changed with no recorded step", "gap": tr.gap})
                return Origin("gap", source=tr.gap, note=f"{f} changed outside any step")
            if tr is None and self.t.unobserved_start:
                # 背景才看到第一眼：「沒有紀錄的步驟寫過它」不等於「本來就在」
                chain.append({**j.brief(), "via": f"ran {f}, which was already there when "
                                                  f"Vacant first managed to look"})
                return Origin("gap", source={"observed_at": "baseline", "path": f},
                              note="steps ran before the first full view of the workspace")
            if tr is None:
                chain.append({**j.brief(), "via": f"ran {f}, which no recorded step wrote"})
                return Origin("pre_existing", source={"kind": "file", "path": f},
                              note=f"{f} was already there and computed the value")
        fetch = None if runs_code else self._fetch_of(j)
        if fetch is not None:
            for kind, w, text, _ref in self.sources(j):
                if kind == "own_write" and w is not None and L.contains(text, value):
                    # 這個行動者自己之前打過這個值（寫到工作區外面也算）：不是網頁說的
                    chain.append({**w.brief(), "via": "its own earlier write"})
                    return self.step_origin(w, value, chain, depth=depth + 1)
            own = self._own_file_with(j, value)
            if own is not None:
                # 抓回來的內容也在這個行動者自己之前寫過的檔裡（上傳再抓回來、貼到外面再抓回來）
                chain.append({**j.brief(), "via": f"fetched it, and {own} (its own file) says it"})
                return self.value_origin(own, value, chain, before_seq=j.seq, depth=depth + 1)
            urls = fetch["urls"]
            carried = in_output or (into is not None and into in fetch["outputs"])
            if carried and fetch["local"]:
                # 這台機器上的伺服器（可能就是 agent 自己開的）：不是外部來源，也說不出是誰算的
                chain.append({**j.brief(), "via": f"fetched {urls[0]} from this machine"})
                return Origin("unresolved", step=j,
                              note="fetched from a server on this machine, which the agent may "
                                   "run itself")
            if carried:
                # `curl <網址>`：值是抓回來的內容，不是 agent 算的（2026-09-24 情境 F）。
                # 值就在有紀錄的輸出裡 ⇒ 和抓網頁的工具同級；輸出直接導進這個檔（沒紀錄）⇒ 只是推論；
                # 抓了好幾個網址 ⇒ 說不出是哪一個，也只是推論
                exact = in_output and len(urls) == 1
                chain.append({**j.brief(), "via": f"fetched {urls[0]}"})
                src: dict[str, Any] = {"kind": "url", "ref": urls[0], "step": j.n,
                                       "observed": exact}
                if len(urls) > 1:
                    src["candidates"] = urls
                return Origin("external", source=src,
                              note="the fetched content says this" if exact else
                              "the command only fetched pages; which one holds the value was "
                              "not recorded")
        if runs_code:
            # 跑了程式卻認不出是哪一支：不可以歸成「指令自己產生的」事實層
            return Origin("unresolved", step=j,
                          note="the command ran code Vacant could not resolve to a file")
        if not fallback:
            return None
        return Origin("agent", step=j, note="the command itself produced the value")

    def _subagent_step(self, j: Step, value: str) -> Step | None:
        out = self.t.output_text(j)
        subs = [s for s in self.t.steps if s.seq < j.seq and s.actor.get("agent")
                and s.ctx[:2] == j.ctx[:2]]
        named = [s for s in subs if str(s.actor.get("agent")) in out]
        pool = named or subs
        for s in reversed(pool):
            if L.contains(self.t.input_text(s), value) or L.contains(self.t.output_text(s), value) \
                    or any(L.contains(self.t.file_text(s.post_index, str(w["path"])) or "", value)
                           for w in s.writes):
                return s
        return None

    def _from_subagent_result(self, ref: Any, value: str, chain: list[dict[str, Any]],
                              depth: int) -> Origin:
        """Claude 背景子 agent 的結果以 `<task-notification>` 的「使用者訊息」送回（blame#5）。"""
        tid = (ref or {}).get("tool_use_id") if isinstance(ref, dict) else None
        spawn = next((x for x in self.t.steps if tid and x.id == tid), None)
        chain.append({"via": "a sub-agent's result"})
        if spawn is not None:
            sub = self._subagent_step(dataclasses.replace(spawn, seq=1 << 62), value)
            if sub is not None:
                chain.append({**sub.brief(), "via": "the sub-agent's step that produced it"})
                return self.step_origin(sub, value, chain, depth=depth + 1)
        return Origin("unresolved", source={"kind": "subagent_reply"},
                      note="a sub-agent's result carries it; its steps don't show where it came "
                           "from")

    def _spawning_step(self, s: Step) -> Step | None:
        agent = s.actor.get("agent")
        for p in self.t.prompts:               # 記下來的：叫它出來的那一步（可能在它之後才寫進鏈）
            if agent and p.get("agent") == agent and p.get("spawned_by"):
                hit = next((x for x in self.t.steps if x.id == p["spawned_by"]), None)
                if hit is not None:
                    return hit
            if agent and p.get("agent") == agent and "spawned_by" in p:
                return None                    # 對不到（或對到好幾個）：不猜
        first = next((x for x in self.t.steps if x.ctx == s.ctx), s)
        cands = [x for x in self.t.steps if x.seq < first.seq and tool_kind(x.tool) == "agent"
                 and x.ctx[:2] == s.ctx[:2] and not x.ctx[2]]
        return cands[-1] if cands else None

    def correct_seen(self, s: Step | None, expected: str | None) -> dict[str, Any] | None:
        """對的值在寫錯的那一步之前看不看得到（報告用；不影響等級）。"""
        if s is None or not expected:
            return None
        for kind, j, text, _ref in self.sources(s):
            if L.contains(text, expected):
                return {"seen": True, "step": j.n if j is not None else None, "via": kind}
        return {"seen": False}


def _command(inp: Any) -> str | None:
    from ..adapters.hook import _command_from
    return _command_from(inp)


def _local_addresses() -> set[str]:
    """這台機器自己的位址（盡力而為：主機名稱解析出來的＋預設路由那張網卡的）。"""
    import socket
    out = {"127.0.0.1", "::1", "0.0.0.0", "::"}
    try:
        name = socket.gethostname()
        out.add(name.lower())
        for fam in (socket.AF_INET, socket.AF_INET6):
            try:
                out.update(str(a[4][0]) for a in socket.getaddrinfo(name, None, fam))
            except OSError:
                pass
    except OSError:
        pass
    try:                                     # UDP connect 不送封包，只問核心會用哪一張網卡
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sk:
            sk.connect(("192.0.2.1", 9))
            out.add(sk.getsockname()[0])
    except OSError:
        pass
    return out


_LOCAL: set[str] | None = None


def _is_local_url(url: str) -> bool:
    """網址指到這台機器（agent 自己開的伺服器也在這裡）⇒ 不能當外部來源。"""
    global _LOCAL
    from urllib.parse import urlsplit
    u = url if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", url) else "http://" + url
    try:
        parts = urlsplit(u)
        host = (parts.hostname or "").lower()
    except ValueError:
        return True
    if parts.scheme.lower() == "file" or not host:
        return True
    if host == "localhost" or host.endswith(".localhost") or host.startswith("127."):
        return True
    if _LOCAL is None:
        _LOCAL = _local_addresses()
    return host in _LOCAL


# ── the verdict ──────────────────────────────────────────────────────

def _grade(origin: Origin, direct: bool, flip: dict[str, Any] | None) -> tuple[str, str, str]:
    """(狀態, 過錯類別, 等級)。"""
    if origin.kind == "gap":
        return "UNOBSERVED", "unattributable", "gap"
    if origin.kind == "ambiguous":
        return "candidate_set", "agent", "heuristic"
    if origin.kind == "unknown":
        return "UNKNOWN", "unattributable", "heuristic"
    if origin.kind == "unresolved":
        return "located", "agent", "heuristic"
    if origin.kind in ("input", "pre_existing", "external"):
        observed = (origin.source or {}).get("observed", True)
        return "located", "input", "lineage_exact" if observed else "heuristic"
    # agent
    if origin.step is None:
        return "located", "agent", "heuristic"
    if direct and flip and flip.get("flipped"):
        return "located", "agent", "provable"
    return "located", "agent", "lineage_internal" if not direct else "heuristic"


class _Seen:
    """這條主張看得到的檔：契約的繳付物規則（include／exclude）＋主張自己點名的路徑。"""

    def __init__(self, contract: Any, claim: Any):
        from ..intake.artifact import matches
        self._m = matches
        self.inc = list(contract.include) if contract is not None else ["**"]
        for k in ("path", "report", "sources", "csv"):
            v = (getattr(claim, "params", {}) or {}).get(k)
            if isinstance(v, str) and not v.startswith("input:"):
                self.inc.append(v)
        self.exc = list(contract.exclude) if contract is not None else []

    def sees(self, rel: str) -> bool:
        return bool(self._m(rel, self.inc)) and not self._m(rel, self.exc)


def rerun_flip(trace: Trace, contract: Any, claim_id: str, step: Step, loc: L.Location,
               *, sandbox: str = "auto", line_after: int | None = None) -> dict[str, Any]:
    """在第 k 步之前與之後重建出來的狀態上重跑主張。`flipped`＝之後不過而且錯的值就在**那一行**、
    之前那一行沒有這個值；重建不出來的檔只算這條主張看得到的那些（blame#10）。"""
    from . import rerun
    claim = rerun.claim_by_id(contract, claim_id)
    sees = _Seen(contract, claim)
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="vacant-blame-"))
    try:
        out: dict[str, Any] = {"claim": claim_id, "verifier": claim.verifier, "step": step.n,
                               "line": line_after}
        for tag, sha in (("before", step.pre_index), ("after", step.post_index)):
            d = tmp / tag
            missing = [m for m in trace.materialize(sha, d, contract) if sees.sees(m)]
            r = rerun.run(contract, d, [claim_id], sandbox=sandbox)[0]
            locs = L.locate(claim, r, d)
            if tag == "before" and line_after is not None:
                # 逐行對齊已經確定那一行是這一步才帶著這個值出現的；別行的同一個值不算
                hit = False
            else:
                hit = any(x.path == loc.path and x.value is not None and loc.value is not None
                          and L.contains(x.value, loc.value)
                          and (line_after is None or x.line is None or x.line == line_after)
                          for x in locs)
            out[tag] = {"status": r["status"], "value_here": hit,
                        "state_index": sha, "unrebuildable": missing[:5]}
        b, a = out["before"], out["after"]
        out["flipped"] = bool(a["status"] == "FAIL" and a["value_here"] and not b["value_here"]
                              and not a["unrebuildable"])
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def blame_location(trace: Trace, loc: L.Location, *, contract: Any = None,
                   claim_id: str | None = None, sandbox: str = "auto",
                   expected: str | None = None) -> dict[str, Any]:
    """一個位置 → 一個追緝結論（dict，可直接進鏈與報告）。"""
    res = _blame_location(trace, loc, contract=contract, claim_id=claim_id, sandbox=sandbox,
                          expected=expected)
    if trace.unreadable and res.get("state") not in ("UNOBSERVED",):
        # 有記下來的狀態讀不回來（版本庫被改過或壞了）：沿著版本往回追的結論都可能被換掉，
        # 不歸給任何人（竄改一個關鍵幀曾經把 provable 移到另一個行動者身上）
        res.update(state="UNOBSERVED", fault_class="unattributable", confidence="gap",
                   layer="inference", step=None,
                   note=f"{len(trace.unreadable)} recorded workspace state(s) can no longer be "
                        f"read (the store was changed or damaged)")
        res.pop("candidates", None)
        res.pop("correct_value_seen", None)
    return res


def _blame_location(trace: Trace, loc: L.Location, *, contract: Any = None,
                    claim_id: str | None = None, sandbox: str = "auto",
                    expected: str | None = None) -> dict[str, Any]:
    b = Blamer(trace, contract)
    chain: list[dict[str, Any]] = []
    value = loc.value
    if value is None and loc.line is not None:
        txt = trace.file_text(trace.latest_index(), loc.path) or ""
        lines = txt.splitlines()
        value = lines[loc.line - 1].strip() if 0 < loc.line <= len(lines) else None
    res: dict[str, Any] = {"location": loc.to_json(), "claim": claim_id}
    if trace.scan_disabled:
        # 工作區太大、不再逐步掃描：寫入都是「不知道」，不可以歸給任何人（recorder#9）
        res.update(state="UNOBSERVED", fault_class="unattributable", confidence="gap",
                   layer="inference", step=None, chain=[], value=value,
                   note=f"the workspace was not observed step by step ({trace.scan_disabled})")
        return res
    if trace.first_look_pending:
        # 第一次看還在背景：什麼都還沒看到，不可以說「那時候那裡沒有這個值」（大專案審查 #3）
        res.update(state="UNOBSERVED", fault_class="unattributable", confidence="gap",
                   layer="inference", step=None, chain=[], value=value,
                   note="the workspace has not been observed yet (the first full look is still "
                        "running in the background)")
        return res
    if not value or loc.kind == "missing":
        # 缺的東西沒有值可追：最後寫這個檔的是誰（推論層）
        last = b._last_writer(loc.path, 1 << 62)
        if last is None and trace.unobserved_start:
            res.update(state="UNOBSERVED", fault_class="unattributable", confidence="gap",
                       layer="inference", step=None, chain=[],
                       note="no observed step wrote this file, and steps ran before the first "
                            "full view of the workspace")
        elif last is None:
            res.update(state="UNKNOWN", fault_class="unattributable", confidence="heuristic",
                       layer="inference", step=None, chain=[],
                       note="nothing recorded wrote this file")
        elif last.kind == "gap":
            res.update(state="UNOBSERVED", fault_class="unattributable", confidence="gap",
                       layer="inference", step=None, chain=[{"gap": last.gap}],
                       note="the last change to this file was not recorded")
        else:
            assert last.step is not None
            res.update(state="located", fault_class="agent", confidence="heuristic",
                       layer="inference", step=last.step.brief(),
                       chain=[{**last.step.brief(), "via": f"last wrote {loc.path}"}],
                       note="something required is missing; this step wrote the file last")
        return res
    origin = b.value_origin(loc.path, value, chain, line=loc.line)
    direct = origin.kind == "agent" and origin.step is not None and bool(chain) and \
        chain[0].get("step") == origin.step.id and len([c for c in chain if "step" in c]) == 1
    flip = None
    if direct and contract is not None and claim_id is not None:
        assert origin.step is not None
        try:
            flip = rerun_flip(trace, contract, claim_id, origin.step,
                              dataclasses.replace(loc, value=value), sandbox=sandbox,
                              line_after=b.intro_line.get(f"{origin.step.seq}")
                              if loc.line is not None else None)
        except (KeyError, OSError, ValueError) as e:
            flip = {"error": str(e)[:200]}
    state, fault, conf = _grade(origin, direct, flip)
    res.update(state=state, fault_class=fault, confidence=conf,
               layer="fact" if conf == "provable" else "inference",
               step=origin.step.brief() if origin.step is not None else None,
               source=origin.source, chain=chain, note=origin.note, value=value)
    if flip is not None:
        res["rerun"] = flip
    if origin.candidates:
        res["candidates"] = [c.brief() for c in origin.candidates]
    if fault == "agent" and expected:
        seen = b.correct_seen(origin.step, expected)
        if seen is not None:
            res["correct_value_seen"] = seen
    return res


def _fallback_locations(claim: Any, r: dict[str, Any], state_dir: pathlib.Path,
                        contract: Any) -> list[L.Location]:
    """定位器找不到位置時：細節裡點名的「成果裡的檔:行」；再不然，繳付物的每一個檔（缺的東西）。"""
    from . import rerun
    inputs = []
    for name in (contract.raw.get("inputs") or {}) if contract is not None else []:
        try:
            inputs.append(contract.input_path(name).resolve())
        except KeyError:
            continue
    sd = pathlib.Path(state_dir).resolve()

    def is_input(rel: str) -> bool:
        p = (sd / rel).resolve()
        base = pathlib.Path(contract.base_dir).resolve() / rel if contract is not None else p
        return any(q == x or x in q.parents for x in inputs for q in (p, base))

    # 驗收套件本身（釘住的輸入）不是繳付物：錯在成果，不在檢查腳本（blame#9）
    files = [f["path"] for f in rerun.manifest_of(contract, state_dir)["files"]
             if not is_input(f["path"])]
    out = []
    for m in _FILE_LINE_RE.finditer(str(r.get("detail") or "")):
        rel, ln = m.group(1), int(m.group(2))
        cands = [f for f in files if f == rel or f.endswith("/" + rel)]
        if cands:
            out.append(L.Location(cands[0], ln, note="named in the check's output"))
    if out:
        return out
    p = (getattr(claim, "params", {}) or {})
    named = p.get("path") or p.get("report")
    if isinstance(named, str) and not any(ch in named for ch in "*?["):
        return [L.Location(named, kind="missing", note=str(r.get("detail"))[:200])]
    return [L.Location(f, kind="missing", note=str(r.get("detail"))[:200]) for f in files[:5]]


#: 病歷裡可以當成值的來源的提示：人打的、`vacant do` 交給 agent 的任務（`Recorder.prompt` 的 docstring：
#: 「`user`／`vacant do`＝任務給的」）、子 agent 的結果、父 agent 給子 agent 的任務。其餘（Vacant 自己的回饋、
#: agent 自己排的提示、別的工作階段的信封）一律不是
_TASK_SOURCES = frozenset({"user", "vacant do", "subagent_result", "parent_agent"})


def _allowed_paths(contract: Any, d: pathlib.Path) -> frozenset[str] | None:
    """餵給 `L.locate` 的 `allowed`：這條主張看得到的繳付物相對路徑集合（契約的
    include／exclude，和收件口的隔離區同一套規則）。`contract` 沒給 ⇒ None（退回舊行為，
    只在呼叫端自己保證 `d` 已經是繳付物範圍時安全）。"""
    if contract is None:
        return None
    from . import rerun
    return frozenset(f["path"] for f in rerun.manifest_of(contract, d)["files"])


def locate_results(contract: Any, results: list[dict[str, Any]], adir: str | pathlib.Path,
                   *, max_per_claim: int = 5) -> list[dict[str, Any]]:
    """沒有病歷時（HTTP 收件口、人工上傳：交來的只有檔案，沒有任何一步）：只做定位——每一條**不過**的
    主張在交來的檔案裡的位置、錯的值、應有的值。**沒有步驟、沒有行動者、沒有來源**；形狀和 `blame_results`
    的結論相同（`feedback.render_agent` 直接吃），缺的欄位就是「不知道」。"""
    from . import rerun
    d = pathlib.Path(adir)
    allowed = _allowed_paths(contract, d)
    out = []
    for r in results:
        if r.get("status") != "FAIL":
            continue
        try:
            claim = rerun.claim_by_id(contract, str(r["claim_id"]))
        except KeyError:
            continue
        found = L.locate(claim, r, d, allowed=allowed)
        locs = [x for x in found if x.kind != "source"] or \
            _fallback_locations(claim, r, d, contract)
        sources = [x.to_json() for x in found if x.kind == "source"]
        for loc in locs[:max_per_claim]:
            b: dict[str, Any] = {"claim": str(r["claim_id"]), "location": loc.to_json(),
                                 "value": loc.value, "detail": r.get("detail"),
                                 "hidden": bool(getattr(claim, "hidden", False)),
                                 "required": bool(r.get("required", True)),
                                 "state": "located" if loc.line else "file"}
            if sources:
                b["expected"] = sources
            out.append(b)
    return out


def blame_results(rec: Recorder, contract: Any, results: list[dict[str, Any]],
                  state_dir: str | pathlib.Path, *, sandbox: str = "auto",
                  max_per_claim: int = 5) -> list[dict[str, Any]]:
    """每一條**不過**的主張：定位 → 追緝。UNKNOWN／CONFLICT 不追（那不是繳付物的錯：
    驗證器、證據或人還沒到位）。"""
    from . import rerun
    trace = Trace(rec)
    sd = pathlib.Path(state_dir)
    allowed = _allowed_paths(contract, sd)
    out = []
    for r in results:
        if r.get("status") != "FAIL":
            continue
        try:
            claim = rerun.claim_by_id(contract, str(r["claim_id"]))
        except KeyError:
            continue
        found = L.locate(claim, r, sd, allowed=allowed)
        locs = [x for x in found if x.kind != "source"]
        sources = [x.to_json() for x in found if x.kind == "source"]
        if not locs:
            locs = _fallback_locations(claim, r, sd, contract)
        expected = next((s.get("value") for s in sources if s.get("value") is not None), None)
        for loc in locs[:max_per_claim]:
            b = blame_location(trace, loc, contract=contract, claim_id=str(r["claim_id"]),
                               sandbox=sandbox, expected=expected)
            b["detail"] = r.get("detail")
            b["hidden"] = bool(getattr(claim, "hidden", False))
            b["required"] = bool(r.get("required", True))
            if sources:
                b["expected"] = sources
            out.append(b)
    return out
