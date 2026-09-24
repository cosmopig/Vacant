#!/usr/bin/env python3
"""要金鑰的中繼：Authorization 必須是 `Bearer <secret>`，否則 401；對了才轉給 1004。

用途：驗 extension「借來的金鑰」真的送到上游。LM Studio 本身不要金鑰，量不出這件事，
所以在它前面放一個會查的門。**日誌只記 auth 對不對（ok／missing／wrong），不記金鑰本身。**
"""
import http.client, json, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BIND, PORT = sys.argv[1], int(sys.argv[2])
UP_HOST, UP_PORT = sys.argv[3], int(sys.argv[4])
SECRET = open(sys.argv[5]).read().strip()
LOG = sys.argv[6]
_lock = threading.Lock()


def log(rec):
    rec["t"] = time.time()
    with _lock, open(LOG, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, *a):
        pass

    def _go(self):
        n = int(self.headers.get("content-length") or 0)
        body = self.rfile.read(n) if n else b""
        a = self.headers.get("authorization")
        auth = "missing" if not a else ("ok" if a == f"Bearer {SECRET}" else "wrong")
        rec = {"method": self.command, "path": self.path, "auth": auth,
               "req_bytes": len(body)}
        if auth != "ok":
            msg = json.dumps({"error": {"message": f"relay: auth {auth}",
                                        "type": "invalid_request_error"}}).encode()
            self.send_response(401)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)
            rec["status"] = 401
            log(rec)
            return
        hdr = {k: v for k, v in self.headers.items()
               if k.lower() not in ("host", "authorization", "connection",
                                    "content-length", "accept-encoding")}
        c = http.client.HTTPConnection(UP_HOST, UP_PORT, timeout=900)
        try:
            c.request(self.command, self.path, body=body or None, headers=hdr)
            r = c.getresponse()
            self.send_response(r.status)
            for k, v in r.getheaders():
                if k.lower() not in ("transfer-encoding", "connection", "content-length"):
                    self.send_header(k, v)
            self.send_header("connection", "close")
            self.end_headers()
            out = 0
            while True:
                chunk = r.read1(65536) if hasattr(r, "read1") else r.read(65536)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
                out += len(chunk)
            rec.update(status=r.status, resp_bytes=out)
        except Exception as e:
            rec.update(status=None, error=f"{type(e).__name__}: {e}")
        finally:
            c.close()
            log(rec)

    do_GET = do_POST = _go


ThreadingHTTPServer((BIND, PORT), H).serve_forever()
