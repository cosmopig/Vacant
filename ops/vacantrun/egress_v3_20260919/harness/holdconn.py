#!/usr/bin/env python3
"""量「封鎖之前就建好的連線」會不會被切斷。

封鎖前建一條到 1004 的 TCP 連線並保持，之後每 5 秒在**同一條連線上**發一次
HTTP 請求，逐次落盤。`-m owner` 比對的是 socket 的 owner，理論上既有連線的
送出封包一樣會被 REJECT——但那是理論，這支是量它。
"""
import json, socket, sys, time

HOST, PORT, OUT = sys.argv[1], int(sys.argv[2]), sys.argv[3]
s = socket.create_connection((HOST, PORT), 10)
s.settimeout(8)
rows = [{"ts": time.strftime("%H:%M:%S"), "event": "connected",
         "peer": str(s.getpeername())}]
with open(OUT, "w") as f:
    f.write(json.dumps(rows[-1], ensure_ascii=False) + "\n"); f.flush()
    for i in range(400):
        rec = {"ts": time.strftime("%H:%M:%S"), "i": i}
        try:
            s.sendall(b"GET /v1/models HTTP/1.1\r\nHost: h\r\n\r\n")
            d = s.recv(200)
            rec.update(ok=bool(d), first=d[:40].decode("latin-1"))
        except Exception as e:
            rec.update(ok=False, error=f"{type(e).__name__}: {e}")
        f.write(json.dumps(rec, ensure_ascii=False) + "\n"); f.flush()
        if not rec.get("ok") and "error" in rec:
            pass
        time.sleep(5)
