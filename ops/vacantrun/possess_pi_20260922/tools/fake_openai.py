#!/usr/bin/env python3
"""假 OpenAI 上游（L-fake 量具）：/v1/models 回一個模型，/v1/chat/completions 回固定答案。
支援 stream=true 的 SSE。只用來證明「通道經過 proxyd」，不證明任何模型能力。"""
import json, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODEL = "fake-gemma"
LOG = sys.argv[2] if len(sys.argv) > 2 else None


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        if LOG:
            with open(LOG, "a") as f:
                f.write(json.dumps({"t": time.time(), "m": self.command, "p": self.path}) + "\n")

    def _send(self, code, body, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/v1/models"):
            self._send(200, json.dumps({"object": "list", "data": [
                {"id": MODEL, "object": "model", "owned_by": "fake"}]}).encode())
        else:
            self._send(404, b"{}")

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b""
        try:
            req = json.loads(raw or b"{}")
        except ValueError:
            req = {}
        if not self.path.startswith("/v1/chat/completions"):
            self._send(404, b"{}")
            return
        text = "OK (fake upstream)"
        if req.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()

            def chunk(obj):
                data = ("data: " + json.dumps(obj) + "\n\n").encode()
                self.wfile.write(("%x\r\n" % len(data)).encode() + data + b"\r\n")
                self.wfile.flush()
            base = {"id": "chatcmpl-fake", "object": "chat.completion.chunk",
                    "created": int(time.time()), "model": MODEL}
            chunk({**base, "choices": [{"index": 0, "delta": {"role": "assistant", "content": text}, "finish_reason": None}]})
            chunk({**base, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                   "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}})
            d = b"data: [DONE]\n\n"
            self.wfile.write(("%x\r\n" % len(d)).encode() + d + b"\r\n0\r\n\r\n")
            self.wfile.flush()
            return
        self._send(200, json.dumps({
            "id": "chatcmpl-fake", "object": "chat.completion", "created": int(time.time()),
            "model": MODEL, "choices": [{"index": 0, "message": {"role": "assistant", "content": text},
                                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}).encode())


if __name__ == "__main__":
    port = int(sys.argv[1])
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    print(f"fake upstream on {port}", flush=True)
    srv.serve_forever()
