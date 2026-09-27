#!/usr/bin/env python3
"""要金鑰、而且**只認一個模型別名**的中繼（§七 重驗用；relay.py 是 §〇–§五 那一跑的原件，不改）。

- Authorization 必須是 `Bearer <secret>`，否則 401（同 relay.py）。
- `GET /v1/models` 回 `[{"id": ALIAS}]`（模擬「上游的模型目錄跟 DEFAULT_MODEL 不一樣」）。
- `POST` 的 JSON body `model` 必須等於 ALIAS，否則 404；等於就改寫成 REAL 再轉給 1004。
日誌只記 auth 對不對、要的是哪個 model id，不記金鑰。
"""
import http.client, json, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BIND, PORT = sys.argv[1], int(sys.argv[2])
UP_HOST, UP_PORT = sys.argv[3], int(sys.argv[4])
SECRET = open(sys.argv[5]).read().strip()
LOG = sys.argv[6]
ALIAS, REAL = sys.argv[7].split("=", 1)
_lock = threading.Lock()


def log(rec):
    rec["t"] = time.time(); rec["bind"] = f"{BIND}:{PORT}"
    with _lock, open(LOG, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, *a):
        pass

    def _json(self, code, obj, rec):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(b)))
        self.end_headers(); self.wfile.write(b)
        rec["status"] = code; log(rec)

    def _go(self):
        n = int(self.headers.get("content-length") or 0)
        body = self.rfile.read(n) if n else b""
        a = self.headers.get("authorization")
        auth = "missing" if not a else ("ok" if a == f"Bearer {SECRET}" else "wrong")
        rec = {"method": self.command, "path": self.path, "auth": auth, "req_bytes": len(body)}
        if auth != "ok":
            return self._json(401, {"error": {"message": f"relay: auth {auth}"}}, rec)
        if self.command == "GET" and self.path.split("?")[0].endswith("/models"):
            return self._json(200, {"object": "list", "data": [{"id": ALIAS, "object": "model"}]}, rec)
        if self.command == "POST":
            try:
                doc = json.loads(body or b"{}")
            except ValueError:
                doc = {}
            rec["model_requested"] = doc.get("model")
            if doc.get("model") != ALIAS:
                return self._json(404, {"error": {"message": f"relay: unknown model {doc.get('model')!r}"}}, rec)
            doc["model"] = REAL
            body = json.dumps(doc).encode()
        hdr = {k: v for k, v in self.headers.items()
               if k.lower() not in ("host", "authorization", "connection", "content-length", "accept-encoding")}
        c = http.client.HTTPConnection(UP_HOST, UP_PORT, timeout=900)
        try:
            c.request(self.command, self.path, body=body or None, headers=hdr)
            r = c.getresponse()
            self.send_response(r.status)
            for k, v in r.getheaders():
                if k.lower() not in ("transfer-encoding", "connection", "content-length"):
                    self.send_header(k, v)
            self.send_header("connection", "close"); self.end_headers()
            out = 0
            while True:
                chunk = r.read1(65536)
                if not chunk:
                    break
                self.wfile.write(chunk); self.wfile.flush(); out += len(chunk)
            rec.update(status=r.status, resp_bytes=out)
        except Exception as e:
            rec.update(status=None, error=f"{type(e).__name__}: {e}")
        finally:
            c.close(); log(rec)

    do_GET = do_POST = _go


ThreadingHTTPServer((BIND, PORT), H).serve_forever()
