"""固定推論槽並逐請求記錄模型 I/O；承接 PROTOCOL.md 的 Ordering 與 Evidence。"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import argparse
import datetime
import json
from pathlib import Path
import re
from threading import Lock
import urllib.error
import urllib.request
import uuid

PATH = re.compile(r"/([a-f0-9]{32})/([0-3])/v1/chat/completions")


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class TraceHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        match = PATH.fullmatch(self.path)
        if match is None:
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", 0))
        if not 0 < length <= 8_000_000:
            self.send_error(413)
            return
        payload = self.rfile.read(length)
        try:
            body = json.loads(payload)
            if not isinstance(body, dict):
                raise ValueError("expected JSON object")
        except ValueError:
            self.send_error(400)
            return
        trace_dir = self.server.out / match[1]
        with self.server.trace_lock:
            first_request = not trace_dir.exists()
            trace_dir.mkdir(exist_ok=True)
        body.update(id_slot=int(match[2]), cache_prompt=not first_request)
        target = trace_dir / f"{uuid.uuid4().hex}.jsonl"
        upstream = urllib.request.Request(
            self.server.upstream, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"},
            method="POST",
        )
        with target.open("w", encoding="utf-8", buffering=1) as trace:
            def event(kind, **data):
                trace.write(json.dumps({"utc": now(), "kind": kind, **data}) + "\n")

            event("request", body=payload.decode("utf-8", "replace"), upstream_body=body)
            try:
                try:
                    response = urllib.request.urlopen(upstream, timeout=900)
                except urllib.error.HTTPError as http_error:
                    response = http_error
                with response:
                    mime = response.headers.get("Content-Type", "application/octet-stream")
                    event("response", status=response.status, content_type=mime)
                    self.send_response(response.status)
                    self.send_header("Content-Type", mime)
                    self.end_headers()
                    while chunk := response.read1(65536):
                        event("chunk", text=chunk.decode("utf-8", "replace"), hex=chunk.hex())
                        self.wfile.write(chunk)
                        self.wfile.flush()
                event("eof")
            except (OSError, ValueError) as exc:
                event("interrupted", detail=str(exc))

    def do_GET(self):
        if self.path != "/health":
            self.send_error(404)
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ready\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    parser.add_argument("--upstream", default="http://hard-r3-model:8080/v1/chat/completions")
    args = parser.parse_args()
    with ThreadingHTTPServer(("0.0.0.0", 8080), TraceHandler) as server:
        server.out = args.out
        server.upstream = args.upstream
        server.trace_lock = Lock()
        server.serve_forever()
