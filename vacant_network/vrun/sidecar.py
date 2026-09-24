"""這支在架構裡承重什麼：**不碰模型端點的可究責層**（旁路 sidecar）原型。

`decisions/DECISION_20260924_MEDIATION_WITHOUT_MODEL_WRAP.md` 是這支的規格與量測紀錄。

## 為什麼要有這一支

既有中介（`wireproxy`／`proxyd`／`possess`）建立在「把 agent 的模型端點改指向本機
proxy」。人類 2026-09-24 否決這個地基：閉源／託管的 agent 不給改——
`ops/vacantrun/possess_claude_20260922/README.md` §一 量到 Claude Code 在
`CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST=1` 下**忽略** settings.json 的 base URL
而且照樣正常回答；Codex 的 ChatGPT 登入走 `wss://`；訂閱／OAuth／憑證釘選同理。

這一支把可究責性建立在**三個不需要改模型端點的來源**上，並讓它們互相對帳：

  1. **agent 自己的掛鉤事件**（Claude Code hooks；pi／OpenCode／Codex／Hermes
     各有對應，`DECISION_20260920_AGENT_HOOKS_MEASURED.md`）——
     每一個事件**同步**送到 collector，collector 當場簽進 logbook。
  2. **agent 自己寫的 session transcript**——每一通模型回應帶 `requestId`、
     每一個工具呼叫帶 `tool_use_id`；collector 在每個掛鉤事件當下量
     transcript 的 `(size, prefix_sha256)` 並簽進鏈 ⇒ 事後改 transcript 看得出來。
  3. **工作區樹雜湊**（`wshash`）——起點與終點，差異檔案要被工具事件解釋。

## 契約（`vacant-sidecar/1`）

    VACANT_SC_ADDR       collector 的 host:port（**TCP 127.0.0.1**：Windows 也有）
    VACANT_SC_TOKEN      每跑一個的隨機 token（擋同機別的使用者，**擋不住 agent 自己**）
    VACANT_SC_FAILCLOSED 1 ⇒ PreToolUse 收不到 ack 就**拒絕執行那個工具**（write-ahead）
    VACANT_SC_FALLBACK   收不到 ack 時落一行的檔案（降級證據，不上鏈）

掛鉤那一端＝`python -m vacant_network.vrun.sidecar hook <Event>`，stdin 是 agent
丟進來的 JSON。**原文只送到 collector 的記憶體，鏈上只放雜湊與路徑**（沿用
`hookcli` 誠實邊界 1：payload 可能含 prompt 全文、檔案內容、憑證）。

## 對帳（`reconcile()`）——**以 id 對 id，不是通數對通數**

  · `tool_uses_without_prehook`：transcript 有、鏈上沒有 PreToolUse 的 tool_use
    ＝**沒有事前紀錄就做了的動作**（掛鉤中途被拆、被 `--bare` 關掉……）。
  · `prehook_without_transcript`：鏈上有、transcript 沒有 ＝ transcript 被刪改或截斷。
  · `transcript_append_only`：鏈上每個 checkpoint 的 `(size, prefix_sha256)`
    對最終 transcript 重算。
  · `ws_unexplained`：工作區有變、而且**沒有任何工具事件解釋得了**的檔案。
    有 Bash 類事件的跑，變動檔案只能歸到 `shell`（不透明）——那不是「解釋了」。
  · `model_requests_reported`：transcript 裡相異 `requestId` 的數目。
    ⚠ **這是 agent 自報，不是 Vacant 觀測**；欄位名與收據上的句子都要帶著這一點。

## 級別：`record_tier`（紀錄級）＋ `channel_tier`（恆為 `unobserved`）

A/B/B′/C 是**通道級**（模型通道有沒有漏網）。本檔完全不看模型通道，所以
用另一組名字，而且收據上兩欄並列、`channel_tier` **不准留空**
（Fable 判斷 #1 Q2；`ops/research_20260924/fable/Q1_mediation_design.md`）。

| record_tier | 條件 | 收據能說的話（`CLAIMS`） |
|---|---|---|
| `R-full` | canary 燒 ＋ tool_use id 雙向 1:1 ＋ transcript 只增 ＋ SessionEnd 之後 transcript 沒再長 ＋ 工作區每個改動都歸得給 Write/Edit ＋ 掛鉤設定沒變 ＋ 全程 fail-closed | 工作區每個改動都對得上一個**在改動之前就簽進鏈**的工具事件；模型呼叫數為 agent 自報 |
| `R-opaque` | 同上，但有改動只能歸給不透明的 shell | shell 動作有事前紀錄，它改了什麼說不出來 |
| `R-partial` | 沒有量到不一致，但有**沒量到**的項目 | 有紀錄、有缺口 |
| `R-broken` | 量到不一致 | 紀錄與 transcript／工作區對不上 |
| `R-none` | canary 沒燒，或 transcript 不存在 | **拒發收據** |

`R-partial` 是本檔比 Fable 的四級多出來的一級：「沒量到」既不是「對不上」
也不是「對得上」（鐵律 3），塞進 `R-broken` 會把設定選擇講成攻擊。

## 誠實邊界（改碼請保留，每一條都是量出來的或推得出來的）

1. **這一層說不出「每一通模型呼叫都經過 Vacant」**。它說得出的是
   「agent 經由**自己的工具**做的每一個動作都有事前紀錄」。模型呼叫數只有
   agent 自報的那一個；框架自己發起的呼叫（標題生成、遙測、更新）**不經過工具層，
   也不一定寫進 transcript**。
2. **掛鉤跟 agent 同一個 uid**：agent 拆得掉 user-level 掛鉤（09-20 實測）。
   本檔能做的是讓拆掉**看得見**（`tool_uses_without_prehook`、`hook_cfg_changed`），
   不是讓它拆不掉。拆不掉要靠 managed settings（root／Administrator 持有）——**本檔沒量**。
3. **transcript 是 agent 寫的**。append-only 檢查只抓得到「checkpoint 之後被改動
   checkpoint 之前的位元組」；agent 在寫入當下就寫假的，本檔抓不到。
   id 對帳能抓到的是**兩個來源不一致**，不是「兩個都假」。
4. **token 擋不住 agent**：`VACANT_SC_TOKEN` 在 agent 的環境變數裡，agent 的 Bash
   看得到，可以對 collector 送假事件。假事件會變成 `prehook_without_transcript`
   （transcript 沒有那個 id）——**偵測，不是防止**。
5. **工作區歸因是檔案層級的**：Write/Edit 事件的 `file_path` 解釋得了那個檔；
   Bash 事件只能把變動歸到「shell（不透明）」。`ws_unexplained == 0` 在有 Bash
   的跑裡**弱**，收據上 `ws_shell_attributed` 要跟著講。
6. **write-ahead 只在掛鉤還在場時成立**（Fable 判斷 #1 的更正）。
   掛鉤被拆掉之後的動作**事前沒有紀錄**，本檔只能事後從 transcript 發現它們。
7. **fail-closed 只管 PreToolUse**。collector 死掉時 agent 仍可以繼續**想**（模型
   呼叫不經過本層），只是工具全部被拒——這正是要的性質，但它也代表
   collector 是單點：它死了，這一跑做不完事。
8. **只有主 transcript 有 checkpoint**。子代理的 transcript（`subagents/*.jsonl`）
   有讀進 id 對帳，但事後改它，append-only 檢查看不到。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import secrets
import socket
import socketserver
import sys
import threading
import time
from typing import Any

CONTRACT = "vacant-sidecar/1"
SC_EVENT = "sc_event"
SC_VERDICT = "sc_verdict"

#: Claude Code 的事件（2.1.281 在本 session 實測觸發過的，`ops/research_20260924/mediation/`）。
CLAUDE_EVENTS = ("SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse",
                 "PostToolUseFailure", "Stop", "SubagentStart", "SubagentStop",
                 "SessionEnd", "PreCompact", "Notification")
_TOOL_EVENTS = ("PreToolUse", "PostToolUse", "PostToolUseFailure")

#: 工具輸入裡哪幾個欄位是「這個工具寫了哪個檔」（檔案層歸因用）。
_EDIT_TOOLS = {"Write": ("file_path",), "Edit": ("file_path",),
               "MultiEdit": ("file_path",), "NotebookEdit": ("notebook_path",)}
#: 做了什麼無法從輸入看出的工具（變動只能歸到 shell）。
_OPAQUE_TOOLS = ("Bash", "PowerShell", "Task", "Agent")
#: 會在執行窗裡「不該再有別的 PreToolUse」的工具。**不含 Task／Agent**：
#: 子代理的工具事件本來就發生在 Task 的窗裡。
_SHELL_TOOLS = ("Bash", "PowerShell")

RECORD_TIERS = ("R-full", "R-opaque", "R-partial", "R-broken", "R-none")


def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def canon(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


# ───────────────────────── collector ─────────────────────────

class _TranscriptTracker:
    """逐步雜湊 transcript：只讀新增的位元組（O(新位元組)），出一個 prefix 雜湊，
    並順手解析**完整的新行**，累積「到這一刻為止 transcript 裡出現過的 tool_use id」。

    ⚠ 檔案變短或舊位元組被改，這裡**不會當場發現**（只讀尾巴）——那是
    `verify_transcript_checkpoints()` 在收尾時對整份重算的工作。
    ⚠ id 集合是 Fable 判斷 #1 Q3-1 的建議：只有 size＋prefix 雜湊的話，
    agent 事後在尾巴**追加**一筆假 tool_use 不會露餡；有了「那個事件發生當下
    transcript 裡有沒有這個 id」，事後追加就對不上時間。
    """

    def __init__(self) -> None:
        self.path: str | None = None
        self.offset = 0
        self.h = hashlib.sha256()
        self.partial = b""
        self.tool_ids: set[str] = set()

    def _ingest(self, new: bytes) -> None:
        buf = self.partial + new
        lines = buf.split(b"\n")
        self.partial = lines.pop()
        for ln in lines:
            if b'"tool_use"' not in ln:
                continue
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            m = r.get("message") if isinstance(r.get("message"), dict) else {}
            c = m.get("content")
            if r.get("type") == "assistant" and isinstance(c, list):
                for b in c:
                    if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("id"):
                        self.tool_ids.add(b["id"])

    def checkpoint(self, path: str | None) -> dict:
        if not path:
            return {"size": None, "prefix_sha256": None, "path_sha256": None,
                    "tool_ids_n": None}
        if path != self.path:  # 換檔（新 session）⇒ 重新起算
            self.__init__()
            self.path = path
        try:
            with open(path, "rb") as f:
                f.seek(self.offset)
                new = f.read()
        except OSError:
            return {"size": None, "prefix_sha256": None,
                    "path_sha256": sha256_hex(path.encode()), "tool_ids_n": None}
        self.h.update(new)
        self.offset += len(new)
        self._ingest(new)
        return {"size": self.offset, "prefix_sha256": self.h.copy().hexdigest(),
                "path_sha256": sha256_hex(path.encode()),
                "tool_ids_n": len(self.tool_ids)}


def digest_event(event: str, payload: dict) -> dict:
    """掛鉤 payload → 上鏈的欄位。**原文不上鏈**，只有雜湊、id、路徑。"""
    ti = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else None
    tool = payload.get("tool_name")
    paths: list[str] = []
    if ti is not None and tool in _EDIT_TOOLS:
        for k in _EDIT_TOOLS[tool]:
            if isinstance(ti.get(k), str):
                paths.append(ti[k])
    return {
        "event": event,
        "hook_event_name": payload.get("hook_event_name"),
        "session_id": payload.get("session_id"),
        "prompt_id": payload.get("prompt_id"),
        "tool_name": tool,
        "tool_use_id": payload.get("tool_use_id"),
        "tool_input_sha256": sha256_hex(canon(ti)) if ti is not None else None,
        "edit_paths": paths,
        "cwd": payload.get("cwd"),
        "payload_sha256": sha256_hex(canon(payload)),
    }


class Collector:
    """localhost TCP collector：**金鑰只在這個行程的記憶體裡**，每個事件當場簽。

    一行 JSON 進、一行 JSON 出。`op=event` 回 `{"ok":true,"seq":n}`；
    token 不對回 `{"ok":false}`（而且**照樣記一筆** `sc_reject`，不讓它安靜消失）。
    """

    def __init__(self, *, hook_cfg_path: str | None = None,
                 identity=None, raw_log: str | None = None) -> None:
        from ..identity import Identity
        from ..logbook import Logbook
        self.ident = identity or Identity.generate()
        self.book = Logbook()
        self.token = secrets.token_hex(16)
        self.hook_cfg_path = hook_cfg_path
        self.raw_log = raw_log  # 偵錯用；正式跑不開（原文不落盤）
        self._lock = threading.Lock()
        self._tt = _TranscriptTracker()
        self.events: list[dict] = []
        self.transcript_paths: list[str] = []  # 只在記憶體；鏈上只有路徑雜湊
        self.rejects = 0
        self._srv: socketserver.ThreadingTCPServer | None = None
        self.addr: str | None = None

    def hook_cfg_sha256(self) -> str | None:
        if not self.hook_cfg_path:
            return None
        try:
            return sha256_hex(pathlib.Path(self.hook_cfg_path).read_bytes())
        except OSError:
            return "MISSING"

    def append(self, etype: str, payload: dict):
        with self._lock:
            e = self.book.append(etype, payload, self.ident,
                                 ts_ms=int(time.time() * 1000))
            return e

    def handle(self, msg: dict) -> dict:
        if msg.get("op") == "ping":
            return {"ok": True}
        if msg.get("token") != self.token:
            self.rejects += 1
            self.append("sc_reject", {"reason": "bad_token",
                                      "msg_sha256": sha256_hex(canon(msg))})
            return {"ok": False, "reason": "bad_token"}
        event = str(msg.get("event") or "")
        payload = msg.get("payload") if isinstance(msg.get("payload"), dict) else {}
        d = digest_event(event, payload)
        tp = payload.get("transcript_path")
        if isinstance(tp, str) and tp not in self.transcript_paths:
            self.transcript_paths.append(tp)
        with self._lock:
            d["transcript"] = self._tt.checkpoint(payload.get("transcript_path"))
            tid = d.get("tool_use_id")
            # 事件當下，transcript 裡有沒有這個 id（None＝不是工具事件或量不到）
            d["id_in_transcript_prefix"] = (
                (tid in self._tt.tool_ids) if tid and d["transcript"]["size"] is not None
                else None)
        d["hook_cfg_sha256"] = self.hook_cfg_sha256()
        d["contract"] = CONTRACT
        d["t_recv"] = time.time()
        if self.raw_log:
            with open(self.raw_log, "a", encoding="utf-8") as f:
                f.write(json.dumps({"event": event, "payload": payload},
                                   ensure_ascii=False) + "\n")
        e = self.append(SC_EVENT, d)
        self.events.append(d)
        return {"ok": True, "seq": e.seq}

    def start(self) -> str:
        coll = self

        class H(socketserver.StreamRequestHandler):
            def handle(self):  # noqa: D401
                line = self.rfile.readline(4 << 20)
                try:
                    resp = coll.handle(json.loads(line))
                except Exception as ex:  # 壞輸入不可以弄死 collector
                    resp = {"ok": False, "reason": f"bad_request:{type(ex).__name__}"}
                self.wfile.write((json.dumps(resp) + "\n").encode())

        socketserver.ThreadingTCPServer.allow_reuse_address = True
        self._srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H)
        self._srv.daemon_threads = True
        host, port = self._srv.server_address[:2]
        self.addr = f"{host}:{port}"
        threading.Thread(target=self._srv.serve_forever, daemon=True).start()
        self.append("sc_start", {"contract": CONTRACT,
                                 "hook_cfg_sha256": self.hook_cfg_sha256()})
        return self.addr

    def stop(self) -> None:
        if self._srv:
            self._srv.shutdown()
            self._srv.server_close()
            self._srv = None


# ───────────────────────── hook 端 ─────────────────────────

def send(addr: str, msg: dict, timeout: float = 5.0) -> dict | None:
    host, port = addr.rsplit(":", 1)
    try:
        with socket.create_connection((host, int(port)), timeout=timeout) as s:
            s.sendall((json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8"))
            buf = b""
            while not buf.endswith(b"\n"):
                chunk = s.recv(65536)
                if not chunk:
                    break
                buf += chunk
        return json.loads(buf) if buf else None
    except (OSError, ValueError):
        return None


def hook_main(event: str, stdin_text: str, env: dict | None = None) -> tuple[int, str]:
    """掛鉤入口的純函式版（測試直接呼叫）。回 `(exit_code, stderr_text)`。

    ⚠ 除了 fail-closed 那一條，**任何失敗都回 0**：掛鉤自己壞掉不可以弄死 agent
    （`hookcli` 誠實邊界 3）。後果是收據降級，那正確。
    """
    env = os.environ if env is None else env
    addr = env.get("VACANT_SC_ADDR")
    if not addr:
        return 0, ""
    try:
        payload = json.loads(stdin_text) if stdin_text.strip() else {}
    except ValueError:
        payload = {"_unparsable_sha256": sha256_hex(stdin_text.encode())}
    # ⚠ 自己的逾時要比 agent 給掛鉤的逾時短：Claude Code 的掛鉤逾時是「不阻擋」，
    #   collector 吊死（不是死掉）會變成安靜放行（Fable 判斷 #1 Q3-2）。
    try:
        tmo = float(env.get("VACANT_SC_TIMEOUT") or 2.0)
    except ValueError:
        tmo = 2.0
    resp = send(addr, {"op": "event", "token": env.get("VACANT_SC_TOKEN"),
                       "event": event, "payload": payload}, timeout=tmo)
    if resp and resp.get("ok"):
        return 0, ""
    fb = env.get("VACANT_SC_FALLBACK")
    if fb:
        try:
            with open(fb, "a", encoding="utf-8") as f:
                f.write(json.dumps({"event": event, "t": time.time(),
                                    "tool_use_id": payload.get("tool_use_id"),
                                    "resp": resp}) + "\n")
        except OSError:
            pass
    if event == "PreToolUse" and env.get("VACANT_SC_FAILCLOSED") == "1":
        # Claude Code：PreToolUse exit 2 ⇒ 擋下這個工具，stderr 回給模型。
        return 2, ("vacant sidecar: 這個動作沒辦法先記錄下來（collector 沒有回應），"
                   "所以沒有執行。")
    return 0, ""


def claude_settings(hook_cmd: str, events=CLAUDE_EVENTS) -> dict:
    """給 Claude Code 的 settings 片段。工具事件要 matcher，其餘不要。"""
    hooks = {}
    for ev in events:
        # timeout 30 秒 ≫ 我們自己的 2 秒：逾時的裁量權留在我們這端（見 hook_main）。
        h = {"hooks": [{"type": "command", "command": f"{hook_cmd} {ev}", "timeout": 30}]}
        if ev in _TOOL_EVENTS:
            h["matcher"] = "*"
        hooks[ev] = [h]
    return {"hooks": hooks}


# ───────────────────────── transcript ─────────────────────────

DENY_MARKER = "vacant sidecar:"


def _result_text(b: dict) -> str:
    c = b.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return " ".join(x.get("text", "") for x in c if isinstance(x, dict))
    return ""


def transcript_files(path: str | os.PathLike | None) -> list[str]:
    """主 transcript ＋ 它的子代理 transcript（Claude Code 2.1.281：
    `<session>.jsonl` 旁邊的 `<session>/subagents/agent-*.jsonl`，A10 實測）。"""
    if not path or not os.path.exists(path):
        return []
    p = pathlib.Path(path)
    subs = sorted(str(x) for x in (p.parent / p.stem / "subagents").glob("*.jsonl"))
    return [str(p)] + subs


def transcript_skeleton(path: str | os.PathLike | None) -> dict | None:
    """從 Claude Code transcript 抽出對帳要的骨架：requestId、tool_use id、sidechain、
    以及哪些 tool_use 是**被 fail-closed 擋下、沒有執行**的。

    `None` ＝沒有 transcript（`--no-session-persistence` 或檔案不在）——**沒量到**，
    不是「零通」。子代理的檔案一起讀（`sidechain=True`），但**只有主檔有 checkpoint**
    （誠實邊界 8）。
    """
    files = transcript_files(path)
    if not files:
        return None
    req_ids: list[str] = []
    tool_uses: list[dict] = []
    tool_results: list[str] = []
    denied: list[str] = []
    bad_lines = 0
    for fi, fp in enumerate(files):
        with open(fp, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    bad_lines += 1
                    continue
                m = r.get("message") if isinstance(r.get("message"), dict) else {}
                c = m.get("content")
                if r.get("type") == "assistant":
                    rid = r.get("requestId")
                    if rid and rid not in req_ids:
                        req_ids.append(rid)
                    if isinstance(c, list):
                        for b in c:
                            if isinstance(b, dict) and b.get("type") == "tool_use":
                                tool_uses.append({"id": b.get("id"), "name": b.get("name"),
                                                  "sidechain": bool(r.get("isSidechain")) or fi > 0})
                elif r.get("type") == "user" and isinstance(c, list):
                    for b in c:
                        if isinstance(b, dict) and b.get("type") == "tool_result":
                            tool_results.append(b.get("tool_use_id"))
                            if b.get("is_error") and DENY_MARKER in _result_text(b):
                                denied.append(b.get("tool_use_id"))
    return {"request_ids": req_ids, "tool_uses": tool_uses, "tool_results": tool_results,
            "denied_failclosed": denied, "files_n": len(files), "bad_lines": bad_lines}


def verify_transcript_checkpoints(path: str | None, checkpoints: list[dict]) -> dict:
    """對最終 transcript 重算每個 checkpoint 的 prefix 雜湊。"""
    cps = [c for c in checkpoints if c.get("size") is not None]
    if not cps:
        return {"append_only": None, "checked": 0, "first_bad": None}
    if not path or not os.path.exists(path):
        return {"append_only": None, "checked": 0, "first_bad": None,
                "reason": "transcript_missing"}
    data = pathlib.Path(path).read_bytes()
    for i, c in enumerate(cps):
        if c["size"] > len(data) or sha256_hex(data[:c["size"]]) != c["prefix_sha256"]:
            return {"append_only": False, "checked": i + 1, "first_bad": i,
                    "final_size": len(data)}
    return {"append_only": True, "checked": len(cps), "first_bad": None,
            "final_size": len(data)}


# ───────────────────────── 對帳 ─────────────────────────

def _norm(p: str, cwd: str | None, ws: str) -> str | None:
    """工具的 file_path → 工作區相對路徑；工作區外回 None。"""
    try:
        ap = pathlib.Path(p)
        if not ap.is_absolute():
            ap = pathlib.Path(cwd or ws) / ap
        return os.path.relpath(os.path.realpath(ap), os.path.realpath(ws)).replace(os.sep, "/")
    except (OSError, ValueError):
        return None


def reconcile(events: list[dict], skeleton: dict | None, *,
              transcript_check: dict, ws_diff: dict | None, workspace: str,
              hook_cfg_start: str | None, hook_cfg_end: str | None,
              failclosed: bool | None) -> dict:
    """三源對帳。每一個欄位三態：值／值／`None`（沒量到）。"""
    pre = [e for e in events if e["event"] == "PreToolUse"]
    pre_ids = {e["tool_use_id"] for e in pre if e.get("tool_use_id")}
    canary = any(e["event"] == "SessionStart" for e in events)
    out: dict[str, Any] = {"contract": CONTRACT, "canary_fired": canary,
                           "hook_events_n": len(events),
                           "prehook_n": len(pre)}
    if skeleton is None:
        out.update(model_requests_reported=None, tool_uses_transcript_n=None,
                   tool_uses_denied_failclosed=None,
                   tool_uses_without_prehook=None, prehook_without_transcript=None,
                   sidechain_tool_uses_n=None)
    else:
        t_ids = [t["id"] for t in skeleton["tool_uses"] if t.get("id")]
        out["model_requests_reported"] = len(skeleton["request_ids"])
        out["tool_uses_transcript_n"] = len(t_ids)
        out["sidechain_tool_uses_n"] = sum(1 for t in skeleton["tool_uses"] if t["sidechain"])
        denied = set(skeleton.get("denied_failclosed") or [])
        # 被 fail-closed 擋下的動作**沒有執行**：它沒有事前紀錄是設計本身，不是缺口。
        # ⚠ 這個分類信的是 transcript 的 tool_result；agent 改 transcript 把一個
        #   執行過的動作寫成「被擋」，工作區差異會對不上（ws_unexplained）。
        out["tool_uses_denied_failclosed"] = sorted(set(t_ids) & denied - pre_ids)
        out["tool_uses_without_prehook"] = sorted(set(t_ids) - pre_ids - denied)
        out["prehook_without_transcript"] = sorted(pre_ids - set(t_ids))
    out["transcript_append_only"] = transcript_check.get("append_only")
    out["transcript_checkpoints_checked"] = transcript_check.get("checked")
    if ws_diff is None:
        out.update(ws_changed=None, ws_edit_attributed=None,
                   ws_shell_attributed=None, ws_unexplained=None)
    else:
        edit_paths = set()
        for e in pre:
            for p in e.get("edit_paths") or []:
                n = _norm(p, e.get("cwd"), workspace)
                if n:
                    edit_paths.add(n)
        opaque = any(e.get("tool_name") in _OPAQUE_TOOLS for e in pre)
        changed = sorted(set(ws_diff["added"]) | set(ws_diff["changed"]) | set(ws_diff["removed"]))
        ea = [p for p in changed if p in edit_paths]
        rest = [p for p in changed if p not in edit_paths]
        out["ws_changed"] = changed
        out["ws_edit_attributed"] = ea
        out["ws_shell_attributed"] = rest if opaque else []
        out["ws_unexplained"] = [] if opaque else rest
    out["hook_cfg_start_sha256"] = hook_cfg_start
    out["hook_cfg_end_sha256"] = hook_cfg_end
    out["hook_cfg_changed"] = (None if hook_cfg_start is None or hook_cfg_end is None
                               else hook_cfg_start != hook_cfg_end)
    out["failclosed"] = failclosed
    # ⚠ **資訊欄位，不進級別**：Fable #1 Q3-1 建議用「事件當下 transcript 裡有沒有
    #   這個 id」抓事後追加。實測（DECISION §四-3）Claude Code 2.1.281 寫 transcript
    #   是非同步的：誠實的 10 格裡 PreToolUse 當下 10/10 還沒寫進去，PostToolUse 當下
    #   也有 1 格還沒寫 ⇒ 當硬規則會把每一格誠實的跑判成 R-broken。量具會說謊的那一種。
    out["prehook_not_yet_in_transcript"] = sorted(
        e["tool_use_id"] for e in pre
        if e.get("tool_use_id") and e.get("id_in_transcript_prefix") is False)
    ends = [e for e in events if e["event"] == "SessionEnd"
            and (e.get("transcript") or {}).get("size") is not None]
    final_size = transcript_check.get("final_size")
    out["transcript_grew_after_session_end"] = (
        None if not ends or final_size is None else final_size > ends[-1]["transcript"]["size"])
    out["hook_events_inside_shell_window"] = shell_window_intrusions(events)
    out["channel_tier"] = "unobserved"  # 本層不看模型通道；**不准留空**（Fable #1 Q2）
    out["level"], out["gaps"] = level_of(out)
    return out


def shell_window_intrusions(events: list[dict]) -> list[str]:
    """不透明 shell 工具**執行中**（它的 Pre 與 Post 之間）冒出來的其他 PreToolUse。

    Claude Code 對 Bash／Write 這類非並行安全的工具是一個接一個跑的，所以誠實的跑
    這個清單應該是空的（誠實基線那十格量過，見 DECISION §四）。agent 從自己的
    Bash 裡對 collector 送假事件，時間上就會落在那個窗裡。
    ⚠ 這是**時序啟發式**，不是證明：agent 把偽造者丟到背景、等 Bash 回來之後才送，
    就不在窗裡（DECISION §四 A7c 量了這一格）。
    """
    open_shell: dict[str, bool] = {}
    bad: list[str] = []
    for e in events:
        tid = e.get("tool_use_id")
        if e["event"] == "PreToolUse":
            if open_shell and tid not in open_shell:
                bad.append(tid or "<no-id>")
            if e.get("tool_name") in _SHELL_TOOLS and tid:
                open_shell[tid] = True
        elif e["event"] in ("PostToolUse", "PostToolUseFailure") and tid in open_shell:
            open_shell.pop(tid, None)
    return bad


def level_of(r: dict) -> tuple[str, list[str]]:
    """紀錄級 `record_tier`。**沒量到（None）一律不算成立**。

    判斷順序：R-none（拒發）→ R-broken（量到不一致）→ R-partial（有沒量到的）
    → R-opaque（一致，但有變動只能歸給不透明的 shell）→ R-full。
    """
    if not r.get("canary_fired"):
        return "R-none", ["canary_not_fired"]
    if r.get("tool_uses_without_prehook") is None:
        return "R-none", ["transcript_missing"]
    broken, partial = [], []
    if r["tool_uses_without_prehook"]:
        broken.append("unrecorded_tool_uses")
    if r.get("prehook_without_transcript"):
        broken.append("phantom_hook_events")
    if r.get("transcript_grew_after_session_end"):
        broken.append("transcript_grew_after_session_end")
    if r.get("hook_events_inside_shell_window"):
        broken.append("hook_event_inside_shell_window")
    if r.get("transcript_append_only") is False:
        broken.append("transcript_not_append_only")
    elif r.get("transcript_append_only") is None:
        partial.append("transcript_append_only_unmeasured")
    if r.get("ws_unexplained") is None:
        partial.append("ws_unmeasured")
    elif r["ws_unexplained"]:
        broken.append("ws_unexplained_changes")
    if r.get("hook_cfg_changed") is True:
        broken.append("hook_cfg_changed")
    elif r.get("hook_cfg_changed") is None:
        partial.append("hook_cfg_unmeasured")
    if r.get("failclosed") is not True:
        partial.append("not_failclosed")
    if broken:
        return "R-broken", broken + partial
    if partial:
        return "R-partial", partial
    if r.get("ws_shell_attributed"):
        return "R-opaque", ["ws_shell_attributed"]
    return "R-full", []


# ───────────────────────── 收據與重驗 ─────────────────────────

def seal(coll: Collector, run_dir: pathlib.Path, *, reconciled: dict,
         skeleton: dict | None, transcript_path: str | None,
         ws_start: str | None, ws_end: str | None, accepted: bool | None,
         verdict_sha256: str | None, task_id: str) -> dict:
    """簽最後一筆 `sc_verdict` 並落盤。S0 ⇒ **不簽 verdict**（拒發收據）。"""
    from ..crypto import pub_to_hex
    run_dir.mkdir(parents=True, exist_ok=True)
    skel_sha = sha256_hex(canon(skeleton)) if skeleton is not None else None
    tr_sha = (sha256_hex(pathlib.Path(transcript_path).read_bytes())
              if transcript_path and os.path.exists(transcript_path) else None)
    issued = reconciled["level"] != "R-none"
    if issued:
        coll.append(SC_VERDICT, {
            "task_id": task_id, "accepted": accepted, "record_tier": reconciled["level"],
            "channel_tier": reconciled["channel_tier"], "level": reconciled["level"],
            "gaps": reconciled["gaps"], "reconciled_sha256": sha256_hex(canon(reconciled)),
            "skeleton_sha256": skel_sha, "transcript_sha256": tr_sha,
            "ws_start_sha256": ws_start, "ws_end_sha256": ws_end,
            "verdict_sha256": verdict_sha256,
            "claim": CLAIMS[reconciled["level"]]})
    coll.book.save(run_dir / "receipts_sidecar.ndjson")
    (run_dir / "receipts_sidecar.pub.json").write_text(json.dumps(
        {"vacant_id": coll.ident.vacant_id, "pub_hex": pub_to_hex(coll.ident.pub)}))
    (run_dir / "reconciled.json").write_text(json.dumps(reconciled, ensure_ascii=False, indent=1))
    (run_dir / "skeleton.json").write_text(json.dumps(skeleton, ensure_ascii=False))
    return {"issued": issued, "level": reconciled["level"]}


CLAIMS = {
    "R-full": ("這一跑，工作區每個改動都對得上一個在改動之前就簽進鏈的工具事件（Write/Edit），"
               "工具事件與 agent 自己的 transcript 逐 id 對得上；模型呼叫數為 agent 自報，"
               "Vacant 沒有觀測模型通道。"),
    "R-opaque": ("同 R-full，但有工作區改動只能歸給不透明的 shell 工具：那個 shell 動作有事前紀錄，"
                 "它改了什麼檔 Vacant 說不出來。"),
    "R-partial": "有工具層紀錄，但有沒量到的項目（列在 gaps）；不可讀成每一個動作都有事前紀錄。",
    "R-broken": "量到不一致（列在 gaps）：這一跑的紀錄與 agent 自己的 transcript 或工作區對不上。",
    "R-none": "拒發收據。",
}


def verify_run(run_dir: str | os.PathLike, transcript_path: str | None = None) -> dict:
    """第三方重驗：只用公鑰＋鏈＋（可選）transcript 全文，重算對帳並比對簽過的雜湊。

    四值：OK／BROKEN（鏈或雜湊對不上）／NO_RECEIPT（S0，本來就不發）／
    UNVERIFIABLE（缺檔）。
    """
    from ..identity import PublicIdentity
    from ..logbook import Logbook
    rd = pathlib.Path(run_dir)
    try:
        pub = json.loads((rd / "receipts_sidecar.pub.json").read_text())
        book = Logbook.load(rd / "receipts_sidecar.ndjson")
        reconciled = json.loads((rd / "reconciled.json").read_text())
        skeleton = json.loads((rd / "skeleton.json").read_text())
    except (OSError, ValueError) as ex:
        return {"verdict": "UNVERIFIABLE", "reason": str(ex)}
    who = PublicIdentity.from_hex(pub["vacant_id"], pub["pub_hex"])
    if not book.verify_chain(who):
        return {"verdict": "BROKEN", "reason": "chain"}
    verdicts = [e for e in book.entries if e.type == SC_VERDICT]
    if not verdicts:
        return {"verdict": "NO_RECEIPT", "reason": "R-none（拒發）或沒有收尾"}
    v = verdicts[-1].payload
    if v["reconciled_sha256"] != sha256_hex(canon(reconciled)):
        return {"verdict": "BROKEN", "reason": "reconciled.json 與簽過的雜湊不同"}
    skel_sha = sha256_hex(canon(skeleton)) if skeleton is not None else None
    if v["skeleton_sha256"] != skel_sha:
        return {"verdict": "BROKEN", "reason": "skeleton.json 與簽過的雜湊不同"}
    # 由鏈上事件＋骨架重算 id 對帳（不需要信任 reconciled.json 的那幾欄）
    events = [e.payload for e in book.entries if e.type == SC_EVENT]
    pre_ids = {e["tool_use_id"] for e in events if e["event"] == "PreToolUse" and e.get("tool_use_id")}
    out = {"verdict": "OK", "record_tier": v["record_tier"],
           "channel_tier": v["channel_tier"], "claim": v["claim"]}
    if skeleton is not None:
        t_ids = {t["id"] for t in skeleton["tool_uses"] if t.get("id")}
        denied = set(skeleton.get("denied_failclosed") or [])
        if sorted(t_ids - pre_ids - denied) != reconciled["tool_uses_without_prehook"]:
            return {"verdict": "BROKEN", "reason": "id 對帳重算不符"}
    if transcript_path:
        full = transcript_skeleton(transcript_path)
        if sha256_hex(canon(full)) != v["skeleton_sha256"]:
            return {"verdict": "BROKEN", "reason": "給的 transcript 抽不出簽過的骨架"}
        chk = verify_transcript_checkpoints(transcript_path, [e["transcript"] for e in events])
        out["transcript_recheck"] = chk
        if chk["append_only"] is False:
            return {"verdict": "BROKEN", "reason": "transcript 不是只增", **chk}
    return out


# ───────────────────────── CLI ─────────────────────────

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="vacant sidecar",
                                 description="不碰模型端點的可究責層（原型）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("hook", help="agent 掛鉤呼叫的入口（stdin＝事件 JSON）")
    h.add_argument("event")
    v = sub.add_parser("verify", help="第三方重驗一個 run 目錄")
    v.add_argument("run_dir")
    v.add_argument("--transcript")
    a = ap.parse_args(argv)
    if a.cmd == "hook":
        rc, err = hook_main(a.event, sys.stdin.read())
        if err:
            sys.stderr.write(err + "\n")
        return rc
    res = verify_run(a.run_dir, a.transcript)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0 if res["verdict"] == "OK" else (3 if res["verdict"] == "NO_RECEIPT" else 1)


if __name__ == "__main__":
    sys.exit(main())
