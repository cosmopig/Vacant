#!/usr/bin/env python3
"""D2′ 的來源伺服器：讓 agent 用 `curl http://s01.d2-sources.example/p1.html` 讀「外部」網頁。

- agent 的環境設 `http_proxy=http://127.0.0.1:<port>`，curl 把絕對網址送到這裡；這裡依 Host 對應到
  路由檔（JSON：{"<host>": "<網站目錄>"}）裡的目錄回檔。路由檔每次請求都重讀，換週期＝改路由檔。
- `.example` 是保留網域，永遠解析不到真的網站；網址不是本機，所以產品的 `blame` 把它當外部來源
  （本機網址會被判成「可能是 agent 自己開的伺服器」⇒ 沒有出處，這是產品刻意的防偽規則）。
- 每一個請求記一行 JSONL（時間、Host、路徑、狀態、回應內容的 sha256）：稽核時和病歷對帳的**獨立**紀錄。
用法：source_server.py --port 18190 --routes routes.json --log access.jsonl
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LOCK = threading.Lock()
#: 第三個產生器（heldout-v3）的「每次抓取都會變的雜訊」：只有 --dynamic 時才換；預設逐位元照舊
DYN_COUNT: dict = {}
CTYPES = {".html": "text/html; charset=utf-8", ".md": "text/markdown; charset=utf-8", ".txt": "text/plain; charset=utf-8",
          ".json": "application/json", ".csv": "text/csv; charset=utf-8"}


def render_dynamic(body: bytes, key: str) -> bytes:
    import datetime
    import secrets
    if b"{{FETCH_" not in body:
        return body
    with LOCK:
        DYN_COUNT[key] = DYN_COUNT.get(key, 1000) + 1
        n = DYN_COUNT[key]
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return (body.replace(b"{{FETCH_TS}}", ts.encode()).replace(b"{{FETCH_COUNT}}", str(n).encode())
            .replace(b"{{FETCH_ID}}", secrets.token_hex(6).encode()))


class H(BaseHTTPRequestHandler):
    routes_path: pathlib.Path
    log_path: pathlib.Path
    meta_path: pathlib.Path | None = None
    dynamic: bool = False

    def log_message(self, *a):          # noqa: D401 — 安靜；自己記 JSONL
        pass

    def _routes(self) -> dict:
        try:
            return json.loads(self.routes_path.read_text())
        except (OSError, ValueError):
            return {}

    def do_GET(self):                   # noqa: N802
        u = urllib.parse.urlsplit(self.path)
        host = (u.hostname or (self.headers.get("Host") or "").split(":")[0]).lower()
        path = u.path if u.scheme else self.path.split("?", 1)[0]
        root = self._routes().get(host)
        body, status = b"not found\n", 404
        template_sha = None
        ctype = "text/html; charset=utf-8"
        if root:
            rel = path.lstrip("/") or "index.html"
            f = (pathlib.Path(root) / rel).resolve()
            if str(f).startswith(str(pathlib.Path(root).resolve()) + os.sep) and f.is_file():
                body, status = f.read_bytes(), 200
                if self.dynamic:
                    template_sha = hashlib.sha256(body).hexdigest()
                    body = render_dynamic(body, host + path)
                    ctype = CTYPES.get(f.suffix.lower(), ctype)
        self.send_response(status)
        self.send_header("Content-Type", ctype if status == 200 else "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        meta = {}
        if self.meta_path is not None:
            try:
                meta = json.loads(self.meta_path.read_text()).get(host) or {}
            except (OSError, ValueError):
                meta = {}
        rec = {"ts": time.time(), "host": host, "path": path, "status": status,
               "arm": meta.get("arm"), "cycle": meta.get("cycle"),
               "sha256": hashlib.sha256(body).hexdigest(), **({"template_sha256": template_sha} if template_sha else {}), "ua": self.headers.get("User-Agent", "")[:60]}
        with LOCK, open(self.log_path, "a") as fh:
            fh.write(json.dumps(rec) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--routes", required=True)
    ap.add_argument("--log", required=True)
    ap.add_argument("--meta", help="routes_meta.json：host → {arm, cycle}，寫進每一筆存取紀錄")
    ap.add_argument("--dynamic", action="store_true", help="換掉 {{FETCH_TS}}／{{FETCH_COUNT}}／{{FETCH_ID}}，並依副檔名給 Content-Type（heldout-v3）")
    a = ap.parse_args()
    H.routes_path = pathlib.Path(a.routes)
    H.log_path = pathlib.Path(a.log)
    H.meta_path = pathlib.Path(a.meta) if a.meta else None
    H.dynamic = a.dynamic
    ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
