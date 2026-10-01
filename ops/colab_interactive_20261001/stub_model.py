#!/usr/bin/env python3
"""stub_model — a scripted OpenAI-compatible chat-completions server (streaming + tool calls).

What it carries in the i1001 interactive campaign (ops/colab_interactive_20261001/):
it lets the interactive-pi driver (idle detection, clean exit, Vacant send-back timing) be
tested offline, with no GPU and no paid model. It is a mechanism stub: it never solves
anything and it carries NO task content — the script (a JSON file) is supplied by the caller.

Protocol: POST /v1/chat/completions (stream or not), GET /v1/models.  Also answers
POST <anything>/chat/completions so a proxy-style prefix (`/t/<tag>/up/<name>/think/off/api/v1`)
works.  Any other path -> 404.

Script (JSON; `--script file` or env STUB_SCRIPT):
  {"turns": [ {"steps": [ {"write": ["solution.py", "..."]},
                          {"bash": "ls"}, {"read": "goal.md"}, {"text": "Done."} ]} , ... ],
   "latency_s": 0.2,          # delay before the first byte of every reply
   "chunk_delay_s": 0.0}      # delay between SSE chunks
Turn index = number of `user` messages in the request (-1); step index = number of `tool`
messages after the last `user` message.  Past the last turn the stub repeats the last turn's
final text step, or says "ok".  A step may carry "delay_s".  A step may be {"error": 500, "times": 2}
to answer that HTTP status the first 2 requests that reach it (infra-void / retry drills).
Default script (no file): turn 0 = write `solution.py`, then "Done."; later turns = "ok".

Log: every request appended to --log (JSONL): n, t (epoch), user_msgs, tool_msgs, reply kind,
last_user_sha256 + first 200 chars of it (to see a Vacant send-back arrive as a user message),
and the tool names offered.  The log is data about the mechanism, not task content.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DEFAULT = {"turns": [{"steps": [{"write": ["solution.py", "def solve():\n    return 1\n"]},
                                {"text": "Done."}]},
                     {"steps": [{"text": "ok"}]}]}
CFG: dict = {"script": DEFAULT, "log": None}
_ctr = itertools.count(1)
_lock = threading.Lock()


def _text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join((p.get("text") or "") for p in content if isinstance(p, dict))
    return ""


def _tool(tools: list[dict], want: str):
    """(tool name, {logical arg -> real arg name}) for a logical tool (write/bash/read)."""
    for t in tools:
        f = t.get("function") or {}
        name = f.get("name") or ""
        if name.lower() == want:
            props = list(((f.get("parameters") or {}).get("properties") or {}).keys())
            return name, props
    return None, []


def _args(kind: str, props: list[str], value) -> dict:
    def pick(*cands):
        for c in cands:
            if c in props:
                return c
        return cands[0]
    if kind == "write":
        return {pick("path", "file_path", "filePath"): value[0], pick("content", "text", "contents"): value[1]}
    if kind == "read":
        return {pick("path", "file_path", "filePath"): value}
    return {pick("command", "cmd"): value}


_served: dict = {}


def _pick_step(steps: list[dict], tool_n: int, turn_ix: int) -> dict:
    """steps[tool_n], except that a step with {"times": N} is served N times in all (an
    `error` step is then skipped without using up a tool message; a non-error step is
    served only N times and the script's last text step is used afterwards)."""
    real = 0
    for j, st in enumerate(steps):
        key = (turn_ix, j)
        if "times" in st and _served.get(key, 0) >= int(st["times"]):
            continue
        if real == tool_n or j == len(steps) - 1:
            if "times" in st:
                _served[key] = _served.get(key, 0) + 1
            return st
        real += 1
    return steps[-1]


def choose(msgs: list[dict], tools: list[dict]):
    users = [i for i, m in enumerate(msgs) if m.get("role") == "user"]
    turn_ix = max(0, len(users) - 1)
    last_user = users[-1] if users else -1
    tool_n = sum(1 for m in msgs[last_user + 1:] if m.get("role") == "tool")
    turns = CFG["script"]["turns"]
    turn = turns[min(turn_ix, len(turns) - 1)]
    steps = turn["steps"]
    if turn_ix >= len(turns):                       # past the script: repeat the last final text
        steps = [{"text": next((s["text"] for s in reversed(steps) if "text" in s), "ok")}]
    st = _pick_step(steps, tool_n, turn_ix)
    last = _text(msgs[last_user].get("content")) if last_user >= 0 else ""
    return turn_ix, tool_n, st, last


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        return

    def _json(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):  # noqa: N802
        if "/models" in self.path:
            return self._json(200, {"object": "list", "data": [
                {"id": "stub-model", "object": "model", "owned_by": "stub"}]})
        return self._json(404, {"error": {"message": "stub: not found"}})

    def do_POST(self):  # noqa: N802
        n = int(self.headers.get("content-length") or 0)
        raw = self.rfile.read(n) if n else b""
        try:
            body = json.loads(raw) if raw else {}
        except ValueError:
            body = {}
        if not self.path.split("?")[0].endswith("/chat/completions"):
            return self._json(404, {"error": {"message": "stub: no route"}})
        with _lock:
            k = next(_ctr)
        msgs, tools = body.get("messages", []), body.get("tools") or []
        turn_ix, tool_n, st, last = choose(msgs, tools)
        kind = next((x for x in ("write", "bash", "read", "text", "error") if x in st), "text")
        rec = {"n": k, "t": time.time(), "turn": turn_ix, "tool_msgs": tool_n,
               "user_msgs": sum(1 for m in msgs if m.get("role") == "user"), "msgs": len(msgs),
               "step": kind, "stream": bool(body.get("stream")), "model": body.get("model"),
               "last_user_sha256": hashlib.sha256(last.encode()).hexdigest(),
               "last_user_head": last[:200], "tools": [(t.get("function") or {}).get("name") for t in tools],
               # fingerprints of what the agent sent (to show two arms send the same request):
               "body_sha256": hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest(),
               "tools_sha256": hashlib.sha256(json.dumps(tools, sort_keys=True).encode()).hexdigest(),
               "system_sha256": hashlib.sha256(_text(msgs[0].get("content")).encode()).hexdigest()
               if msgs and msgs[0].get("role") == "system" else None,
               "msg_roles": [m.get("role") for m in msgs]}
        if CFG["log"]:
            with _lock, open(CFG["log"], "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        if kind == "error":
            return self._json(int(st["error"]), {"error": {"message": "stub: scripted error"}})
        time.sleep(float(st.get("delay_s", CFG["script"].get("latency_s", 0.2))))
        name = None
        if kind == "text":
            msg = {"role": "assistant", "content": st["text"]}
            fin = "stop"
        else:
            name, props = _tool(tools, kind)
            if name is None:                         # the agent has no such tool: say so in text
                msg, fin = {"role": "assistant", "content": f"(stub: no {kind} tool offered)"}, "stop"
            else:
                msg = {"role": "assistant", "content": None, "tool_calls": [{
                    "id": f"call_{k}_0", "type": "function",
                    "function": {"name": name, "arguments": json.dumps(_args(kind, props, st[kind]))}}]}
                fin = "tool_calls"
        usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        cid, model = f"chatcmpl-{k}", body.get("model", "stub-model")
        if not body.get("stream"):
            return self._json(200, {"id": cid, "object": "chat.completion", "created": int(time.time()),
                                    "model": model, "choices": [{"index": 0, "message": msg,
                                                                 "finish_reason": fin}], "usage": usage})

        def chunk(delta, fin_=None, use=None, choices=True):
            d = {"id": cid, "object": "chat.completion.chunk", "created": int(time.time()), "model": model,
                 "choices": [{"index": 0, "delta": delta, "finish_reason": fin_}] if choices else []}
            if use:
                d["usage"] = use
            return f"data: {json.dumps(d)}\n\n".encode()
        out = [chunk({"role": "assistant", "content": ""})]
        if kind == "text" or name is None:
            out.append(chunk({"content": msg["content"]}))
        else:
            tc = msg["tool_calls"][0]
            out.append(chunk({"tool_calls": [{"index": 0, "id": tc["id"], "type": "function",
                                              "function": {"name": tc["function"]["name"], "arguments": ""}}]}))
            out.append(chunk({"tool_calls": [{"index": 0, "function": {"arguments": tc["function"]["arguments"]}}]}))
        out += [chunk({}, fin), chunk({}, None, usage, choices=False), b"data: [DONE]\n\n"]
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.send_header("cache-control", "no-cache")
        self.send_header("connection", "close")
        self.end_headers()
        cd = float(CFG["script"].get("chunk_delay_s", 0))
        for c in out:
            self.wfile.write(c)
            self.wfile.flush()
            if cd:
                time.sleep(cd)
        self.close_connection = True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--script")
    ap.add_argument("--log")
    a = ap.parse_args()
    if a.script:
        CFG["script"] = json.load(open(a.script, encoding="utf-8"))
    CFG["log"] = a.log
    httpd = ThreadingHTTPServer((a.host, a.port), H)
    print(f"stub_model listening on {a.host}:{httpd.server_address[1]}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
