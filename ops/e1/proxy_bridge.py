#!/usr/bin/env python3
"""ops.e1.proxy_bridge — 沙箱內（--unshare-net）極簡 TCP→UNIX 轉發器（僅用標準函式庫）。

在 `bwrap --unshare-net` 沙箱內啟動：
1. 在本機回環 `127.0.0.1:<ephemeral>` 開一個 TCP 監聽埠。
2. 每一條進來的 TCP 連線原封不動雙向轉發到宿主唯讀掛入的 UNIX socket（`--sock`）。
3. 把 `HTTP_PROXY`／`http_proxy`／`HTTPS_PROXY`／`https_proxy` 設為該本機埠，並把 `NO_PROXY`／`no_proxy`
   清空，再啟動真正的子行程（例如 `claude` 或負控制探針），最後原樣回傳子行程的退出碼。

本檔故意不 import 任何 `ops.*`，方便單檔 `--ro-bind` 進沙箱且不掛載 repo。
"""
from __future__ import annotations

import argparse
import os
import signal
import socket
import subprocess
import sys
import threading


def _relay(src: socket.socket, dst: socket.socket) -> None:
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
    except OSError:
        pass
    finally:
        try:
            dst.shutdown(socket.SHUT_WR)
        except OSError:
            pass


def _handle_client(cli: socket.socket, sock_path: str) -> None:
    up: socket.socket | None = None
    try:
        up = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        up.connect(sock_path)
    except OSError:
        try:
            cli.close()
        except OSError:
            pass
        if up is not None:
            try:
                up.close()
            except OSError:
                pass
        return

    t1 = threading.Thread(target=_relay, args=(cli, up), daemon=True)
    t2 = threading.Thread(target=_relay, args=(up, cli), daemon=True)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    for s in (cli, up):
        try:
            s.close()
        except OSError:
            pass


def main() -> int:
    ap = argparse.ArgumentParser(description="E1 sandbox TCP->UNIX proxy bridge")
    ap.add_argument("--sock", required=True, help="UNIX domain socket path bound from host")
    ap.add_argument("cmd", nargs=argparse.REMAINDER, help="Command after --")
    args = ap.parse_args()

    cmd = list(args.cmd)
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]
    if not cmd:
        sys.stderr.write("proxy_bridge: missing command after --\n")
        return 2

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(64)
    port = srv.getsockname()[1]

    stop = threading.Event()

    def _accept_loop() -> None:
        while not stop.is_set():
            try:
                cli, _ = srv.accept()
            except OSError:
                break
            threading.Thread(target=_handle_client, args=(cli, args.sock), daemon=True).start()

    th = threading.Thread(target=_accept_loop, daemon=True)
    th.start()

    proxy_url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env["HTTP_PROXY"] = proxy_url
    env["http_proxy"] = proxy_url
    env["HTTPS_PROXY"] = proxy_url
    env["https_proxy"] = proxy_url
    env["NO_PROXY"] = ""
    env["no_proxy"] = ""

    proc = subprocess.Popen(cmd, env=env)

    def _fwd_sig(signum: int, _frame: object) -> None:
        try:
            proc.send_signal(signum)
        except OSError:
            pass

    signal.signal(signal.SIGTERM, _fwd_sig)
    signal.signal(signal.SIGINT, _fwd_sig)

    try:
        rc = proc.wait()
    finally:
        stop.set()
        try:
            srv.close()
        except OSError:
            pass
    return int(rc)


if __name__ == "__main__":
    raise SystemExit(main())
