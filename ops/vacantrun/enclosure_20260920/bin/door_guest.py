#!/usr/bin/env python3
"""門的 enclosure 側：在 enclosure 內聽 127.0.0.1:<port>，轉給被 ro-bind 進來的
路徑型 unix socket。agent 只認得 HTTP base URL，所以圍牆裡面需要這一段。

⚠ **這一段是 byte pipe，而且那沒關係。** 它住在圍牆**裡面**，繞不過任何東西：
  HTTP 是在圍牆**外面**那一側（`proxyd --unix`）被終結的，path 政策、journal、
  金鑰穿透全部發生在那裡。圍牆裡的 agent 想跳過這一段直接連
  `/run/vacant/relay.sock` 也可以——那還是同一扇門。

用法：`door_guest.py <port> <sock>`
"""
import os
import socket
import socketserver
import sys
import threading

PORT = int(sys.argv[1])
SOCK = sys.argv[2]


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        try:
            up = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            up.connect(SOCK)
        except Exception as e:                               # noqa: BLE001
            sys.stderr.write(f"DOOR_GUEST_FAIL {type(e).__name__}: {e}\n")
            return
        down = self.request

        def pipe(a, b):
            try:
                while True:
                    data = a.recv(65536)
                    if not data:
                        break
                    b.sendall(data)
            except Exception:                                # noqa: BLE001
                pass
            finally:
                try:
                    b.shutdown(socket.SHUT_WR)
                except Exception:                            # noqa: BLE001
                    pass

        t = threading.Thread(target=pipe, args=(down, up), daemon=True)
        t.start()
        pipe(up, down)
        t.join(timeout=30)
        up.close()


class Srv(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


srv = Srv(("127.0.0.1", PORT), Handler)
print(f"DOOR_GUEST_READY port={PORT} sock={SOCK}", flush=True)
srv.serve_forever()
