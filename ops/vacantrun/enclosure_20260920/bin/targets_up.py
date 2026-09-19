#!/usr/bin/env python3
"""把三個探針目標立起來。每個都印 READY，沒印 READY 就不准拿去當「不可達」的對照。"""
import os, socket, socketserver, sys, threading, time

BASE = sys.argv[1]
mode = sys.argv[2]   # tcp_localhost | unix_path | unix_abstract

class H(socketserver.BaseRequestHandler):
    def handle(self):
        try:
            self.request.recv(1024)
            self.request.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 6\r\n\r\nALIVE\n")
        except Exception:
            pass

if mode == "tcp_localhost":
    class S(socketserver.ThreadingTCPServer):
        allow_reuse_address = True; daemon_threads = True
    s = S(("127.0.0.1", int(sys.argv[3])), H)
    print(f"READY tcp_localhost 127.0.0.1:{sys.argv[3]} uid={os.getuid()}", flush=True)
    s.serve_forever()
elif mode == "unix_path":
    p = sys.argv[3]
    if os.path.exists(p): os.unlink(p)
    class S(socketserver.ThreadingUnixStreamServer):
        allow_reuse_address = True; daemon_threads = True
    s = S(p, H); os.chmod(p, 0o666)
    print(f"READY unix_path {p} uid={os.getuid()}", flush=True)
    s.serve_forever()
elif mode == "unix_abstract":
    name = sys.argv[3]
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind("\0" + name); srv.listen(8)
    print(f"READY unix_abstract @{name} uid={os.getuid()}", flush=True)
    while True:
        c, _ = srv.accept()
        try:
            c.recv(1024); c.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 6\r\n\r\nALIVE\n")
        except Exception:
            pass
        c.close()
