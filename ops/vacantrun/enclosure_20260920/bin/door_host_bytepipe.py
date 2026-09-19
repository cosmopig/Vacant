#!/usr/bin/env python3
"""門的主機側，**byte pipe 版本——已被取代，留著只為了當負控制**。

2026-09-20 早上的那一版：聽一個路徑型 unix socket，把 bytes 原樣轉給上游 TCP。
它證明了「門開得起來」（路徑型 unix socket 不受 network namespace 管，
所以穿得過 `--unshare-net`，而 TCP／DNS／抽象 socket 都穿不過去）。

⚠ **但它不看內容。** enclosure 裡的 agent 照樣可以對它送**任何** HTTP 請求，
  只要對面那台主機收——洞從「任意主機」縮小到「那一台上游」，**不是關掉**。
  所以正式的門換成了 `python3 -m vacant_network.vrun.proxyd --unix <sock>`
  （會終結 HTTP、有 path 政策、有 journal、`sentinel=""` 不持有金鑰）。

**這一份留在 repo 裡的唯一理由**：它是 `/admin` 那一格的負控制——同一個
enclosure、同一支探針，門換成這一支就會把 `GET /admin` 原樣隧道到上游。
沒有那一格，「proxyd 擋掉了 /admin」讀起來會像是上游本來就沒有那條路。

用法：`door_host_bytepipe.py <sock> <up_host> <up_port> [logfile]`
"""
import os
import socket
import socketserver
import sys
import threading

SOCK = sys.argv[1]
UP_HOST, UP_PORT = sys.argv[2], int(sys.argv[3])
LOGF = sys.argv[4] if len(sys.argv) > 4 else None
_lock = threading.Lock()
_count = [0]


def log(msg):
    if LOGF:
        with _lock, open(LOGF, "a") as fh:
            fh.write(msg + "\n")


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        with _lock:
            _count[0] += 1
            n = _count[0]
        log(f"CONN {n}")
        try:
            up = socket.create_connection((UP_HOST, UP_PORT), 15)
        except Exception as e:                               # noqa: BLE001
            log(f"UPSTREAM_FAIL {n} {type(e).__name__}: {e}")
            return
        down = self.request

        def pipe(a, b, tag):
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

        t = threading.Thread(target=pipe, args=(down, up, "u"), daemon=True)
        t.start()
        pipe(up, down, "d")
        t.join(timeout=30)
        up.close()


class Srv(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True
    allow_reuse_address = True


if os.path.exists(SOCK):
    os.unlink(SOCK)
srv = Srv(SOCK, Handler)
os.chmod(SOCK, 0o666)
print(f"DOOR_HOST_READY sock={SOCK} upstream={UP_HOST}:{UP_PORT}", flush=True)
srv.serve_forever()
