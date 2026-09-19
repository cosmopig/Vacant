#!/usr/bin/env python3
"""這支在架構裡承重什麼：出網封鎖的**負向控制**。

`block_egress.sh` 跑完會印「已封鎖」。那句話是**它自己說的**，不是量到的。
本檔從 agent 的 uid 實際去連，把三件事分開量：

  1. **直連真上游必須失敗**（負向控制——這一條過不了，封鎖就是沒效）
  2. **連 proxy 埠必須成功**（正向控制——擋到連自己都連不上不叫封鎖，叫壞掉）
  3. **DNS 必須失敗**（`block_egress.sh` 邊界 3：放行 DNS 等於留一條外洩通道）

判準寫死在這裡，不看規則長什麼樣——**規則存在**與**規則有效**是兩件事，
只驗前者就是在驗自己的字串。`iptables -L` 的輸出另外落盤，但它是**旁證**。

⚠ 誠實邊界（改碼請保留）：本檔量的是「從我這個 uid、用 TCP connect 去打這幾個
  位址會怎樣」。它**不**證明沒有別的出口（IPv6、既有的長連線、透過另一個 uid
  的服務代發、raw socket）。它是一條會紅的擋門，不是一份完整的出口清單。
  IPv6 另外量一次（`--upstream6`），量不到就在報告裡寫「沒量」，不要寫「沒有」。

用法（在 agent 的 uid 底下跑）：
    sudo -u '#1234' python3 ops/vacantrun/verify_egress_block.py \\
        --proxy-port 8899 --upstream 100.119.113.56:1234 --json out.json

退出碼：0＝三條都如預期；1＝有任何一條不如預期（**封鎖不可信**）。
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import time


def _connect(host: str, port: int, timeout: float) -> dict:
    t0 = time.time()
    try:
        s = socket.create_connection((host, port), timeout)
        s.close()
        return {"reached": True, "error": None,
                "elapsed_s": round(time.time() - t0, 3)}
    except Exception as exc:                                 # noqa: BLE001
        return {"reached": False, "error": f"{type(exc).__name__}: {exc}",
                "elapsed_s": round(time.time() - t0, 3)}


def _dns(name: str, timeout: float) -> dict:
    t0 = time.time()
    socket.setdefaulttimeout(timeout)
    try:
        return {"reached": True, "addr": socket.gethostbyname(name),
                "error": None, "elapsed_s": round(time.time() - t0, 3)}
    except Exception as exc:                                 # noqa: BLE001
        return {"reached": False, "addr": None,
                "error": f"{type(exc).__name__}: {exc}",
                "elapsed_s": round(time.time() - t0, 3)}


def main() -> int:
    ap = argparse.ArgumentParser(description="出網封鎖的負向控制（要在 agent 的 uid 下跑）")
    ap.add_argument("--proxy-port", type=int, required=True)
    ap.add_argument("--proxy-host", default="127.0.0.1")
    ap.add_argument("--upstream", required=True,
                    help="真上游 host:port——封鎖之後**必須連不上**")
    ap.add_argument("--upstream6", default=None, help="IPv6 的真上游（選填）")
    ap.add_argument("--dns-name", default="api.openai.com")
    ap.add_argument("--timeout", type=float, default=5.0)
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    host, _, port = args.upstream.rpartition(":")
    checks = {
        "negative_control_direct_upstream": _connect(host, int(port), args.timeout),
        "positive_control_proxy_port": _connect(args.proxy_host, args.proxy_port,
                                                args.timeout),
        "negative_control_dns": _dns(args.dns_name, args.timeout),
    }
    if args.upstream6:
        h6, _, p6 = args.upstream6.rpartition(":")
        checks["negative_control_direct_upstream_ipv6"] = _connect(h6, int(p6),
                                                                   args.timeout)
    #: 每一條的**期望**。判準寫死在這裡，不看 iptables 規則長什麼樣。
    expect = {"negative_control_direct_upstream": False,
              "negative_control_direct_upstream_ipv6": False,
              "positive_control_proxy_port": True,
              "negative_control_dns": False}

    fails = [k for k, v in checks.items() if v["reached"] is not expect[k]]
    try:
        rules = subprocess.run(["iptables", "-S", "OUTPUT"], capture_output=True,
                               text=True, timeout=10).stdout
    except Exception as exc:                                 # noqa: BLE001
        rules = f"<拿不到：{exc!r}>"      # 拿不到也要記下拿不到

    out = {
        "uid": os.getuid(), "euid": os.geteuid(),
        "proxy": f"{args.proxy_host}:{args.proxy_port}",
        "upstream": args.upstream, "checks": checks, "expect": expect,
        "failed": fails,
        "verdict": "BLOCKED" if not fails else "NOT_BLOCKED",
        "note": ("`verdict=BLOCKED` 只代表這三（四）條如預期。它不證明沒有別的"
                 "出口（既有長連線、其他 uid 代發、raw socket）——見本檔 docstring。"
                 "`iptables_S` 是旁證，不是判準。"),
        "iptables_S": rules,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
