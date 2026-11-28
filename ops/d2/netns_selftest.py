#!/usr/bin/env python3
"""網路隔離沙箱的自我測試（2026-11-28；附錄 B 補充 B13 要求：先負控制、後正控制，逐項記指令與結果）。

在和正式批次相同的設定下起一套最小環境：來源伺服器（兩個主機：本格自己的、別組的）＋ Vacant 出口代理（同一個 venv）＋
外面帶白名單的 unix socket 轉送器，再用 `bwrap_expT_agent.sh`（EXPT_NETNS_PROXY_PORT 有值 ⇒ --unshare-net）在沙箱裡逐項測試。
模型端點用 cfg 的 models.json 裡第一個 LM Studio 端點（執行時讀；報告裡的 IP 一律遮成 <lms>）。
全部項目都符合預期才回 0。輸出：--out 指定的 JSON（逐項：名稱、指令、預期、實際、是否通過）。
用法：netns_selftest.py --models-json <cfg/models.json> --venv <venv> --out <報告.json>
"""
from __future__ import annotations
import argparse, json, os, pathlib, re, shutil, socket, subprocess, sys, tempfile, time

HERE = pathlib.Path(__file__).resolve().parent
OWN = "selftest-s01-r1.d2-sources.example"
OTHER = "selftest-s02-r1.d2-sources.example"

INNER = r'''
import json, os, socket, subprocess, sys, urllib.request
P = os.environ["EXPT_NETNS_PROXY_PORT"]; LMS = os.environ["SELFTEST_LMS"]; OWN = os.environ["SELFTEST_OWN"]; OTHER = os.environ["SELFTEST_OTHER"]
SRC_PORT = os.environ["SELFTEST_SRC_PORT"]; LMS_H, LMS_P = LMS.rsplit(":", 1)
res = []
def sh(name, cmd, expect):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=25)
        out = (r.stdout + r.stderr)[-300:]; rc = r.returncode
    except subprocess.TimeoutExpired:
        out, rc = "timeout", "timeout"
    res.append({"name": name, "cmd": cmd, "expect": expect, "rc": rc, "out": out})
def py(name, code, expect):
    try:
        exec(code, {}); out, rc = "ok", 0
    except Exception as e:
        out, rc = f"{type(e).__name__}: {e}"[:300], 1
    res.append({"name": name, "cmd": "python: " + code.replace("\n", "; ")[:200], "expect": expect, "rc": rc, "out": out})
def raw(name, reqs, expect):
    """同一條連線上依序送多個請求，記錄每個請求有沒有拿到回應。"""
    s = socket.create_connection(("127.0.0.1", int(P)), timeout=10); got = []
    try:
        for q in reqs:
            try:
                s.sendall(q.encode())
                d = s.recv(4096)
            except OSError:
                d = b""
            got.append(d.split(b"\r\n", 1)[0].decode("latin-1", "replace") if d else "<closed>")
    finally:
        s.close()
    res.append({"name": name, "cmd": " | ".join(q.split("\r\n", 1)[0] for q in reqs), "expect": expect, "rc": 0, "out": " || ".join(got)})
# ---- 負控制（都要失敗）
sh("N01 curl --noproxy direct https wikipedia", "curl -sS -m 8 --noproxy '*' https://en.wikipedia.org/wiki/Main_Page -o /dev/null -w '%{http_code}'", "fail")
py("N02 python urllib direct (ignore proxy env)", "import urllib.request as u; u.build_opener(u.ProxyHandler({})).open('https://en.wikipedia.org/', timeout=8)", "fail")
sh("N03 node fetch (node ignores proxy env)", "node -e \"fetch('https://en.wikipedia.org/').then(r=>{console.log(r.status);process.exit(0)}).catch(e=>{console.log(String(e));process.exit(1)})\"", "fail")
py("N04 raw socket to an IP", "import socket; socket.create_connection(('1.1.1.1', 443), timeout=5)", "fail")
py("N05 DNS lookup", "import socket; socket.getaddrinfo('en.wikipedia.org', 443)", "fail")
py("N06 host source server port directly (127.0.0.1 is the sandbox's own)", f"import socket; socket.create_connection(('127.0.0.1', {SRC_PORT}), timeout=5)", "fail")
sh("N07 host /run is not visible", "ls -A /run 2>&1 | head -5; test ! -e /run/user && test ! -e /run/dbus && test ! -e /var/run/docker.sock", "pass_cmd")
sh("N08 host /tmp is a private tmpfs (empty)", "test -z \"$(ls -A /tmp)\"", "pass_cmd")
sh("N09 only the forwarder socket exists", "find / -xdev -type s 2>/dev/null | grep -v '^/proc' | sed 's#.*/##' | sort | tr '\\n' ' '; test \"$(find / -xdev -type s 2>/dev/null | grep -v '^/proc' | wc -l)\" -le 1", "pass_cmd")
sh("N10 curl -x proxy https wikipedia (must be 403/blocked)", f"curl -sS -m 10 -x http://127.0.0.1:{P} https://en.wikipedia.org/ -o /dev/null -w '%{{http_code}}'", "fail")
sh("N11 other set's source host via proxy", f"curl -sS -m 10 http://{OTHER}/index.html -o /dev/null -w '%{{http_code}}' | grep -qx 200", "fail")
sh("N12 LM Studio host on another port via proxy", f"curl -sS -m 10 http://{LMS_H}:22/ -o /dev/null -w '%{{http_code}}' | grep -qx 200", "fail")
sh("N13 LM Studio admin API via proxy (/api/v0/models)", f"curl -sS -m 10 http://{LMS}/api/v0/models -o /dev/null -w '%{{http_code}}' | grep -qx 200", "fail")
sh("N14 LM Studio /v1/responses via proxy", f"curl -sS -m 10 -X POST -H 'Content-Type: application/json' -d '{{}}' http://{LMS}/v1/responses -o /dev/null -w '%{{http_code}}' | grep -qx 200", "fail")
raw("N15 pipelined: allowed request + /api/v0/models in one send (2nd must be blocked)", [
    f"GET http://{OWN}/index.html HTTP/1.1\r\nHost: {OWN}\r\n\r\nGET http://{LMS}/api/v0/models HTTP/1.1\r\nHost: {LMS}\r\n\r\n"], "blocked_logged")
raw("N16 CONNECT tunnel to LM Studio, then /api/v0/ inside the tunnel", [
    f"CONNECT {LMS} HTTP/1.1\r\nHost: {LMS}\r\n\r\n",
    f"GET /api/v0/models HTTP/1.1\r\nHost: {LMS}\r\n\r\n"], "second_closed")
raw("N17 smuggling: Transfer-Encoding and Content-Length together", [
    f"POST http://{OWN}/index.html HTTP/1.1\r\nHost: {OWN}\r\nContent-Length: 4\r\nTransfer-Encoding: chunked\r\n\r\n0\r\n\r\n"], "first_closed")
raw("N18 malformed request line", ["GARBAGE\r\n\r\n"], "first_closed")
# ---- 正控制（都要成功）
sh("P01 own source host revision-0 page via env proxy", f"curl -sS -m 10 http://{OWN}/index.html | grep -q SELFTEST_OK", "pass_cmd")
sh("P02 model endpoint /v1/models via proxy CONNECT tunnel (how pi connects)", f"curl -sS -m 15 -p http://{LMS}/v1/models -o /dev/null -w '%{{http_code}}' | grep -qx 200", "pass_cmd")
raw("P03 keep-alive inside the LM Studio tunnel: two /v1/models requests", [
    f"CONNECT {LMS} HTTP/1.1\r\nHost: {LMS}\r\n\r\n",
    f"GET /v1/models HTTP/1.1\r\nHost: {LMS}\r\n\r\n",
    f"GET /v1/models HTTP/1.1\r\nHost: {LMS}\r\n\r\n"], "all_answered")
print(json.dumps(res))
'''


def free_port() -> int:
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--models-json", required=True); ap.add_argument("--venv", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    eps = re.findall(r"https?://([^/\"':]+):?(\d+)?", pathlib.Path(a.models_json).read_text())
    lms = f"{eps[0][0]}:{eps[0][1] or 80}"
    base = pathlib.Path.home() / "dev" / "ops" / "tmp_redo"; base.mkdir(parents=True, exist_ok=True)
    work = pathlib.Path(tempfile.mkdtemp(prefix="nst_", dir=str(base)))     # unix socket 路徑有 108 字元上限，放短路徑
    live = work / "live"; out = work / "out"
    for d in (live / "ws", live / "tmp", live / "vh", live / "cfg", out, work / "own", work / "other"):
        d.mkdir(parents=True)
    (work / "own" / "index.html").write_text("<html>SELFTEST_OK revision0</html>")
    (work / "own" / "page.html").write_text("<html>page2</html>")
    (work / "other" / "index.html").write_text("<html>OTHER_SET</html>")
    routes = work / "routes.json"; routes.write_text(json.dumps({OWN: str(work / "own"), OTHER: str(work / "other")}))
    sport = free_port(); procs = []
    try:
        procs.append(subprocess.Popen([sys.executable, str(HERE / "source_server.py"), "--port", str(sport), "--routes", str(routes),
                                       "--log", str(work / "access.jsonl")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        ready = work / "egress.ready"
        env = {k: v for k, v in os.environ.items() if "proxy" not in k.lower()}
        env["VACANT_HOME"] = str(live / "vh")
        procs.append(subprocess.Popen([str(pathlib.Path(a.venv) / "bin" / "python"), "-I", "-m", "vacant_network", "trace", "egress", "--port", "0",
                                       "--upstream-proxy", f"http://127.0.0.1:{sport}", "--ready-file", str(ready)],
                                      cwd=live / "ws", env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        for _ in range(100):
            if ready.exists():
                break
            time.sleep(0.1)
        eport = json.loads(ready.read_text())["port"]
        sock = live / "tmp" / "egress.sock"
        procs.append(subprocess.Popen([sys.executable, "-I", str(HERE / "sockfwd.py"), "unix2tcp", str(sock), f"127.0.0.1:{eport}",
                                       "--allow", f"{OWN}:80", "--model", lms, "--log", str(out / "net_blocked.jsonl")]))
        for _ in range(50):
            if sock.exists():
                break
            time.sleep(0.1)
        (live / "ws" / "inner.py").write_text(INNER)
        senv = dict(env)
        senv.update({"EXPT_NETNS_PROXY_PORT": str(eport), "SELFTEST_LMS": lms, "SELFTEST_OWN": OWN, "SELFTEST_OTHER": OTHER,
                     "SELFTEST_SRC_PORT": str(sport)})
        for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "all_proxy"):
            senv[k] = f"http://127.0.0.1:{eport}"
        r = subprocess.run([str(HERE / "bwrap_expT_agent.sh"), str(live), str(out), str(a.venv), "--", "python3", "-I", str(live / "ws" / "inner.py")],
                           env=senv, capture_output=True, text=True, timeout=600)
        try:
            res = json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:
            print("inner failed:", r.stdout[-500:], r.stderr[-500:]); return 2
        blocked = [json.loads(l) for l in (out / "net_blocked.jsonl").read_text().splitlines()] if (out / "net_blocked.jsonl").exists() else []
        egress = []
        for ej in (live / "vh").glob("trace/projects/*/egress.jsonl"):
            egress += [json.loads(l) for l in ej.read_text().splitlines() if l.strip()]
        ok_all = True
        for t in res:
            e, o = t["expect"], str(t["out"])
            if e == "fail":
                t["pass"] = t["rc"] != 0
            elif e == "pass_cmd":
                t["pass"] = t["rc"] == 0
            elif e == "second_closed":
                parts = o.split(" || "); t["pass"] = len(parts) == 2 and parts[1] in ("<closed>",) or (len(parts) == 2 and "403" in parts[1])
            elif e == "first_closed":
                t["pass"] = o.startswith("<closed>") or "403" in o.split(" || ")[0]
            elif e == "all_answered":
                parts = o.split(" || "); t["pass"] = len(parts) >= 2 and all(" 200" in x for x in parts)
            elif e == "blocked_logged":
                t["pass"] = any(b.get("reason") == "model_path_not_allowed" and "/api/v0" in str(b.get("path")) and b.get("method") == "GET"
                                for b in blocked) and len([b for b in blocked if "/api/v0" in str(b.get("path"))]) >= 2
            ok_all &= bool(t["pass"])
            for k in ("cmd", "out"):
                t[k] = t[k].replace(eps[0][0], "<lms>")
        own_url_in_egress = any(e_.get("url") == f"http://{OWN}/index.html" and e_.get("status") == 200 for e_ in egress)
        wiki_blocked = any(b.get("host") == "en.wikipedia.org" for b in blocked)
        # 預期被白名單擋下的：N10–N18 各一筆（N11 別組主機、N12 其他埠、N13 管理 API、N14 /v1/responses、N15 管線第 2 個、
        # N16 通道內 /api/v0、N17 走私、N18 格式不合、N10 經代理連維基）＝9 筆
        blocked_ok = len(blocked) == 9
        ok_all &= blocked_ok
        report = {"lms": "<lms>:" + lms.rsplit(":", 1)[1], "tests": res, "net_blocked_count": len(blocked), "net_blocked_expected": 9,
                  "net_blocked_reasons": sorted({b.get("reason") for b in blocked}),
                  "wikipedia_attempt_logged_as_blocked": wiki_blocked, "own_page_in_egress_record": own_url_in_egress,
                  "all_pass": bool(ok_all and wiki_blocked and own_url_in_egress)}
        pathlib.Path(a.out).write_text(json.dumps(report, ensure_ascii=False, indent=1))
        for t in res:
            print(("PASS " if t["pass"] else "FAIL ") + t["name"] + "  →  rc=" + str(t["rc"]) + "  " + str(t["out"])[:90].replace("\n", " "))
        print("blocked log:", len(blocked), sorted({b.get("reason") for b in blocked}), "| wikipedia blocked logged:", wiki_blocked, "| own page in egress:", own_url_in_egress)
        print("ALL PASS" if report["all_pass"] else "NOT ALL PASS")
        return 0 if report["all_pass"] else 1
    finally:
        for p_ in procs:
            p_.terminate()
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
