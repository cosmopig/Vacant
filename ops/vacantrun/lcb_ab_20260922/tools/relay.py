#!/usr/bin/env python3
"""把「容器出網過濾器的 DNS 不穩」吸收掉的**本機重試中繼**。

## 它是什麼、不是什麼

· **不是 Vacant 的一部分。** 它是這台機器的基礎設施補償，跑在 Vacant 外面。
· **兩臂共用、逐位元同一個端點**（ON 與 OFF 都指到 `http://127.0.0.1:<port>/v1`）
  ⇒ 它不可能偏袒任何一臂。這是它存在的唯一前提，改碼要保住。
· 只在**環境層的失敗**上重試：403 `resolve_no_records`、503 `DNS resolution failure`、
  連線層例外。**上游模型自己回的 4xx/5xx 原樣透傳，不重試**——那是內容不是環境。

## 為什麼需要它

`BLOCKER.txt`：同一個名字直連的成功率約 42%，一個 agent session 要 5–15 通
⇒ 跑完的機率約 1%。沒有這一層，量到的會是網路而不是 agent。

## 誠實邊界

1. **每一次重試都落盤**（`relay.jsonl`：時間、path、第幾次、狀態）⇒ 事後查得到
   「這一格被環境補償了幾次」。補償不是隱形的。
2. 它**不改 body、不改 header**（除了 Host）⇒ 逐位元轉送。
3. 重試上限 `MAX_TRIES`；用完仍失敗就把最後一個狀態原樣回給呼叫端，
   **不假裝成功**（那一格就會是 infra_void，該作廢就作廢）。
"""
from __future__ import annotations

import http.client
import http.server
import json
import os
import pathlib
import ssl
import sys
import threading
import time
import urllib.parse

UPSTREAM = os.environ.get("RELAY_UPSTREAM", "https://1003.taild870c4.ts.net/v1")
PORT = int(os.environ.get("RELAY_PORT", "19000"))
LOG = pathlib.Path(os.environ.get("RELAY_LOG", "/tmp/relay.jsonl"))
MAX_TRIES = int(os.environ.get("RELAY_MAX_TRIES", "12"))
BACKOFF = float(os.environ.get("RELAY_BACKOFF", "1.5"))

_u = urllib.parse.urlparse(UPSTREAM)
HOST, PORT_UP = _u.hostname, (_u.port or 443)
BASE_PATH = _u.path.rstrip("/")
_lock = threading.Lock()

#: 只有這些算「環境壞了」⇒ 可以重試。其餘原樣透傳。
ENV_FAIL_BODIES = (b"resolve_no_records", b"DNS resolution failure",
                   b"Host resolves to a private/reserved IP")


def _log(rec: dict) -> None:
    with _lock:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


class H(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):          # 不要把每通都印到 stderr
        return

    def _relay(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n) if n else b""
        # `/v1/...` → 上游的 BASE_PATH + 剩下的
        path = self.path
        if path.startswith("/v1"):
            path = BASE_PATH + path[len("/v1"):]
        hdrs = {k: v for k, v in self.headers.items()
                if k.lower() not in ("host", "connection", "content-length")}
        hdrs["Host"] = HOST
        if body:
            hdrs["Content-Length"] = str(len(body))
        t0 = time.time()
        last = None
        for attempt in range(1, MAX_TRIES + 1):
            try:
                c = http.client.HTTPSConnection(
                    HOST, PORT_UP, timeout=600,
                    context=ssl.create_default_context())
                c.request(self.command, path, body=body, headers=hdrs)
                r = c.getresponse()
                data = r.read()
                status, rh = r.status, r.getheaders()
                c.close()
                env_fail = (status in (403, 502, 503)
                            and any(m in data for m in ENV_FAIL_BODIES))
                _log({"t": time.time(), "path": self.path, "attempt": attempt,
                      "status": status, "env_fail": env_fail,
                      "bytes": len(data)})
                if env_fail and attempt < MAX_TRIES:
                    time.sleep(min(BACKOFF * attempt, 8.0))
                    continue
                self.send_response(status)
                for k, v in rh:
                    if k.lower() in ("connection", "transfer-encoding",
                                     "content-length"):
                        continue
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            except Exception as e:                           # noqa: BLE001
                last = f"{type(e).__name__}: {e}"
                _log({"t": time.time(), "path": self.path, "attempt": attempt,
                      "status": None, "env_fail": True, "error": last})
                if attempt < MAX_TRIES:
                    time.sleep(min(BACKOFF * attempt, 8.0))
                    continue
        # 用完了還是不行 ⇒ **老實回 502**，不假裝成功
        msg = json.dumps({"error": {"message": f"relay exhausted: {last}",
                                    "type": "relay_env_failure"}}).encode()
        _log({"t": time.time(), "path": self.path, "attempt": MAX_TRIES,
              "status": 502, "env_fail": True, "exhausted": True,
              "wall_s": round(time.time() - t0, 1)})
        self.send_response(502)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(msg)))
        self.end_headers()
        self.wfile.write(msg)

    do_GET = do_POST = do_PUT = do_DELETE = _relay


if __name__ == "__main__":
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), H)
    print(f"relay :{PORT} -> {UPSTREAM}  max_tries={MAX_TRIES}  log={LOG}",
          flush=True)
    srv.serve_forever()
