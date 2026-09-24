"""twin/twinjoin_e2e — 分身真跑 → 電視上那個人：**本機假上游**的端到端一次（D 線，2026-09-24）。

## 這支在架構裡承重什麼

`decisions/DECISION_20260924_TWIN_AGENT_RUN.md` 把分身改成在 `vacant run` 底下真跑，
B 線的 `serve_twin --live` 會 tail lifecycle，電視（`vacant_hm/world3`）邊收邊演——
但**三段各自驗過、沒有一次串起來**。這一支把整條線一次跑完，而且全部用產品路徑：

```
 假上游（本機，零模型）                twinlink serve（唯讀名冊）──&twin=──┐
        ▲                                                               ▼
 twinlink.generate(agent) ─ launcher ─ proxy ─ lifecycle.jsonl ─ serve_twin --live ─ 電視
   （腳本化分身：真的打 proxy、寫 PLAN.md）                                （headless Chrome 截圖）
```

**合成特質，不是真人資料**（`SYNTH` 開頭）。觀眾原文一個字都不送外部服務：上游是本機假 server。

## 量什麼（判準在 `vacant_hm/tools/twinjoinshot.mjs` 的 e2e 模式，E 系列）

他的分身上台（照他的卡生的那一隻）、他的決定（名冊上讀到的那一句）畫出來、判決拍說
「這類任務沒有客觀標準」、收據拍照常。撤回「演到一半」的那一條在
`vacant_hm/tools/twinjoinshot.mjs`（時間軸可控才量得準）。

## 誠實邊界

1. **這一格不是能力證據**：分身是一支腳本（寫死的決定），上游是假 server。
   證明的是「lifecycle → serve_twin → 電視 → 名冊 join」這條接線走得通。
2. 證據等級會是 `L-unknown`：`twinagent` 的 `caller.declared_evidence` 是空字串
   （C 線的現況），`pack.evidence_level` 照規則推不出上游是什麼。畫面照實印。

用法：
    python3 ops/exhibit/twin/twinjoin_e2e.py --hm ../vacant_hm-wt-twinjoin \\
        --out ../vacant_hm-wt-twinjoin/evidence/twinjoin_20260924/e2e --seconds 170
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = pathlib.Path(__file__).resolve()
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from ops.exhibit.twin import serve_twin as S  # noqa: E402
from ops.exhibit.twin import twinagent, twinlink  # noqa: E402
from ops.exhibit.twin.twinstore import TwinStore  # noqa: E402

SUB_ID = "SYNTH-e2e-sub-0001"
TRAITS = "SYNTH：合成特質（不是真人）。喜歡慢慢來，會把事情寫成清單，最近想好好過一個週末。"
DECISION = "SYNTH：寫一份慢節奏週末的散步清單"
ARTIFACT = "SYNTH 週末散步清單\n1. 早上泡茶\n2. 沿河走一段\n"

# 腳本化分身：每一步真的打一通 proxy（所以 lifecycle 有 model_call、電視有 working），
# 中間停幾秒讓「正在做」那一拍看得到；最後寫 PLAN.md（第一行＝決定）與成品。
AGENT = r'''
import json, os, pathlib, sys, time, urllib.request
traits = pathlib.Path("TRAITS.md").read_text(encoding="utf-8")
sysp, msg = sys.argv[-2], sys.argv[-1]
base = os.environ["OPENAI_BASE_URL"].rstrip("/")
n = int(os.environ.get("E2E_CALLS", "4")); gap = float(os.environ.get("E2E_GAP", "6"))
for i in range(n):
    body = json.dumps({"model": "m", "messages": [
        {"role": "system", "content": sysp},
        {"role": "user", "content": traits + "\n" + msg + f"\n(step {i})"}]},
        ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(base + "/chat/completions", data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as r:
        r.read()
    time.sleep(gap)
pathlib.Path("PLAN.md").write_text("__DECISION__\n我喜歡慢慢來，所以先把週末寫成清單。\n",
                                   encoding="utf-8")
pathlib.Path("walk.md").write_text(__ARTIFACT__, encoding="utf-8")
print("交出了 walk.md")
'''.replace("__DECISION__", DECISION).replace("__ARTIFACT__", repr(ARTIFACT))


class _Upstream(BaseHTTPRequestHandler):
    """本機假上游：零模型。回一句固定的話。"""
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        return

    def do_GET(self):  # noqa: N802
        self._send(b'{"data":[{"id":"m"}]}')

    def do_POST(self):  # noqa: N802
        n = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(n)
        self._send(json.dumps({"choices": [{"message": {"content": "好"}}]}).encode())

    def _send(self, payload: bytes):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def _serve(handler) -> tuple[ThreadingHTTPServer, str]:
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.1},
                     daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def _wait_http(url: str, s: float = 20.0) -> None:
    import urllib.request
    t = time.time() + s
    while time.time() < t:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return
        except Exception:  # noqa: BLE001
            time.sleep(0.3)
    raise SystemExit(f"等不到 {url}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--hm", required=True, help="vacant_hm 的工作樹（有 world3/ 與 tools/）")
    ap.add_argument("--out", required=True, help="證據資料夾")
    ap.add_argument("--seconds", type=int, default=170)
    ap.add_argument("--start-after", type=float, default=12.0,
                    help="電視開起來幾秒之後才投卡（先讓它進等待態）")
    a = ap.parse_args(argv)
    hm, out = pathlib.Path(a.hm).resolve(), pathlib.Path(a.out).resolve()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    work = pathlib.Path(tempfile.mkdtemp(prefix="twinjoin_e2e_"))
    up_srv, up = _serve(_Upstream)
    os.environ["VACANT_RUN_UPSTREAM_OPENAI"] = up + "/v1"
    os.environ["VACANT_AGENT_MODEL"] = "m"
    os.environ.pop("VACANT_TWIN_AGENTRUNS", None)
    os.environ.pop("VACANT_EVENTS", None)       # 用「庫旁邊」那一個（開機腳本的預設）
    os.environ["E2E_CALLS"], os.environ["E2E_GAP"] = "4", "6"
    agent = work / "agent.py"
    agent.write_text(AGENT, encoding="utf-8")

    db = work / "store" / "twinstore.sqlite3"
    st = TwinStore(db)
    lc = twinagent.default_events_path(db)            # loop 會寫的那一個（＝開機腳本算的那一個）
    cfg = twinagent.AgentConfig(work_root=twinagent.default_work_root(db), events_path=lc,
                                model="m", endpoint=up + "/v1", parallel=1, timeout_s=120.0,
                                argv_prefix=[sys.executable, str(agent)], requires=[])
    # serve_twin --live：開機時 lifecycle 還不存在（Tail 從檔尾讀）
    srv, stage = S.make_server(S.default_recordings(), bind="127.0.0.1", port=0,
                               out=work / "events.jsonl", dwell=30, quiet=True, live=lc,
                               live_idle_s=20,
                               # 截圖那一支把 /qr.png 同源轉送（跨來源的圖會弄髒畫布、
                               # 量具讀不到像素）⇒ /state.qr_url 要指到它的來源。
                               base_url="http://127.0.0.1:8469")
    stop = threading.Event()
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    threading.Thread(target=S.autoplay, args=(stage, stop), daemon=True).start()
    twin_base = f"http://127.0.0.1:{srv.server_address[1]}"
    # twinlink serve（唯讀名冊；電視 &twin= 指這裡）——跟展場一樣是另一個行程
    import socket
    s = socket.socket(); s.bind(("127.0.0.1", 0)); store_port = s.getsockname()[1]; s.close()
    store = subprocess.Popen([sys.executable, str(HERE.parent / "twinlink.py"), "--db", str(db),
                              "serve", "--bind", "127.0.0.1", "--port", str(store_port)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    store_url = f"http://127.0.0.1:{store_port}/visitors.json"
    _wait_http(store_url)
    _wait_http(twin_base + "/state")

    shot = subprocess.Popen(
        ["node", str(hm / "tools" / "twinjoinshot.mjs"), str(out),
         f"{twin_base}/live/events.jsonl", store_url, str(a.seconds),
         twinagent.public_twin_id(SUB_ID), DECISION],
        cwd=str(hm), env={**os.environ, "TJ_E2E": "1", "PORT": "8469", "CDP_PORT": "9349"})
    time.sleep(a.start_after)

    # 觀眾投卡（合成特質）：不走公網，直接把一筆 queue item 抄進庫（ingest 的產品路徑）
    def fake(url, payload=None, timeout=30.0, headers=None):  # noqa: ANN001
        return 200, {"items": [{"id": SUB_ID, "ts": int(time.time() * 1000),
                                "card": {"need": "SYNTH：想把週末過得慢一點", "shape": "圓潤",
                                         "color": "暖土", "texture": "光滑",
                                         "first_line": "SYNTH：合成特質，不是真人"},
                                "card_text": TRAITS}]}
    twinlink._http_json = fake
    twinlink.ingest(st, "http://cloud.invalid", "t")
    t_gen = time.time()
    r = twinlink.generate(st, up + "/v1", "m", agent=cfg)
    gen_s = round(time.time() - t_gen, 1)
    view = twinlink.build_view(st)
    rc = shot.wait(timeout=a.seconds + 120)
    stop.set()
    srv.server_close()
    store.terminate()
    up_srv.shutdown()

    # 落盤：合成資料，可以進版控（沒有真人原文）
    shutil.copy(lc, out / "lifecycle.jsonl")
    shutil.copy(work / "events.jsonl", out / "tv_events.jsonl")
    p = [x for x in view["people"] if x["id"] == SUB_ID][0]
    (out / "roster_person.json").write_text(json.dumps(
        {k: p.get(k) for k in ("id", "twin_id", "card", "decision", "reason", "run", "engine",
                               "status", "tier")}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    (out / "driver.json").write_text(json.dumps({
        # agent 那一欄是暫存目錄的絕對路徑：建置機的路徑不跟著證據走。
        "generate": {k: v for k, v in r.items() if k != "agent"}, "generate_wall_s": gen_s, "shot_rc": rc,
        "twin_id": twinagent.public_twin_id(SUB_ID),
        "live_errors": stage.live_errors, "note": "合成特質；本機假上游；腳本化分身"},
        ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    shutil.rmtree(work, ignore_errors=True)
    print(f"generate={r} 牆鐘 {gen_s}s；截圖判準 rc={rc} → {out}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
