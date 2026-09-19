"""這支在架構裡承重什麼：R534 的「逐字落盤」底座。

紀律 3（全 I/O JSONL 落盤）要求每一次模型呼叫連同失敗與重試都留逐字紀錄。
pi（@earendil-works/pi-coding-agent）自己的 session JSONL 是它整理過的視圖，
不是 wire 上真正送出去的 request body；而 R534 的核心變因 reasoning_effort
恰恰只存在於 wire 上。所以在 pi 與 LM Studio 之間插一個透明反向代理，
把「真的送出去的 bytes」與「真的收回來的 bytes」原樣寫成 JSONL，
之後任何關於「這一跑到底有沒有送 reasoning_effort」的爭議都用這份檔案裁決，
不用相信 harness 的自述（同 12 §4.3 的可究責原則：自述不算證據，收據才算）。

用法：
    python3 wire_tap.py --listen 127.0.0.1:8801 \
        --upstream http://100.86.226.21:1234/v1 \
        --log /path/to/wire.jsonl

行為邊界（誠實邊界句，改碼請保留）：
- 它 records 而非 verifies：代理只證明「這些 bytes 經過我」，
  不證明上游真的照著跑，也不防止 pi 走別的路徑繞過代理。
- 不截斷、不去識別：body 原樣以 utf-8 (errors=replace) 寫入。
"""

from __future__ import annotations

import argparse
import json
import threading
import time
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_LOCK = threading.Lock()
_LOG_PATH = ""
_UPSTREAM = ""


def _append(record: dict) -> None:
    line = json.dumps(record, ensure_ascii=False)
    with _LOCK:
        with open(_LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
            fh.flush()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "vacant-wiretap/1"

    def log_message(self, fmt, *args):  # noqa: D102 - 靜音預設 stderr log
        return

    def _proxy(self, method: str) -> None:
        call_id = uuid.uuid4().hex
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        url = _UPSTREAM.rstrip("/") + self.path
        req_headers = {k: v for k, v in self.headers.items()
                       if k.lower() not in ("host", "content-length", "connection")}
        _append({
            "call_id": call_id,
            "dir": "request",
            "ts": time.time(),
            "method": method,
            "path": self.path,
            "url": url,
            "headers": req_headers,
            "body": body.decode("utf-8", errors="replace"),
        })
        req = urllib.request.Request(url, data=body or None, method=method)
        for k, v in req_headers.items():
            req.add_header(k, v)
        t0 = time.time()
        chunks: list[bytes] = []
        try:
            with urllib.request.urlopen(req, timeout=3600) as resp:
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() in ("transfer-encoding", "content-length", "connection"):
                        continue
                    self.send_header(k, v)
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                while True:
                    chunk = resp.read(4096)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    self.wfile.write(b"%X\r\n%s\r\n" % (len(chunk), chunk))
                    self.wfile.flush()
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()
                status = resp.status
                err = None
        except urllib.error.HTTPError as exc:  # 失敗也要留紀錄
            payload = exc.read()
            chunks.append(payload)
            status = exc.code
            err = None
            self.send_response(exc.code)
            self.send_header("Content-Type", exc.headers.get("Content-Type", "application/json"))
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except Exception as exc:  # noqa: BLE001 - infra_void 也要落盤
            status = 0
            err = repr(exc)
            try:
                self.send_response(502)
                self.send_header("Content-Length", "0")
                self.end_headers()
            except Exception:  # noqa: BLE001
                pass
        _append({
            "call_id": call_id,
            "dir": "response",
            "ts": time.time(),
            "elapsed_s": round(time.time() - t0, 3),
            "status": status,
            "error": err,
            "body": b"".join(chunks).decode("utf-8", errors="replace"),
        })

    def do_POST(self):  # noqa: N802
        self._proxy("POST")

    def do_GET(self):  # noqa: N802
        self._proxy("GET")


def main() -> None:
    global _LOG_PATH, _UPSTREAM
    ap = argparse.ArgumentParser()
    ap.add_argument("--listen", default="127.0.0.1:8801")
    ap.add_argument("--upstream", required=True)
    ap.add_argument("--log", required=True)
    args = ap.parse_args()
    _LOG_PATH = args.log
    _UPSTREAM = args.upstream
    host, _, port = args.listen.rpartition(":")
    srv = ThreadingHTTPServer((host or "127.0.0.1", int(port)), Handler)
    print(f"wire_tap listening on {args.listen} -> {args.upstream}, log={args.log}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
