#!/usr/bin/env python3
"""抵達層量測用的靜態伺服器。

⚠ **刻意不用展場那台（8420）**：那一台是共用的活展件，而且這一批同時有
   十幾個 agent 在動。這一支只讀 vacant_hm 的檔，額外掛兩條虛擬路徑：

     /probe/visitors.json        ← 從 scratchpad 讀（投稿注入口，每次 no-store）
     /world3/index.before.html   ← 改動前那一版（git HEAD），掛在同一個目錄底下
                                   ⇒ 相對路徑的板／精靈／bridge.js 全部照常解析

   **一個 byte 都不寫進 repo。**
"""
import http.server, os, socketserver, sys, threading

ROOT = "/Users/cosmopig/Documents/GitHub/vacant_hm"
SCRATCH = os.path.dirname(os.path.abspath(__file__))
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8471

class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def _send_file(self, path, ctype):
        try:
            with open(path, "rb") as f:
                body = f.read()
        except OSError as e:
            self.send_error(404, str(e)); return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = self.path.split("?", 1)[0]
        if p == "/probe/visitors.json":
            return self._send_file(os.path.join(SCRATCH, "visitors.json"), "application/json")
        if p == "/world3/index.before.html":
            return self._send_file(os.path.join(SCRATCH, "index.before.html"), "text/html; charset=utf-8")
        # ⚠ **凍結副本。** 第一批五臂跑到一半，`index.html` 的 sha 從
        #   ebabae34 變成 8e2ec474——別的 agent 也在改這個檔（記號層、精簡模式、
        #   等待態同時在動）。⇒ 那五臂嚴格講不是同一份碼。
        #   從 S06／S07 起改成**服務一份凍結副本**：兩臂比的是同一個 byte 串，
        #   而副本的 sha 記在證據裡，對得回當下的 index.html。
        if p == "/world3/index.frozen.html":
            return self._send_file(os.path.join(SCRATCH, "index.frozen.html"), "text/html; charset=utf-8")
        return super().do_GET()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, max-age=0")
        super().end_headers()

    def log_message(self, *a):
        pass

class S(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

if __name__ == "__main__":
    with S(("127.0.0.1", PORT), H) as httpd:
        print(f"serving {ROOT} on 127.0.0.1:{PORT}", flush=True)
        httpd.serve_forever()
