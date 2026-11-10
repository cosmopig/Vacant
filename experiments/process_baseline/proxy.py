"""Tiny OpenAI-compatible logging proxy for the process baseline.

Why: qwen3.8:27b (and other reasoning models on Ollama /v1) spend the whole
max_tokens budget on hidden reasoning and return empty `content` unless the
request carries ``"reasoning_effort": "none"``. pi does not expose arbitrary
extra body params, so this proxy injects it, adds the upstream bearer token,
throttles to a request budget (default 28 req/min) and appends one line per
call to a JSONL call log (timestamps, latency, usage) so token accounting does
not depend on the agent CLI.

Stdlib only. Usage:
  UPSTREAM_BASE=https://host/v1 UPSTREAM_TOKEN=... CALL_LOG=calls.jsonl \
    python proxy.py --port 18080
"""
from __future__ import annotations

import argparse
import json
import os
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_LOCK = threading.Lock()
_STAMPS: list[float] = []


def _throttle(rpm: int) -> None:
    while True:
        with _LOCK:
            now = time.time()
            while _STAMPS and now - _STAMPS[0] > 60:
                _STAMPS.pop(0)
            if len(_STAMPS) < rpm:
                _STAMPS.append(now)
                return
            wait = 60 - (now - _STAMPS[0]) + 0.05
        time.sleep(max(wait, 0.05))


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):  # quiet
        pass

    def _forward(self, method: str) -> None:
        base = os.environ["UPSTREAM_BASE"].rstrip("/")
        path = self.path
        if path.startswith("/v1"):
            path = path[3:]
        body = b""
        n = int(self.headers.get("Content-Length") or 0)
        if n:
            body = self.rfile.read(n)
        req_json = None
        if body and path.endswith("/chat/completions"):
            req_json = json.loads(body)
            req_json["reasoning_effort"] = os.environ.get("REASONING_EFFORT", "none")
            req_json.pop("reasoning", None)
            if os.environ.get("FORCE_MODEL"):
                req_json["model"] = os.environ["FORCE_MODEL"]
            if req_json.get("stream"):
                req_json.setdefault("stream_options", {})["include_usage"] = True
            body = json.dumps(req_json).encode()
            _throttle(int(os.environ.get("RPM", "28")))
        headers = {"Content-Type": "application/json"}
        tok = os.environ.get("UPSTREAM_TOKEN")
        if tok:
            headers["Authorization"] = f"Bearer {tok}"
        t0 = time.time()
        req = urllib.request.Request(base + path, data=body or None, headers=headers, method=method)
        status, chunks, usage, err = 0, [], None, None
        try:
            resp = urllib.request.urlopen(req, timeout=600)
            status = resp.status
            self.send_response(status)
            ctype = resp.headers.get("Content-Type", "application/json")
            self.send_header("Content-Type", ctype)
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            while True:
                line = resp.readline()
                if not line:
                    break
                chunks.append(line)
                self.wfile.write(f"{len(line):X}\r\n".encode() + line + b"\r\n")
                self.wfile.flush()
            self.wfile.write(b"0\r\n\r\n")
        except urllib.error.HTTPError as e:
            status = e.code
            data = e.read()
            err = data[:500].decode("utf-8", "replace")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:  # upstream down
            status, err = 502, repr(e)
            data = json.dumps({"error": {"message": err}}).encode()
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        raw = b"".join(chunks)
        for line in raw.splitlines():
            s = line.strip()
            if s.startswith(b"data:"):
                s = s[5:].strip()
            if not s or s == b"[DONE]":
                continue
            try:
                obj = json.loads(s)
            except Exception:
                continue
            if isinstance(obj, dict) and obj.get("usage"):
                usage = obj["usage"]
        if req_json is not None and os.environ.get("CALL_LOG"):
            rec = {
                "ts_start": t0,
                "latency_s": round(time.time() - t0, 3),
                "path": path,
                "status": status,
                "model": req_json.get("model"),
                "n_messages": len(req_json.get("messages", [])),
                "n_tools": len(req_json.get("tools", []) or []),
                "reasoning_effort": req_json.get("reasoning_effort"),
                "usage": usage,
                "error": err,
            }
            with _LOCK, open(os.environ["CALL_LOG"], "a") as f:
                f.write(json.dumps(rec) + "\n")

    def do_POST(self):
        self._forward("POST")

    def do_GET(self):
        self._forward("GET")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=18080)
    a = ap.parse_args()
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
