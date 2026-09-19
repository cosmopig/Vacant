#!/usr/bin/env python3
"""圍牆探針：同一支腳本在「套 enclosure」與「不套」兩種情況下跑，逐目標印結果。

⚠ 量具自己要先活著：每一格都印 RESULT 行，沒有 RESULT 行＝腳本沒跑到，
  不是「不可達」。最後一行一定印 PROBE_DONE。
"""
import json
import os
import socket
import sys
import time

TARGETS = json.loads(os.environ.get("PROBE_TARGETS", "{}"))


def tcp(host, port, timeout=4.0):
    t0 = time.time()
    try:
        s = socket.create_connection((host, int(port)), timeout)
        s.close()
        return True, "connected", int((time.time() - t0) * 1000)
    except Exception as e:                                   # noqa: BLE001
        return False, f"{type(e).__name__}: {e}", int((time.time() - t0) * 1000)


def unix_path(path, timeout=4.0):
    t0 = time.time()
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(path)
        s.close()
        return True, "connected", int((time.time() - t0) * 1000)
    except Exception as e:                                   # noqa: BLE001
        return False, f"{type(e).__name__}: {e}", int((time.time() - t0) * 1000)


def unix_abstract(name, timeout=4.0):
    t0 = time.time()
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect("\0" + name)
        s.close()
        return True, "connected", int((time.time() - t0) * 1000)
    except Exception as e:                                   # noqa: BLE001
        return False, f"{type(e).__name__}: {e}", int((time.time() - t0) * 1000)


def dns(name, timeout=4.0):
    t0 = time.time()
    socket.setdefaulttimeout(timeout)
    try:
        info = socket.getaddrinfo(name, 80, proto=socket.IPPROTO_TCP)
        return True, str(info[0][4]), int((time.time() - t0) * 1000)
    except Exception as e:                                   # noqa: BLE001
        return False, f"{type(e).__name__}: {e}", int((time.time() - t0) * 1000)


def http_via_tcp(host, port, path="/v1/models", timeout=6.0):
    t0 = time.time()
    try:
        s = socket.create_connection((host, int(port)), timeout)
        s.settimeout(timeout)
        req = (f"GET {path} HTTP/1.1\r\nHost: {host}\r\n"
               "Connection: close\r\nAccept: */*\r\n\r\n").encode()
        s.sendall(req)
        buf = b""
        while len(buf) < 256:
            chunk = s.recv(256)
            if not chunk:
                break
            buf += chunk
        s.close()
        first = buf.split(b"\r\n", 1)[0].decode("latin1")
        return True, first, int((time.time() - t0) * 1000)
    except Exception as e:                                   # noqa: BLE001
        return False, f"{type(e).__name__}: {e}", int((time.time() - t0) * 1000)


def main():
    rows = []
    print(f"PROBE_START uid={os.getuid()} py={sys.version.split()[0]} "
          f"cwd={os.getcwd()}", flush=True)
    for key, spec in TARGETS.items():
        kind = spec["kind"]
        if kind == "tcp":
            ok, detail, ms = tcp(spec["host"], spec["port"])
        elif kind == "unix":
            ok, detail, ms = unix_path(spec["path"])
        elif kind == "abstract":
            ok, detail, ms = unix_abstract(spec["name"])
        elif kind == "dns":
            ok, detail, ms = dns(spec["name"])
        elif kind == "http":
            ok, detail, ms = http_via_tcp(spec["host"], spec["port"],
                                          spec.get("path", "/v1/models"))
        else:
            ok, detail, ms = False, "UNKNOWN_KIND", 0
        rows.append({"target": key, "kind": kind, "reachable": ok,
                     "detail": detail[:160], "ms": ms,
                     "want": spec.get("want")})
        print(f"RESULT {key:24s} kind={kind:9s} reachable={ok!s:5s} "
              f"want={spec.get('want')!s:5s} ms={ms:5d} {detail[:110]}",
              flush=True)
    out = os.environ.get("PROBE_JSON_OUT")
    if out:
        try:
            with open(out, "w") as fh:
                json.dump(rows, fh, ensure_ascii=False, indent=2)
        except Exception as e:                               # noqa: BLE001
            print(f"PROBE_JSON_FAIL {type(e).__name__}: {e}", flush=True)
    bad = [r for r in rows if r["want"] is not None and r["reachable"] != r["want"]]
    print(f"PROBE_DONE rows={len(rows)} mismatched={len(bad)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
