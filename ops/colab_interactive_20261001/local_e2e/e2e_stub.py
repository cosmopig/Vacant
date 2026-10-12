#!/usr/bin/env python3
"""e2e_stub — 本機端到端（沒有 GPU）用的「按格子編劇」的機制替身模型。

這支在架構裡承重什麼：`smoke_stub.py` 是按「第幾個普通對話」選行為，只在一條線一次只有一個對話時才對；
真的 driver 會讓 A 與 C 同時開、R 與 K 同時跑，順序不固定。要在**真題目、真計分器、真 bridge、真 Vacant、真 pi TUI**
上驗證「這一格該發生什麼」，替身必須知道**這通請求屬於哪一格的哪一段 session**。代理（orproxy）把標籤
`/t/<格子>.n<第幾段>/…` 在轉給上游時丟掉了，所以本機測試在 pi 與代理之間放一個 `tag_front.py`，把標籤寫進請求本文的 `user` 欄位
（OpenAI 規格內的欄位）；這支替身讀它，按 `rules`（正規表示式對標籤，第一條符合的贏）決定這一段的行為：

  right   讀 goal.md、contract.md → 寫出對的交付物 → 說「做完了」
  wrong   同上，但寫的是錯的
  claim   讀兩個檔 → 說「已寫好」但**沒有寫**（Vacant 的零設定檢查該抓的那種）
  hang    讀 goal.md → 下一通請求卡 hang_s 秒（撞逾時）
  none    什麼都沒做就說做完

另有：`fail_first: N`＋`status`：這個標籤的前 N 通請求回那個 HTTP 狀態（N 大於代理的重試次數 ⇒ 錯誤透到 pi 與帳本 ⇒ infra_void；
N 小於 ⇒ 被代理的重試吃掉、不 void）；Vacant 送回（最後一則 user 訊息含 `Before delivery`）一律走 `sendback_mode`
（直接寫出對的交付物）。腳本（JSON）由 `build_e2e_inputs.py` 在 scratchpad 產生——**含參考答案，所以不進 repo**；這支程式本身不含任何題目內容。

誠實邊界：這是機制替身；它驗證的是管線（打字、完成偵測、分支、bridge、計分、打包），不是 agent 的表現。
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import stub_model as sm  # noqa: E402

TAG_RE = re.compile(r"^(?P<prefix>[A-Za-z0-9_.]+?)-(?P<arm>[ACRK])-(?P<bank>lcb_v[123]|dabench|databench|polyglot_py)-"
                    r"(?P<task>.+)-s(?P<sample>\d+)(?:v(?P<att>\d+))?\.n(?P<n>\d+)$")
LOCK = threading.Lock()
TL = threading.local()
CFG: dict = {}
SEEN: dict[str, int] = {}


def steps_for(mode: str, info: dict, hang_s: float, sendback: bool = False) -> list[dict]:
    f = info["file"]
    if sendback:
        return [{"write": [f, info["right"]]}, {"text": f"Updated {f}. Done."}]
    reads = [{"read": "goal.md"}, {"read": "contract.md"}]
    if mode == "right":
        return reads + [{"write": [f, info["right"]]}, {"text": f"I wrote {f}. Done."}]
    if mode == "wrong":
        return reads + [{"write": [f, info["wrong"]]}, {"text": f"I wrote {f}. Done."}]
    if mode == "claim":
        return reads + [{"text": f"I have written the solution to {f}. Done."}]
    if mode == "hang":
        return [{"read": "goal.md"}, {"read": "contract.md", "delay_s": hang_s}, {"text": "Done."}]
    return [{"text": "Done."}]


def log_row(row: dict) -> None:
    p = CFG.get("log")
    if p:
        with LOCK, open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def choose(msgs: list[dict], tools: list[dict]):
    tag = getattr(TL, "tag", None) or ""
    users = [i for i, m in enumerate(msgs) if m.get("role") == "user"]
    last_user = users[-1] if users else -1
    last = sm._text(msgs[last_user].get("content")) if last_user >= 0 else ""
    tool_n = sum(1 for m in msgs[last_user + 1:] if m.get("role") == "tool")
    has_assistant = any(m.get("role") == "assistant" for m in msgs)
    m = TAG_RE.match(tag)
    with LOCK:
        SEEN[tag] = SEEN.get(tag, 0) + 1
        k = SEEN[tag]
    row = {"t": round(time.time(), 3), "tag": tag, "req_in_tag": k, "user_msgs": len(users), "tool_msgs": tool_n,
           "has_assistant": has_assistant, "last_user_head": last[:120]}
    rule = next((r for r in CFG["rules"] if re.search(r["tag"], tag)), None)
    # 注入的 HTTP 錯誤（前 N 通）
    if rule and rule.get("fail_first") and k <= int(rule["fail_first"]):
        row.update({"mode": rule.get("mode"), "step": "error", "status": int(rule.get("status", 500)), "rule": rule.get("note")})
        log_row(row)
        return len(users) - 1, tool_n, {"error": int(rule.get("status", 500))}, last
    if m is None or f"{m['bank']}/{m['task']}" not in CFG["tasks"]:
        row.update({"mode": "none", "step": "text", "note": "tag does not parse or task unknown"})
        log_row(row)
        return len(users) - 1, tool_n, {"text": "Done."}, last
    info = CFG["tasks"][f"{m['bank']}/{m['task']}"]
    sendback = "Before delivery" in last and has_assistant
    mode = (rule or {}).get("mode") or CFG.get("default_mode", "right")
    steps = steps_for(mode, info, float(CFG.get("hang_s", 240)), sendback=sendback)
    st = steps[min(tool_n, len(steps) - 1)]
    kind = next((x for x in ("write", "read", "bash", "text") if x in st), "text")
    row.update({"mode": "sendback" if sendback else mode, "step": kind, "arm": m["arm"], "n": int(m["n"]),
                "task": f"{m['bank']}/{m['task']}", "rule": (rule or {}).get("note"), "delay_s": st.get("delay_s")})
    log_row(row)
    return len(users) - 1, tool_n, st, last


class Handler(sm.H):
    """讀出請求本文裡的 `user`（tag_front 寫進去的格子標籤），再交給 stub_model 原本的處理。"""

    def do_POST(self):  # noqa: N802
        n = int(self.headers.get("content-length") or 0)
        raw = self.rfile.read(n) if n else b""
        try:
            body = json.loads(raw) if raw else {}
        except ValueError:
            body = {}
        TL.tag = str(body.get("user") or "")
        self.rfile = io.BytesIO(raw)
        return super().do_POST()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=18000)
    ap.add_argument("--script", required=True)
    ap.add_argument("--log")
    a = ap.parse_args()
    CFG.update(json.load(open(a.script, encoding="utf-8")))
    CFG["log"] = a.log
    sm.CFG["script"] = {"turns": [{"steps": [{"text": "ok"}]}], "latency_s": float(CFG.get("latency_s", 0.25))}
    sm.CFG["log"] = None
    sm.choose = choose
    httpd = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    httpd.daemon_threads = True
    print(f"e2e_stub listening on 127.0.0.1:{httpd.server_address[1]} rules={len(CFG['rules'])} tasks={len(CFG['tasks'])}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
