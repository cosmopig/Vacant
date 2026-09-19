#!/usr/bin/env python3
"""一台**什麼 path 都回 200** 的假上游，而且**逐通把 path 記下來**。

它存在的唯一理由是 `/admin` 那一格的負控制：要說「門把 `GET /admin` 擋下來、
沒有隧道過去」，就必須有一台**本來會回答 `/admin` 的上游**在對面——否則
403 跟「上游本來就沒有那條路」長得一模一樣，那不是量到，是猜到。

`--hits <檔>` 逐行記下收到的 path。**它是空的才算「上游沒收到」**，
而它在負控制那一格會有東西 ⇒ 證明這個量具本身是活的。

用法：`echo_upstream.py --port 0 --hits /path/hits.log [--ready /path/ready]`
"""
import argparse
import json
import pathlib
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_LOCK = threading.Lock()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--hits", required=True)
    ap.add_argument("--ready", default=None)
    a = ap.parse_args()
    hits = pathlib.Path(a.hits)
    hits.parent.mkdir(parents=True, exist_ok=True)
    hits.write_text("", encoding="utf-8")
    # ⚠ **先把 ready 檔刪掉再 bind**：留著上一次的 ready 檔，呼叫端會把
    #   「上一次的埠號」讀成「這一次就緒了」。2026-09-20 實際踩過一次。
    if a.ready:
        try:
            pathlib.Path(a.ready).unlink()
        except FileNotFoundError:
            pass

    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_a):
            return

        def _any(self):
            n = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(n) if n else b""
            with _LOCK, hits.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"method": self.command,
                                     "path": self.path,
                                     "auth": self.headers.get("Authorization"),
                                     "body_bytes": len(body)},
                                    ensure_ascii=False) + "\n")
                fh.flush()
            payload = json.dumps({"echo_upstream": True,
                                  "path": self.path}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = _any

    srv = ThreadingHTTPServer(("127.0.0.1", a.port), H)
    srv.daemon_threads = True
    port = srv.server_address[1]
    if a.ready:
        pathlib.Path(a.ready).write_text(str(port), encoding="utf-8")
    print(f"ECHO_UPSTREAM_READY port={port} hits={hits}", flush=True)
    srv.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
