#!/usr/bin/env python3
"""這支在架構裡承重什麼：把「這一跑有沒有東西繞過中介」做成收據上的**一個數字**。

## 為什麼需要它（2026-09-19，V3 撞出來的洞）

V3（`ops/vacantrun/egress_v3_20260919/`）量到一件事：同一個洩漏情境
（Hermes 漏設 `CUSTOM_BASE_URL`，跑去打它編死的 openrouter），
**封鎖開與關兩跑的 `run_RUN-ON.json` 有 26 個判斷欄位逐字相同**
（`accepted`／`stop_reason`／`requests_seen`／`agent_rc`／`wire_by_protocol`／
`ws_end_sha256`／`refused`／`infra_void` 全部一樣）。
⇒ **世界變了，收據沒變。**

而 V3 同時留下一個現成的量具：那一跑的 REJECT 規則上有 **73 個封包**的計數。
`iptables` 自己一直在數，只是沒有人把那個數字寫進收據。本檔就是把它寫進去。

## 判準（`ops/vacantrun/bypass_stress_20260919/` 實測，見同目錄 data/）

| 情境 | `off_mediation_packets` | 意思 |
|---|---|---|
| 正常跑（接線正確） | **0** | 這一跑所有出網都走了 proxy |
| Hermes 漏設 `CUSTOM_BASE_URL` | **> 0** | 有東西走了中介以外的路 |
| 沒裝刻度（`egress_gauge.sh` 沒套用） | **`null`** | **沒量到，不是量到 0** |

第三列是鐵律 3 的直接後果，也是本檔最容易被改壞的地方：
`available=False` 的時候所有計數欄位一律 `None`，**不准填 0**。
`0` 是一個有內容的觀測（「我量了，沒有」），`null` 是「我沒量」。
兩者在資料上同形的那一刻，這個欄位就不再是證據。

## 誠實邊界（改碼請保留）

1. **這不是「擋住了」。** Saltzer & Schroeder 的 complete mediation 要求每一次
   存取都必經中介點，而 agent 與 proxy 跑在**同一台機器、同一個使用者**底下。
   `vacant_network/controller.py:7-8` 與 `wireproxy` 的模組 docstring 都寫著同一條邊界。
   本檔做的是**可究責性**：繞過時留下痕跡，不是讓繞過不可能。
2. **unix domain socket 不經 netfilter ⇒ 本檔對那條路是瞎的**（V3 實測：
   0.038 秒 200 OK，`iptables` 計數器一個封包都沒動）。
   數字是 0 的時候能說的是「**我數得到的那些路**上沒有封包」。
3. 計數器是**那條 chain 的**，不是那一跑的。前後各讀一次相減才是這一跑的；
   相減期間有別的行程用同一個 uid，它的封包會混進來。**一跑一專屬 uid** 才乾淨。
4. `dns_*`／`loopback_*` 兩個桶子 > 0 **不等於**被繞過了，等於**繞得過**：
   同機另一個 uid 的 listener 走的就是迴圈那條（`block_egress.sh` 規則 1
   `-o lo -j ACCEPT` 放行整條迴圈）。數字要人去看，不是自動判罪。
5. 讀計數器要 root。拿不到 root ⇒ `available=False` ＋ `reason`，
   **不是** `packets=0`。

## 怎麼接進 `vacant run`

`launcher.run()` 裡兩行（`ops/vacantrun/bypass_stress_20260919/README.md`
的「要改 `vacant_network/` 的清單」有逐字 diff）：

    gauge_before = egress_counter.snapshot()          # proxy.start() 之後
    ...
    summary["egress_gauge"] = egress_counter.delta(gauge_before,
                                                   egress_counter.snapshot())
"""
from __future__ import annotations

import json
import shutil
import subprocess
import time

#: chain 名字與 `egress_gauge.sh` 寫死的那兩個**必須一致**。
#: 這裡是唯一一份（腳本裡那份是 shell 變數，改一邊就會漂——所以
#: `read_counters.py --check` 會把兩邊對起來比）。
CHAIN_V4 = "VACANT_EG"
CHAIN_V6 = "VACANT_EG6"

#: 規則順序 → 語意。**順序就是 `egress_gauge.sh` 裡 `-A` 的順序**，
#: 靠位置對應，所以兩邊改動必須成對。
LABELS_V4: tuple[str, ...] = (
    "mediated_proxy",    # 1 被中介的那條路（proxy 埠）
    "dns_any",           # 2 任何 DNS 查詢（53/udp）
    "dns_redirected",    # 3 被導到名稱記錄器的 DNS
    "loopback_other",    # 4 迴圈上不是 proxy 的東西
    "lo_other",          # 5 其餘走 lo 的
    "udp_offbox",        # 6 出機器的 UDP（QUIC…）
    "offbox",            # 7 出機器的 TCP／ICMP／raw ← 頭條
)
LABELS_V6: tuple[str, ...] = (
    "mediated_proxy", "dns_any", "loopback_other", "lo_other",
    "udp_offbox", "offbox",
)

#: 哪些桶子算「走了中介以外的路」。`mediated_proxy` 以外全部算。
#: 分三層是因為它們的意思不同（邊界 4）：離開機器的、留在機器上的。
OFFBOX_BUCKETS = ("udp_offbox", "offbox")
ONBOX_OTHER_BUCKETS = ("dns_any", "dns_redirected", "loopback_other", "lo_other")


def _run(argv: list[str], timeout: float = 10.0) -> tuple[int, str, str]:
    p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def _iptables_argv(chain: str, *, ip6: bool, sudo: bool) -> list[str]:
    exe = "ip6tables" if ip6 else "iptables"
    argv = [exe, "-xnvL", chain]
    return (["sudo", "-n"] + argv) if sudo else argv


def read_chain(chain: str, labels: tuple[str, ...], *, ip6: bool = False,
               sudo: bool = True) -> dict:
    """讀一條 chain 的計數器。**chain 不存在 ⇒ `available=False`，不是 0。**"""
    exe = "ip6tables" if ip6 else "iptables"
    if shutil.which(exe) is None and shutil.which("sudo") is None:
        return {"available": False, "reason": f"{exe} 不在 PATH 上"}
    try:
        rc, out, err = _run(_iptables_argv(chain, ip6=ip6, sudo=sudo))
    except Exception as exc:                                     # noqa: BLE001
        return {"available": False, "reason": f"{type(exc).__name__}: {exc}"}
    if rc != 0:
        # chain 不存在、沒有 root、核心模組沒載入——**三種都不是 0**。
        return {"available": False, "reason": (err or out).strip()[:300], "rc": rc}
    pkts: dict[str, int] = {}
    byts: dict[str, int] = {}
    i = 0
    for line in out.splitlines():
        f = line.split()
        if len(f) < 3 or not f[0].isdigit() or not f[1].isdigit():
            continue           # 標頭兩行（`Chain …` 與欄位名）跳掉
        if i < len(labels):
            pkts[labels[i]] = int(f[0])
            byts[labels[i]] = int(f[1])
        i += 1
    if i != len(labels):
        # 規則數對不上標籤數 ⇒ **不要猜**。標籤是靠位置對應的，
        # 對不上就代表這條 chain 不是我們裝的那一條。
        return {"available": False,
                "reason": f"規則數 {i} ≠ 標籤數 {len(labels)}（chain 不是本工具裝的？）"}
    return {"available": True, "chain": chain, "packets": pkts, "bytes": byts}


def snapshot(*, sudo: bool = True) -> dict:
    """前後各讀一次用的那一次。**兩條 chain 都讀**（v4 ＋ v6）。"""
    return {
        "ts": time.time(),
        "v4": read_chain(CHAIN_V4, LABELS_V4, ip6=False, sudo=sudo),
        "v6": read_chain(CHAIN_V6, LABELS_V6, ip6=True, sudo=sudo),
    }


def _sub(after: dict, before: dict, labels: tuple[str, ...]) -> dict:
    if not (after.get("available") and before.get("available")):
        reason = after.get("reason") or before.get("reason") or "沒有可用的計數器"
        return {"available": False, "reason": reason,
                "packets": None, "bytes": None}
    return {"available": True, "chain": after.get("chain"),
            "packets": {k: after["packets"][k] - before["packets"][k] for k in labels},
            "bytes": {k: after["bytes"][k] - before["bytes"][k] for k in labels}}


def delta(before: dict | None, after: dict | None) -> dict:
    """兩個 snapshot 相減，組出**要寫進收據的那一格**。

    回傳的形狀**凍結**（收據欄位，改了會讓既有資料失去可比性）：

        {"available": bool,
         "reason": str|None,                       # available=False 時為什麼
         "off_mediation_packets": int|None,        # 頭條。**null ≠ 0**
         "offbox_packets": int|None,               # 離開機器的
         "onbox_other_packets": int|None,          # 留在機器上、不經 proxy 的
         "mediated_packets": int|None,             # 走 proxy 的（正向控制）
         "v4": {...}, "v6": {...},                 # 逐桶原始差值
         "blind_to": [...], "note": str}
    """
    blind = ["unix_domain_socket（不經 netfilter，V3 實測 0.038s 200 OK）",
             "已送出的位元組（計數器只說有，收不回來）",
             "內容（這是封包計數不是內容擷取）"]
    note = ("`off_mediation_packets` 是**可究責性**的欄位不是防護的欄位："
            "它說得出「有東西走了中介以外的路」，說不出「沒有路可以走」。"
            "`null` ＝ 沒裝刻度 ⇒ **沒量到，不是量到 0**。")
    if before is None or after is None:
        return {"available": False, "reason": "沒有前／後 snapshot",
                "off_mediation_packets": None, "offbox_packets": None,
                "onbox_other_packets": None, "mediated_packets": None,
                "v4": None, "v6": None, "blind_to": blind, "note": note}
    d4 = _sub(after["v4"], before["v4"], LABELS_V4)
    d6 = _sub(after["v6"], before["v6"], LABELS_V6)
    if not (d4["available"] or d6["available"]):
        return {"available": False,
                "reason": d4.get("reason") or d6.get("reason"),
                "off_mediation_packets": None, "offbox_packets": None,
                "onbox_other_packets": None, "mediated_packets": None,
                "v4": d4, "v6": d6, "blind_to": blind, "note": note}

    def _sum(d: dict, buckets) -> int:
        if not d.get("available"):
            return 0
        return sum(d["packets"].get(b, 0) for b in buckets)

    offbox = _sum(d4, OFFBOX_BUCKETS) + _sum(d6, OFFBOX_BUCKETS)
    onbox = _sum(d4, ONBOX_OTHER_BUCKETS) + _sum(d6, ONBOX_OTHER_BUCKETS)
    mediated = _sum(d4, ("mediated_proxy",)) + _sum(d6, ("mediated_proxy",))
    return {"available": True,
            "reason": None if (d4["available"] and d6["available"]) else
                      f"只有一半可用：v4={d4['available']} v6={d6['available']}",
            "off_mediation_packets": offbox + onbox,
            "offbox_packets": offbox,
            "onbox_other_packets": onbox,
            "mediated_packets": mediated,
            "v4": d4, "v6": d6, "blind_to": blind, "note": note}


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="讀／相減 egress 刻度計數器")
    ap.add_argument("--snapshot", action="store_true", help="印一次 snapshot")
    ap.add_argument("--before", help="before snapshot 的 json 檔")
    ap.add_argument("--after", help="after snapshot 的 json 檔")
    ap.add_argument("--no-sudo", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.snapshot:
        out = snapshot(sudo=not a.no_sudo)
    else:
        b = json.load(open(a.before, encoding="utf-8")) if a.before else None
        f = json.load(open(a.after, encoding="utf-8")) if a.after else None
        out = delta(b, f)
    s = json.dumps(out, ensure_ascii=False, indent=2)
    print(s)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
