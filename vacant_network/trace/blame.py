"""blame — **追到造成錯誤的那一步**：錯的值 → 寫下它的那一步 → 重跑證明 → 它是從哪裡讀來的。

這支在架構裡承重什麼（`decisions/DECISION_20260924_ACCOUNTABLE_TRACE.md` §三、§4.5、§4.8 K7–K10；
LOOP §二-2）：

輸入是一個位置（`locate.py`：檔案、行、錯的值）與病歷（`recorder.py` 的簽章鏈）。步驟：

1. **誰把它寫進去的**：沿著這個檔案的寫入歷史（每一步與每個缺口的前後版本），找出最後一次
   「之前沒有這個值、之後有」的那一個轉變。它可能是一步、一個缺口（沒被記錄的改動），
   或是「第一次看到的時候就在了」（輸入）。
2. **它從哪裡來**：那一步的行動者**在那之前觀察到**的東西（工具輸出：讀到的檔、指令輸出、
   抓到的網頁、子 agent 的回覆）裡找這個值；找到就往上追（讀到的檔 ⇒ 那個檔的寫入歷史；
   子 agent 回覆 ⇒ 子 agent 的步驟；指令輸出 ⇒ 那個指令與它用到的腳本）。殼層指令直接寫檔而
   指令字串裡沒有這個值 ⇒ 值是算出來的：看它用到的檔（資料裡有這個值 ⇒ 追資料；
   腳本是這個工作階段寫的 ⇒ 寫腳本的那一步）。
3. **重跑**：直接寫下它的那一步，在重建出來的前後狀態上重跑同一條主張；之後不過、而且錯的值
   就在那個位置 ⇒ 事實層的證據。
4. **分級**（兩層，K9）：`provable`（事實層）／`lineage_exact`／`lineage_internal`／`heuristic`／`gap`；
   **過錯類別**另外標（K10）：`agent`／`input`／`unattributable`／`suite_or_verifier`。
   結果狀態（K8）：`located`／`candidate_set`／`UNOBSERVED`／`UNKNOWN`。

## 誠實邊界（改碼請保留）

1. 讀取是**下限**（DECISION §4.2）：「沒在觀察到的讀取裡找到來源」**單獨**永遠不構成 `provable`；
   `provable` 還要重跑翻轉，而且只給**直接寫下它**的那一步。往上追出來的都是推論層。
2. 值比對是逐字（數字依數值）：同一個值從兩個地方都讀得到時，取**最近**觀察到的那一個；
   巧合相同的值會被誤認成來源——所以往上追的結論都是推論層，不接任何重罰。
3. 平行的步驟、`post` 沒來的步驟、沒有 `pre` 的步驟：寫入不確定是誰的 ⇒ `candidate_set`。
4. 殼層指令執行中讀了哪些檔看不到；這裡只看**指令字串裡點名的**檔。
5. 模型上下文本來就有的東西（系統提示、記憶、之前的對話）看不到；使用者訊息只在平台有給
   （`UserPromptSubmit`）或 `vacant do` 自己送出時才看得到。
"""
from __future__ import annotations

import dataclasses
import json
import pathlib
import shlex
import shutil
import tempfile
from typing import Any

from . import locate as L
from . import workspace as W
from .recorder import Recorder

MAX_DEPTH = 8
MAX_FLIP_EVALS = 24

_READ = {"read", "view", "cat", "notebookread", "read_file", "readfile", "open"}
_WRITE = {"write", "edit", "multiedit", "apply_patch", "notebookedit", "str_replace",
          "create", "patch", "write_file", "replace"}
_SHELL = {"bash", "shell", "exec_command", "local_shell", "powershell", "run_shell_command",
          "shell_command", "exec"}
_AGENT = {"agent", "task", "spawn_agent", "collaborationspawn_agent", "wait_agent",
          "multi_agent_v1wait_agent", "collaborationwait_agent", "subagent"}
_INTERPRETERS = {"python", "python3", "node", "bash", "sh", "zsh", "ruby", "perl", "deno", "bun",
                 "Rscript", "php", "lua", "awk", "source", "."}


def tool_kind(tool: str | None) -> str:
    t = (tool or "").lower()
    if t in _READ:
        return "read"
    if t in _WRITE:
        return "write"
    if t in _SHELL:
        return "shell"
    if t in _AGENT:
        return "agent"
    if any(h in t for h in ("fetch", "web", "http", "browse", "url", "search")):
        return "fetch"
    return "other"


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
        for e in rec.events():
            t = e.get("type")
            if t == "step":
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
                s = Step(seq=int(e["seq"]), n=int(e.get("n") or 0), id=str(e.get("step")),
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

    # ── content access ───────────────────────────────────────────────
    def index(self, sha: str | None) -> W.Index:
        if not sha:
            return {}
        if sha not in self._idx:
            try:
                self._idx[sha] = self.rec.load_index(sha)
            except (OSError, ValueError):
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
        return self.blob_text(s.input_blob) or ""

    def input_obj(self, s: Step) -> Any:
        try:
            return json.loads(self.input_text(s))
        except ValueError:
            return {}

    def output_text(self, s: Step) -> str:
        return self.blob_text(s.output_blob) or ""

    def latest_index(self) -> str | None:
        for t in reversed(self.transitions):
            if t.after:
                return t.after
        for s in reversed(self.steps):
            if s.post_index:
                return s.post_index
        return self.initial

    def materialize(self, index_sha: str | None, dest: pathlib.Path) -> list[str]:
        return W.materialize(self.index(index_sha), self.rec.blobs, dest)


# ── lineage ──────────────────────────────────────────────────────────

@dataclasses.dataclass
class Origin:
    kind: str                      # agent｜input｜pre_existing｜external｜gap｜ambiguous｜unknown
    step: Step | None = None
    source: dict[str, Any] | None = None
    note: str = ""
    candidates: list[Step] = dataclasses.field(default_factory=list)


class Blamer:
    def __init__(self, trace: Trace, contract: Any = None):
        self.t = trace
        self.contract = contract
        self.inputs: dict[str, tuple[str, pathlib.Path]] = {}   # 工作區相對路徑 → (名字, 絕對路徑)
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
    def introducer(self, path: str, value: str, before_seq: int | None = None
                   ) -> Transition | str | None:
        """回傳引入它的轉變；`"initial"`＝第一次看到時就在；None＝那時候不在。"""
        cur_text = self.t.file_text(self.t.initial, path)
        cur = cur_text is not None and L.contains(cur_text, value)
        intro: Transition | str | None = "initial" if cur else None
        for tr in self.t.transitions:
            if before_seq is not None and tr.seq >= before_seq:
                break
            if path not in tr.paths:
                continue
            txt = self.t.file_text(tr.after, path)
            now = txt is not None and L.contains(txt, value)
            if now and not cur:
                intro = tr
            elif cur and not now:
                intro = None
            cur = now
        return intro

    # 2. 它從哪裡來 -------------------------------------------------------
    def sources(self, s: Step) -> list[tuple[str, Step | None, str, str | None]]:
        """`s` 的行動者在 `s` 之前觀察到的東西，最近的在前：(種類, 步驟, 文字, 參照)。"""
        out: list[tuple[str, Step | None, str, str | None]] = []
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
            ref = None
            if kind in ("read", "fetch"):
                from ..adapters.hook import _paths_from
                ps = _paths_from(inp)
                ref = ps[0] if ps else (inp.get("url") if isinstance(inp, dict) else None)
            elif kind == "shell":
                ref = _command(inp)
            out.append((kind if kind != "write" else "tool", j, self.t.output_text(j), ref))
        if s.actor.get("agent"):
            # 子 agent 的任務說明＝父 agent 叫它的那個工具呼叫的輸入
            for j in self.t.steps:
                if j.seq >= (first_of_ctx or s.seq):
                    break
                if tool_kind(j.tool) == "agent" and j.ctx[:2] == s.ctx[:2] and not j.ctx[2]:
                    out.append(("spawn_input", j, self.t.input_text(j), None))
        for p in self.t.prompts:
            if int(p.get("seq", 0)) < s.seq and \
                    str(p.get("session")) in ("*", str(s.actor.get("session"))):
                out.append(("prompt", None, self.t.blob_text(p.get("text_blob")) or "",
                            None))
        out.sort(key=lambda x: -(x[1].seq if x[1] is not None else 0))
        return out

    def _rel(self, ref: str | None) -> str | None:
        if not ref:
            return None
        ws = self.t.rec.workspace
        p = pathlib.Path(ref)
        try:
            return (p if p.is_absolute() else ws / p).resolve().relative_to(ws).as_posix()
        except (ValueError, OSError):
            return None

    def _referenced_files(self, s: Step) -> tuple[list[str], list[str]]:
        """指令字串點名的工作區檔案：`(讀的, 執行的)`。重導向的目標（`> out`）不算——那是
        這個指令寫的，不是它用的；只有直譯器的引數或直接執行的路徑算「執行的腳本」。"""
        cmd = _command(self.t.input_obj(s)) or ""
        try:
            toks = shlex.split(cmd, posix=True)
        except ValueError:
            toks = cmd.split()
        idx = self.t.index(s.pre_index)
        reads: list[str] = []
        scripts: list[str] = []
        prev = ""
        for tok in toks:
            if prev in (">", ">>", "1>", "2>", "&>", "1>>", "2>>", "tee") or tok.startswith(">"):
                prev = tok
                continue
            for piece in tok.replace("=", " ").split():
                rel = self._rel(piece.strip("'\"<>|;&()"))
                if not rel or rel not in idx:
                    continue
                if rel in reads or rel in scripts:
                    continue
                if pathlib.PurePosixPath(prev).name in _INTERPRETERS or piece.startswith("./"):
                    scripts.append(rel)
                else:
                    reads.append(rel)
            prev = tok
        return reads, scripts

    def _last_writer(self, path: str, before_seq: int) -> Transition | None:
        last = None
        for tr in self.t.transitions:
            if tr.seq >= before_seq:
                break
            if path in tr.paths:
                last = tr
        return last

    def value_origin(self, path: str, value: str, chain: list[dict[str, Any]], *,
                     before_seq: int | None = None, depth: int = 0) -> Origin:
        if depth > MAX_DEPTH:
            return Origin("unknown", note="lineage too deep")
        intro = self.introducer(path, value, before_seq)
        if intro is None:
            return Origin("unknown", note=f"{value!r} is not in {path} at that point")
        if intro == "initial":
            src = {"kind": "file", "path": path, **self._line_of(self.t.initial, path, value)}
            if path in self.inputs:
                name, _p = self.inputs[path]
                return Origin("input", source={**src, "kind": "input", "name": name},
                              note="the pinned input already says this")
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
        return self.step_origin(s, value, chain, depth=depth)

    def _concurrent(self, s: Step) -> list[Step]:
        return [j for j in self.t.steps if j.id != s.id and (s.id in j.conc or j.id in s.conc)]

    def _line_of(self, index_sha: str | None, path: str, value: str) -> dict[str, Any]:
        txt = self.t.file_text(index_sha, path) or ""
        occ = L.occurrences(txt, value)
        return {"line": occ[0][0]} if occ else {}

    def step_origin(self, s: Step, value: str, chain: list[dict[str, Any]], *,
                    depth: int) -> Origin:
        typed = L.contains(self.t.input_text(s), value)
        if tool_kind(s.tool) == "shell" and not typed:
            # 值不在指令字串裡：可能是指令算出來的（看它點名的檔：資料裡有這個值 ⇒ 追資料；
            # 腳本是這個工作階段寫的 ⇒ 寫腳本的那一步），也可能只是編碼過（`base64 -d`、
            # `printf '%b'`）——那就和直接打字一樣，往下看行動者之前觀察到什麼
            o = self._shell_origin(s, value, chain, depth, fallback=False)
            if o is not None:
                return o
        for kind, j, text, ref in self.sources(s):
            if not L.contains(text, value):
                continue
            if kind == "prompt":
                chain.append({"via": "the user's message"})
                return Origin("input", source={"kind": "prompt"},
                              note="the value is in the user's message")
            assert j is not None
            if kind == "read":
                rel = self._rel(ref)
                chain.append({**j.brief(), "via": f"read {ref}"})
                if rel is not None and rel not in self.inputs:
                    return self.value_origin(rel, value, chain, before_seq=j.seq,
                                             depth=depth + 1)
                if rel is not None:
                    name, _p = self.inputs[rel]
                    return Origin("input", source={"kind": "input", "name": name, "path": rel,
                                                   **self._line_of(j.pre_index, rel, value)},
                                  note="the pinned input says this")
                return Origin("input", source={"kind": "file", "path": ref},
                              note="a file outside the workspace says this")
            if kind == "fetch":
                chain.append({**j.brief(), "via": f"fetched {ref}"})
                return Origin("external", source={"kind": "url", "ref": ref, "step": j.n},
                              note="the fetched content says this")
            if kind == "agent":
                chain.append({**j.brief(), "via": "a sub-agent's reply"})
                sub = self._subagent_step(j, value)
                if sub is None:
                    return Origin("agent", step=None, source={"kind": "subagent_reply",
                                                              "step": j.n},
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
                return self._shell_origin(j, value, chain, depth) or \
                    Origin("agent", step=j, note="the command itself produced the value")
            chain.append({**j.brief(), "via": f"the output of {j.tool}"})
            return Origin("external", source={"kind": "tool_output", "tool": j.tool,
                                              "step": j.n},
                          note=f"{j.tool} returned it")
        for rel, (name, p) in self.inputs.items():
            try:
                if L.contains(p.read_text(encoding="utf-8"), value):
                    return Origin("input", step=s, source={"kind": "input", "name": name,
                                                           "path": rel, "observed": False},
                                  note="a pinned input has this value, but no recorded read "
                                       "shows it being read")
            except (OSError, UnicodeDecodeError):
                continue
        return Origin("agent", step=s, note="no recorded read contains this value")

    def _shell_origin(self, j: Step, value: str, chain: list[dict[str, Any]],
                      depth: int, *, fallback: bool = True) -> Origin | None:
        reads, scripts = self._referenced_files(j)
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


def _command(inp: Any) -> str | None:
    from ..adapters.hook import _command_from
    return _command_from(inp)


# ── the verdict ──────────────────────────────────────────────────────

def _grade(origin: Origin, direct: bool, flip: dict[str, Any] | None) -> tuple[str, str, str]:
    """(狀態, 過錯類別, 等級)。"""
    if origin.kind == "gap":
        return "UNOBSERVED", "unattributable", "gap"
    if origin.kind == "ambiguous":
        return "candidate_set", "agent", "heuristic"
    if origin.kind == "unknown":
        return "UNKNOWN", "unattributable", "heuristic"
    if origin.kind in ("input", "pre_existing", "external"):
        observed = (origin.source or {}).get("observed", True)
        return "located", "input", "lineage_exact" if observed else "heuristic"
    # agent
    if origin.step is None:
        return "located", "agent", "heuristic"
    if direct and flip and flip.get("flipped"):
        return "located", "agent", "provable"
    return "located", "agent", "lineage_internal" if not direct else "heuristic"


def rerun_flip(trace: Trace, contract: Any, claim_id: str, step: Step, loc: L.Location,
               *, sandbox: str = "auto") -> dict[str, Any]:
    """在第 k 步之前與之後重建出來的狀態上重跑主張。`flipped`＝之後不過而且錯的值就在那個位置、
    之前那個位置沒有這個值。"""
    from . import rerun
    claim = rerun.claim_by_id(contract, claim_id)
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="vacant-blame-"))
    try:
        out: dict[str, Any] = {"claim": claim_id, "verifier": claim.verifier, "step": step.n}
        for tag, sha in (("before", step.pre_index), ("after", step.post_index)):
            d = tmp / tag
            missing = trace.materialize(sha, d)
            r = rerun.run(contract, d, [claim_id], sandbox=sandbox)[0]
            locs = L.locate(claim, r, d)
            hit = any(x.path == loc.path and x.value is not None and loc.value is not None
                      and L.contains(x.value, loc.value) for x in locs)
            out[tag] = {"status": r["status"], "value_here": hit,
                        "state_index": sha, "unrebuildable": missing[:5]}
        b, a = out["before"], out["after"]
        out["flipped"] = bool(a["status"] == "FAIL" and a["value_here"] and not b["value_here"]
                              and not a["unrebuildable"])
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def blame_location(trace: Trace, loc: L.Location, *, contract: Any = None,
                   claim_id: str | None = None, sandbox: str = "auto") -> dict[str, Any]:
    """一個位置 → 一個追緝結論（dict，可直接進鏈與報告）。"""
    b = Blamer(trace, contract)
    chain: list[dict[str, Any]] = []
    value = loc.value
    if value is None and loc.line is not None:
        txt = trace.file_text(trace.latest_index(), loc.path) or ""
        lines = txt.splitlines()
        value = lines[loc.line - 1].strip() if 0 < loc.line <= len(lines) else None
    res: dict[str, Any] = {"location": loc.to_json(), "claim": claim_id}
    if not value or loc.kind == "missing":
        # 缺的東西沒有值可追：最後寫這個檔的是誰（推論層）
        last = b._last_writer(loc.path, 1 << 62)
        if last is None:
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
    origin = b.value_origin(loc.path, value, chain)
    direct = origin.step is not None and bool(chain) and chain[0].get("step") == origin.step.id \
        and len([c for c in chain if "step" in c]) == 1
    flip = None
    if origin.kind == "agent" and origin.step is not None and direct and contract is not None \
            and claim_id is not None:
        try:
            flip = rerun_flip(trace, contract, claim_id, origin.step,
                              dataclasses.replace(loc, value=value), sandbox=sandbox)
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
    return res


def blame_results(rec: Recorder, contract: Any, results: list[dict[str, Any]],
                  state_dir: str | pathlib.Path, *, sandbox: str = "auto",
                  max_per_claim: int = 5) -> list[dict[str, Any]]:
    """每一條**不過**的主張：定位 → 追緝。UNKNOWN／CONFLICT 不追（那不是繳付物的錯：
    驗證器、證據或人還沒到位）。"""
    from . import rerun
    trace = Trace(rec)
    out = []
    for r in results:
        if r.get("status") != "FAIL":
            continue
        try:
            claim = rerun.claim_by_id(contract, str(r["claim_id"]))
        except KeyError:
            continue
        locs = [x for x in L.locate(claim, r, state_dir) if x.kind != "source"]
        sources = [x.to_json() for x in L.locate(claim, r, state_dir) if x.kind == "source"]
        if not locs:
            locs = [L.Location(str((claim.params or {}).get("path") or
                                   (claim.params or {}).get("report") or "?"),
                               kind="missing", note=str(r.get("detail"))[:200])]
        for loc in locs[:max_per_claim]:
            b = blame_location(trace, loc, contract=contract, claim_id=str(r["claim_id"]),
                               sandbox=sandbox)
            b["detail"] = r.get("detail")
            b["hidden"] = bool(getattr(claim, "hidden", False))
            b["required"] = bool(r.get("required", True))
            if sources:
                b["expected"] = sources
            out.append(b)
    return out
