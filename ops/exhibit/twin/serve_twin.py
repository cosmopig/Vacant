"""twin/serve_twin — 展場機上那一支伺服器：手機按一下，電視就演那一格。

## 這支在架構裡承重什麼

`decisions/DECISION_20260919_TWIN_V2_FIDELITY.md` §二 把手機定成
**C 導播端 ＋ B 稽核端**（不是委託端）。這一支就是那個決定的實作：

```
  手機（phone.html）            這一支                    電視（world3/index.html）
  ┌──────────────┐   POST /control   ┌──────────┐   GET /live/events.jsonl   ┌────────┐
  │ 介面扣住      │ ────────────────▶ │ 排程＋    │ ─────────────────────────▶ │ 演那一格 │
  │ 介面寫明      │                   │ 逐格吐出  │   GET /state（導播狀態）    └────────┘
  │ 翻一個位元    │ ─── GET /r/<cell> ▶│          │
  └──────────────┘   （收據頁，自己重算）└──────────┘
```

**為什麼手機不是委託端**：真模型每題約 114 秒（E10），展場等不起（CLAUDE.md
硬約束 1）。C 的每一次按壓都落在**已經跑完、簽好章的真資料**上，回應是毫秒級的，
而資料本身是真跑。觀眾決定要看反事實的哪一邊，那件事才從影片變成示範。

## 四個端點（接口契約）

| 端點 | 方法 | 回什麼 | 誰用 |
|---|---|---|---|
| `/live/events.jsonl` | GET | 已經吐出去的事件（JSONL，**逐格追加**） | 電視 |
| `/state` | GET | 現在演到哪一格、下一步是什麼、翻位元的狀態 | 手機＋電視的導播列 |
| `/control` | POST | `{"action": "held"｜"pc"｜"tamper"｜"next"｜"resume"｜"untamper"}` | 手機 |
| `/r/<cell_id>` | GET | 302 → `/viewer.html#cell=<cell_id>`（C4：per-cell 收據） | 手機 |

附帶：`/viewer.html`（收據頁）、`/phone.html`（手機頁）、`/`（現場說明頁）。

## 展場鐵律怎麼守

1. **零模型呼叫**：全部是 `twin_pack.json` 裡已經跑完的格子。這一支一通模型都不打，
   也沒有任何地方打得出去——它連 `urllib` 都沒 import。
2. **離線**：只有 stdlib、只綁 loopback（預設）、頁面零外部資源。
3. **無人值守**：沒人按就照排程輪播（`--dwell` 秒一格）。有人按就插隊。
   一輪播完把 `events.jsonl` 截掉重來——電視的 `LIVE.seen` 去重鍵含 `ts`，
   重播的 ts 是新的，所以截檔不會讓它重播舊的，而檔案不會無限長（D3）。
4. **一格卡住不准卡死整批**（D2）：每一格在追加之前先過 `to_events.validate`。
   沒有 `verdict` 的格子（`infra_void` 不簽收據也不發裁決）**不播、跳過、記在
   `/state.skipped` 裡講明原因**——不是靜靜丟掉，也不是硬編一個裁決。

## 誠實邊界

1. **這一支不驗簽章，也不對觀眾宣告任何驗證結果。** 事件流本身沒有簽章
   （LIVE_INTERFACE.md §四）。可驗的那一份是 `/r/<cell_id>` 那一頁，
   它在**觀眾自己的瀏覽器裡**從創世重算到鏈頭。面板不是信任來源。
2. **「翻一個位元」不是電視演出來的。** `/control` 的 `tamper` 只記下
   「有人要翻這一格」並把收據頁的網址給他；真正翻、真正重算、真正看到簽章對不上，
   發生在**他手上那一頁**。電視只說「有人正在手機上重驗這一格」——
   那是關於現場發生什麼的陳述，不是關於密碼學結果的宣告。
3. **`/control` 沒有驗證**（`--token` 是可選的）。預設只綁 loopback。
   展場要讓手機連得到就得 `--bind 0.0.0.0`，那一刻起同一個區網上的任何人
   都按得動這台電視——那是展場的現實，不是可以靜靜略過的細節。
4. 排程順序是**確定性**的（cell_id 排序後配對），不是隨機。
   同一份 pack 起兩次，播出來的順序一模一樣。

用法：
    python3 ops/exhibit/twin/serve_twin.py                     # 127.0.0.1:8899
    python3 ops/exhibit/twin/serve_twin.py --bind 0.0.0.0      # 展場（手機要連得到）
    python3 ops/exhibit/twin/serve_twin.py --dwell 25 --token abc

電視：
    world3/index.html?live=http://<展場機>:8899/live/events.jsonl&poll=2000
    （`state` 參數可省略：電視會自己把 `/live/events.jsonl` 換成 `/state`）
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = pathlib.Path(__file__).resolve()
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from ops.exhibit.twin import to_events as tolib  # noqa: E402

TWIN = HERE.parent
DEFAULT_PACK = TWIN / "twin_pack.json"
VIEWER = REPO / "examples" / "twin_viewer.html"
PHONE = TWIN / "phone.html"

#: 兩顆導播鍵 → 那一格是哪一邊的反事實。
#: `held`＝客戶沒講介面叫什麼（`explicit=False`）；`pc`＝寫明了（`explicit=True`）。
SIDES = ("held", "pc")

SIDE_TEXT = {
    "held": "介面扣住：客戶沒講那兩個函式叫什麼名字",
    "pc": "介面寫明：客戶把函式名字寫在題目裡",
}


def now_ms() -> int:
    return int(time.time() * 1000)


def iso_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


class Playlist:
    """把 pack 的格子配成「同一題 × 扣住／寫明」的對，並記住現在演到哪一對。

    ⚠ 配對是**資料本身的形狀**，不是我們湊出來的：`run_twin.py` 的排程本來就是
    一個居民 × 一題 × 兩種題面。配不成對的格子（只有一邊）仍然留在清單裡，
    但 `/state` 會標 `paired: false`——**不要讓畫面上出現一個不存在的對照**。
    """

    def __init__(self, pack: dict):
        self.pack = pack
        self.cells = {c["cell_id"]: c for c in pack["cells"]}
        pairs: dict[tuple[str, str], dict] = {}
        for c in sorted(pack["cells"], key=lambda c: c["cell_id"]):
            key = (c["resident"], c["task_id"])
            slot = pairs.setdefault(key, {"resident": c["resident"],
                                          "task_id": c["task_id"],
                                          "title": (c.get("task") or {}).get("title", ""),
                                          "held": None, "pc": None})
            slot["pc" if c["explicit"] else "held"] = c["cell_id"]
        self.pairs = [pairs[k] for k in sorted(pairs)]

    def pair(self, i: int) -> dict:
        return self.pairs[i % len(self.pairs)]

    def cell_id(self, i: int, side: str) -> str | None:
        return self.pair(i).get(side)


class Stage:
    """導播台：誰在演、下一個是誰、事件檔寫到哪。所有狀態變更都走這裡。"""

    def __init__(self, pack: dict, *, out: pathlib.Path, dwell: float,
                 base_url: str):
        self.lock = threading.RLock()
        self.pl = Playlist(pack)
        self.out = out
        self.dwell = dwell
        self.base_url = base_url.rstrip("/")
        # 排程攤平成一條確定性的清單：同一對先扣住、再寫明，然後換下一對。
        # 配不成對的格子（只有一邊跑過）仍然在清單裡，但 `/state.pair.paired`
        # 會標 false——**不要讓畫面上出現一個不存在的對照**。
        self.flat: list[tuple[int, str]] = []
        for i, pr in enumerate(self.pl.pairs):
            for side in SIDES:
                if pr.get(side):
                    self.flat.append((i, side))
        self.cursor = 0
        self.pair_idx = 0
        self.n_emitted = 0
        self.laps = 0
        self.ts_ms = now_ms()
        self.now: dict | None = None
        self.last_control: dict | None = None
        self.skipped: list[dict] = []
        self.tamper: dict | None = None
        self.deadline = time.monotonic() + dwell
        self.out.parent.mkdir(parents=True, exist_ok=True)
        self.out.write_text("", encoding="utf-8")

    # ── 事件 ────────────────────────────────────────────────────
    def verify_url(self, cell_id: str) -> str:
        return f"{self.base_url}/r/{cell_id}"

    def _block(self, cell_id: str) -> list[dict]:
        cell = self.pl.cells[cell_id]
        # ts 一定比上一次吐出去的晚：電視的去重鍵含 ts，撞鍵會被靜靜吃掉一格。
        self.ts_ms = max(self.ts_ms + 1000, now_ms())
        evs = tolib.events_for_cell(cell, verify_url=self.verify_url(cell_id),
                                    ts_ms=self.ts_ms)
        self.ts_ms += (len(evs) + 2) * 1000
        return evs

    def emit(self, cell_id: str, *, why: str) -> dict:
        """把一格追加進 events.jsonl。**過不了契約自檢就不播，而且講明原因。**"""
        with self.lock:
            evs = self._block(cell_id)
            bad = tolib.validate(evs)
            if bad:
                # D2：一格收不了尾，不准卡死整個佇列，也不准靜靜丟掉。
                rec = {"cell_id": cell_id, "reason": bad[:4], "at": iso_now()}
                self.skipped.append(rec)
                self.deadline = time.monotonic() + self.dwell
                return {"ok": False, "skipped": rec}
            with self.out.open("a", encoding="utf-8") as fh:
                for e in evs:
                    fh.write(json.dumps(e, ensure_ascii=False, sort_keys=True) + "\n")
            cell = self.pl.cells[cell_id]
            self.n_emitted += 1
            self.now = {
                "cell_id": cell_id,
                "resident": cell["resident"],
                "task_id": cell["task_id"],
                "side": "pc" if cell["explicit"] else "held",
                "side_text": SIDE_TEXT["pc" if cell["explicit"] else "held"],
                "evidence": cell["evidence"],
                "evidence_note": tolib.packlib.EVIDENCE_TEXT.get(cell["evidence"], ""),
                "exit_code": cell["exit_code"],
                "stop_reason": cell.get("stop_reason"),
                "attempts_used": cell.get("attempts_used"),
                "receipt_url": self.verify_url(cell_id),
                "why": why,
                "at": iso_now(),
                "n": self.n_emitted,
            }
            self.deadline = time.monotonic() + self.dwell
            return {"ok": True, "now": self.now}

    # ── 排程 ────────────────────────────────────────────────────
    def advance(self) -> dict:
        """輪播：同一對先扣住、再寫明，然後換下一對。一圈播完截檔重來。"""
        with self.lock:
            if not self.flat:
                return {"ok": False, "skipped": {"reason": ["排程裡一格可播的都沒有"]}}
            if self.cursor >= len(self.flat):
                # **截檔在新的一圈開頭**，不是上一圈結尾：剛播完的那一格要留在
                # 檔案裡，不然電視在兩圈之間會抓到一個空檔案。
                self.cursor = 0
                self._lap()
            i, side = self.flat[self.cursor]
            self.cursor += 1
            self.pair_idx = i
            return self.emit(self.pl.pair(i)[side], why="autoplay")

    def _seek(self, pair_idx: int) -> None:
        """把輪播游標移到某一對的開頭（手機插隊之後輪播要從那裡接下去）。"""
        self.pair_idx = pair_idx % len(self.pl.pairs)
        for n, (i, _side) in enumerate(self.flat):
            if i == self.pair_idx:
                self.cursor = n
                return

    def _lap(self) -> None:
        """一圈播完：截掉事件檔。

        電視的去重鍵是 `ts|type|task_id|…`，而下一圈的 ts 是新的 ⇒ 截檔不會
        讓它重播舊的，只是讓檔案不要一整天無限長（D3 的 O(n²) 輪詢）。
        """
        self.laps += 1
        self.out.write_text("", encoding="utf-8")

    def press(self, action: str, **kw) -> dict:
        """手機按鍵。回傳的東西會直接進 `/state`，手機拿來更新自己的畫面。"""
        with self.lock:
            self.last_control = {"action": action, "at": iso_now(), **kw}
            if action in SIDES:
                cid = kw.get("cell_id") or self.pl.cell_id(self.pair_idx, action)
                if not cid:
                    return {"ok": False, "error": f"這一對沒有 {action} 那一邊"}
                return self.emit(cid, why="phone")
            if action == "next":
                self._seek(self.pair_idx + 1)
                return self.advance()
            if action == "resume":
                return self.advance()
            if action == "tamper":
                cid = kw.get("cell_id") or (self.now or {}).get("cell_id")
                if not cid or cid not in self.pl.cells:
                    return {"ok": False, "error": "還沒有一格可以翻"}
                self.tamper = {
                    "cell_id": cid,
                    "at": iso_now(),
                    "url": self.verify_url(cid) + "?tamper=1",
                    # ⚠ 誠實邊界 2：這裡不宣告任何驗證結果。
                    "note": "翻位元與重算發生在觀眾自己的瀏覽器裡；這台機器沒有驗、"
                            "電視也沒有驗。",
                }
                return {"ok": True, "tamper": self.tamper}
            if action == "untamper":
                self.tamper = None
                return {"ok": True, "tamper": None}
            return {"ok": False, "error": f"不認得的 action：{action!r}"}

    def state(self) -> dict:
        with self.lock:
            pair = self.pl.pair(self.pair_idx)
            return {
                "v": 1,
                "at": iso_now(),
                "now": self.now,
                "pair": {
                    **pair,
                    "paired": bool(pair.get("held") and pair.get("pc")),
                    "index": self.pair_idx % len(self.pl.pairs),
                    "of": len(self.pl.pairs),
                },
                "buttons": [
                    {"action": "held", "label": "介面扣住", "text": SIDE_TEXT["held"],
                     "cell_id": pair.get("held")},
                    {"action": "pc", "label": "介面寫明", "text": SIDE_TEXT["pc"],
                     "cell_id": pair.get("pc")},
                    # ⚠ 措辭：這裡**不准預告結果**。「翻掉就會紅」是一個宣告，
                    #   而這台機器沒有算過。要看的是他自己那一頁算出什麼。
                    {"action": "tamper", "label": "翻一個位元",
                     "text": "在你自己的手機上把收據裡的一個位元翻掉，自己重算一次看看",
                     "cell_id": (self.now or {}).get("cell_id")},
                ],
                "tamper": self.tamper,
                "last_control": self.last_control,
                "skipped": self.skipped,
                "emitted": self.n_emitted,
                "laps": self.laps,
                "dwell_s": self.dwell,
                "next_in_s": round(max(0.0, self.deadline - time.monotonic()), 1),
                "evidence_counts": self.pack_counts(),
                "pairs": self.pl.pairs,
                # 整批格子的**原值**。手機的稽核分頁逐格印它——
                # ⚠ 不准由 `side` 反推收下沒（`held` 不等於一定被擋下）。
                # 那正是這一輪在修的那一類錯：從一個欄位猜另一個欄位。
                "cells": [
                    {"cell_id": c["cell_id"], "resident": c["resident"],
                     "task_id": c["task_id"],
                     "side": "pc" if c["explicit"] else "held",
                     "exit_code": c["exit_code"], "evidence": c["evidence"],
                     "stop_reason": c.get("stop_reason"),
                     "attempts_used": c.get("attempts_used"),
                     "receipt_url": f"/r/{c['cell_id']}"}
                    for c in sorted(self.pl.cells.values(),
                                    key=lambda c: c["cell_id"])
                ],
                "source": self.pl.pack.get("source", {}),
                "honesty": [
                    "這條線上一通模型都沒有打：每一格都是先跑完、簽好章的真資料。",
                    "事件流沒有簽章。可驗的那一份是收據頁，它在你自己的瀏覽器裡重算。",
                    "這台電視不驗簽章，所以它不會告訴你簽章對不對。",
                ],
            }

    def pack_counts(self) -> dict:
        return dict(self.pl.pack.get("evidence_counts") or {})


INDEX_HTML = """<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vacant 展件 · 展場機</title>
<style>
 :root{color-scheme:dark}
 body{background:#12100c;color:#efe7d8;font:16px/1.7 system-ui,"Noto Sans TC",sans-serif;
      margin:0;padding:24px;max-width:680px}
 h1{font-size:22px;margin:0 0 4px} a{color:#bedcbe}
 code{background:#0000004d;padding:2px 6px;border-radius:4px}
 li{margin:6px 0}
 .note{color:#efe7d899;font-size:14px}
</style></head><body>
<h1>Vacant 展件 · 展場機</h1>
<p class="note">全部離線。這台機器一通模型都不打。</p>
<ul>
  <li><a href="/phone.html">手機頁</a>（導播＋稽核）</li>
  <li><a href="/viewer.html">收據頁</a>（在你自己的瀏覽器裡從創世重算）</li>
  <li><a href="/state">/state</a> · <a href="/live/events.jsonl">/live/events.jsonl</a></li>
</ul>
<p class="note">電視接法：<code>world3/index.html?live=__BASE__/live/events.jsonl&amp;poll=2000</code></p>
</body></html>
"""


class Handler(BaseHTTPRequestHandler):
    stage: Stage = None       # type: ignore[assignment]
    token: str = ""
    quiet: bool = False
    server_version = "serve_twin/1"

    # ── 共用 ────────────────────────────────────────────────────
    def log_message(self, fmt, *args):     # noqa: A003
        if not self.quiet:
            sys.stderr.write("[serve_twin] %s\n" % (fmt % args))

    def _cors(self) -> None:
        # 電視在另一個埠（run.sh 的 8420），跨來源 fetch 需要這個。
        # 這是一條**本機唯讀展示線**，不是公開 API。
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "content-type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._cors()
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, obj, code: int = 200) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _file(self, p: pathlib.Path, ctype: str) -> None:
        if not p.exists():
            self._json({"error": f"沒有這個檔：{p.name}"}, 404)
            return
        self._send(200, p.read_bytes(), ctype)

    def do_OPTIONS(self):  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    # ── GET ────────────────────────────────────────────────────
    def do_GET(self):      # noqa: N802
        path, _, query = self.path.partition("?")
        st = self.stage
        if path in ("/", "/index.html"):
            base = f"http://{self.headers.get('Host', '127.0.0.1:8899')}"
            self._send(200, INDEX_HTML.replace("__BASE__", base).encode("utf-8"),
                       "text/html; charset=utf-8")
        elif path == "/live/events.jsonl":
            self._send(200, st.out.read_bytes(), "text/plain; charset=utf-8")
        elif path == "/state":
            self._json(st.state())
        elif path == "/viewer.html":
            self._file(VIEWER, "text/html; charset=utf-8")
        elif path == "/phone.html":
            self._file(PHONE, "text/html; charset=utf-8")
        elif path.startswith("/r/"):
            cell = path[3:]
            if cell not in st.pl.cells:
                self._json({"error": f"沒有這一格：{cell}"}, 404)
                return
            # `#` 之後的東西不會送到伺服器，所以收據頁要吃的是 fragment。
            frag = f"#cell={cell}" + ("&tamper=1" if "tamper=1" in query else "")
            self.send_response(302)
            self.send_header("Location", "/viewer.html" + frag)
            self._cors()
            self.end_headers()
        else:
            self._json({"error": "沒有這個端點", "path": path}, 404)

    do_HEAD = do_GET

    # ── POST ───────────────────────────────────────────────────
    def do_POST(self):     # noqa: N802
        path, _, _q = self.path.partition("?")
        if path != "/control":
            self._json({"error": "沒有這個端點", "path": path}, 404)
            return
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8")) if n else {}
        except ValueError:
            self._json({"ok": False, "error": "body 不是 JSON"}, 400)
            return
        if self.token and body.get("token") != self.token:
            self._json({"ok": False, "error": "token 不對"}, 403)
            return
        action = str(body.get("action") or "")
        kw = {k: v for k, v in body.items() if k in ("cell_id",)}
        res = self.stage.press(action, **kw)
        res["state"] = self.stage.state()
        self._json(res, 200 if res.get("ok") else 400)


def autoplay(stage: Stage, stop: threading.Event) -> None:
    """沒人按就自己播。**這是無人值守的那一條**（CLAUDE.md 硬約束 2）。"""
    while not stop.is_set():
        if time.monotonic() >= stage.deadline:
            stage.advance()
        stop.wait(0.2)


def make_server(pack: dict, *, bind: str, port: int, out: pathlib.Path,
                dwell: float, token: str = "", quiet: bool = False,
                base_url: str = "") -> tuple[ThreadingHTTPServer, Stage]:
    srv = ThreadingHTTPServer((bind, port), Handler)
    host = bind if bind not in ("0.0.0.0", "") else "127.0.0.1"
    stage = Stage(pack, out=out, dwell=dwell,
                  base_url=base_url or f"http://{host}:{srv.server_address[1]}")
    Handler.stage = stage
    Handler.token = token
    Handler.quiet = quiet
    return srv, stage


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="展場機上的展件伺服器（零依賴、離線）")
    ap.add_argument("--pack", default=str(DEFAULT_PACK))
    ap.add_argument("--bind", default="127.0.0.1",
                    help="展場要讓手機連得到就用 0.0.0.0（同一個區網的人都按得動）")
    ap.add_argument("--port", type=int, default=8899)
    ap.add_argument("--out", default=None, help="events.jsonl 的落點")
    ap.add_argument("--dwell", type=float, default=30.0, help="沒人按的時候幾秒換一格")
    ap.add_argument("--token", default="", help="可選：/control 的共享密鑰")
    ap.add_argument("--base-url", default="", help="收據網址的前綴（手機看得到的那個）")
    a = ap.parse_args(argv)

    pack = json.loads(pathlib.Path(a.pack).read_text(encoding="utf-8"))
    out = pathlib.Path(a.out) if a.out else TWIN / "live" / "events.jsonl"
    srv, stage = make_server(pack, bind=a.bind, port=a.port, out=out,
                             dwell=a.dwell, token=a.token, base_url=a.base_url)
    stop = threading.Event()
    threading.Thread(target=autoplay, args=(stage, stop), daemon=True).start()
    host = a.bind if a.bind != "0.0.0.0" else "127.0.0.1"
    print(f"展件伺服器 http://{host}:{srv.server_address[1]}/")
    print(f"  手機頁   http://{host}:{srv.server_address[1]}/phone.html")
    print(f"  電視接法 world3/index.html?live=http://{host}:"
          f"{srv.server_address[1]}/live/events.jsonl&poll=2000")
    print(f"  {len(stage.pl.pairs)} 對（同一題 × 扣住／寫明）、"
          f"{len(stage.pl.cells)} 格、{a.dwell:g} 秒輪播一格")
    print("  ⚠ 這一支不驗簽章也不宣告驗證結果：可驗的那一份是收據頁（/r/<cell_id>）")
    if a.bind == "0.0.0.0" and not a.token:
        print("  ⚠ 綁在 0.0.0.0 而且沒有 --token：同一個區網上的任何人都按得動這台電視")
    stage.advance()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
