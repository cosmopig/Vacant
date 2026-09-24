"""recorder — **病歷**：每一次工具呼叫一筆簽章事件，誰、做了什麼、讀了什麼、寫了什麼。

這支在架構裡承重什麼（`ops/accountability/LOOP.md` §二-1；論文 4.2「事件鏈」、3.1.3 Bovens
「說明義務」）：

掛鉤在工具呼叫**之前**與**之後**各叫一次這支（四個 agent 的原生事件由 `adapters/hook.py`
翻譯成 `pre()`／`post()`）：

    pre(step)   掃工作區；若和上一次看到的不同、而中間沒有任何一步 ⇒ 記「沒有紀錄的改動」
    post(step)  再掃一次；差異 ＝ 這一步寫了什麼。連同行動者、工具、輸入、讀到的內容、輸出
                一起簽進鏈。輸出與每個看到的檔案版本都存進內容定址的版本庫，追緝時可以重建。

**一個專案一條鏈**（不是一個工作階段一條）：子 agent 在自己的 session 裡寫的檔案，
和主 agent 寫的在同一個工作區——若以 session 分開，子 agent 的寫入在主 agent 那條鏈上就會
被誤記成「沒有紀錄的改動」。鏈上每一筆帶自己的 `session` 與 `actor`。

## 誠實邊界（改碼請保留）

1. **自己記自己的結構弱點**（Figuera 2026；論文 4.2.2）：掛鉤是 agent 平台叫的，agent 拆得掉
   （論文 4.6.3 實測）。所以本檔另外用 Vacant **自己看到的**工作區差異對帳：沒有任何一步解釋得了的
   改動記成 `unrecorded_change`——**究責缺口，不歸給任何人**。完備性要外部錨定才能更強。
2. 同時進行的兩步（平行工具呼叫）之間的寫入分不清是誰的：記成 `concurrent_with`，
   追緝把它標成「多人之一」，不硬選一個。
3. 讀取的判定是**宣告式**的（工具輸入裡的路徑、網址、指令輸出本身）；殼層指令在執行中讀了哪些檔，
   掛鉤看不到（要系統呼叫追蹤才看得到，這裡沒有）。
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import pathlib
import time
from typing import Any

from ..atomic import atomic_write_text, file_lock
from ..canonical import canonical_bytes
from ..intake import keys as _keys
from ..intake.statepaths import state_dir, state_dirs
from ..logbook import MAX_PAYLOAD_BYTES, LogEntry, Logbook
from . import workspace as W

TRACE_SCHEMA = "vacant-trace/1"
EVENT_TYPES = frozenset({"trace_genesis", "session_seen", "step", "unrecorded_change",
                         "transcript", "session_closed", "finding", "flag"})
MAX_OUTPUT_BLOB = 2 * 1024 * 1024
#: 事件裡直接列出的清單上限；超過的整份存進版本庫，事件帶它的 sha256（鏈上每筆有 64KB 上限）
INLINE_LIST = 64
_LIST_KEYS = ("writes", "reads", "changes")


def _fit(payload: dict[str, Any], blobs: W.Blobs) -> dict[str, Any]:
    """長清單移進版本庫，事件只留前 `INLINE_LIST` 筆＋全份的 sha256＋總數——不截斷資訊，
    只是換個地方放（全份仍被鏈上的 sha256 綁住）。"""
    out = dict(payload)
    for k in _LIST_KEYS:
        v = out.get(k)
        if isinstance(v, list) and len(v) > INLINE_LIST:
            out[k] = v[:INLINE_LIST]
            out[k + "_blob"] = blobs.put_bytes(json.dumps(v, ensure_ascii=False).encode())
            out["n_" + k] = len(v)
    if len(canonical_bytes(out)) > MAX_PAYLOAD_BYTES - 1024:
        blob = blobs.put_bytes(json.dumps(out, ensure_ascii=False, default=str).encode())
        out = {k: out[k] for k in ("step", "n", "actor", "tool", "observed_at") if k in out}
        out["payload_blob"] = blob
    return out


def trace_home() -> pathlib.Path:
    return state_dir() / "trace"


def project_key(root: str | os.PathLike) -> str:
    return hashlib.sha256(str(pathlib.Path(root).resolve()).encode()).hexdigest()[:16]


@dataclasses.dataclass(frozen=True)
class Actor:
    """誰做的。`agent` 為 None ＝ 使用者直接對話的那個主 agent；子 agent 帶它的 id 與類型。
    `model` 可能在掛鉤當下還不知道（Claude 的模型寫在逐字稿裡），由 `transcript` 事件補上。"""
    platform: str
    session: str
    agent: str | None = None
    agent_type: str | None = None
    model: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {k: v for k, v in dataclasses.asdict(self).items() if v is not None}

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> "Actor":
        return cls(platform=str(d.get("platform")), session=str(d.get("session")),
                   agent=d.get("agent"), agent_type=d.get("agent_type"), model=d.get("model"))

    def label(self) -> str:
        who = f"{self.platform}:{self.agent_type or 'main'}"
        return who + (f"#{self.agent[:8]}" if self.agent else "") + \
            (f"@{self.model}" if self.model else "")


@dataclasses.dataclass
class Read:
    """這一步讀到的東西。`kind`：file（工作區或外面的檔）／url／command_output／agent_reply／
    tool_output。`blob`：讀到的內容存在版本庫裡的 sha256（追緝拿它比對錯的值從哪裡來）。"""
    kind: str
    ref: str
    blob: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {k: v for k, v in dataclasses.asdict(self).items() if v is not None}


class Recorder:
    """一個專案（工作區根目錄）的追緝紀錄。所有方法都是行程安全的（檔案鎖）。"""

    def __init__(self, workspace: str | os.PathLike, root: pathlib.Path | None = None):
        self.workspace = pathlib.Path(workspace).resolve()
        self.home = root or trace_home()
        self.dir = self.home / "projects" / project_key(self.workspace)
        self.blobs = W.Blobs(self.home / "objects")
        self.chain_path = self.dir / "chain.ndjson"
        self.state_path = self.dir / "state.json"
        self.skip = set(state_dirs())

    # ── state ────────────────────────────────────────────────────────
    def _state(self) -> dict[str, Any]:
        if self.state_path.is_file():
            try:
                return json.loads(self.state_path.read_text(encoding="utf-8"))
            except ValueError:
                pass
        return {"workspace": str(self.workspace), "last_index": None, "pending": {},
                "sessions": {}, "n_steps": 0}

    def _save(self, st: dict[str, Any]) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.state_path, json.dumps(st, ensure_ascii=False))

    def _lock(self):
        self.dir.mkdir(parents=True, exist_ok=True)
        return file_lock(self.dir / "lock", timeout=30.0)

    def _tail(self) -> Logbook:
        """只讀創世與最後一筆（接鏈只需要這兩筆；整條讀進來每一步都是 O(n)）。"""
        if not self.chain_path.is_file():
            return Logbook()
        with self.chain_path.open("rb") as f:
            first = f.readline()
            f.seek(0, os.SEEK_END)
            end = f.tell()
            back = min(end, 1 << 16)
            while True:
                f.seek(end - back)
                lines = f.read(back).rstrip(b"\n").split(b"\n")
                if len(lines) > 1 or back == end:
                    break
                back = min(end, back * 4)
        entries = [LogEntry.from_json(json.loads(first))]
        last = LogEntry.from_json(json.loads(lines[-1]))
        if last.seq != entries[0].seq:
            entries.append(last)
        return Logbook(entries)

    def _append(self, etype: str, payload: dict[str, Any]) -> dict[str, Any]:
        if etype not in EVENT_TYPES:
            raise ValueError(f"unknown trace event {etype!r}")
        ident = _keys.load_or_create("verifier")
        book = self._tail()
        ts = int(time.time() * 1000)
        new: list[LogEntry] = []
        if not book.entries:
            new.append(book.append("trace_genesis",
                                   {"schema": TRACE_SCHEMA, "workspace": str(self.workspace),
                                    "signer": _keys.pub_hex(ident)}, ident, ts_ms=ts))
        e = book.append(etype, {"schema": TRACE_SCHEMA, **_fit(payload, self.blobs)}, ident,
                        ts_ms=ts)
        new.append(e)
        self.dir.mkdir(parents=True, exist_ok=True)
        with self.chain_path.open("ab") as f:
            for x in new:
                f.write(canonical_bytes(x.to_json()) + b"\n")
            f.flush()
            os.fsync(f.fileno())
        return {"seq": e.seq, "hash": e.hash()}

    def _index_blob(self, idx: W.Index) -> str:
        return self.blobs.put_bytes(W.dump(idx))

    def load_index(self, sha: str) -> W.Index:
        return W.load(self.blobs.get(sha))

    def _scan(self, prev: W.Index | None) -> W.Index:
        return W.scan(self.workspace, prev, skip=self.skip, blobs=self.blobs)

    def _ensure_session(self, st: dict[str, Any], actor: Actor) -> None:
        key = f"{actor.platform}:{actor.session}"
        if key not in st["sessions"]:
            st["sessions"][key] = {"first_seen": time.time(), "closed": False}
            self._append("session_seen", {"actor": actor.to_json()})

    # ── the two hook points ──────────────────────────────────────────
    def pre(self, step: str, actor: Actor, tool: str, tool_input: Any) -> dict[str, Any]:
        """工具呼叫之前。回傳這一步的暫存紀錄（測試與除錯用）。"""
        with self._lock():
            st = self._state()
            self._ensure_session(st, actor)
            prev = self.load_index(st["last_index"]) if st.get("last_index") else None
            idx = self._scan(prev)
            gap = []
            if prev is not None and not st["pending"]:
                # 上一次看到之後、而且這段時間沒有任何一步在進行 ⇒ 誰改的沒有紀錄
                gap = [c.to_json() for c in W.diff(prev, idx)]
            if gap:
                self._append("unrecorded_change", {"changes": gap, "n": len(gap),
                                                   "before_index": st["last_index"],
                                                   "after_index": self._index_blob(idx),
                                                   "observed_at": "pre_tool",
                                                   "next_actor": actor.to_json()})
            idx_sha = self._index_blob(idx)
            inp = json.dumps(tool_input, ensure_ascii=False, sort_keys=True, default=str)
            pend = {"step": step, "actor": actor.to_json(), "tool": tool,
                    "input_blob": self.blobs.put_bytes(inp.encode()),
                    "pre_index": idx_sha, "t0": time.time(),
                    "concurrent_with": sorted(st["pending"])}
            for other in st["pending"].values():
                other.setdefault("concurrent_with", []).append(step)
            st["pending"][step] = pend
            st["last_index"] = idx_sha
            self._save(st)
            return pend

    def post(self, step: str, actor: Actor, tool: str, tool_input: Any, output: Any,
             *, error: str | None = None, reads: list[Read] | None = None) -> dict[str, Any]:
        """工具呼叫之後：這一步寫了什麼＝前後差異。沒有對應的 `pre` 也記（標 `pre_missing`，
        差異以上一次看到的工作區為準，可能混進兩步之間的改動）；連上一次都沒有的標
        `baseline_missing`，寫入記成空（不知道 ≠ 沒寫）。"""
        with self._lock():
            st = self._state()
            self._ensure_session(st, actor)
            pend = st["pending"].pop(step, None)
            prev = self.load_index(st["last_index"]) if st.get("last_index") else None
            idx = self._scan(prev)
            base_sha = pend["pre_index"] if pend else st.get("last_index")
            # 從來沒看過這個工作區（第一個事件就是 post）⇒ 沒有「之前」可比，寫了什麼不知道；
            # 不可以把整個既有工作區算成這一步寫的
            changes = W.diff(self.load_index(base_sha), idx) if base_sha else []
            out_blob = None
            if output is not None:
                data = output if isinstance(output, bytes) else (
                    output if isinstance(output, str)
                    else json.dumps(output, ensure_ascii=False, default=str)).encode()
                out_blob = self.blobs.put_bytes(data[:MAX_OUTPUT_BLOB])
            inp = json.dumps(tool_input, ensure_ascii=False, sort_keys=True, default=str)
            idx_sha = self._index_blob(idx)
            st["n_steps"] = int(st.get("n_steps", 0)) + 1
            payload = {
                "step": step, "n": st["n_steps"], "actor": actor.to_json(), "tool": tool,
                "input_blob": pend["input_blob"] if pend else self.blobs.put_bytes(inp.encode()),
                "reads": [r.to_json() for r in (reads or [])],
                "writes": [c.to_json() for c in changes],
                "output_blob": out_blob, "error": (error or "")[:500] or None,
                "pre_index": base_sha, "post_index": idx_sha,
                "concurrent_with": (pend or {}).get("concurrent_with") or [],
                "pre_missing": pend is None, "baseline_missing": base_sha is None,
                "wall_ms": int((time.time() - pend["t0"]) * 1000) if pend else None}
            ref = self._append("step", payload)
            st["last_index"] = idx_sha
            self._save(st)
            return {**payload, **ref}

    def close(self, actor: Actor, reason: str | None = None) -> dict[str, Any]:
        """工作階段結束：最後再看一次，沒被任何一步解釋的改動記成缺口。"""
        with self._lock():
            st = self._state()
            prev = self.load_index(st["last_index"]) if st.get("last_index") else None
            idx = self._scan(prev)
            gap = [c.to_json() for c in W.diff(prev, idx)] if prev is not None else []
            if gap and not st["pending"]:
                self._append("unrecorded_change", {"changes": gap, "n": len(gap),
                                                   "before_index": st["last_index"],
                                                   "after_index": self._index_blob(idx),
                                                   "observed_at": "session_end"})
            idx_sha = self._index_blob(idx)
            key = f"{actor.platform}:{actor.session}"
            st["sessions"].setdefault(key, {})["closed"] = True
            ref = self._append("session_closed", {"actor": actor.to_json(), "reason": reason,
                                                  "final_index": idx_sha,
                                                  "open_steps": sorted(st["pending"])})
            st["last_index"] = idx_sha
            self._save(st)
            return ref

    # ── reading back ─────────────────────────────────────────────────
    def events(self) -> list[dict[str, Any]]:
        if not self.chain_path.is_file():
            return []
        return [{"seq": e.seq, "type": e.type, "ts_ms": e.ts_ms, "hash": e.hash(),
                 **(e.payload or {})} for e in Logbook.load(self.chain_path).entries]

    def verify(self, trust: _keys.Trust | None = None) -> tuple[bool, str]:
        from ..identity import PublicIdentity
        if not self.chain_path.is_file():
            return False, "no trace"
        book = Logbook.load(self.chain_path)
        signer = (book.entries[0].payload or {}).get("signer")
        t = trust or _keys.Trust.load()
        name = t.name_of("verifier", str(signer))
        if name is None:
            return False, "trace signer is not on the accepted-signer list"
        if not book.verify_chain(PublicIdentity.from_hex(name, str(signer))):
            return False, "trace chain does not verify"
        return True, f"{len(book)} entries"
