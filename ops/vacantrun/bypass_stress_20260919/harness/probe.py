#!/usr/bin/env python3
"""出網封鎖的量具（比 verify_egress_block.py 寬）：一次量一整排出口。

判準是「擋得住」不是「設定了」：每一格都實際建連線／發封包，落盤原始錯誤字串。
同一支在**封鎖前**與**封鎖後**各跑一次；封鎖前那一次就是負向控制
（「本來就連不出去」與「被擋住」在這裡分得開）。
"""
from __future__ import annotations
import json, os, socket, ssl, struct, subprocess, sys, time

TIMEOUT = 6.0
T4_1004 = ("100.86.226.21", 1234)          # 本地模型端點（tailnet IPv4）
T6_1004 = ("fd7a:115c:a1e0::6135:e216", 1234)   # 同一台的 tailnet IPv6
T4_LIT  = ("1.1.1.1", 443)                 # 公網 IP 字面值（不經 DNS）
# ⚠ **V3 沒量到的那一格**：IPv6 上的 TCP 出網。V3 只有 `tcp6_tailnet_1004`
#   （1004 的 :1234），而那個埠**本來就沒在 v6 上聽** ⇒ 封鎖前後都 timeout，
#   量到的是「沒有服務」不是「有沒有被擋」。2026-09-19 找到兩個**封鎖前就連得上**
#   的 v6 TCP 目標（tailnet 上的 sshd，只讀 banner、不認證、不碰任何憑證），
#   於是「IPv6 TCP 出網會不會被擋」第一次有了真正的負向控制。
T6_SSH_LINUX = ("fd7a:115c:a1e0::4335:3667", 22)   # tailnet peer `user1`（Linux）
T6_SSH_1004  = ("fd7a:115c:a1e0::6135:e216", 22)   # 1004 本人（Windows sshd）
OPENROUTER = ("openrouter.ai", 443)        # Hermes 編死的第三方


def _t(fn, *a, **kw):
    t0 = time.time()
    try:
        v = fn(*a, **kw)
        return {"ok": True, "value": v, "error": None,
                "elapsed_s": round(time.time() - t0, 3)}
    except Exception as e:                                   # noqa: BLE001
        return {"ok": False, "value": None,
                "error": f"{type(e).__name__}: {e}",
                "elapsed_s": round(time.time() - t0, 3)}


def tcp(host, port, family=socket.AF_INET):
    ai = socket.getaddrinfo(host, port, family, socket.SOCK_STREAM)[0]
    s = socket.socket(ai[0], ai[1])
    s.settimeout(TIMEOUT)
    s.connect(ai[4])
    peer = s.getpeername()
    s.close()
    return f"connected {peer}"


def tcp6_banner(host, port):
    """IPv6 TCP 出網：連上去、讀第一行 banner 就關。**不認證、不送任何東西。**"""
    s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    s.settimeout(TIMEOUT)
    s.connect((host, port, 0, 0))
    b = s.recv(60)
    s.close()
    return f"connected v6, banner={b[:40]!r}"


def https_get(host, port, path, sni=None, connect_to=None):
    ctx = ssl.create_default_context()
    tgt = connect_to or (host, port)
    raw = socket.create_connection(tgt, TIMEOUT)
    s = ctx.wrap_socket(raw, server_hostname=sni or host)
    s.settimeout(TIMEOUT)
    s.sendall(f"GET {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n"
              f"User-Agent: vacant-v3-probe\r\n\r\n".encode())
    buf = s.recv(200)
    s.close()
    return buf.decode("latin-1").splitlines()[0]


def dns_resolver():
    return socket.gethostbyname("api.openai.com")


def dns_udp_direct(server="8.8.8.8"):
    q = (struct.pack(">HHHHHH", 0x1234, 0x0100, 1, 0, 0, 0)
         + b"\x03api\x06openai\x03com\x00" + struct.pack(">HH", 1, 1))
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(TIMEOUT)
    s.sendto(q, (server, 53))
    d, _ = s.recvfrom(512)
    s.close()
    return f"answer {len(d)} bytes"


def icmp_ping(target="1.1.1.1", v6=False):
    r = subprocess.run(["ping"] + (["-6"] if v6 else []) + ["-c", "1", "-W", "3", target],
                       capture_output=True, text=True, timeout=10)
    return f"rc={r.returncode} {r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ''}"


def main():
    relay_port = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    proxy_port = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    out = {"uid": os.getuid(), "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "probes": {}}
    p = out["probes"]
    p["tcp4_tailnet_1004"]        = _t(tcp, *T4_1004)
    p["tcp6_tailnet_1004"]        = _t(tcp, T6_1004[0], T6_1004[1], socket.AF_INET6)
    p["tcp6_ssh_linux_peer"]      = _t(tcp6_banner, *T6_SSH_LINUX)
    p["tcp6_ssh_1004"]            = _t(tcp6_banner, *T6_SSH_1004)
    p["tcp4_public_ip_literal"]   = _t(tcp, *T4_LIT)
    p["tcp4_openrouter_dns"]      = _t(tcp, *OPENROUTER)
    p["https_openrouter_models"]  = _t(https_get, "openrouter.ai", 443,
                                       "/api/v1/models")
    p["dns_via_systemd_resolved"] = _t(dns_resolver)
    p["dns_udp_direct_8888"]      = _t(dns_udp_direct)
    p["icmp_ping_1111"]           = _t(icmp_ping)
    p["icmp6_ping_tailnet_1004"]  = _t(icmp_ping, T6_1004[0], True)
    if proxy_port:
        p["proxy_port_loopback"]  = _t(tcp, "127.0.0.1", proxy_port)
    if relay_port:
        p["loopback_relay_to_openrouter"] = _t(
            https_get, "openrouter.ai", 443, "/api/v1/models",
            sni="openrouter.ai", connect_to=("127.0.0.1", relay_port))
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
