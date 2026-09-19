#!/usr/bin/env python3
"""同機**另一個 uid** 的迴圈中繼：量 `block_egress.sh` 的迴圈放行有多寬。

`block_egress.sh` 規則 1（`-o lo -j ACCEPT`）放行**整條迴圈**，不是只放行
proxy 那個埠（規則 3 因此是死碼）。這支以 user1 的身分聽 127.0.0.1:<port>，
把 bytes 原樣轉給 openrouter.ai:443。被封鎖的 uid 連得到它 ⇒ 封鎖被繞過。
"""
import socket, sys, threading

LISTEN = int(sys.argv[1]); TARGET = (sys.argv[2], int(sys.argv[3]))

def pump(a, b):
    try:
        while True:
            d = a.recv(65536)
            if not d: break
            b.sendall(d)
    except Exception: pass
    finally:
        for s in (a, b):
            try: s.shutdown(socket.SHUT_RDWR)
            except Exception: pass
            try: s.close()
            except Exception: pass

srv = socket.socket(); srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(("127.0.0.1", LISTEN)); srv.listen(8)
print(f"relay 127.0.0.1:{LISTEN} -> {TARGET}", flush=True)
while True:
    c, _ = srv.accept()
    try:
        u = socket.create_connection(TARGET, 10)
    except Exception as e:
        print("upstream fail", e, flush=True); c.close(); continue
    threading.Thread(target=pump, args=(c, u), daemon=True).start()
    threading.Thread(target=pump, args=(u, c), daemon=True).start()
