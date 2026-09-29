"""A scripted OpenAI-compatible stub so agent behaviour can be tested for free.

Why this exists
---------------
Measuring whether a hook can deliver feedback needs a model turn on both sides of
the delivery. OpenRouter's free tier is 1000 requests/day at the account level
(measured: `X-RateLimit-Limit: 1000`), which is not enough to iterate on
mechanism. This stub removes the model from the loop entirely:

  * it counts every request it receives, so "did the plugin actually re-prompt
    the session?" becomes a number instead of an opinion;
  * it serves whatever turns are listed in SCRIPT, so a run is deterministic;
  * it can be told to fail, to stall, or to emit a tool call.

What it is NOT: a model. It does not decide anything, so nothing measured
through it says anything about capability. It only says whether a *mechanism*
fired.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LOG = pathlib.Path(os.environ.get("STUB_LOG", "/tmp/stub_requests.jsonl"))
SCRIPT = json.loads(os.environ.get("STUB_SCRIPT", "[]"))
PORT = int(os.environ.get("STUB_PORT", "3939"))

_lock = threading.Lock()
_count = 0
CAP = int(os.environ.get("STUB_CAP", "40"))


def _turn(i: int) -> dict:
    if i < len(SCRIPT):
        return SCRIPT[i]
    return {"message": {"role": "assistant", "content": "STUB_DONE turn=%d" % i},
            "finish_reason": "stop"}


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):        # keep stdout clean
        pass

    def _send(self, code: int, body: dict) -> None:
        raw = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        self._send(200, {"object": "list", "data": [
            {"id": "stub-model", "object": "model", "owned_by": "stub"}]})

    def do_POST(self):
        global _count
        n = int(self.headers.get("content-length", 0))
        raw = self.rfile.read(n)
        try:
            req = json.loads(raw)
        except Exception:
            req = {}
        with _lock:
            i = _count
            _count += 1
        if i >= CAP:
            # Stop the flood instead of answering forever. opencode spawns title
            # and build sub-agents that each call the model; an uncapped stub
            # turns one experiment into thousands of requests.
            self._send(429, {"error": {"message": "stub: cap reached", "code": 429}})
            return
        turn = _turn(i)
        msgs = req.get("messages") or []
        with _lock:
            with LOG.open("a") as f:
                f.write(json.dumps({
                    "n": i,
                    "path": self.path,
                    "authorization": self.headers.get("authorization"),
                    "model": req.get("model"),
                    "n_messages": len(msgs),
                    "roles": [m.get("role") for m in msgs],
                    "last_text": (str((msgs[-1] or {}).get("content"))[:400]
                                  if msgs else ""),
                    "tools_offered": len(req.get("tools") or []),
                }, ensure_ascii=False) + "\n")
        if turn.get("status"):
            self._send(int(turn["status"]), turn.get("body") or {"error": {"message": "stub"}})
            return
        msg = turn.get("message") or {}
        if not msg.get("role"):
            msg = {"role": "assistant", "content": turn.get("content", "")}
        self._send(200, {
            "id": "stub-%d" % i, "object": "chat.completion", "created": 1,
            "model": req.get("model", "stub-model"),
            "choices": [{"index": 0, "message": msg,
                         "finish_reason": turn.get("finish_reason", "stop")}],
            "usage": {"prompt_tokens": len(msgs) * 10, "completion_tokens": 5,
                      "total_tokens": len(msgs) * 10 + 5},
        })


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    print("stub listening on 127.0.0.1:%d, log=%s" % (PORT, LOG), flush=True)
    srv.serve_forever()
