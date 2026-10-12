#!/usr/bin/env python3
"""tag_front — 本機端到端專用：pi → tag_front → orproxy → 替身模型。

這支在架構裡承重什麼：orproxy 把網址前綴 `/t/<標籤>/…` 當成帳本的標籤、轉給上游時就丟掉了；本機測試的替身模型
（`e2e_stub.py`）卻需要知道每通請求屬於哪一格的哪一段 session 才能「按格子編劇」。這裡只做一件事：把標籤原樣寫進請求本文的
`user` 欄位（OpenAI 規格內的欄位，orproxy 的 `prepare_request` 會原樣轉送），其餘（路徑、回應、串流、狀態碼）一律原樣穿透。
**只在本機測試用；Colab 上沒有這一層**（driver 直接打 orproxy，`--proxy` 預設值不變）。
誠實邊界：多了一個 `user` 欄位與一跳 localhost；代理的帳本與標籤不變（路徑原樣轉）。
"""
from __future__ import annotations

import argparse
import http.client
import json
import re
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TARGET = ("127.0.0.1", 18900)
TAG_RE = re.compile(r"^/t/([^/]+)/")
HOP = {"transfer-encoding", "connection", "keep-alive", "content-length"}


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"                      # 每通請求一條連線、回應以關閉連線收尾（SSE 不需要長度）

    def log_message(self, *a):
        return

    def do_POST(self):  # noqa: N802
        n = int(self.headers.get("content-length") or 0)
        raw = self.rfile.read(n) if n else b""
        m = TAG_RE.match(urllib.parse.urlsplit(self.path).path)
        if m:
            try:
                body = json.loads(raw)
                body["user"] = m.group(1)
                raw = json.dumps(body).encode()
            except ValueError:
                pass
        conn = http.client.HTTPConnection(*TARGET, timeout=900)
        try:
            conn.request("POST", self.path, body=raw, headers={"Content-Type": "application/json",
                                                                 "Content-Length": str(len(raw)),
                                                                 "Accept": self.headers.get("Accept", "*/*")})
            r = conn.getresponse()
            self.send_response(r.status)
            for k, v in r.getheaders():
                if k.lower() not in HOP:
                    self.send_header(k, v)
            self.send_header("Connection", "close")
            self.end_headers()
            while True:
                chunk = r.read1(8192) if hasattr(r, "read1") else r.read(8192)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        except OSError as e:
            try:
                b = json.dumps({"error": f"tag_front: {e!r}"}).encode()
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)
            except OSError:
                pass
        finally:
            conn.close()


def main() -> int:
    global TARGET
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--listen", type=int, default=18950)
    ap.add_argument("--target-port", type=int, default=18900)
    a = ap.parse_args()
    TARGET = ("127.0.0.1", a.target_port)
    httpd = ThreadingHTTPServer(("127.0.0.1", a.listen), H)
    httpd.daemon_threads = True
    print(f"tag_front 127.0.0.1:{a.listen} -> 127.0.0.1:{a.target_port}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
