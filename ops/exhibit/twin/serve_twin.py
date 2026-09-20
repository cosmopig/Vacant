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
| `/qr.png`／`/qr.svg` | GET | **執行期畫的** QR，內容＝這一台真正綁在哪裡 | 電視 |

附帶：`/viewer.html`（收據頁）、`/phone.html`（手機頁）、`/`（現場說明頁）。

⚠ **QR 一定要執行期生成。** `vacant_hm/world3/qr.png` 是 2026-08-30 的靜態佔位圖
（比 `phone.html` 早三個星期），而 `--bind 0.0.0.0` 之後手機要連的是展場那台機器的
**區網 IP**，每次開機可能不同。烤死的 QR **必然指到錯的地方**，而畫面正在叫觀眾
「掃一下」。編碼器在 `ops/exhibit/twin/qr.py`（stdlib only，判準見 `tests/test_qr.py`）。

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
3. **`/control` 的門檻是「看得到 QR」，不是身分驗證。**
   非 loopback 綁定（展場的 `--bind 0.0.0.0`）**預設自動生一把 token**，
   編進 QR 的網址裡；沒帶或帶錯一律 403。但那把 token 就印在電視上——
   **在場所有看得到那台電視的人都按得動它**，而且拍一張照就帶得走。
   它擋掉的是「連上同一個 hotspot、但沒站在展件前面」的人，不是現場的人。
   **不要把它讀成身分驗證、授權或防竄改。**
   要完全關掉得明講 `--no-token`（開機橫幅會一直吼）。
4. **token 不會透過 `/state`／`/qr.png` 外流給區網上的其他人。**
   電視跟展件跑在同一台機器上，所以電視畫得出帶 token 的 QR；
   從別台機器打 `/state` 拿到的 `phone_url` 是**沒有 token 的**。
   否則 token 只是一個 GET 的距離，等於沒有。
   判準是 `Handler._is_same_machine`：**對端位址 ＝ 本端位址**，
   不是「對端是 127.0.0.1」——電視連的是這台機器的區網位址
   （`?live=http://<區網IP>:8899/...`），只看 loopback 會把電視自己擋在外面。
5. 排程順序是**確定性**的（cell_id 排序後配對），不是隨機。
   同一份 pack 起兩次，播出來的順序一模一樣。

用法：
    python3 ops/exhibit/twin/serve_twin.py                     # 127.0.0.1:8899
    python3 ops/exhibit/twin/serve_twin.py --bind 0.0.0.0      # 展場（自動生 token）
    python3 ops/exhibit/twin/serve_twin.py --dwell 25 --token abc
    python3 ops/exhibit/twin/serve_twin.py --bind 0.0.0.0 --no-token  # 明知故犯

電視：
    world3/index.html?live=http://<展場機>:8899/live/events.jsonl&poll=2000
    （`state` 參數可省略：電視會自己把 `/live/events.jsonl` 換成 `/state`）
"""
from __future__ import annotations

import argparse
import json
import pathlib
import secrets
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = pathlib.Path(__file__).resolve()
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from ops.exhibit.twin import qr as qrlib  # noqa: E402
from ops.exhibit.twin import to_events as tolib  # noqa: E402

TWIN = HERE.parent
DEFAULT_PACK = TWIN / "twin_pack.json"
VIEWER = REPO / "examples" / "twin_viewer.html"
PHONE = TWIN / "phone.html"

#: 🔴 **觀展者的頁**（2026-09-20 人類指定：「你的 QRCODE 應該都要依照這個」）。
#: 觀眾用自己的手機、自己的 AI 生一張分身卡，卡會顯示在現場螢幕。
#: ⚠ 這跟 `phone.html`（**導播**頁，「用手機決定要看哪一邊」）是**兩件事**：
#:   導播頁在展場那台機器上、要 token、只給操作的人；
#:   觀展者頁在公網上、不帶 token、給觀眾。
#: ⚠ 展場那台**仍然離線可跑**（電視與事件流都在本機）；需要網路的是**觀眾自己的手機**
#:   ——而那是本來就需要的（他們要用自己的 ChatGPT／Claude／Gemini）。
DEFAULT_VISITOR_URL = "https://vacant-world.cosmopig.com"

#: 有人按過之後，那一格至少停這麼久才輪播——**他的選擇不可以 20 秒就被蓋掉**。
#: （Fable 的觀眾視角稽核：輪播把人的選擇蓋掉 ⇒ 擁有感歸零。）
HOLD_AFTER_PRESS_S = 45.0

#: 翻一個位元是一個**瞬間動作**，不是一種狀態。留這麼多秒就過期。
#:
#: ⚠ 為什麼一定要有這個：舊版的 `tamper` **只能靠明確呼叫 `untamper` 清掉**，
#:   而無人值守的展場沒有人會去按。實測：第一個觀眾按完走掉，那行字
#:   （「有人正在自己的手機上重算 KAL-52__… 的收據」）留在螢幕上 4 分半，
#:   對後面每一位觀眾指著一格他們沒看到的東西。**它不是捏造，是舊狀態不會清。**
#:   而且光看畫面看不出來——字在、格式對、措辭也對，要按下去同時讀 `/state`
#:   比對 `cell_id` 才會現形。
TAMPER_TTL_S = 45.0

#: 兩顆導播鍵 → 那一格是哪一邊的反事實。
#: `held`＝客戶沒講介面叫什麼（`explicit=False`）；`pc`＝寫明了（`explicit=True`）。
SIDES = ("held", "pc")

#: ⚠ **鍵名用觀眾的詞。** 「介面」在一般人耳裡是 UI、「扣住」不知道扣什麼、
#: 「位元」沒人懂——這些是我們的詞，不是走進展場那個人的詞。
SIDE_LABEL = {
    "held": "不告訴它名字",
    "pc": "告訴它名字",
}
SIDE_TEXT = {
    "held": "客戶沒說要寫成什麼名字，只說要什麼功能",
    "pc": "客戶把要用的名字寫在需求裡了",
}


def now_ms() -> int:
    return int(time.time() * 1000)


def iso_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _query_token(query: str) -> str:
    """從 query string 撈出 `t=`。

    ⚠ **故意不用 `urllib.parse`。** `venue_check.sh` 第六節用一條很笨的 grep
    擋「這一支有沒有匯入對外連線的模組」，而 `urllib` 整個名字都在它的名單上。
    `urllib.parse` 確實不會連線，但把那條 grep 改精細＝把一道擋門變薄，
    而這裡要的只是切三個字元。**不值得為了省三行去動那道門。**
    """
    for part in query.split("&"):
        k, _, v = part.partition("=")
        if k == "t":
            return v.replace("+", " ")
    return ""


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
                 base_url: str, token: str = "", visitor_url: str = ""):
        self.lock = threading.RLock()
        self.pl = Playlist(pack)
        self.out = out
        self.dwell = dwell
        self.base_url = base_url.rstrip("/")
        #: 🔴 **觀眾掃的那個 QR 指的地方**（2026-09-20 人類指定）。
        #: 跟 `base_url` 是**兩件事**，不要合併：
        #:   `base_url`    ＝ 展場那台機器（區網 IP），`/phone.html` 是**導播**頁、要 token
        #:   `visitor_url` ＝ **觀展者的頁**，在公網上（觀眾用自己的手機、自己的 AI）
        #: 觀眾要的是後者；導播頁不是給觀眾的。
        #: ⚠ 空字串 ⇒ 退回 `phone_url()`（舊行為），但那時 QR 是導播頁，**不是觀眾頁**。
        self.visitor_url = visitor_url.rstrip("/")
        #: `/control` 的共享密鑰。空字串＝沒有門檻。它只會出現在
        #: **同一台機器**上的客戶端（＝電視）看到的 `phone_url`／QR 裡
        #: （見模組 docstring §4 與 `Handler._is_same_machine`）。
        self.token = token
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
        self.tamper_mono: float = 0.0
        self.deadline = time.monotonic() + dwell
        self.out.parent.mkdir(parents=True, exist_ok=True)
        self.out.write_text("", encoding="utf-8")

    # ── 事件 ────────────────────────────────────────────────────
    def verify_url(self, cell_id: str) -> str:
        return f"{self.base_url}/r/{cell_id}"

    def phone_url(self, *, with_token: bool = True) -> str:
        """手機要連的那個網址。**`base_url` 是什麼，這裡就是什麼**——

        不要在這裡自己組 `127.0.0.1`：那是展場當天最容易壞的一格
        （電視上顯示 `127.0.0.1`，觀眾的手機連不到自己的迴路位址）。
        `exhibit_boot.sh --lan` 會把區網 IP 從命令列傳進來。

        `with_token=False` 時**不帶 token**。呼叫端是 `/state` 與 `/qr.png`：
        非 loopback 的客戶端拿到的是沒有 token 的那一版，否則 token 只是
        一個 GET 的距離（模組 docstring §4）。
        """
        base = f"{self.base_url}/phone.html"
        return f"{base}?t={self.token}" if (with_token and self.token) else base

    def qr_target(self, *, with_token: bool = True) -> str:
        """**QR 裡到底編什麼。** 觀眾掃的是這一個。

        設了 `--visitor-url` ⇒ 就是它，**而且不附 token**
        （token 是本機 `/control` 的門檻，公網那一頁跟它無關；
        附上去等於把展場的控制 token 印在一張誰都能拍的圖上）。
        沒設 ⇒ 退回 `phone_url()`，維持舊行為。
        """
        if self.visitor_url:
            return self.visitor_url
        return self.phone_url(with_token=with_token)

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
                "side_label": SIDE_LABEL["pc" if cell["explicit"] else "held"],
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
            # 人按出來的那一格停久一點：輪播 20 秒就把他的選擇蓋掉 ＝ 白按。
            self.deadline = time.monotonic() + (
                max(self.dwell, HOLD_AFTER_PRESS_S) if why.startswith("phone")
                else self.dwell)
            # 換格了 ⇒ 上一格的翻位元狀態沒有指涉對象了，當場清掉。
            self._expire_tamper(cell_id)
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
                    # 這一對只跑過一邊。**不給按**，而且說出來——
                    # 生一個不存在的對照出來才是真正的錯。
                    return {"ok": False, "error": f"這一對沒有 {action} 那一邊"}
                # 輪播的游標跟著移到這一格之後：人放手之後接下去播的是下一格，
                # 不是又回到他剛剛看過的那一格。
                for n, (i, side) in enumerate(self.flat):
                    if i == self.pair_idx and side == action:
                        self.cursor = n + 1
                        break
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
                self.tamper_mono = time.monotonic()
                self.tamper = {
                    "cell_id": cid,
                    "at": iso_now(),
                    "ttl_s": TAMPER_TTL_S,
                    "url": self.verify_url(cid) + "?tamper=1",
                    # ⚠ 誠實邊界 2：這裡不宣告任何驗證結果。
                    "note": "翻位元與重算發生在觀眾自己的瀏覽器裡；這台機器沒有驗、"
                            "電視也沒有驗。",
                }
                return {"ok": True, "tamper": self.tamper}
            if action == "untamper":
                self.tamper = None
                self.tamper_mono = 0.0
                return {"ok": True, "tamper": None}
            return {"ok": False, "error": f"不認得的 action：{action!r}"}

    def _expire_tamper(self, playing: str | None = None) -> None:
        """翻位元的狀態自己會過期，**不需要有人來按 `untamper`**。

        兩條，滿足任一條就清掉：

        1. **超過 TTL**（`TAMPER_TTL_S`）。翻位元是瞬間動作，不是狀態。
        2. **電視換格了**。那行字講的是「有人正在重算**這一格**」；
           電視都演到下一格了，那句話就沒有指涉對象了。

        ⚠ 這件事一定要在**伺服器**這一端做，不能只靠電視端不印：
        `/state` 是手機也在讀的，而手機那一頁上「翻一個位元」那顆鍵的狀態
        也是從這裡來的。
        """
        if not self.tamper:
            return
        if time.monotonic() - self.tamper_mono > TAMPER_TTL_S:
            self.tamper = None
            self.tamper_mono = 0.0
            return
        if playing and self.tamper.get("cell_id") != playing:
            self.tamper = None
            self.tamper_mono = 0.0

    def state(self, *, with_token: bool = True) -> dict:
        with self.lock:
            self._expire_tamper((self.now or {}).get("cell_id"))
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
                    {"action": "held", "label": SIDE_LABEL["held"],
                     "text": SIDE_TEXT["held"], "cell_id": pair.get("held")},
                    {"action": "pc", "label": SIDE_LABEL["pc"],
                     "text": SIDE_TEXT["pc"], "cell_id": pair.get("pc")},
                    # ⚠ 措辭：這裡**不准預告結果**。「翻掉就會紅」是一個宣告，
                    #   而這台機器沒有算過。要看的是他自己那一頁算出什麼。
                    {"action": "tamper", "label": "自己驗一次收據",
                     "text": "把收據裡的一個字改掉，看它自己算出對不上",
                     "cell_id": (self.now or {}).get("cell_id")},
                ],
                "tamper": self.tamper,
                "last_control": self.last_control,
                "skipped": self.skipped,
                "emitted": self.n_emitted,
                "laps": self.laps,
                "dwell_s": self.dwell,
                "next_in_s": round(max(0.0, self.deadline - time.monotonic()), 1),
                # 電視要拿這個去畫 QR／印在螢幕上。**沒有這一格的時候電視是瞎的**
                # （它只知道事件流的網址，不知道手機該連哪裡）。
                # ⚠ `with_token` 由**請求端的位址**決定（Handler）：電視在本機，
                #   區網上的其他人拿到的是沒有 token 的那一版。
                "phone_url": self.phone_url(with_token=with_token),
                # 🔴 電視那一行字要印這個，不是 phone_url（那是導播頁）。
                "visitor_url": self.visitor_url,
                "qr_target": self.qr_target(with_token=with_token),
                "qr_url": f"{self.base_url}/qr.png",
                # 手機／稽核腳本要知道「這台機器有沒有門檻」。
                # 只回布林，**不回 token 本身**。
                "control_token_required": bool(self.token),
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
                    # ⚠ 這一句與「證據等級：AI 真的動手了」擺在同一頁上，觀眾
                    #   會讀成矛盾。**兩句都真，差別在時態**：AI 動手是在錄的
                    #   時候，不是現在。時態要寫出來，不然就是我們自己製造誤讀。
                    "AI 真的動手過——那是錄的時候。現在這條線上一通 AI 都沒有打："
                    "每一格都是先跑完、簽好章的紀錄。",
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
    quiet: bool = False
    server_version = "serve_twin/1"

    @property
    def token(self) -> str:
        """單一真相來源是 `Stage.token`，不要在 Handler 上再存一份。

        （舊版兩邊各存一份，改一邊就會出現「QR 帶著 A、伺服器認 B」
        這種只在展場才看得到的錯。）
        """
        return self.stage.token if self.stage else ""

    def _is_same_machine(self) -> bool:
        """請求是不是從**這台機器自己**來的（電視就是這種）。

        判準是「這條連線的對端位址 ＝ 本端位址」，不是「對端是 127.0.0.1」。

        ⚠ 為什麼不能只看 loopback——這一條差點在展場當天才會現形：
          電視開的網址是 `?live=http://<區網IP>:8899/...`，而 QR 那張圖
          （`stage.qr_url`）也是 `http://<區網IP>:8899/qr.png`。
          瀏覽器連到**自己這台機器的區網位址**時，核心挑的來源位址是那個
          區網位址，不是 127.0.0.1 ⇒ 只看 loopback 會把電視自己也當成外人，
          **電視畫出來的 QR 會沒有 token，全場一顆鍵都按不動**。
          對端＝本端這個判準對兩種接法（127.0.0.1 與區網 IP）都成立。

        ⚠ 這不是安全邊界，是**不要把 token 白送出去**的一道分流。
          要騙過它得偽造來源位址，而偽造之後收不到回包。
          **真正的門檻一直是「看得到那台電視」**，這裡只是不要連那個都省掉。
        """
        peer = (self.client_address or ("",))[0]
        if peer.startswith("127.") or peer in ("::1", "::ffff:127.0.0.1", ""):
            return True
        try:
            return peer == self.connection.getsockname()[0]
        except OSError:
            return False

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
            self._json(st.state(with_token=self._is_same_machine()))
        elif path in ("/qr.png", "/qr.svg"):
            # 內容＝**觀眾該去的地方**。設了 --visitor-url 就是觀展者頁（公網、不帶 token）；
            # 沒設才退回導播頁（這一台真正綁在哪裡，不是開發時寫死的那個）。
            url = st.qr_target(with_token=self._is_same_machine())
            try:
                if path.endswith(".svg"):
                    self._send(200, qrlib.to_svg(url).encode("utf-8"),
                               "image/svg+xml; charset=utf-8")
                else:
                    self._send(200, qrlib.to_png(url, scale=8),
                               "image/png")
            except ValueError as e:
                # 網址太長畫不出來 ⇒ **明講**，不要吐一張掃不開的圖。
                self._json({"error": str(e), "url": url}, 500)
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
        path, _, query = self.path.partition("?")
        if path != "/control":
            self._json({"error": "沒有這個端點", "path": path}, 404)
            return
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8")) if n else {}
        except ValueError:
            self._json({"ok": False, "error": "body 不是 JSON"}, 400)
            return
        if self.token:
            # 三個地方都收：body（手機頁走這條）、query string（curl／稽核腳本）、
            # header（反向代理）。**少一條就會在展場當天變成「怎麼按都沒反應」**。
            got = (str(body.get("token") or "")
                   or _query_token(query)
                   or self.headers.get("X-Twin-Token", ""))
            if not secrets.compare_digest(got, self.token):
                self._json({"ok": False,
                            "error": "token 不對：請重新掃電視上的 QR"}, 403)
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
                base_url: str = "", visitor_url: str = DEFAULT_VISITOR_URL,
                ) -> tuple[ThreadingHTTPServer, Stage]:
    srv = ThreadingHTTPServer((bind, port), Handler)
    host = bind if bind not in ("0.0.0.0", "") else "127.0.0.1"
    stage = Stage(pack, out=out, dwell=dwell, token=token,
                  base_url=base_url or f"http://{host}:{srv.server_address[1]}",
                  visitor_url=visitor_url)
    Handler.stage = stage
    Handler.quiet = quiet
    return srv, stage


#: 非 loopback 綁定卻沒給 `--token` 時，自動生一把的長度（bytes → urlsafe base64）。
#: 9 bytes ＝ 12 個字元。夠短，QR 不會因此變密；夠長，猜不到。
AUTO_TOKEN_BYTES = 9


def resolve_token(bind: str, token: str, no_token: bool) -> tuple[str, str]:
    """決定這一次要不要有 token，以及是誰決定的。

    回 `(token, why)`，`why` ∈ {`"given"`, `"auto"`, `"off-loopback"`,
    `"off-explicit"`}。**這是一個純函數**，因為它是這一塊唯一的判準，
    而判準要可以被 `tests/test_serve_twin.py` 逐條釘住。

    規則：

    1. 明確給了 `--token` ⇒ 用它（`given`）。
    2. `--no-token` ⇒ 沒有門檻（`off-explicit`）。橫幅會一直吼。
    3. 只綁 loopback ⇒ 沒有門檻（`off-loopback`）。手機本來就連不到，
       加一道門只是讓本機開發變麻煩。
    4. 其他（展場的 `--bind 0.0.0.0`）⇒ **自動生一把**（`auto`）。

    為什麼是「自動生」不是「拒絕啟動」：拒絕啟動在**有人在場**的時候是對的，
    在無人值守的開機流程裡是致命的——`systemd` 每 10 秒重試一次、每次都以
    同一個理由失敗，展場的電視就是一整天黑的。而自動生達成的是同一個保證
    （**不存在沒有門檻的區網監聽**），代價只是 token 每次開機會換。
    完整理由寫在 `decisions/DECISION_20260919_EXHIBIT_UNATTENDED.md` §一。
    """
    if token:
        return token, "given"
    if no_token:
        return "", "off-explicit"
    if bind in ("127.0.0.1", "::1", "localhost", ""):
        return "", "off-loopback"
    return secrets.token_urlsafe(AUTO_TOKEN_BYTES), "auto"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="展場機上的展件伺服器（零依賴、離線）")
    ap.add_argument("--pack", default=str(DEFAULT_PACK))
    ap.add_argument("--bind", default="127.0.0.1",
                    help="展場要讓手機連得到就用 0.0.0.0（同一個區網的人都按得動）")
    ap.add_argument("--port", type=int, default=8899)
    ap.add_argument("--out", default=None, help="events.jsonl 的落點")
    ap.add_argument("--dwell", type=float, default=30.0, help="沒人按的時候幾秒換一格")
    ap.add_argument("--token", default="",
                    help="/control 的共享密鑰。非 loopback 綁定沒給就自動生一把")
    ap.add_argument("--no-token", action="store_true",
                    help="明確關掉 token（非 loopback 綁定＝區網上任何人都按得動）")
    ap.add_argument("--base-url", default="",
                    help="手機看得到的位址前綴（收據與導播頁用它）。"
                         "展場一定要給區網 IP，不然導播頁會指到 127.0.0.1")
    ap.add_argument("--visitor-url", default=DEFAULT_VISITOR_URL,
                    help="🔴 **觀眾掃的 QR 指到哪裡**＝觀展者的頁（公網）。"
                         f"預設 {DEFAULT_VISITOR_URL}。"
                         "傳空字串就退回舊行為（QR 指導播頁 phone.html）")
    a = ap.parse_args(argv)

    pack = json.loads(pathlib.Path(a.pack).read_text(encoding="utf-8"))
    out = pathlib.Path(a.out) if a.out else TWIN / "live" / "events.jsonl"
    token, why = resolve_token(a.bind, a.token, a.no_token)
    srv, stage = make_server(pack, bind=a.bind, port=a.port, out=out,
                             dwell=a.dwell, token=token, base_url=a.base_url,
                             visitor_url=a.visitor_url)
    stop = threading.Event()
    threading.Thread(target=autoplay, args=(stage, stop), daemon=True).start()
    host = a.bind if a.bind != "0.0.0.0" else "127.0.0.1"
    print(f"展件伺服器 http://{host}:{srv.server_address[1]}/")
    print(f"  手機頁   {stage.phone_url()}")
    print(f"  QR       {stage.base_url}/qr.png（執行期畫的，內容就是上面那一行）")
    print(f"  電視接法 world3/index.html?live=http://{host}:"
          f"{srv.server_address[1]}/live/events.jsonl&poll=2000")
    print(f"  {len(stage.pl.pairs)} 對（同一題 × 扣住／寫明）、"
          f"{len(stage.pl.cells)} 格、{a.dwell:g} 秒輪播一格")
    print("  ⚠ 這一支不驗簽章也不宣告驗證結果：可驗的那一份是收據頁（/r/<cell_id>）")
    if why == "auto":
        print(f"  ✓ /control 的 token（這次開機自動生的）：{token}")
        print("    它已經編進上面那一行手機頁的網址與 QR 裡。**重開就會換一把。**")
        print("    ⚠ 它擋的是「連上同一個 hotspot 但沒站在展件前面」的人。"
              "看得到電視的人都按得動——這不是身分驗證。")
    elif why == "given":
        print("  ✓ /control 要 token（`--token` 指定的），已編進手機頁的網址與 QR")
    elif why == "off-explicit" and a.bind != "127.0.0.1":
        print("  ⚠⚠ `--no-token` ＋ 非 loopback 綁定："
              "**同一個區網上的任何人都按得動這台電視**。")
        print("     只有在「展件自己一台獨立熱點、沒有別人連得上」時才是對的。")
    if a.bind == "0.0.0.0" and "127.0.0.1" in stage.base_url:
        print("  ⚠ 綁在 0.0.0.0 但 --base-url 還是 127.0.0.1："
              "QR 會指到手機自己的迴路位址，掃了一定連不到。用 --base-url 給區網 IP。")
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
