#!/usr/bin/env python3
"""從被封鎖的 uid 經 unix socket 中繼打 openrouter.ai（完整 TLS）。"""
import json, socket, ssl, sys, time
PATH=sys.argv[1]; t0=time.time()
out={"channel":"unix_domain_socket_relay","path":PATH}
try:
    raw=socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); raw.settimeout(8); raw.connect(PATH)
    s=ssl.create_default_context().wrap_socket(raw, server_hostname="openrouter.ai")
    s.sendall(b"GET /api/v1/models HTTP/1.1\r\nHost: openrouter.ai\r\nConnection: close\r\n\r\n")
    out.update(ok=True, value=s.recv(200).decode("latin-1").splitlines()[0]); s.close()
except Exception as e:
    out.update(ok=False, error=f"{type(e).__name__}: {e}")
out["elapsed_s"]=round(time.time()-t0,3)
print(json.dumps(out, ensure_ascii=False))
