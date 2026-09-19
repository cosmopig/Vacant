#!/usr/bin/env python3
"""門的 HTTP 探針：在 enclosure 裡直接對 unix socket 講 HTTP，逐格對答案。

⚠ **每一格都要給 `want_status`**，而且最後印 `mismatched=`。沒有期望值的
  「我看到 403」不算量到——量具自己可能只是連不上。

規格從 `DOOR_CHECKS`（環境變數，JSON）讀：

    {"名字": {"sock": "/run/vacant/relay.sock", "method": "GET",
              "path": "/admin", "body": "", "want_status": 403,
              "header_auth": "Bearer ..."}}

`want_status` 給 `0` 代表「這一格應該連不上」（例如 socket 不存在）。
"""
import http.client
import json
import os
import socket
import sys
import time


class UnixHTTP(http.client.HTTPConnection):
    def __init__(self, sock_path, timeout=30.0):
        super().__init__("localhost", timeout=timeout)
        self._p = sock_path

    def connect(self):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(self.timeout)
        s.connect(self._p)
        self.sock = s


def one(spec):
    t0 = time.time()
    body = (spec.get("body") or "").encode()
    headers = {}
    if body:
        headers["Content-Type"] = "application/json"
    if spec.get("header_auth"):
        headers["Authorization"] = spec["header_auth"]
    try:
        c = UnixHTTP(spec["sock"])
        c.request(spec.get("method", "GET"), spec["path"],
                  body=body or None, headers=headers)
        r = c.getresponse()
        payload = r.read(400)
        c.close()
        return {"status": r.status, "snippet": payload[:200].decode(
            "utf-8", "replace"), "error": None,
            "ms": int((time.time() - t0) * 1000)}
    except Exception as e:                                   # noqa: BLE001
        return {"status": 0, "snippet": "", "error": f"{type(e).__name__}: {e}",
                "ms": int((time.time() - t0) * 1000)}


def main():
    checks = json.loads(os.environ.get("DOOR_CHECKS", "{}"))
    print(f"DOOR_PROBE_START n={len(checks)} uid={os.getuid()}", flush=True)
    rows = []
    for name, spec in checks.items():
        got = one(spec)
        want = spec.get("want_status")
        row = {"name": name, "sock": spec["sock"],
               "method": spec.get("method", "GET"), "path": spec["path"],
               "want_status": want, **got}
        row["match"] = (want is None) or (got["status"] == want)
        rows.append(row)
        print(f"DOOR {name:<22s} {row['method']:<5s} {spec['path']:<26s} "
              f"got={got['status']:<4d} want={want!s:<5s} "
              f"match={row['match']!s:<5s} {got['error'] or got['snippet'][:70]!r}",
              flush=True)
    out = os.environ.get("DOOR_JSON_OUT")
    if out:
        try:
            with open(out, "w", encoding="utf-8") as fh:
                json.dump(rows, fh, ensure_ascii=False, indent=2)
        except Exception as e:                               # noqa: BLE001
            print(f"DOOR_JSON_FAIL {type(e).__name__}: {e}", flush=True)
    bad = [r for r in rows if not r["match"]]
    print(f"DOOR_PROBE_DONE rows={len(rows)} mismatched={len(bad)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
