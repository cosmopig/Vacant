#!/usr/bin/env python3
"""這支在架構裡承重什麼：把 B 類繞過（agent 自己的第二條連線）**講出名字**。

封包計數器說得出「有 N 個封包走了中介以外的路」，說不出那是誰。
但 agent 要連遙測／更新檢查／外掛下載之前，**幾乎一定先查 DNS**，
而 DNS 查詢裡有明文的主機名。這支就是把那個名字抓下來。

做法：以 proxy 的 uid（不被封的那個）聽 127.0.0.1:5353/udp，
`iptables -t nat` 把被量的 uid 的 53/udp 全部導過來，解出 QNAME 落盤，
再原樣轉給真 resolver、把答案送回去 ⇒ **agent 的行為不變**（它照樣查得到）。

誠實邊界（改碼請保留）：
 1. **直接連 IP 字面值的不會出現在這裡。** 沒有 DNS 就沒有名字。
    那種路只剩封包計數器看得到（而且看不到是誰）。
 2. **DoH／DoT 不會出現在這裡**（443/853 上的 TLS，本支看不到）。
    `udp_offbox`／`offbox` 計數器數得到封包，名字量不到。
 3. 這支**不擋**任何東西：名字記下來，查詢照樣成功。
    它是可究責性的量具，不是閘門。
 4. 只解 QNAME，不解答案。回應原樣轉送，一個 byte 不改。
"""
from __future__ import annotations

import json
import socket
import sys
import time

LISTEN = ("127.0.0.1", int(sys.argv[1]) if len(sys.argv) > 1 else 5353)
UPSTREAM = (sys.argv[2] if len(sys.argv) > 2 else "127.0.0.53", 53)
OUT = sys.argv[3] if len(sys.argv) > 3 else "/var/tmp/vbypass/logs/dns.jsonl"

QTYPE = {1: "A", 2: "NS", 5: "CNAME", 12: "PTR", 15: "MX", 16: "TXT",
         28: "AAAA", 33: "SRV", 65: "HTTPS", 64: "SVCB"}


def qname(pkt: bytes) -> tuple[str, str]:
    """從 DNS 查詢解出 (name, qtype)。解不出來就回原樣 hex 的前 40 字元。"""
    try:
        i, parts = 12, []
        while pkt[i]:
            n = pkt[i]
            parts.append(pkt[i + 1:i + 1 + n].decode("latin-1"))
            i += n + 1
        qt = int.from_bytes(pkt[i + 1:i + 3], "big")
        return ".".join(parts), QTYPE.get(qt, str(qt))
    except Exception:                                            # noqa: BLE001
        return f"<unparsed:{pkt[:20].hex()}>", "?"


def main() -> int:
    srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(LISTEN)
    f = open(OUT, "a", encoding="utf-8")
    print(f"dnslog up {LISTEN} -> {UPSTREAM}, log={OUT}", flush=True)
    while True:
        try:
            pkt, peer = srv.recvfrom(4096)
        except Exception as exc:                                 # noqa: BLE001
            print("recv fail", exc, flush=True)
            continue
        name, qt = qname(pkt)
        rec = {"ts": round(time.time(), 3), "name": name, "qtype": qt,
               "from": f"{peer[0]}:{peer[1]}", "bytes": len(pkt)}
        try:
            up = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            up.settimeout(5)
            up.sendto(pkt, UPSTREAM)
            ans, _ = up.recvfrom(4096)
            up.close()
            srv.sendto(ans, peer)
            rec["forwarded"] = True
            rec["answer_bytes"] = len(ans)
        except Exception as exc:                                 # noqa: BLE001
            rec["forwarded"] = False
            rec["error"] = f"{type(exc).__name__}: {exc}"
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        f.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
