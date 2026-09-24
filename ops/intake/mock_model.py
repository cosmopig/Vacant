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

劇本（`MOCK_SCENARIO` 指向的 JSON）：`{"files": {"path": "content", ...}, "final": "..."}`。
每一通請求：數對話裡已經有幾個工具結果 k；k < 檔案數 ⇒ 叫一個「寫檔」工具寫第 k 個檔；
否則回最後那句話。工具從 agent **這一通送來的工具清單**裡挑：先找有「路徑＋內容」參數的
寫檔工具，沒有就用 shell 工具（`printf <base64> | base64 -d > path`）。

## 誠實邊界

1. 這是 **L-fake**：它證明的是「agent 的工具迴圈、掛鉤、工作區、收件口接得起來」，
   **不是**任何模型的能力，也不是真模型下的行為。
2. 劇本決定寫什麼，所以「成果好不好」完全由劇本控制——用它量的是收件口有沒有把
   壞劇本擋在目的端外、好劇本放進去，不是 agent 做得好不好。
"""
from __future__ import annotations

import base64
import itertools
import json
import os
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


def split_on_feedback(items: list[Any], is_result, text_of) -> tuple[bool, int]:
    """回 `(看過回饋, 回饋之後的工具結果數)`；沒看過回饋 ⇒ 全部的工具結果數。"""
    last = -1
    for i, it in enumerate(items):
        if FEEDBACK_MARK in text_of(it):
            last = i
    after = items[last + 1:] if last >= 0 else items
    return last >= 0, sum(1 for it in after if is_result(it))


def plan(n_results: int, tools: list[dict[str, Any]], cwd_hint: str | None,
         fed_back: bool = False):
    sc = scenario()
    if fed_back and isinstance(sc.get("fix"), dict):
        sc = sc["fix"]
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
        if "/models" in self.path:
            return self._json(200, {"object": "list", "data": [
                {"id": "mock-model", "object": "model", "owned_by": "mock"}], "has_more": False})
        return self._json(404, {"error": {"message": "mock: not found"}})

    def do_POST(self):  # noqa: N802
        body = self._body()
        n = next(_ctr)
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
        blocks = [b for m in msgs for b in (m.get("content") if isinstance(m.get("content"), list)
                                            else [{"type": "text", "text": str(m.get("content"))}])]
        fed, k = split_on_feedback(blocks, lambda b: b.get("type") == "tool_result",
                                   lambda b: json.dumps(b))
        tools = body.get("tools") or []
        kind, a, b = plan(k, tools, _cwd_hint(json.dumps(body.get("system"))), fed)
        log({"proto": "anthropic", "n": n, "k": k, "fed_back": fed, "reply": kind,
             "skill_listed": SKILL_MARK in json.dumps(body),
             "tools": [t.get("name") for t in tools][:40], "tool": a if kind == "tool" else None})
        model = body.get("model", "mock")
        if not body.get("stream"):
            content = ([{"type": "text", "text": a}] if kind == "text" else
                       [{"type": "tool_use", "id": f"toolu_{n}", "name": a, "input": b}])
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
            out += [ev("content_block_start", {"type": "content_block_start", "index": 0,
                                               "content_block": {"type": "tool_use",
                                                                 "id": f"toolu_{n}", "name": a,
                                                                 "input": {}}}),
                    ev("content_block_delta", {"type": "content_block_delta", "index": 0,
                                               "delta": {"type": "input_json_delta",
                                                         "partial_json": json.dumps(b)}})]
            stop = "tool_use"
        out += [ev("content_block_stop", {"type": "content_block_stop", "index": 0}),
                ev("message_delta", {"type": "message_delta",
                                     "delta": {"stop_reason": stop, "stop_sequence": None},
                                     "usage": {"output_tokens": 7}}),
                ev("message_stop", {"type": "message_stop"})]
        return self._sse(out)

    # OpenAI Responses -----------------------------------------------------
    def _responses(self, body, n):
        items = [it for it in (body.get("input") or []) if isinstance(it, dict)]
        fed, k = split_on_feedback(items, lambda it: it.get("type") in (
            "function_call_output", "custom_tool_call_output", "local_shell_call_output"),
            lambda it: json.dumps(it))
        tools = [t for t in (body.get("tools") or []) if isinstance(t, dict)]
        kind, a, b = plan(k, tools, None, fed)
        log({"proto": "responses", "n": n, "k": k, "fed_back": fed, "reply": kind,
             "skill_listed": SKILL_MARK in json.dumps(body),
             "tools": [t.get("name") or t.get("type") for t in tools][:40],
             "tool": a if kind == "tool" else None})
        rid = f"resp_{n}"
        if kind == "text":
            item = {"type": "message", "id": f"msg_{n}", "role": "assistant", "status": "completed",
                    "content": [{"type": "output_text", "text": a, "annotations": []}]}
        else:
            item = {"type": "function_call", "id": f"fc_{n}", "call_id": f"call_{n}",
                    "name": a, "arguments": json.dumps(b), "status": "completed"}
        resp = {"id": rid, "object": "response", "created_at": int(time.time()),
                "status": "completed", "model": body.get("model", "mock"), "output": [item],
                "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15,
                          "input_tokens_details": {"cached_tokens": 0},
                          "output_tokens_details": {"reasoning_tokens": 0}}}
        if not body.get("stream"):
            return self._json(200, resp)

        def ev(data):
            return f"event: {data['type']}\ndata: {json.dumps(data)}\n\n".encode()
        added = dict(item)
        if kind == "tool":
            added["arguments"] = ""
        out = [ev({"type": "response.created", "response": {**resp, "status": "in_progress",
                                                           "output": []}}),
               ev({"type": "response.output_item.added", "output_index": 0, "item": added})]
        if kind == "text":
            out.append(ev({"type": "response.output_text.delta", "output_index": 0,
                           "content_index": 0, "item_id": item["id"], "delta": a}))
        else:
            out.append(ev({"type": "response.function_call_arguments.delta", "output_index": 0,
                           "item_id": item["id"], "delta": item["arguments"]}))
        out += [ev({"type": "response.output_item.done", "output_index": 0, "item": item}),
                ev({"type": "response.completed", "response": resp})]
        return self._sse(out)

    # OpenAI Chat Completions ----------------------------------------------
    def _chat(self, body, n):
        msgs = body.get("messages", [])
        fed, k = split_on_feedback(msgs, lambda m: m.get("role") == "tool",
                                   lambda m: json.dumps(m.get("content")))
        tools = body.get("tools") or []
        kind, a, b = plan(k, tools, None, fed)
        log({"proto": "chat", "n": n, "k": k, "fed_back": fed, "reply": kind,
             "skill_listed": SKILL_MARK in json.dumps(body),
             "tools": [(t.get("function") or {}).get("name") for t in tools][:40],
             "tool": a if kind == "tool" else None})
        cid, model = f"chatcmpl-{n}", body.get("model", "mock")
        if kind == "text":
            msg = {"role": "assistant", "content": a}
            finish = "stop"
        else:
            msg = {"role": "assistant", "content": None, "tool_calls": [
                {"id": f"call_{n}", "type": "function",
                 "function": {"name": a, "arguments": json.dumps(b)}}]}
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
            tc = msg["tool_calls"][0]
            out.append(chunk({"tool_calls": [{"index": 0, "id": tc["id"], "type": "function",
                                              "function": {"name": tc["function"]["name"],
                                                           "arguments": ""}}]}))
            out.append(chunk({"tool_calls": [{"index": 0, "function": {
                "arguments": tc["function"]["arguments"]}}]}))
        out.append(chunk({}, finish))
        out.append(f"data: {json.dumps({'id': cid, 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': model, 'choices': [], 'usage': usage})}\n\n".encode())
        out.append(b"data: [DONE]\n\n")
        return self._sse(out)


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    httpd = ThreadingHTTPServer(("127.0.0.1", port), H)
    print(f"mock_model listening on 127.0.0.1:{httpd.server_address[1]}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
