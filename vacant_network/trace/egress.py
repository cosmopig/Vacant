"""網路出口紀錄（v4，2026-11-25 第四輪）：agent 的工具發出的 HTTP 請求經過這個本機代理，每一筆抓取（網址、狀態、
回應內容）都記下來；`sources.ingest_egress` 再把它們簽進這個工作區的鏈（`source_fetch` 事件）。

承重的是「候選來源不靠指令文字」：curl、wget、python、node、變數拼出來的網址，只要走代理，抓了什麼都記得到。

誠實邊界（照實寫）：
- 只看得到走代理的請求：工具不吃 `http_proxy` 環境變數、或打完整路徑繞過代理設定的，記不到。
- HTTPS（CONNECT）只記主機與埠，看不到網址路徑與內容（不做中間人憑證）。
- 模型請求要排除在代理之外（`NO_PROXY`）——這樣模型收到的請求位元組不經過 Vacant；排除錯了，代理會照實記下並轉送。
- 紀錄先寫成 `<project>/egress.jsonl`＋內容定址庫，不是即時上鏈；進鏈時保留抓取當時的時間戳。這段時間內有人改檔可以偽造，
  鏈只保證「進鏈之後」不可竄改。
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import select
import socket
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .recorder import Recorder

_HOP = {"proxy-connection", "connection", "keep-alive", "proxy-authorization", "te", "trailer",
        "transfer-encoding", "upgrade", "host"}
MAX_BODY = 8 * 1024 * 1024


def serve(ws: str | os.PathLike, port: int, *, upstream_proxy: str | None = None,
          ready_file: str | None = None) -> int:
    rec = Recorder(pathlib.Path(ws).resolve())
    rec.dir.mkdir(parents=True, exist_ok=True)
    log_path = rec.dir / "egress.jsonl"
    lock = threading.Lock()
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": upstream_proxy} if upstream_proxy else {}))

    def log(entry: dict) -> None:
        with lock, open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"

        def log_message(self, *a):          # noqa: D401
            pass

        def _forward(self, method: str) -> None:
            url = self.path
            if not url.startswith("http://"):
                self.send_error(400, "absolute http:// URL required (this is a proxy)")
                return
            headers = {k: v for k, v in self.headers.items() if k.lower() not in _HOP}
            n = int(self.headers.get("Content-Length") or 0)
            data = self.rfile.read(n) if n else None
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            t0 = time.time()
            try:
                r = opener.open(req, timeout=60)
                status, rh, body = r.status, r.headers, r.read(MAX_BODY)
            except urllib.error.HTTPError as e:
                status, rh, body = e.code, e.headers, e.read(MAX_BODY)
            except Exception as e:          # noqa: BLE001
                log({"ts_ms": int(t0 * 1000), "url": url, "method": method, "error": f"{type(e).__name__}: {e}"[:200]})
                self.send_error(502, "upstream error")
                return
            sha = rec.blobs.put_bytes(body)
            log({"ts_ms": int(t0 * 1000), "url": url, "method": method, "status": status,
                 "sha256": sha, "bytes": len(body), "ua": (self.headers.get("User-Agent") or "")[:60]})
            self.send_response(status)
            for k, v in rh.items():
                if k.lower() not in _HOP and k.lower() != "content-length":
                    self.send_header(k, v)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if method != "HEAD":
                self.wfile.write(body)

        def do_GET(self):                   # noqa: N802
            self._forward("GET")

        def do_HEAD(self):                  # noqa: N802
            self._forward("HEAD")

        def do_POST(self):                  # noqa: N802
            self._forward("POST")

        def do_CONNECT(self):               # noqa: N802
            host, _, p = self.path.partition(":")
            log({"ts_ms": int(time.time() * 1000), "url": f"https://{host}:{p or 443}", "method": "CONNECT", "tls": True})
            try:
                up = socket.create_connection((host, int(p or 443)), timeout=30)
            except OSError:
                self.send_error(502, "connect failed")
                return
            self.send_response(200, "Connection Established")
            self.end_headers()
            socks = [self.connection, up]
            try:
                while True:
                    r, _, x = select.select(socks, [], socks, 60)
                    if x or not r:
                        break
                    for s in r:
                        d = s.recv(65536)
                        if not d:
                            return
                        (up if s is self.connection else self.connection).sendall(d)
            finally:
                up.close()

    srv = ThreadingHTTPServer(("127.0.0.1", port), H)     # port 0 ⇒ 系統挑一個空的
    if ready_file:
        pathlib.Path(ready_file).write_text(json.dumps({"pid": os.getpid(), "port": srv.server_address[1]}))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


def body_sha(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()
