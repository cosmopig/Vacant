"""替身 LM Studio。用法：fakemodel.py PORT [DELAY_MS]

這支不是 1003。要量的是「模型不回話時 loop 會怎樣」，替身比真模型精確：
真模型還會逾時、會被思考擠掉，那些是 e2e_1003.sh 的事。
"""
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1]); DELAY = float(sys.argv[2]) / 1000.0 if len(sys.argv) > 2 else 0.0
N = {"calls": 0}


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *a):
        sys.stderr.write("model %s\n" % (fmt % a))

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(n)
        if not self.path.endswith("/chat/completions"):
            body = json.dumps({"error": "not found"}).encode()
            self.send_response(404); self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body); return
        if DELAY:
            time.sleep(DELAY)
        N["calls"] += 1
        content = json.dumps({"arrival": "替身：我到了。", "working": "替身：動手了。",
                              "handover": "替身：交給你。"}, ensure_ascii=False)
        body = json.dumps({
            "choices": [{"message": {"content": content, "reasoning_content": ""}}],
            "usage": {"completion_tokens": 40,
                      "completion_tokens_details": {"reasoning_tokens": 0}},
        }).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
