"""twin/probe_twin_enclosure — **pi 這個行程本身**被圍住了嗎（不是「模型叫得到哪些工具」）。

## 這支在架構裡承重什麼

`probe_pi_tools.py` 量的是「模型叫不叫得到 bash／越界讀寫」——它的射程寫明了
**不是** pi 行程的 OS 權限（裁決 `DECISION_20260924_TWIN_AGENT_RUN.md` §三 1）。
這一支補那一半：在 VM 上把分身那一跑放進圍牆（`twinenclose.py`），然後**站在
pi 的位置**（launcher 的子行程、同一個 namespace、同一份環境）去試每一條別的路。

「站在 pi 的位置」的做法：把 agent 命令換成本檔的 `--agent` 模式。launcher 起它的方式、
它拿到的環境變數、它所在的 netns／mount ns 跟 pi **完全相同**（argv 前綴是唯一的差別）。
namespace 是行程層級的性質，換成 node 量到的是同一件事。

## 三格（**負控制先跑**）

| 格 | 怎麼跑 | 預期 |
|---|---|---|
| `negctl` | `launcher.run`（**不圍**，現行 1003／舊路徑） | 每一條別的路都**通**；收據 tier `C` |
| `enc` | `twinenclose.run_enclosed`（產品路徑） | 別的路**全斷**、門（經過 Vacant）**通**；tier `B`；`door_excess=0` |
| `enc_bypass` | 同上，但探針**繞過 launcher 的 proxy 直接敲門** | 那一通在門的 journal 裡、不在收據裡 ⇒ `door_excess=1` ⇒ `build_twin` 判 `door_unreconciled` |

負控制量得到「做得到」，`enc` 那一欄的「做不到」才算數。

## 探的路（每一條在 `negctl` 都要通，否則那一條量具說謊，整份不收）

1. `tcp_upstream_direct`：直接連模型上游（**繞過 Vacant**）
2. `tcp_internet`：1.1.1.1:443
3. `dns`：解析 example.com
4. `tcp_host_loopback`：主機 loopback 上一個我們開的埠（展場的 8899／8901 就住在這一層）
5. `unix_host_path`：主機 `/tmp` 底下一個我們開的路徑型 unix socket（**要 mount ns 才擋得住**）
6. `read_other_twin`：另一位分身的 `TRAITS.md`（canary）
7. `read_store`：twinstore 那個 sqlite 的位置（canary）
8. `read_home`：`$HOME` 以外的使用者家目錄檔（`/home/<user>/.bashrc` 或 canary）
9. `write_outside`：在 work_root 寫一個檔（**判準是主機側那個檔有沒有出現**：圍牆裡的
   `/var/tmp` 是私有 tmpfs，寫得進去不代表寫到了主機）
10. `model_via_vacant`（**正控制**）：`GET $VACANT_RUN_PROXY/v1/models` ⇒ 200
11. `write_own_ws`（**正控制**）：寫自己的工作區

⚠ 誠實邊界：
* 量的是**這一跑**的圍牆（級別是一跑的屬性，不是 pi 的）。
* 圍牆**外面**（loop、serve_twin）什麼都連得到；這一支一個字都沒改變那件事。
* 上游是本檔自己開的假 server（零模型、零 GPU）。

用法（VM 上，要有 pi 在 PATH 上——圍牆要綁 node 的目錄）：
    python3 ops/exhibit/twin/probe_twin_enclosure.py --out <證據目錄>
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import socket
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = pathlib.Path(__file__).resolve()
TWIN = HERE.parent
REPO = TWIN.parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

CANARY = "VACANT-ENCLOSURE-CANARY-7f3a"
TARGETS = ("tcp_upstream_direct", "tcp_internet", "dns", "tcp_host_loopback",
           "unix_host_path", "read_other_twin", "read_store", "read_home",
           "write_outside", "model_via_vacant", "write_own_ws")
#: 圍牆裡**應該通**的（正控制）。其餘在圍牆裡都應該斷。
POSITIVE = ("model_via_vacant", "write_own_ws")


# ---------------------------------------------------------------------------
# agent 模式：站在 pi 的位置試每一條路（只用 stdlib，圍牆裡跑）
# ---------------------------------------------------------------------------

def _try(fn) -> dict:
    try:
        detail = fn()
        return {"reached": True, "detail": str(detail)[:200]}
    except Exception as e:                                   # noqa: BLE001
        return {"reached": False, "detail": f"{type(e).__name__}: {e}"[:200]}


def agent_main(run_dir: str) -> int:              # pragma: no cover - 在 launcher 底下跑
    plan = json.loads(os.environ.get("VACANT_PROBE_PLAN") or "{}")
    if not plan:
        # launcher 不一定原樣傳環境；退而求其次讀 run-dir 旁邊的計畫檔
        pp = pathlib.Path(run_dir) / "_probe_plan.json"
        plan = json.loads(pp.read_text("utf-8"))
    up_host, up_port = plan["upstream_host"], plan["upstream_port"]

    def tcp(host, port):
        s = socket.create_connection((host, port), 3)
        s.close()
        return "connected"

    def unix(path):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(3)
        s.connect(path)
        s.close()
        return "connected"

    def read(path):
        b = pathlib.Path(path).read_bytes()
        return "read:" + ("CANARY" if CANARY.encode() in b else f"{len(b)}B")

    def write(path):
        pathlib.Path(path).write_text("x", encoding="utf-8")
        return "wrote"

    def model():
        url = os.environ["VACANT_RUN_PROXY"].rstrip("/") + "/v1/models"
        with urllib.request.urlopen(url, timeout=10) as r:
            return f"HTTP {r.status}"

    out = {
        "tcp_upstream_direct": _try(lambda: tcp(up_host, up_port)),
        "tcp_internet": _try(lambda: tcp("1.1.1.1", 443)),
        "dns": _try(lambda: socket.getaddrinfo("example.com", 80)[0][4]),
        "tcp_host_loopback": _try(lambda: tcp("127.0.0.1", plan["host_tcp_port"])),
        "unix_host_path": _try(lambda: unix(plan["host_unix_sock"])),
        "read_other_twin": _try(lambda: read(plan["other_twin_traits"])),
        "read_store": _try(lambda: read(plan["store_path"])),
        "read_home": _try(lambda: read(plan["home_file"])),
        "write_outside": _try(lambda: write(plan["outside_write"])),
        "model_via_vacant": _try(model),
        "write_own_ws": _try(lambda: write(os.path.join(os.getcwd(), "PROBE_OK.txt"))),
    }
    if plan.get("bypass_door"):
        # 繞過 launcher 的 proxy、直接敲門（`/run/vacant/relay.sock`）——
        # 門會記下這一通，而收據不會 ⇒ 主機側對帳要抓到它。
        def door():
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect("/run/vacant/relay.sock")
            s.sendall(b"GET /v1/models HTTP/1.1\r\nHost: door\r\nConnection: close\r\n\r\n")
            data = s.recv(200)
            s.close()
            return data.split(b"\r\n", 1)[0].decode("latin-1")
        out["bypass_door_direct"] = _try(door)
    out["_ns"] = {"net": os.readlink("/proc/self/ns/net"),
                  "mnt": os.readlink("/proc/self/ns/mnt"),
                  "interfaces": [n for _, n in socket.if_nameindex()],
                  "pid": os.getpid()}
    (pathlib.Path(run_dir) / "probe_result.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


# ---------------------------------------------------------------------------
# 主機側：佈置 canary、開假上游與兩個主機監聽，跑三格
# ---------------------------------------------------------------------------

class _Up(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):                                        # noqa: N802
        body = b'{"object":"list","data":[{"id":"probe-model"}]}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _serve_tcp() -> tuple[socket.socket, int]:
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", 0))
    s.listen(16)

    def loop():
        while True:
            try:
                c, _ = s.accept()
                c.close()
            except OSError:
                return
    threading.Thread(target=loop, daemon=True).start()
    return s, s.getsockname()[1]


def _serve_unix(path: str) -> socket.socket:
    if os.path.exists(path):
        os.unlink(path)
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.bind(path)
    s.listen(16)

    def loop():
        while True:
            try:
                c, _ = s.accept()
                c.close()
            except OSError:
                return
    threading.Thread(target=loop, daemon=True).start()
    return s


def run_probe(base: pathlib.Path) -> dict:
    from ops.exhibit.twin import twinagent, twinenclose
    from vacant_network.vrun import launcher
    from vacant_network.vrun import verify_receipts as vrr

    ok, why = twinenclose.available(force=True)
    if not ok:
        return {"enclosure_available": False, "why": why}
    base.mkdir(parents=True, exist_ok=True)
    work_root = base / "twinstore.agentruns"
    other = work_root / "ws" / ("0" * 32)
    other.mkdir(parents=True, exist_ok=True)
    (other / "TRAITS.md").write_text(f"另一位分身的特質 {CANARY}\n", encoding="utf-8")
    store = base / "twinstore.sqlite3"
    store.write_text(f"sqlite canary {CANARY}\n", encoding="utf-8")
    home_file = pathlib.Path.home() / ".bashrc"
    if not home_file.is_file():
        home_file = base / "home_canary.txt"
        home_file.write_text(CANARY, encoding="utf-8")

    up = ThreadingHTTPServer(("0.0.0.0", 0), _Up)
    threading.Thread(target=up.serve_forever, daemon=True).start()
    # 上游位址要用**非 loopback** 的那一張（圍牆裡的 loopback 是另一個 netns）
    host_ip = None
    for fam, _, _, _, sa in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
        if not sa[0].startswith("127."):
            host_ip = sa[0]
            break
    if host_ip is None:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("192.168.76.1", 9))
            host_ip = s.getsockname()[0]
        finally:
            s.close()
    up_port = up.server_address[1]
    endpoint = f"http://{host_ip}:{up_port}/v1"
    tcp_sock, tcp_port = _serve_tcp()
    unix_path = f"/tmp/vacant_probe_{os.getpid()}.sock"
    unix_sock = _serve_unix(unix_path)
    os.environ["VACANT_RUN_UPSTREAM_OPENAI"] = endpoint

    report: dict = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "host_ip": host_ip, "upstream": endpoint,
                    "enc_sh": str(twinenclose.ENC_SH), "cells": {}}

    def plan_for(cell: str, bypass: bool) -> dict:
        return {"upstream_host": host_ip, "upstream_port": up_port,
                "host_tcp_port": tcp_port, "host_unix_sock": unix_path,
                "other_twin_traits": str(other / "TRAITS.md"),
                "store_path": str(store), "home_file": str(home_file),
                "outside_write": str(work_root / f"ESCAPED_{cell}.txt"),
                "bypass_door": bypass}

    def cell(name: str, enclosed: bool, bypass: bool = False) -> dict:
        sid = f"PROBE-{name}"
        ws, rd = twinagent.paths_for(work_root, sid)
        for d in (ws, rd):
            if d.exists():
                shutil.rmtree(d)
        ws.mkdir(parents=True)
        rd.mkdir(parents=True)
        (ws / "TRAITS.md").write_text("probe\n", encoding="utf-8")
        (rd / "_probe_plan.json").write_text(json.dumps(plan_for(name, bypass)),
                                             encoding="utf-8")
        argv = [("/usr/bin/python3" if enclosed else sys.executable), str(HERE),
                "--agent", str(rd)]
        tid = twinagent.public_twin_id(sid)
        caller = {"cell_id": tid, "resident": "probe", "stratum": "twin",
                  "prompt": twinagent.CALLER_PROMPT, "declared_evidence": ""}
        t0 = time.time()
        if enclosed:
            summ = twinenclose.run_enclosed(
                argv=argv, workspace=ws, run_dir=rd,
                door_dir=twinenclose.door_dir_for(work_root, twinagent.slug_for(sid)),
                task_id=f"twin:{tid}", timeout_s=60, events_path=None,
                events_caller=caller, endpoint=endpoint, model="probe-model",
                pi_bin=os.environ.get("VACANT_TWIN_PI") or "pi")
        else:
            summ = launcher.run(argv, workspace=ws, run_dir=rd, suite_dir=None,
                                vacant_on=True, allow_no_suite=True,
                                task_id=f"twin:{tid}", timeout_s=60,
                                capture_agent_stdout=True)
        res_p = rd / "probe_result.json"
        got = json.loads(res_p.read_text("utf-8")) if res_p.is_file() else None
        att = summ.get("attestation") or {}
        return {"enclosed": enclosed, "bypass": bypass,
                "wall_s": round(time.time() - t0, 2),
                "probe": got,
                "requests_seen": summ.get("requests_seen"),
                "tier": att.get("tier"),
                "enclosure_applied": (att.get("enclosure") or {}).get("applied"),
                "ns_differs_from_outer": ((att.get("enclosure") or {}).get("probe") or {})
                .get("ns_differs_from_outer"),
                "twin_enclosure": summ.get("twin_enclosure"),
                "receipt_verdicts": [r.get("verdict") for r in vrr.verify_run(rd)],
                "escaped_file_exists": (work_root / f"ESCAPED_{name}.txt").exists()}

    try:
        # ⚠ **負控制先跑**：它通，圍牆那一欄的「斷」才算數。
        report["cells"]["negctl"] = cell("negctl", enclosed=False)
        report["cells"]["enc"] = cell("enc", enclosed=True)
        report["cells"]["enc_bypass"] = cell("enc_bypass", enclosed=True, bypass=True)
    finally:
        up.shutdown()
        tcp_sock.close()
        unix_sock.close()
        try:
            os.unlink(unix_path)
        except OSError:
            pass
    report["judgement"] = judge(report["cells"])
    return report


def judge(cells: dict) -> dict:
    """判準全部從落盤的結果讀。`mismatched` 是總紅燈數，0 才算過。"""
    rows, bad = [], 0

    def reached(c, t):
        if t == "write_outside":
            # ⚠ 圍牆裡 `/var/tmp` 是私有 tmpfs：bwrap 為了掛 ws／run-dir 會在裡面建出
            #   空的中間目錄，所以「寫得進去」在圍牆裡可能是真的——寫進的是**圍牆自己的
            #   tmpfs**。判準改成主機側看那個檔有沒有出現（2026-09-24 設計時就預期到）。
            return (cells.get(c) or {}).get("escaped_file_exists")
        return (((cells.get(c) or {}).get("probe") or {}).get(t) or {}).get("reached")

    for t in TARGETS:
        neg, enc = reached("negctl", t), reached("enc", t)
        want_enc = t in POSITIVE
        ok = (neg is True) and (enc is want_enc)
        bad += 0 if ok else 1
        rows.append({"target": t, "negctl": neg, "enc": enc,
                     "want_negctl": True, "want_enc": want_enc, "ok": ok})
    n, e, b = cells.get("negctl") or {}, cells.get("enc") or {}, cells.get("enc_bypass") or {}
    checks = {
        "negctl_tier_C": n.get("tier") == "C",
        "enc_tier_B": e.get("tier") == "B",
        "enc_applied": e.get("enclosure_applied") is True,
        "enc_ns_differs": e.get("ns_differs_from_outer") is True,
        "enc_door_excess_0": (e.get("twin_enclosure") or {}).get("door_excess") == 0,
        "enc_receipt_OK": e.get("receipt_verdicts") == ["OK"],
        "bypass_reached_door": reached("enc_bypass", "bypass_door_direct") is True,
        "bypass_door_excess_gt0": ((b.get("twin_enclosure") or {}).get("door_excess") or 0) > 0,
        "negctl_escaped_file": n.get("escaped_file_exists") is True,
        "enc_no_escaped_file": e.get("escaped_file_exists") is False,
    }
    bad += sum(1 for v in checks.values() if not v)
    return {"targets": rows, "checks": checks, "mismatched": bad}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="pi 行程本身被圍住了嗎（負控制先跑）")
    ap.add_argument("--agent", nargs="?", const="", default=None,
                    help="（launcher 底下用）站在 pi 的位置試每一條路")
    ap.add_argument("rest", nargs="*")
    ap.add_argument("--out", default=None, help="證據目錄（寫 probe_twin_enclosure.json）")
    ap.add_argument("--workdir", default=None, help="暫存（預設 mkdtemp，跑完刪）")
    a = ap.parse_args(argv)
    if a.agent is not None:
        return agent_main(a.agent or (a.rest[0] if a.rest else "."))
    if not a.out:
        ap.error("--out 必填")
    base = pathlib.Path(a.workdir) if a.workdir else pathlib.Path(
        tempfile.mkdtemp(prefix="twin_encprobe_", dir="/var/tmp" if os.path.isdir("/var/tmp") else None))
    try:
        rep = run_probe(base)
    finally:
        if not a.workdir:
            shutil.rmtree(base, ignore_errors=True)
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "probe_twin_enclosure.json").write_text(
        json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    j = rep.get("judgement") or {}
    print(json.dumps({"mismatched": j.get("mismatched"), "checks": j.get("checks"),
                      "enclosure_available": rep.get("enclosure_available", True)},
                     ensure_ascii=False))
    return 0 if j.get("mismatched") == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
