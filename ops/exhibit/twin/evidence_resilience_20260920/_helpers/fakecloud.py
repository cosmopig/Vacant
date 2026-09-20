"""替身雲端郵箱。**不是 server.js**——存在的理由是要餵進真伺服器產不出來的
畸形 `/api/all` 回應（那是 twinlink 眼中的外部輸入）。

用法：fakecloud.py PORT TOKEN ITEMS_JSON
ITEMS_JSON 每次請求重讀，所以演練中途可以換內容。格式：
    {"mode": "ok"|"nonjson"|"http500"|"noitems"|"no_all", "items": [...]}
"""
import json
import pathlib
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

PORT = int(sys.argv[1]); TOKEN = sys.argv[2]; ITEMS = pathlib.Path(sys.argv[3])


def load():
    try:
        d = json.loads(ITEMS.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return {"mode": "ok", "items": [], "_err": str(e)}
    if isinstance(d, list):
        return {"mode": "ok", "items": d}
    return d


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *a):
        sys.stderr.write("cloud %s\n" % (fmt % a))

    def _send(self, code, obj=None, raw=None, ctype="application/json"):
        # ensure_ascii=True（預設）：這樣連 lone surrogate 都送得出去，
        # 跟 Node 的 JSON.stringify 一樣是逃脫成 \\udXXX。
        body = raw if raw is not None else json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        tok = (q.get("token") or [""])[0]
        cfg = load()
        mode = cfg.get("mode", "ok")
        if u.path not in ("/api/all", "/api/queue"):
            return self._send(404, {"error": "not found"})
        if u.path == "/api/all" and mode == "no_all":
            return self._send(404, {"error": "no /api/all on this build"})
        if tok != TOKEN:
            return self._send(401, {"error": "bad token"})
        if mode == "http500":
            return self._send(500, {"error": "boom"})
        if mode == "nonjson":
            return self._send(200, raw=b"<html>not json</html>", ctype="text/html")
        if mode == "noitems":
            return self._send(200, {"ok": True})
        return self._send(200, {"items": cfg.get("items", [])})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(n)
        if self.path != "/api/result":
            return self._send(404, {"error": "not found"})
        return self._send(200, {"ok": True})


ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
