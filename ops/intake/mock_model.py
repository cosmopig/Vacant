#!/usr/bin/env python3
"""mock_model — **假模型供應商**：讓四個真 agent（pi／Claude Code／OpenCode／Codex）離線跑完整工具迴圈。

這支在架構裡承重什麼（`decisions/DECISION_20260924_UNIVERSAL_INTAKE.md` §七）：

證明「收件口不需要看模型流量」最乾淨的做法，是讓四個**未修改的** agent 各自用它們**自己的**
工具迴圈寫出成果，然後只在收件端判斷。這裡沒有真模型可用（沒有 API key、也不該花錢），
所以用一個照劇本回答的假上游代替「模型供應商」——它是 agent 設定裡的 provider，
**不是 Vacant 的中介**：Vacant 從頭到尾不碰這條線。

三種協定：

- Anthropic Messages（`POST /v1/messages`，SSE）         ← Claude Code
- OpenAI Responses（`POST /v1/responses`，SSE）          ← Codex
- OpenAI Chat Completions（`POST /v1/chat/completions`） ← pi、OpenCode

劇本（`MOCK_SCENARIO` 指向的 JSON）：`{"files": {"path": "content", ...}, "final": "..."}`，
或有序的 `{"steps": [{"run": "<指令>"} | {"write": ["<路徑>", "<內容>"]}, ...], "final": "..."}`
（可究責追緝的埋錯情境，`ops/accountability/e2e_trace.py`）；`fix` 段是看到回饋之後的劇本。
`GET /web/<名>` 回劇本 `"web"` 裡的那一頁（假的網頁；也可以當 `http_proxy` 用——那時請求是絕對網址；
`run` 裡的 `{{port}}` 換成這個假模型的埠）。
子 agent：步驟 `{"agent": {"prompt": "ROLE:<角色> …", "description": "…"}}` 用這個 agent 自己的委派工具
（Claude Code `Agent`／`Task`、OpenCode `task`、pi 範例擴充的 `subagent`）交出去；`"roles": {"<角色>": {劇本}}`
是子 agent 的劇本——對話**開頭的使用者訊息**裡有 `ROLE:<角色>` 的，照那一份演。
多回合（互動介面：人先問一句、之後才要它做事）：`"turns": [{"when": "<人那一則裡的一段字>", 劇本}, …]`
——照**人最近打的那一則**對到的那一段演，工具結果與回饋只數那一則之後的（`ops/accountability/e2e_tui.py`）。
每一通請求：數對話裡已經有幾個工具結果 k；k < 檔案數 ⇒ 叫一個「寫檔」工具寫第 k 個檔；
否則回最後那句話。工具從 agent **這一通送來的工具清單**裡挑：先找有「路徑＋內容」參數的
寫檔工具，沒有就用 shell 工具（`printf <base64> | base64 -d > path`）。

## 誠實邊界

1. 這是 **L-fake**：它證明的是「agent 的工具迴圈、掛鉤、工作區、收件口接得起來」，
   **不是**任何模型的能力，也不是真模型下的行為。
2. 劇本決定寫什麼，所以「成果好不好」完全由劇本控制——用它量的是收件口有沒有把
   壞劇本擋在目的端外、好劇本放進去，不是 agent 做得好不好。
3. **只收假金鑰**：模型請求帶的憑證（`x-api-key`、`Authorization: Bearer`）只要有一個不是 `sk-fake` 開頭，
   就回 401、記一筆 `{"auth": "rejected", "header": <哪一個標頭>}`——**不記值、不存標頭**。這樣一跑成功
   證明的是**送到這個假模型的每一通模型請求**都只帶實驗給的假金鑰——不是「agent 沒碰到機器上別的憑證」
   （2026-09-25：Claude Code 在隔離的 HOME 裡仍會提示它看得到主機的另一種憑證；它拿那個做什麼、送去哪裡，
   這裡量不到）。
"""
from __future__ import annotations

import base64
import itertools
import json
import os
import re
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

LOG = os.environ.get("MOCK_LOG")
#: SKILL.md 的描述裡一段獨特的字：出現在請求裡 ⇒ agent 把 Vacant 技能列給了模型。
SKILL_MARK = "Use when the project has a task contract"
_ctr = itertools.count(1)


def scenario() -> dict[str, Any]:
    p = os.environ.get("MOCK_SCENARIO")
    if p and os.path.isfile(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {"files": {"out.txt": "hello\n"}, "final": "Done."}


def log(rec: dict[str, Any]) -> None:
    if LOG:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": time.time(), **rec}, ensure_ascii=False) + "\n")


# ── 工具選擇（跨協定）──────────────────────────────────────────────────

_PATH_KEYS = ("file_path", "filePath", "path", "filename", "target_file")
_CONTENT_KEYS = ("content", "contents", "text", "file_text")


def _props(schema: Any) -> dict[str, Any]:
    if isinstance(schema, dict):
        return schema.get("properties") or {}
    return {}


def _tool_name(t: dict[str, Any]) -> str:
    if t.get("type") == "function" and isinstance(t.get("function"), dict):
        return str(t["function"].get("name", ""))
    return str(t.get("name", ""))


def pick_tool(tools: list[dict[str, Any]]) -> tuple[str, str, dict[str, str]] | None:
    """回 `(kind, name, argmap)`。kind ∈ write／shell_list／shell_str。"""
    norm = []
    for t in tools or []:
        if t.get("type") == "function" and isinstance(t.get("function"), dict):
            f = t["function"]
            norm.append((f.get("name", ""), f.get("parameters") or {}))
        else:
            norm.append((t.get("name", ""), t.get("input_schema") or t.get("parameters") or {}))
    for name, sch in norm:
        pr = _props(sch)
        pk = next((k for k in _PATH_KEYS if k in pr), None)
        ck = next((k for k in _CONTENT_KEYS if k in pr), None)
        if pk and ck and "edit" not in name.lower():
            return "write", name, {"path": pk, "content": ck}
    for name, sch in norm:
        pr = _props(sch)
        low = name.lower()
        if low in ("shell", "local_shell", "container.exec") and "command" in pr:
            typ = (pr["command"] or {}).get("type")
            return ("shell_list" if typ == "array" else "shell_str"), name, {"cmd": "command"}
        if low in ("exec_command", "bash", "run_shell_command") or "command" in pr or "cmd" in pr:
            key = "cmd" if "cmd" in pr else "command"
            typ = (pr.get(key) or {}).get("type")
            return ("shell_list" if typ == "array" else "shell_str"), name, {"cmd": key}
    return None


def tool_args(kind: str, argmap: dict[str, str], path: str, content: str,
              cwd_hint: str | None = None, raw_cmd: str | None = None) -> dict[str, Any]:
    if raw_cmd is not None:
        if kind == "shell_list":
            return {argmap["cmd"]: ["bash", "-lc", raw_cmd]}
        return {argmap["cmd"]: raw_cmd}
    if kind == "write":
        p = path
        if cwd_hint and argmap["path"] in ("file_path", "filePath"):
            p = os.path.join(cwd_hint, path)
        return {argmap["path"]: p, argmap["content"]: content}
    b64 = base64.b64encode(content.encode()).decode()
    d = os.path.dirname(path)
    cmd = (f"mkdir -p {d} && " if d else "") + f"printf '%s' {b64} | base64 -d > {path}"
    if kind == "shell_list":
        return {argmap["cmd"]: ["bash", "-lc", cmd]}
    return {argmap["cmd"]: cmd}


#: Vacant 回饋的開頭（`adapters/hookpolicy.FEEDBACK_HEADER`）。看到它 ⇒ 改用劇本的 `fix` 段。
FEEDBACK_MARK = "The task contract's checks do not pass yet"
#: 契約過了、但人標記了錯處（`trace/feedback.FLAG_HEADER`）：一樣是回饋
FLAG_MARK = "the task owner marked these places"


def feedback_excerpt(blob: str) -> str | None:
    """模型**真的收到**的回饋文字（最後一則，最多 800 字）：量回饋有沒有到、內容是什麼。"""
    i = blob.rfind(FEEDBACK_MARK)
    if i < 0:
        i = blob.rfind(FLAG_MARK)
    if i < 0:
        return None
    return blob[i:i + 800].encode().decode("unicode_escape", "replace") \
        if "\\n" in blob[i:i + 800] else blob[i:i + 800]


def split_on_feedback(items: list[Any], is_result, text_of) -> tuple[bool, int]:
    """回 `(看過回饋, 回饋之後的工具結果數)`；沒看過回饋 ⇒ 全部的工具結果數。"""
    last = -1
    for i, it in enumerate(items):
        txt = text_of(it)
        if FEEDBACK_MARK in txt or FLAG_MARK in txt:
            last = i
    after = items[last + 1:] if last >= 0 else items
    return last >= 0, sum(1 for it in after if is_result(it))


def pick_turn(user_texts: list[tuple[int, str]]) -> tuple[dict[str, Any] | None, int]:
    """劇本有 `turns`（互動介面的多回合：人問一句、再要它做事）：人**最近打的那一則**對到哪一段
    （`when` 是那一則裡的一段字）；回 `(那一段, 那一則在對話裡的位置)`。回饋被送回來的那幾則不算人打的。"""
    turns = scenario().get("turns")
    if not isinstance(turns, list):
        return None, -1
    for pos, txt in reversed(user_texts):
        if FEEDBACK_MARK in txt or FLAG_MARK in txt:
            continue
        for t in turns:
            if isinstance(t, dict) and t.get("when") and str(t["when"]) in txt:
                return t, pos
    return None, -1


ROLE_RE = re.compile(r"ROLE:([A-Za-z0-9_]+)")
#: 實驗給 agent 的假金鑰都是這個開頭（`e2e_four_agents.Lab.env`／`user_config`、R536 的冒煙）
FAKE_KEY_PREFIX = "sk-fake"


def role_of(opening: str) -> str | None:
    """對話開頭的使用者訊息 → 角色（子 agent 的任務說明帶著 `ROLE:<角色>`）。只看開頭：主 agent 之後
    收到的工具結果、子 agent 的回報都可能提到它，但那不會讓主 agent 變成子 agent。"""
    m = ROLE_RE.search(opening or "")
    return m.group(1) if m else None


def _text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(str(c.get("text") or "") for c in content
                         if isinstance(c, dict) and c.get("type") in ("text", "input_text"))
    return ""


def opening_user_text(msgs: list[dict[str, Any]]) -> str:
    """第一則助理訊息／工具呼叫之前的所有使用者訊息（Codex 會先送環境與指令檔）。"""
    out = []
    for m in msgs:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        if role in ("system", "developer"):
            continue
        if role != "user":
            break
        out.append(_text_of(m.get("content")))
    return "\n".join(out)


def _agent_tool(tools: list[dict[str, Any]], spec: dict[str, Any]
                ) -> tuple[str, dict[str, Any]] | None:
    """這個 agent 自己的委派工具＋參數。"""
    by = {_tool_name(t): t for t in tools}
    prompt = str(spec.get("prompt") or "")
    desc = str(spec.get("description") or "delegated task")
    for name in ("Agent", "Task"):                       # Claude Code
        if name in by:
            sch = by[name].get("input_schema") or {}
            args: dict[str, Any] = {"description": desc, "prompt": prompt,
                                    "subagent_type": spec.get("type") or "general-purpose"}
            if "run_in_background" in _props(sch):
                # 預設前景（做完才往下）；`background` ⇒ 背景，結果之後以 `<task-notification>` 回來
                args["run_in_background"] = bool(spec.get("background"))
            return name, args
    if "task" in by:                                     # OpenCode
        return "task", {"description": desc, "prompt": prompt,
                        "subagent_type": spec.get("type") or "general"}
    if "subagent" in by:                                 # pi 的範例擴充
        return "subagent", {"agent": spec.get("pi_agent") or "worker", "task": prompt}
    ns = by.get("multi_agent_v1") or {}                  # Codex：命名空間工具（v1，預設開）
    if ns.get("type") == "namespace" and any(_tool_name(x) == "spawn_agent"
                                             for x in ns.get("tools") or []):
        return "multi_agent_v1/spawn_agent", {"message": prompt}
    return None


def _expand_agent_steps(steps: list[Any], tools: list[dict[str, Any]]) -> list[Any]:
    """Codex 的委派是兩通：`spawn_agent` 之後 `wait_agent`（等它做完、拿回結果）。"""
    by = {_tool_name(t): t for t in tools}
    if (by.get("multi_agent_v1") or {}).get("type") != "namespace":
        return steps
    out: list[Any] = []
    for st in steps:
        out.append(st)
        if isinstance(st, dict) and "agent" in st:
            out.append({"codex_wait": True})
        elif isinstance(st, dict) and st.get("parallel"):
            # 一次叫了 k 個：`wait_agent` 在**第一個**做完時就回來，所以逐一等（最後 k 個 id）
            k = sum(1 for x in st["parallel"] if isinstance(x, dict) and "agent" in x)
            out.extend({"codex_wait": True, "of": k, "i": i} for i in range(k))
    return out


def _width(st: Any) -> int:
    """這一步會帶回幾個工具結果（平行的一批＝批裡的步數）。"""
    return len(st["parallel"]) if isinstance(st, dict) and st.get("parallel") else 1


def _step_call(st: dict[str, Any], tools: list[dict[str, Any]], cwd_hint: str | None,
               agent_ids: list[str]) -> tuple[str, dict[str, Any]] | None:
    """一步劇本 → `(工具名, 參數)`；這個 agent 沒有合適的工具 ⇒ None。"""
    if st.get("codex_wait"):
        if st.get("of"):
            k, i = int(st["of"]), int(st["i"])
            pick = agent_ids[len(agent_ids) - k + i] if len(agent_ids) >= k else ""
            return "multi_agent_v1/wait_agent", {"targets": [pick], "timeout_ms": 120000}
        return "multi_agent_v1/wait_agent", {"targets": (agent_ids or [""])[-1:],
                                             "timeout_ms": 120000}
    if "agent" in st:
        return _agent_tool(tools, st["agent"])
    if "run" in st:
        sh = _shell_tool(tools)
        if sh and sh[0] != "write":
            return sh[1], tool_args(sh[0], sh[2], "", "", None,
                                    raw_cmd=str(st["run"]).replace(
                                        "{{port}}", os.environ.get("MOCK_PORT", "")))
        return None
    path, content = st["write"]
    pk = pick_tool(tools)
    if pk and pk[0] == "write" and pk[2]["path"] in ("file_path", "filePath") and not cwd_hint:
        sh = pick_tool([t for t in tools if _tool_name(t) != pk[1]])
        if sh and sh[0] != "write":
            pk = sh
    if pk:
        return pk[1], tool_args(pk[0], pk[2], path, content, cwd_hint)
    return None


def _shell_tool(tools: list[dict[str, Any]]):
    return pick_tool([t for t in tools if _tool_name(t).lower() in (
        "bash", "shell", "exec_command", "local_shell", "run_shell_command")])


def plan(n_results: int, tools: list[dict[str, Any]], cwd_hint: str | None,
         fed_back: bool = False, role: str | None = None, last_agent_id: str | None = None,
         notified: bool = False, agent_ids: list[str] | None = None,
         section: dict[str, Any] | None = None):
    sc = section if section is not None else scenario()
    roles = sc.get("roles") or {}
    if role and isinstance(roles.get(role), dict):
        sc = roles[role]
    if fed_back and isinstance(sc.get("fix"), dict):
        sc = sc["fix"]
    steps = sc.get("steps")
    if isinstance(steps, list):
        steps = _expand_agent_steps(steps, tools)
        # `{"await": "notification"}`：等背景子 agent 的結果回來（不算一步工具呼叫）
        if any(isinstance(x, dict) and x.get("await") for x in steps):
            i = 0
            for k, x in enumerate(steps):
                if isinstance(x, dict) and x.get("await"):
                    if i >= n_results and not notified:
                        return ("text", "Waiting for the delegated task to finish.", None)
                    continue
                if i == n_results:
                    steps = [y for y in steps[k:] if not (isinstance(y, dict) and y.get("await"))]
                    n_results = 0
                    break
                i += 1
            else:
                steps, n_results = [], 0
        # 有序的步驟（可究責追緝的埋錯情境要「先寫腳本、再跑它」）：
        # {"run": "<shell 指令>"} 或 {"write": ["<路徑>", "<內容>"]}；{"parallel": [步驟, …]}＝同一則回覆裡的一批
        ids = agent_ids if agent_ids else ([last_agent_id] if last_agent_id else [])
        seen = 0
        for st in steps:
            if seen > n_results or not tools:
                break
            if seen == n_results:
                if st.get("parallel"):
                    calls = [c for c in (_step_call(x, tools, cwd_hint, ids)
                                         for x in st["parallel"]) if c]
                    if calls:
                        return ("tools", calls, None)
                    return ("text", "no tool for this batch", None)
                call = _step_call(st, tools, cwd_hint, ids)
                if call:
                    return ("tool", call[0], call[1])
                if "agent" in st:
                    return ("text", "no delegation tool available", None)
                break
            seen += _width(st)
        return ("text", str(sc.get("final", "Done.")), None)
    files = list((sc.get("files") or {}).items())
    pre = list(sc.get("pre_commands") or [])
    if n_results < len(pre) and tools:
        # 劇本要求先跑一條指令（例：契約禁止的 `git push`）——一律走 shell 工具
        shell = pick_tool([t for t in tools if _tool_name(t).lower() in (
            "bash", "shell", "exec_command", "local_shell", "run_shell_command")])
        if shell and shell[0] != "write":
            return ("tool", shell[1], tool_args(shell[0], shell[2], "", "", None,
                                                 raw_cmd=pre[n_results]))
    n_results -= len(pre)
    if n_results < len(files) and tools:
        pk = pick_tool(tools)
        if pk and pk[0] == "write" and pk[2]["path"] in ("file_path", "filePath") \
                and not cwd_hint:
            # 這類寫檔工具要絕對路徑；不知道工作目錄就改用 shell（相對於 cwd）
            shell = pick_tool([t for t in tools if _tool_name(t) != pk[1]])
            if shell and shell[0] != "write":
                pk = shell
        if pk:
            kind, name, argmap = pk
            path, content = files[n_results]
            return ("tool", name, tool_args(kind, argmap, path, content, cwd_hint))
    return ("text", str(sc.get("final", "Done.")), None)


def _cwd_hint(blob: str) -> str | None:
    # Claude Code 的寫檔工具要絕對路徑；它的 system prompt 裡有工作目錄。
    for marker in ("Working directory: ", "Primary working directory: ", "<cwd>"):
        i = blob.find(marker)
        if i >= 0:
            rest = blob[i + len(marker):]
            end = min([x for x in (rest.find("\\n"), rest.find("\n"), rest.find("<"),
                                    rest.find('"')) if x >= 0] or [len(rest)])
            v = rest[:end].strip()
            if v.startswith("/"):
                return v
    return None


# ── HTTP ─────────────────────────────────────────────────────────────

class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        return

    def _body(self) -> dict[str, Any]:
        n = int(self.headers.get("content-length") or 0)
        raw = self.rfile.read(n) if n else b""
        if self.headers.get("content-encoding") == "gzip" and raw:
            import gzip
            raw = gzip.decompress(raw)
        try:
            return json.loads(raw) if raw else {}
        except ValueError:
            return {}

    def _json(self, code: int, obj: Any) -> None:
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _sse(self, chunks: list[bytes]) -> None:
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.send_header("cache-control", "no-cache")
        self.send_header("connection", "close")
        self.end_headers()
        for c in chunks:
            self.wfile.write(c)
            self.wfile.flush()
        self.close_connection = True

    def do_HEAD(self):  # noqa: N802
        self.send_response(200)
        self.send_header("content-length", "0")
        self.end_headers()

    def do_GET(self):  # noqa: N802
        log({"method": "GET", "path": self.path})
        path = self.path
        if path.startswith("http://"):             # 當代理用（`http_proxy`）：絕對網址
            from urllib.parse import urlsplit
            path = urlsplit(path).path
        if path.startswith("/web/"):               # 劇本裡的「網頁」（情境 F：網頁本身就錯）
            page = (scenario().get("web") or {}).get(path[len("/web/"):])
            if page is not None:
                b = str(page).encode()
                self.send_response(200)
                self.send_header("content-type", "text/plain; charset=utf-8")
                self.send_header("content-length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)
                return None
        if "/models" in self.path:
            return self._json(200, {"object": "list", "data": [
                {"id": "mock-model", "object": "model", "owned_by": "mock"}], "has_more": False})
        return self._json(404, {"error": {"message": "mock: not found"}})

    def _foreign_credential(self) -> str | None:
        """帶了不是實驗假金鑰的憑證 ⇒ 回那個標頭的名字（只比開頭，值不記、不存）。"""
        auth = self.headers.get("authorization") or ""
        creds = {"x-api-key": self.headers.get("x-api-key"),
                 "authorization": auth[7:].strip() if auth.lower().startswith("bearer ") else
                 (auth or None)}
        for name, v in creds.items():
            if v is not None and not str(v).startswith(FAKE_KEY_PREFIX):
                return name
        return None

    def do_POST(self):  # noqa: N802
        body = self._body()
        n = next(_ctr)
        bad = self._foreign_credential()
        if bad:
            log({"method": "POST", "path": self.path.split("?")[0], "n": n, "auth": "rejected",
                 "header": bad})
            return self._json(401, {"error": {"type": "authentication_error",
                                              "message": "mock: only the experiment's fake key"}})
        if os.environ.get("MOCK_BODIES"):          # 除錯：每一通請求的原文（不含標頭）
            os.makedirs(os.environ["MOCK_BODIES"], exist_ok=True)
            with open(os.path.join(os.environ["MOCK_BODIES"], f"{n:03d}.json"), "w",
                      encoding="utf-8") as f:
                json.dump(body, f, ensure_ascii=False)
        path = self.path.split("?")[0]
        if path.endswith("/messages/count_tokens"):
            return self._json(200, {"input_tokens": 100})
        if path.endswith("/messages"):
            return self._anthropic(body, n)
        if path.endswith("/responses"):
            return self._responses(body, n)
        if path.endswith("/chat/completions"):
            return self._chat(body, n)
        log({"method": "POST", "path": self.path, "unhandled": True})
        return self._json(404, {"error": {"message": f"mock: no route {self.path}"}})

    # Anthropic Messages ---------------------------------------------------
    def _anthropic(self, body, n):
        msgs = body.get("messages", [])
        sec, pos = pick_turn([(i, _text_of(m.get("content"))) for i, m in enumerate(msgs)
                              if m.get("role") == "user"])
        blocks = [b for m in msgs[pos + 1:]
                  for b in (m.get("content") if isinstance(m.get("content"), list)
                            else [{"type": "text", "text": str(m.get("content"))}])]
        fed, k = split_on_feedback(blocks, lambda b: b.get("type") == "tool_result",
                                   lambda b: json.dumps(b))
        tools = body.get("tools") or []
        role = role_of(_text_of(msgs[0].get("content")) if msgs else "")
        notified = any(m.get("role") == "user" and "<task-notification>" in _text_of(m.get("content"))
                       for m in msgs)
        kind, a, b = plan(k, tools, _cwd_hint(json.dumps(body.get("system"))), fed, role,
                          notified=notified, section=sec)
        log({"proto": "anthropic", "n": n, "k": k, "fed_back": fed, "reply": kind, "role": role,
             "feedback": feedback_excerpt(json.dumps(body)) if fed else None,
             "skill_listed": SKILL_MARK in json.dumps(body),
             "tools": [t.get("name") for t in tools][:40], "tool": a if kind == "tool" else ([c[0] for c in a] if kind == "tools" else None)})
        model = body.get("model", "mock")
        calls = a if kind == "tools" else ([(a, b)] if kind == "tool" else [])
        if not body.get("stream"):
            content = ([{"type": "text", "text": a}] if kind == "text" else
                       [{"type": "tool_use", "id": f"toolu_{n}_{i}", "name": nm, "input": ar}
                        for i, (nm, ar) in enumerate(calls)])
            return self._json(200, {"id": f"msg_{n}", "type": "message", "role": "assistant",
                                    "model": model, "content": content,
                                    "stop_reason": "end_turn" if kind == "text" else "tool_use",
                                    "stop_sequence": None,
                                    "usage": {"input_tokens": 10, "output_tokens": 5}})

        def ev(name, data):
            return f"event: {name}\ndata: {json.dumps(data)}\n\n".encode()
        out = [ev("message_start", {"type": "message_start", "message": {
            "id": f"msg_{n}", "type": "message", "role": "assistant", "model": model,
            "content": [], "stop_reason": None, "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 1}}})]
        if kind == "text":
            out += [ev("content_block_start", {"type": "content_block_start", "index": 0,
                                               "content_block": {"type": "text", "text": ""}}),
                    ev("content_block_delta", {"type": "content_block_delta", "index": 0,
                                               "delta": {"type": "text_delta", "text": a}})]
            stop = "end_turn"
        else:
            for i, (nm, ar) in enumerate(calls):
                out += [ev("content_block_start", {"type": "content_block_start", "index": i,
                                                   "content_block": {"type": "tool_use",
                                                                     "id": f"toolu_{n}_{i}",
                                                                     "name": nm, "input": {}}}),
                        ev("content_block_delta", {"type": "content_block_delta", "index": i,
                                                   "delta": {"type": "input_json_delta",
                                                             "partial_json": json.dumps(ar)}})]
                if i < len(calls) - 1:
                    out.append(ev("content_block_stop", {"type": "content_block_stop",
                                                         "index": i}))
            stop = "tool_use"
        last = max(len(calls) - 1, 0) if kind != "text" else 0
        out += [ev("content_block_stop", {"type": "content_block_stop", "index": last}),
                ev("message_delta", {"type": "message_delta",
                                     "delta": {"stop_reason": stop, "stop_sequence": None},
                                     "usage": {"output_tokens": 7}}),
                ev("message_stop", {"type": "message_stop"})]
        return self._sse(out)

    # OpenAI Responses -----------------------------------------------------
    def _responses(self, body, n):
        items = [it for it in (body.get("input") or []) if isinstance(it, dict)]
        sec, pos = pick_turn([(i, _text_of(it.get("content"))) for i, it in enumerate(items)
                              if it.get("type") == "message" and it.get("role") == "user"])
        fed, k = split_on_feedback(items[pos + 1:], lambda it: it.get("type") in (
            "function_call_output", "custom_tool_call_output", "local_shell_call_output"),
            lambda it: json.dumps(it))
        tools = [t for t in (body.get("tools") or []) if isinstance(t, dict)]
        role = role_of(opening_user_text(items))
        ids: list[str] = []
        for it in items:                         # spawn_agent 的結果：{"agent_id": …}
            if it.get("type") == "function_call_output" and "agent_id" in str(it.get("output")):
                try:
                    aid = json.loads(it["output"]).get("agent_id")
                except (ValueError, TypeError, AttributeError):
                    aid = None
                if aid:
                    ids.append(str(aid))
        kind, a, b = plan(k, tools, None, fed, role, ids[-1] if ids else None, agent_ids=ids,
                          section=sec)
        log({"proto": "responses", "n": n, "k": k, "fed_back": fed, "reply": kind, "role": role,
             "feedback": feedback_excerpt(json.dumps(body)) if fed else None,
             "skill_listed": SKILL_MARK in json.dumps(body),
             "tools": [t.get("name") or t.get("type") for t in tools][:40],
             "tool": a if kind == "tool" else ([c[0] for c in a] if kind == "tools" else None)})
        rid = f"resp_{n}"
        items_out: list[dict[str, Any]] = []
        if kind == "text":
            items_out.append({"type": "message", "id": f"msg_{n}", "role": "assistant",
                              "status": "completed",
                              "content": [{"type": "output_text", "text": a, "annotations": []}]})
        else:
            for i, (nm, ar) in enumerate(a if kind == "tools" else [(a, b)]):
                it = {"type": "function_call", "id": f"fc_{n}_{i}", "call_id": f"call_{n}_{i}",
                      "name": nm, "arguments": json.dumps(ar), "status": "completed"}
                if "/" in nm:                    # 命名空間工具（Codex 的 multi_agent_v1）
                    it["namespace"], it["name"] = nm.split("/", 1)
                items_out.append(it)
        resp = {"id": rid, "object": "response", "created_at": int(time.time()),
                "status": "completed", "model": body.get("model", "mock"), "output": items_out,
                "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15,
                          "input_tokens_details": {"cached_tokens": 0},
                          "output_tokens_details": {"reasoning_tokens": 0}}}
        if not body.get("stream"):
            return self._json(200, resp)

        def ev(data):
            return f"event: {data['type']}\ndata: {json.dumps(data)}\n\n".encode()
        out = [ev({"type": "response.created", "response": {**resp, "status": "in_progress",
                                                           "output": []}})]
        for oi, it in enumerate(items_out):
            added = dict(it)
            if it["type"] == "function_call":
                added["arguments"] = ""
            out.append(ev({"type": "response.output_item.added", "output_index": oi,
                           "item": added}))
            if it["type"] == "message":
                out.append(ev({"type": "response.output_text.delta", "output_index": oi,
                               "content_index": 0, "item_id": it["id"], "delta": a}))
            else:
                out.append(ev({"type": "response.function_call_arguments.delta",
                               "output_index": oi, "item_id": it["id"],
                               "delta": it["arguments"]}))
            out.append(ev({"type": "response.output_item.done", "output_index": oi, "item": it}))
        out.append(ev({"type": "response.completed", "response": resp}))
        return self._sse(out)

    # OpenAI Chat Completions ----------------------------------------------
    def _chat(self, body, n):
        msgs = body.get("messages", [])
        sec, pos = pick_turn([(i, _text_of(m.get("content"))) for i, m in enumerate(msgs)
                              if m.get("role") == "user"])
        fed, k = split_on_feedback(msgs[pos + 1:], lambda m: m.get("role") == "tool",
                                   lambda m: json.dumps(m.get("content")))
        tools = body.get("tools") or []
        role = role_of(opening_user_text(msgs))
        kind, a, b = plan(k, tools, None, fed, role, section=sec)
        log({"proto": "chat", "n": n, "k": k, "fed_back": fed, "reply": kind, "role": role,
             "feedback": feedback_excerpt(json.dumps(body)) if fed else None,
             "skill_listed": SKILL_MARK in json.dumps(body),
             "tools": [(t.get("function") or {}).get("name") for t in tools][:40],
             "tool": a if kind == "tool" else ([c[0] for c in a] if kind == "tools" else None)})
        cid, model = f"chatcmpl-{n}", body.get("model", "mock")
        if kind == "text":
            msg = {"role": "assistant", "content": a}
            finish = "stop"
        else:
            msg = {"role": "assistant", "content": None, "tool_calls": [
                {"id": f"call_{n}_{i}", "type": "function",
                 "function": {"name": nm, "arguments": json.dumps(ar)}}
                for i, (nm, ar) in enumerate(a if kind == "tools" else [(a, b)])]}
            finish = "tool_calls"
        usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        if not body.get("stream"):
            return self._json(200, {"id": cid, "object": "chat.completion",
                                    "created": int(time.time()), "model": model,
                                    "choices": [{"index": 0, "message": msg,
                                                 "finish_reason": finish}], "usage": usage})

        def chunk(delta, fin=None, use=None):
            d = {"id": cid, "object": "chat.completion.chunk", "created": int(time.time()),
                 "model": model, "choices": [{"index": 0, "delta": delta, "finish_reason": fin}]}
            if use:
                d["usage"] = use
            return f"data: {json.dumps(d)}\n\n".encode()
        out = [chunk({"role": "assistant", "content": ""})]
        if kind == "text":
            out.append(chunk({"content": a}))
        else:
            for i, tc in enumerate(msg["tool_calls"]):
                out.append(chunk({"tool_calls": [{"index": i, "id": tc["id"], "type": "function",
                                                  "function": {"name": tc["function"]["name"],
                                                               "arguments": ""}}]}))
                out.append(chunk({"tool_calls": [{"index": i, "function": {
                    "arguments": tc["function"]["arguments"]}}]}))
        out.append(chunk({}, finish))
        out.append(f"data: {json.dumps({'id': cid, 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': model, 'choices': [], 'usage': usage})}\n\n".encode())
        out.append(b"data: [DONE]\n\n")
        return self._sse(out)


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    httpd = ThreadingHTTPServer(("127.0.0.1", port), H)
    os.environ["MOCK_PORT"] = str(httpd.server_address[1])     # 劇本的 `{{port}}`
    print(f"mock_model listening on 127.0.0.1:{httpd.server_address[1]}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
