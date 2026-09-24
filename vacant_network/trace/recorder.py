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
   追緝把它標成「多人之一」，不硬選一個。工具呼叫進行中、掛鉤外面發生的改動（使用者自己的編輯、
   背景行程）也會算進那一步——`post` 之後才寫檔的背景行程則會在下一次看的時候變成缺口。
   `pre` 之後一直沒等到 `post` 的步驟（Codex 的 apply_patch 失敗與長跑行程不發 PostToolUse）
   在回合結束、工作階段結束或開了 `STALE_S` 秒之後收尾，標 `post_missing`。
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
from .tools import tool_kind

TRACE_SCHEMA = "vacant-trace/1"
EVENT_TYPES = frozenset({"trace_genesis", "session_seen", "step", "unrecorded_change",
                         "transcript", "session_closed", "finding", "flag", "coverage",
                         "consequence", "prompt"})
MAX_OUTPUT_BLOB = 2 * 1024 * 1024
#: 一個步驟開著超過這麼久還沒等到 `post`，就當它不會來了（和 Stop 掛鉤的上限同一個數量級）
STALE_S = 900.0
#: 掛鉤裡的一次掃描最多這麼久（掛鉤有 30 秒上限；被 agent 砍掉＝靜默略過＝更大的缺口）。
#: 第一次看就超過 ⇒ 改在背景看（`baseline`）；之後的增量掃描還超過 ⇒ 這個專案不再逐步掃描
HOOK_SCAN_S = 8.0
#: 子 agent 開始之後這麼久沒有結束的消息 ⇒ 當成已經結束（驗收不可以因為漏掉一個事件就永遠不跑）
SUBAGENT_MAX_S = 3600.0
#: 主 agent 的回合結束最多**連續**延後幾次（背景子 agent 還在做）；到了就照常驗收
MAX_DEFERRALS = 3
#: 背景的第一次完整觀察最多等這麼久；過了還沒寫回來 ⇒ 當它失敗了，這個專案不再逐步掃描
BASELINE_WAIT_S = 600.0
#: 檔案數到這裡以上，工作區狀態存成對上一份完整索引的差異（見 `_index_blob`）
DELTA_MIN_FILES = 1000
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


def _ctx(actor: dict[str, Any]) -> tuple[str, str, str]:
    return (str(actor.get("platform")), str(actor.get("session")), str(actor.get("agent") or ""))


def _session_key(actor: dict[str, Any]) -> str:
    return f"{actor.get('platform')}:{actor.get('session')}"


def _same_task(template: str, task: str) -> bool:
    """委派呼叫裡寫的任務 vs 子 agent 收到的任務（pi 的範例會加上 `Task: `；串接模式的
    `{previous}` 會被換成上一步的輸出）。"""
    got = task.strip()
    if got.startswith("Task:"):
        got = got[len("Task:"):].strip()
    want = template.strip()
    if not want:
        return False
    if "{previous}" not in want:
        return want == got
    pos = 0
    for part in want.split("{previous}"):
        part = part.strip()
        if not part:
            continue
        i = got.find(part, pos)
        if i < 0:
            return False
        pos = i + len(part)
    return True


def _task_in(inp: Any, task: str) -> tuple[bool, str | None]:
    """`(這個呼叫的輸入裡有沒有這個任務, 它指定的代理人)`。"""
    if not isinstance(inp, dict):
        return False, None
    if isinstance(inp.get("task"), str) and _same_task(inp["task"], task):
        return True, inp.get("agent") if isinstance(inp.get("agent"), str) else None
    for k in ("tasks", "chain"):
        for e in inp.get(k) or []:
            if isinstance(e, dict) and isinstance(e.get("task"), str) \
                    and _same_task(e["task"], task):
                return True, e.get("agent") if isinstance(e.get("agent"), str) else None
    body = task.strip()
    body = body[len("Task:"):].strip() if body.startswith("Task:") else body
    for v in inp.values():                     # 例如殼層指令 `pi -p '<任務>'`
        if isinstance(v, str) and len(body) >= 16 and body in v:
            return True, None
    return False, None


def _explains_own_writes(pend: dict[str, Any]) -> bool:
    """這個還在跑的步驟之後能不能用自己的前後差異解釋它寫了什麼：開始時有看到工作區、
    而且還沒被界住。開始時沒看到（背景還在看第一眼）的步驟永遠解釋不了——它不可以擋住缺口
    （2026-09-24 大專案審查 #2）。"""
    return bool(pend.get("pre_index")) and not pend.get("bound_index")


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
        #: 在掛鉤裡用時由 `capture.py` 設成 `HOOK_SCAN_S`；命令列與 `vacant do` 不設（沒有上限）
        self.scan_deadline_s: float | None = None
        self._idx_cache: dict[str, W.Index] = {}

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

    def _lock(self, timeout: float = 30.0):
        for d in (self.home, self.dir):
            d.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            os.chmod(self.home, 0o700)    # 病歷與版本庫裡有工作區的內容與任務訊息
        except OSError:
            pass
        return file_lock(self.dir / "lock", timeout=timeout)

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

    def _repair_tail(self) -> dict[str, Any] | None:
        """寫到一半被砍（當機、磁碟滿）留下的半行：搬到旁邊的檔、截掉，之後照常接鏈——
        否則之後每一次追加都失敗、整個專案從此沒有紀錄（2026-09-24 審查 recorder#6）。"""
        if not self.chain_path.is_file():
            return None
        data = self.chain_path.read_bytes()
        if not data or data.endswith(b"\n"):
            return None
        cut = data.rfind(b"\n") + 1
        saved = self.dir / f"chain.torn.{int(time.time() * 1000)}"
        saved.write_bytes(data[cut:])
        with self.chain_path.open("r+b") as f:
            f.truncate(cut)
        return {"torn_tail_bytes": len(data) - cut, "saved_as": saved.name}

    def _append(self, etype: str, payload: dict[str, Any]) -> dict[str, Any]:
        if etype not in EVENT_TYPES:
            raise ValueError(f"unknown trace event {etype!r}")
        repaired = self._repair_tail()
        book = self._tail()
        if not book.entries:
            # 第一次簽：本機的簽章者要在收件端清單上，`vacant trace verify` 才驗得過（recorder#3）
            _keys.ensure_local()
        ident = _keys.load_or_create("verifier")
        ts = int(time.time() * 1000)
        new: list[LogEntry] = []
        if not book.entries:
            new.append(book.append("trace_genesis",
                                   {"schema": TRACE_SCHEMA, "workspace": str(self.workspace),
                                    "signer": _keys.pub_hex(ident)}, ident, ts_ms=ts))
        if repaired:
            new.append(book.append("coverage", {"schema": TRACE_SCHEMA, **repaired}, ident,
                                   ts_ms=ts))
        e = book.append(etype, {"schema": TRACE_SCHEMA, **_fit(payload, self.blobs)}, ident,
                        ts_ms=ts)
        new.append(e)
        self.dir.mkdir(parents=True, exist_ok=True)
        with self.chain_path.open("ab") as f:
            for x in new:
                f.write(canonical_bytes(x.to_json()) + b"\n")
            f.flush()
            os.fsync(f.fileno())
        # 鏈頭另外記一份：鏈被從尾巴截短時 verify 看得出來（recorder#4；收件端帳本另有一份）
        atomic_write_text(self.dir / "head.json", json.dumps({"seq": e.seq, "hash": e.hash()}))
        return {"seq": e.seq, "hash": e.hash()}

    def _index_blob(self, idx: W.Index, st: dict[str, Any] | None = None) -> str:
        """存一個工作區狀態。大專案存成對「關鍵幀」（上一份完整索引）的差異：每一步都存一份
        完整索引，4 萬個檔的專案每個有寫檔的步驟要多 4.9 MB。差異檔用 sha256 指向關鍵幀，
        兩者都是內容定址 ⇒ 還原出來的狀態和存完整索引一樣被雜湊綁住。"""
        key = (st or {}).get("index_key")
        base = self._try_load(key) if key else None
        data = None
        if base is not None and len(base) >= DELTA_MIN_FILES:
            put = {p: e.to_json() for p, e in idx.items() if base.get(p) != e}
            gone = sorted(p for p in base if p not in idx)
            if not put and not gone:
                return str(key)                       # 和關鍵幀一樣：同一個狀態、同一個 sha256
            if len(put) + len(gone) <= max(64, len(base) // 10):
                data = json.dumps({"": {"base": key, "del": gone}, **dict(sorted(put.items()))},
                                  separators=(",", ":"), ensure_ascii=False).encode()
        full = data is None
        # 索引要落盤（fsync）：狀態檔與鏈會指向它，當機後留下空檔＝之後每一次掛鉤都讀不回來（審查 #6）
        sha = self.blobs.put_bytes(data if data is not None else W.dump(idx), durable=True)
        if full and st is not None:
            st["index_key"] = sha                     # 這一份是完整的：之後的差異對它算
        self._idx_cache[sha] = idx
        return sha

    def _try_load(self, sha: str) -> W.Index | None:
        try:
            return self.load_index(sha)
        except (OSError, ValueError):
            return None

    def load_index(self, sha: str) -> W.Index:
        """索引是內容定址、不可變的：同一個行程裡讀過就不再讀（`post` 會讀兩次同一份）。
        回傳的字典不可以改。差異檔（`""` 鍵帶著關鍵幀的 sha256）還原成完整狀態。"""
        idx = self._idx_cache.get(sha)
        if idx is None:
            raw = json.loads(self.blobs.get(sha))
            meta = raw.pop("", None)
            if isinstance(meta, dict):
                base = self.load_index(str(meta["base"]))
                gone = set(meta.get("del") or [])
                idx = {p: e for p, e in base.items() if p not in gone}
                idx.update({str(p): W.Entry.from_json(v) for p, v in raw.items()})
            else:
                idx = {str(p): W.Entry.from_json(v) for p, v in raw.items()}
            self._idx_cache[sha] = idx
        return idx

    def _scan(self, prev: W.Index | None,
              st: dict[str, Any] | None = None) -> W.Index | None:
        """掃一次；`None`＝這一次沒看（掃描關了、第一次看改到背景、超時）。"""
        if st is not None and st.get("scan_disabled"):
            return None
        deadline = time.monotonic() + self.scan_deadline_s \
            if (self.scan_deadline_s and st is not None) else None
        try:
            # `prev` 是這個紀錄器帶著同一個版本庫掃出來的 ⇒ 它的版本都在庫裡，不逐檔確認
            return W.scan(self.workspace, prev, skip=self.skip, blobs=self.blobs,
                          deadline=deadline, prev_stored=True)
        except W.ScanTimeout as e:
            if st is None:
                raise
            if prev is None:
                self._defer_baseline(st, str(e))
            else:
                self._disable_scan(st, f"an incremental scan passed {self.scan_deadline_s:.0f}s")
            return None
        except ValueError as e:                      # 檔案數上限
            if st is None:
                raise
            self._disable_scan(st, str(e))
            return None

    def _observe(self, st: dict[str, Any]
                 ) -> tuple[W.Index | None, W.Index | None, str | None]:
        """`(上一次看到的, 現在, 現在的索引 sha)`。這一次沒看 ⇒ `現在＝None`、sha＝上一次的
        （掃描關掉之後連舊索引都不讀：大專案每一次掛鉤曾經因此多花半秒）。"""
        last = st.get("last_index")
        if st.get("scan_disabled"):
            return None, None, last
        if not last and st.get("baseline_pending"):
            # 背景還在看第一次：這段時間的掛鉤不再各自花掉整個時限去重掃（否則每一步多 8 秒）
            if time.time() - float(st["baseline_pending"]) < BASELINE_WAIT_S:
                st["unobserved_before_baseline"] = True
                return None, None, None
            self._disable_scan(st, f"the background first look did not finish in "
                                   f"{BASELINE_WAIT_S:.0f}s")
            return None, None, None
        try:
            prev = self.load_index(last) if last else None
        except (OSError, ValueError) as e:
            # 上一次看到的狀態讀不回來（版本庫被改過或壞了）：之後的差異都沒有根據。
            # 不可以讓每一次掛鉤都在這裡炸掉（審查 #6），也不可以假裝從頭看起——關掉、照實記下
            self._disable_scan(st, f"the last recorded view of the workspace is unreadable "
                                   f"({type(e).__name__})")
            return None, None, last
        idx = self._scan(prev, st)
        if idx is None:
            return prev, None, last
        return prev, idx, self._index_blob(idx, st)

    def _gap_since(self, st: dict[str, Any], prev: W.Index | None, idx: W.Index | None,
                   idx_sha: str | None, observed_at: str) -> None:
        """上一次看到之後到現在的改動記成缺口，並把「上一次看到」往前推（同一批改動不再被算一次）。"""
        if prev is None or idx is None:
            return
        gap = [c.to_json() for c in W.diff(prev, idx)]
        if gap:
            self._append("unrecorded_change", {"changes": gap, "n": len(gap),
                                               "before_index": st["last_index"],
                                               "after_index": idx_sha,
                                               "observed_at": observed_at})
        st["last_index"] = idx_sha

    def _disable_scan(self, st: dict[str, Any], why: str) -> None:
        st["scan_disabled"] = why
        self._append("coverage", {"scan_disabled": why})

    def _defer_baseline(self, st: dict[str, Any], why: str) -> None:
        """第一次看就超過掛鉤的時限：在背景把整個工作區看一次（不拿鎖地掃，最後才進鎖寫入）。
        在它完成之前的步驟都記成「沒觀察到」。"""
        st["unobserved_before_baseline"] = True
        st["baseline_pending"] = time.time()
        self._append("coverage", {"baseline_deferred": why})
        import subprocess
        import sys
        try:
            subprocess.Popen([sys.executable, "-m", "vacant_network.trace.recorder", "baseline",
                              str(self.workspace)], stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
        except OSError:
            pass

    def baseline(self) -> dict[str, Any]:
        """把整個工作區看一次（沒有時限、不拿鎖地掃）。已經有人看過了就不動。"""
        t0 = time.monotonic()
        try:
            idx: W.Index | None = W.scan(self.workspace, None, skip=self.skip, blobs=self.blobs)
            too_big = None
        except ValueError as e:                      # 檔案數上限：背景也看不完
            idx, too_big = None, str(e)
        secs = time.monotonic() - t0
        with self._lock():
            st = self._state()
            if too_big is not None or idx is None:
                st.pop("baseline_pending", None)
                if not st.get("last_index") and not st.get("scan_disabled"):
                    self._disable_scan(st, too_big or "no index")
                self._save(st)
                return {"disabled": st.get("scan_disabled")}
            if st.get("last_index") or st.get("scan_disabled"):
                st.pop("baseline_pending", None)
                self._save(st)
                return {"skipped": "already observed"}
            sha = self._index_blob(idx, st)
            st["last_index"] = sha
            st.pop("baseline_pending", None)
            info = {"files": len(idx), "seconds": round(secs, 1), "index": sha,
                    "after_unobserved": bool(st.get("unobserved_before_baseline"))}
            self._append("coverage", {"baseline": info})
            self._save(st)
            return info

    def _ensure_session(self, st: dict[str, Any], actor: Actor) -> None:
        key = f"{actor.platform}:{actor.session}"
        if key not in st["sessions"]:
            st["sessions"][key] = {"first_seen": time.time(), "closed": False}
            self._append("session_seen", {"actor": actor.to_json()})
        if actor.model and not actor.agent:
            # 主 agent 自稱的模型（掛鉤不是每個事件都帶）：工作階段結束記結果時用同一格
            st["sessions"][key]["model"] = actor.model
        st["last_session"] = key

    def session_info(self, platform: str, session: str) -> dict[str, Any]:
        return dict(self._state()["sessions"].get(f"{platform}:{session}") or {})

    def last_platform(self) -> str | None:
        key = self._state().get("last_session")
        return str(key).split(":", 1)[0] if key else None

    # ── the two hook points ──────────────────────────────────────────
    def pre(self, step: str, actor: Actor, tool: str, tool_input: Any) -> dict[str, Any]:
        """工具呼叫之前。回傳這一步的暫存紀錄（測試與除錯用）。"""
        with self._lock():
            st = self._state()
            self._ensure_session(st, actor)
            self._finish_open(st, "stale", older_than=STALE_S)
            prev, idx, idx_sha = self._observe(st)
            gap = []
            blocking = [k for k, v in st["pending"].items() if _explains_own_writes(v)]
            if prev is not None and idx is not None and not blocking:
                # 上一次看到之後、而且這段時間沒有任何一步在進行 ⇒ 誰改的沒有紀錄。
                # 已經有界的孤兒步驟（同一個行動者後來又開始了下一步）不算「在進行」——否則它會
                # 一直擋住缺口，兩步之間的改動就此消失（審查 recorder#1）。平行的平台上這會把
                # 還在跑的那一步的寫入記成缺口：寧可「沒人解釋」，不可錯怪。
                gap = [c.to_json() for c in W.diff(prev, idx)]
            if gap:
                self._append("unrecorded_change", {"changes": gap, "n": len(gap),
                                                   "before_index": st["last_index"],
                                                   "after_index": idx_sha,
                                                   "observed_at": "pre_tool",
                                                   "next_actor": actor.to_json()})
            inp = json.dumps(tool_input, ensure_ascii=False, sort_keys=True, default=str)
            me = _ctx(actor.to_json())
            # 等子 agent 的那個父呼叫（Agent／Task／spawn／wait）不算「同時在寫」：它的寫入就是
            # 子 agent 的步驟，那些另外有紀錄（2026-09-24 審查 blame#8）
            busy = [k for k, v in st["pending"].items() if tool_kind(v.get("tool")) != "agent"]
            pend = {"step": step, "actor": actor.to_json(), "tool": tool,
                    "input_blob": self.blobs.put_bytes(inp.encode()),
                    "pre_index": idx_sha if idx is not None else None, "t0": time.time(),
                    "concurrent_with": sorted(busy)}
            for k, other in st["pending"].items():
                if k in busy and tool_kind(tool) != "agent":
                    other.setdefault("concurrent_with", []).append(step)
                if _ctx(other.get("actor") or {}) == me and not other.get("bound_index") \
                        and idx is not None:
                    # 同一個行動者開始了下一步：若它永遠等不到 post，它的寫入最多到這裡為止
                    other["bound_index"] = idx_sha
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
            prev, idx, idx_sha = self._observe(st)
            if pend and not pend.get("pre_index"):
                # 開始時沒看到（背景還在看第一眼），結束時看得到：上一次看到之後的改動可能是它寫的、
                # 也可能不是——記成缺口，不可以就此消失（否則下一個碰這個檔的人會背；審查 #1）
                self._gap_since(st, prev, idx, idx_sha, "post_tool_unobserved_start")
            base_sha = pend["pre_index"] if pend else st.get("last_index")
            # 從來沒看過這個工作區（第一個事件就是 post）⇒ 沒有「之前」可比，寫了什麼不知道；
            # 不可以把整個既有工作區算成這一步寫的。這一次沒看 ⇒ 也是不知道
            changes = W.diff(self.load_index(base_sha), idx) \
                if base_sha and idx is not None else []
            delegated: list[str] = []
            if pend and tool_kind(tool) == "agent":
                # 子 agent 自己的步驟已經記下它們的寫入；父呼叫只留沒有任何子步驟解釋的那些
                covered = set(pend.get("covered") or [])
                delegated = sorted(c.path for c in changes if c.path in covered)
                changes = [c for c in changes if c.path not in covered]
            else:
                for other in st["pending"].values():
                    if tool_kind(other.get("tool")) == "agent":
                        other["covered"] = sorted(set(other.get("covered") or [])
                                                  | {c.path for c in changes})
            out_blob = None
            if output is not None:
                data = output if isinstance(output, bytes) else (
                    output if isinstance(output, str)
                    else json.dumps(output, ensure_ascii=False, default=str)).encode()
                out_blob = self.blobs.put_bytes(data[:MAX_OUTPUT_BLOB])
            inp = json.dumps(tool_input, ensure_ascii=False, sort_keys=True, default=str)
            st["n_steps"] = int(st.get("n_steps", 0)) + 1
            payload = {
                "step": step, "n": st["n_steps"], "actor": actor.to_json(), "tool": tool,
                "input_blob": pend["input_blob"] if pend else self.blobs.put_bytes(inp.encode()),
                "reads": [r.to_json() for r in (reads or [])],
                "writes": [c.to_json() for c in changes],
                "output_blob": out_blob, "error": (error or "")[:500] or None,
                "pre_index": base_sha, "post_index": idx_sha if idx is not None else None,
                "concurrent_with": (pend or {}).get("concurrent_with") or [],
                "pre_missing": pend is None, "baseline_missing": base_sha is None,
                "observed_by": "agent_hook",       # 工具名／輸入／輸出；writes 是 vacant_scan
                "wall_ms": int((time.time() - pend["t0"]) * 1000) if pend else None}
            if delegated:
                payload["delegated"] = delegated
            if idx is None or not base_sha:
                payload["writes_unknown"] = st.get("scan_disabled") or "the workspace was not " \
                    "observed around this step"
            ref = self._append("step", payload)
            st["last_index"] = idx_sha
            self._save(st)
            return {**payload, **ref}

    def denied(self, step: str, actor: Actor, tool: str, tool_input: Any,
               reason: str) -> dict[str, Any]:
        """Vacant 在工具執行前拒絕了這一步：記下「它試過」，不掃工作區（工具沒有執行）。
        拒絕要立刻回給 agent：鎖等不到 3 秒就不記了（掛鉤的逾時也是 30 秒；integration#8）。"""
        with self._lock(timeout=3.0):
            st = self._state()
            self._ensure_session(st, actor)
            inp = json.dumps(tool_input, ensure_ascii=False, sort_keys=True, default=str)
            st["n_steps"] = int(st.get("n_steps", 0)) + 1
            payload = {"step": step, "n": st["n_steps"], "actor": actor.to_json(), "tool": tool,
                       "input_blob": self.blobs.put_bytes(inp.encode()), "writes": [],
                       "denied": reason[:500], "observed_by": "agent_hook"}
            ref = self._append("step", payload)
            self._save(st)
            return {**payload, **ref}

    def _finish_open(self, st: dict[str, Any], why: str, *,
                     older_than: float | None = None,
                     session: str | None = None,
                     agent: str | None = None) -> list[dict[str, Any]]:
        """`pre` 之後一直沒等到 `post` 的步驟（Codex：apply_patch 失敗、長跑行程；工作階段被砍）。
        寫入以「它的 pre 到同一個行動者的下一步 pre」估（沒有下一步就到現在），標 `post_missing`
        ——追緝只能當候選，不能當定論。`session`＝只收那個工作階段的（另一個工作階段的 Stop 不可以
        收掉別人正在跑的步驟：2026-09-24 審查 recorder#7）。"""
        now = time.time()
        done = []
        for step in sorted(st["pending"]):
            pend = st["pending"][step]
            if older_than is not None and now - float(pend.get("t0", now)) < older_than:
                continue
            if session is not None and _session_key(pend.get("actor") or {}) != session:
                continue
            if agent is not None and str((pend.get("actor") or {}).get("agent") or "") != agent:
                continue
            done.append(step)
        if not done:
            return []
        prev, idx, idx_sha = self._observe(st)
        if any(not st["pending"][s].get("pre_index") for s in done):
            self._gap_since(st, prev, idx, idx_sha, "open_step_unobserved_start")
        out = []
        for step in done:
            pend = st["pending"].pop(step)
            st["n_steps"] = int(st.get("n_steps", 0)) + 1
            end_sha = pend.get("bound_index") or (idx_sha if idx is not None else None)
            changes = W.diff(self.load_index(pend["pre_index"]), self.load_index(end_sha)) \
                if pend.get("pre_index") and end_sha else []
            payload = {"step": step, "n": st["n_steps"], "actor": pend["actor"],
                       "tool": pend["tool"], "input_blob": pend["input_blob"],
                       "writes": [c.to_json() for c in changes], "output_blob": None,
                       "error": None, "pre_index": pend["pre_index"], "post_index": end_sha,
                       "concurrent_with": sorted(set(pend.get("concurrent_with") or [])
                                                 | (set(done) - {step})),
                       "pre_missing": False, "post_missing": why,
                       "observed_by": "vacant_scan"}
            if not (pend.get("pre_index") and end_sha):
                payload["writes_unknown"] = "the workspace was not observed around this step"
            out.append({**payload, **self._append("step", payload)})
        if idx is not None and any(x["post_index"] == idx_sha for x in out):
            # 至少一步的寫入算到了「現在」：上次看到的狀態前進到現在（否則同一批改動會再被記成缺口）。
            # 全部都有界（同一個行動者後來又開始了下一步）⇒ 不前進：界之後沒人解釋的改動，
            # 下一次看的時候照樣是缺口（2026-09-24 審查 recorder#1 的驗證）
            st["last_index"] = idx_sha
        return out

    def checkpoint(self, observed_at: str = "check") -> str:
        """追緝之前再看一次工作區：上次看到之後、沒有任何步驟在進行時的改動記成缺口。
        回傳現在這個狀態的索引 sha256。"""
        with self._lock():
            st = self._state()
            prev, idx, idx_sha = self._observe(st)
            if prev is not None and idx is not None and \
                    not any(v.get("pre_index") for v in st["pending"].values()):
                gap = [c.to_json() for c in W.diff(prev, idx)]
                if gap:
                    self._append("unrecorded_change", {"changes": gap, "n": len(gap),
                                                       "before_index": st["last_index"],
                                                       "after_index": idx_sha,
                                                       "observed_at": observed_at})
            st["last_index"] = idx_sha
            self._save(st)
            return idx_sha or ""

    def prompt(self, text: str, *, session: str = "*", source: str = "user",
               tool_use_id: str | None = None, agent: str | None = None,
               spawned_by: str | None = None) -> dict[str, Any]:
        """任務訊息（使用者的話、`vacant do` 送出的提示）：追緝判斷「這個值是不是任務自己給的」。
        內容只進本機版本庫，鏈上是 sha256。`session="*"`＝這個工作區裡的任何工作階段。
        `source`：`user`／`vacant do`＝任務給的；`subagent_result`＝平台把子 agent 的結果當成一則
        使用者訊息送回（Claude 的 `<task-notification>`）；`parent_agent`＝子 agent 收到的任務說明。"""
        payload: dict[str, Any] = {"session": session, "source": source,
                                   "text_blob": self.blobs.put_bytes(text.encode())}
        if tool_use_id:
            payload["tool_use_id"] = tool_use_id
        if agent:
            payload["agent"] = agent                 # 這是哪一個子 agent 收到的任務說明
        if spawned_by:
            payload["spawned_by"] = spawned_by       # 叫它出來的那一步（父 agent 的工具呼叫）
        with self._lock():
            return self._append("prompt", payload)

    def subagent_state(self, actor: Actor, *, running: bool) -> dict[str, Any]:
        """子 agent 開始／結束（Claude／Codex 的 SubagentStart／SubagentStop）。只記在狀態裡：
        用來判斷「主 agent 的回合結束時，還有沒有它叫出來的子 agent 在做事」。"""
        if not actor.agent:
            return {}
        with self._lock():
            st = self._state()
            subs = st.setdefault("subagents", {})
            key = f"{actor.platform}:{actor.session}:{actor.agent}"
            subs[key] = {"running": running, "t": time.time()}
            self._save(st)
            return dict(subs[key])

    def running_subagents(self, session_key: str, *, max_age: float = SUBAGENT_MAX_S
                          ) -> list[str]:
        """這個工作階段裡開始了、還沒結束的子 agent（超過 `max_age` 沒消息的當成已經結束：
        漏掉一個 SubagentStop 不可以讓驗收永遠不跑）。"""
        now = time.time()
        subs = self._state().get("subagents") or {}
        return sorted(k for k, v in subs.items()
                      if k.startswith(session_key + ":") and v.get("running")
                      and now - min(float(v.get("t", 0)), now) < max_age)

    def should_defer(self, session_key: str) -> bool:
        """主 agent 的回合結束要不要先不驗收：有子 agent 在做，而且**連續**延後還沒到上限。
        不設上限的話，每一回合都先叫一個背景子 agent 的主 agent 就永遠不被驗（2026-09-24 審查 defer#3）。
        真的驗了（沒子 agent、或到了上限）就把連續次數歸零。"""
        running = self.running_subagents(session_key)
        with self._lock():
            st = self._state()
            cnt = st.setdefault("deferrals", {})
            n = int(cnt.get(session_key, 0))
            defer = bool(running) and n < MAX_DEFERRALS
            cnt[session_key] = n + 1 if defer else 0
            self._save(st)
            return defer

    def link_child(self, actor: Actor, parent_agent: str | None,
                   task: str | None = None) -> dict[str, Any]:
        """另開行程的子 agent（pi）是哪一個工具呼叫叫出來的：拿它收到的任務文字去對父 agent
        **還在跑**的呼叫的輸入。對到恰好一個 ⇒ 那一步、以及它指定的代理人；對不到或對到好幾個 ⇒
        不猜（2026-09-24 子 agent 審查 #3、#4）。結果記在狀態裡，同一個子 agent 之後的事件沿用。"""
        with self._lock():
            st = self._state()
            links = st.setdefault("children", {})
            key = f"{actor.platform}:{actor.session}:{actor.agent}"
            if key in links or task is None:
                return dict(links.get(key) or {})
            root = f"{actor.platform}:{actor.session}"
            hits: list[tuple[str, str | None]] = []
            for step, pend in sorted(st["pending"].items()):
                a = pend.get("actor") or {}
                if _session_key(a) != root or str(a.get("agent") or "") != str(parent_agent or ""):
                    continue
                try:
                    inp = json.loads(self.blobs.get(pend["input_blob"]))
                except (OSError, ValueError):
                    continue
                ok, typ = _task_in(inp, task)
                if ok:
                    hits.append((step, typ))
            info: dict[str, Any] = {"spawned_by": None, "agent_type": None}
            if len(hits) == 1:
                info = {"spawned_by": hits[0][0], "agent_type": hits[0][1]}
            elif hits:
                info["candidates"] = [h[0] for h in hits]
            links[key] = info
            self._save(st)
            return dict(info)

    def append(self, etype: str, payload: dict[str, Any]) -> dict[str, Any]:
        """追緝結論、人的標記：同一條鏈、同一把鎖。"""
        with self._lock():
            return self._append(etype, payload)

    def settle(self, actor: Actor, why: str = "turn_end") -> list[dict[str, Any]]:
        """回合結束：**這個行動者**還開著的步驟不會再有 `post` 了（背景行程另計，誠實邊界 2）。
        只收它自己的：主 agent 的回合結束時，背景子 agent 可能正在一步的中間（審查 defer#4）。"""
        with self._lock():
            st = self._state()
            out = self._finish_open(st, why, session=f"{actor.platform}:{actor.session}",
                                    agent=actor.agent or "")
            self._save(st)
            return out

    def close(self, actor: Actor, reason: str | None = None) -> dict[str, Any]:
        """工作階段結束：最後再看一次，沒被任何一步解釋的改動記成缺口。"""
        with self._lock():
            st = self._state()
            key = f"{actor.platform}:{actor.session}"
            open_steps = sorted(k for k, v in st["pending"].items()
                                if _session_key(v.get("actor") or {}) == key)
            self._finish_open(st, "session_end", session=key)
            # 工作階段結束：它的子 agent 不會活得比它久（沒送 SubagentStop 的也一樣；審查 defer#1）
            for k in list((st.get("subagents") or {})):
                if k.startswith(key + ":"):
                    st["subagents"][k]["running"] = False
            (st.get("deferrals") or {}).pop(key, None)
            prev, idx, idx_sha = self._observe(st)
            gap = [c.to_json() for c in W.diff(prev, idx)] \
                if prev is not None and idx is not None and \
                not any(v.get("pre_index") for v in st["pending"].values()) else []
            if gap:
                self._append("unrecorded_change", {"changes": gap, "n": len(gap),
                                                   "before_index": st["last_index"],
                                                   "after_index": idx_sha,
                                                   "observed_at": "session_end"})
            st["sessions"].setdefault(key, {})["closed"] = True
            ref = self._append("session_closed", {"actor": actor.to_json(), "reason": reason,
                                                  "final_index": idx_sha,
                                                  "open_steps": open_steps})
            st["last_index"] = idx_sha
            self._save(st)
            return ref

    # ── reading back ─────────────────────────────────────────────────
    def _book(self) -> tuple[Logbook, int]:
        """整條鏈；尾巴那半行（寫到一半被砍）不算，回傳它的位元組數。"""
        data = self.chain_path.read_bytes() if self.chain_path.is_file() else b""
        torn = 0
        if data and not data.endswith(b"\n"):
            cut = data.rfind(b"\n") + 1
            torn, data = len(data) - cut, data[:cut]
        entries = [LogEntry.from_json(json.loads(x)) for x in data.split(b"\n") if x.strip()]
        return Logbook(entries), torn

    def events(self) -> list[dict[str, Any]]:
        if not self.chain_path.is_file():
            return []
        return [{"seq": e.seq, "type": e.type, "ts_ms": e.ts_ms, "hash": e.hash(),
                 **(e.payload or {})} for e in self._book()[0].entries]

    def verify(self, trust: _keys.Trust | None = None) -> tuple[bool, str]:
        from ..identity import PublicIdentity
        if not self.chain_path.is_file():
            return False, "no trace"
        book, torn = self._book()
        if not book.entries:
            return False, "trace chain is empty"
        signer = (book.entries[0].payload or {}).get("signer")
        t = trust or _keys.Trust.load()
        name = t.name_of("verifier", str(signer))
        if name is None:
            return False, "trace signer is not on the accepted-signer list"
        if not book.verify_chain(PublicIdentity.from_hex(name, str(signer))):
            return False, "trace chain does not verify"
        try:
            head = json.loads((self.dir / "head.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            head = None
        last = book.entries[-1]
        if head and (int(head.get("seq", 0)) > last.seq or
                     (int(head.get("seq", 0)) == last.seq and head.get("hash") != last.hash())):
            return False, (f"trace chain ends at entry {last.seq} but its recorded head is entry "
                           f"{head.get('seq')} (truncated or replaced)")
        if torn:
            return True, f"{len(book)} entries (+{torn} bytes of a torn last line, not counted)"
        return True, f"{len(book)} entries"


def main(argv: list[str] | None = None) -> int:
    """`python -m vacant_network.trace.recorder baseline <工作區>`：背景的第一次完整觀察。"""
    import sys
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2 or args[0] != "baseline":
        print("usage: python -m vacant_network.trace.recorder baseline <workspace>",
              file=sys.stderr)
        return 2
    print(json.dumps(Recorder(args[1]).baseline()))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
