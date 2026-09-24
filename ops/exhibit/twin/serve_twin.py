"""twin/serve_twin — 展場機上那一支伺服器：重播錄影／轉播真跑，手機按一下，電視就演那一格。

## 這支在架構裡承重什麼

`decisions/DECISION_20260919_TWIN_V2_FIDELITY.md` §二 把手機定成
**C 導播端 ＋ B 稽核端**（不是委託端）。這一支就是那個決定的實作：

```
  手機（phone.html）            這一支                    電視（world3/index.html）
  ┌──────────────┐   POST /control   ┌──────────┐   GET /live/events.jsonl   ┌────────┐
  │ 不告訴它名字  │ ────────────────▶ │ 排程＋    │ ─────────────────────────▶ │ 演那一格 │
  │ 告訴它名字    │                   │ 重播／轉播│   GET /state（導播狀態）    └────────┘
  │ 自己驗收據    │ ─── GET /r/<cell> ▶│          │
  └──────────────┘   （收據頁，自己重算）└──────────┘
```

## 2026-09-24：資料來源只剩 lifecycle（「刪事後推導，留錄影重播」）

電視事件**只有一個產生者**：`live_events.Folder`。這一支餵給它的只有兩種東西：

| 模式 | 旗標 | 餵什麼 | `mode` |
|---|---|---|---|
| 重播（離線備援、預設） | `--recording <檔>`（可多個；不給＝`recordings/*.jsonl`） | **錄下來的** `vacant.lifecycle/1` 檔 | `"replay"` |
| 轉播（現場真跑） | `--live <檔>` | `run_twin.py --events` **正在寫**的那個檔（tail） | `"live"` |

在此之前這一支吃 `twin_pack.json`、呼叫 `to_events.events_for_cell` 從 run 目錄
**事後推**事件。那一條刪掉了；資料包現在只有一個用途：**收據頁**
（觀眾在自己的瀏覽器裡從創世重驗簽章鏈）。

### 收據頁：每一份錄影配它自己那一批（`pair_receipts.py`）

| 收據從哪來 | 頁面網址 | 綁定 |
|---|---|---|
| 錄影 `X.jsonl` 旁邊的 `X.pack.json`（同一次 `run_twin.py` 產的） | `/v/X.html` | sha256＋逐格鏈頭（`pair_receipts.check_pair`，載入時驗，不過整份不收） |
| `--live` 真跑：`--live-runs` 指到那一次 `run_twin.py --out`，那一格跑完就即時打包 | `/v/live.html` | 打包出來那一格的鏈頭＝`run_ended.verdict_hash` 才收 |
| `--pack`（預設 `twin_pack.json`，舊的 54 格 L-real） | `/viewer.html` | 只剩「鏈頭相等」那一道 |

`/r/<cell>` 找**鏈頭等於電視上演的那一跑**的那一份（誠實邊界 2），轉到那一頁；
一份都找不到就 404 並講明。頁面是同一份 `examples/twin_viewer.html`，
只換內嵌的 `twin-pack` 區塊（`build_viewer.with_pack`）——驗證程式只有一份。

### 分身的旁註與整批累計（2026-09-24 人類裁決「分身側自己記一份補回」）

- **`postaudit`**：錄影 `X.jsonl` 旁邊的 `X.sidecar.jsonl`（`twin.sidecar/1`，
  `sidecar.py`）是分身自己記的旁註，**不是** Vacant 的事件。載入時先驗旁註契約＋
  綁定（每一筆綁得上錄影裡的一跑 OFF：`run_id`＋`ws_end_sha256`），有配對收據就再驗
  旁註的 sha256（`pair_receipts.check_sidecar`）。**旁註過不了＝整份旁註不收**、
  錄影照播（lifecycle 是 Vacant 的紀錄，它沒壞），原因在
  `/state.recordings[*].sidecar.problems`。沒有旁註的舊錄影照播，**畫面上就沒有
  postaudit**。`--live L.jsonl` 會一併 tail `L.sidecar.jsonl`。
- **`counters`**：`_write` 每寫出一筆 `verdict`／`postaudit` 就緊接一筆
  （`live_events.Tally`／`with_counters`）。數的是**已經寫進事件檔的格子**，
  重播與現場各一本帳（各帶自己的 `mode`），同一格播兩次算一格，截檔不歸零。

### 一格＝錄影裡那一格的 `run_started … run_ended` 區段

錄影按 `run_started.caller.cell_id` 分格（ON 那一跑＋OFF 那一跑）。
手機的 `held`／`pc`＝同一位居民、同一題的兩邊（`caller.stratum`）。
同一個 `cell_id` 在錄影裡出現第二次（同一臂又開一跑）⇒ 留第一次、其餘記在
`/state.recordings[*].problems`，**不合併**。

### 重播的節奏：保留相對時間、壓縮進 `--dwell`

真模型一題約 114 秒（E10），展場等不起。重播**保留錄影裡事件之間的相對間隔**，
但整格等比例壓進 `dwell × REPLAY_FILL` 秒（剩下的時間留給電視演完最後一拍）：

    壓縮比 ratio = min(1, dwell×REPLAY_FILL ÷ 那一格錄影的跨度)
    第 i 筆的播出時刻 = 開播時刻 + (ts_i − ts_0) × ratio

**只壓不拉**（ratio ≤ 1）：錄影本來就比 dwell 短就照原速。壓縮比、原跨度、
播出跨度都落在 `/state.replay`，電視與手機要講「這是 N 倍速重播」有資料可講。
事件的 `ts` 是**重播當下的牆鐘**，不是錄影當時的（電視的去重鍵含 `ts`，
而且重播本來就不是那一刻發生的事）；錄影當時的時間只拿來算相對間隔。

### 真跑與重播怎麼切換（`--live` 才有這一段）

1. **有真跑就先播真跑。** tail 到新行 ⇒ 正在重播的那一格**先快轉寫完**
   （不准留一格開了沒 verdict，電視的佇列會卡死），然後把真跑的事件接上去。
2. **「有真跑」的定義**：這一支親眼看到 `run_started` 而還沒看到 `run_ended`
   的跑存在，**且**最後一行離現在不到 `--live-stale` 秒（預設 900）；
   或者最後一行離現在不到 `--live-idle` 秒（預設 20，讓最後那個裁決有時間被看到）。
3. 真跑期間**輪播暫停**，手機的 `held`／`pc`／`next`／`resume` 回
   `ok:false` 並講明「正在真跑」（`tamper` 照常：它只交出收據頁網址）。
4. 真跑閒下來 ⇒ 下一個 tick 就回到錄影輪播，從輪播游標原本的位置接下去。
5. 開機時從 `--live` 檔的**檔尾**開始讀：檔案裡已經有的不是「正在發生」。
   開機那一刻正在跑的那一跑整跑不轉（`live_events.Tail` 的代價，寫在那邊）。

### 分身那一格（`caller.task_kind="practical"`，2026-09-24）

`twinlink loop` 的分身真跑跟 `run_twin.py` 寫**同一種** lifecycle，所以同一條 `--live`
吃得下；差別是**只有 ON 一臂、沒有閘門、`accepted=null`（`ungated`）**。
這一支對它做的事只有三件，其餘規則逐字相同：

- 切換規則照舊（一跑開著就先播、閒下來回輪播）：只有一臂的格子 `run_ended` 一到就收尾，
  `tv_contract.validate` 逐臂收尾本來就只看**開過的臂**。
- `/state.now` 不套反事實那兩顆鍵的字（`side=null`、`side_label="數位分身"`）：
  分身那一格沒有「告訴它名字／不告訴它名字」這回事。
- 收據頁：分身的 run 目錄在 `twinlink` 的 `<庫名>.agentruns/runs/<sha256(sub_id)[:32]>/`，
  **不在** `--live-runs`（那是 `run_twin.py --out`），而且撤回時整個刪掉。
  這一支**不打包分身的收據**；`/r/<twin_id>` 照實講為什麼沒有頁可以帶去
  （收據本身有簽、有 `verdict_hash`，只是展場這一頁沒有接）。
- 現場那條路的電視事件用 `validate(require_task_kind=True)` 驗：新的東西一定要講明
  是題庫格還是分身的自主任務。

## 端點（接口契約）

| 端點 | 方法 | 回什麼 | 誰用 |
|---|---|---|---|
| `/live/events.jsonl` | GET | 已經寫出去的電視事件（JSONL，逐筆追加） | 電視 |
| `/state` | GET | 現在演哪一格、`mode`、重播壓縮比、真跑狀態、導播鍵 | 手機＋電視的導播列 |
| `/control` | POST | `{"action": "held"｜"pc"｜"tamper"｜"next"｜"resume"｜"untamper"}` | 手機 |
| `/r/<cell_id>` | GET | 302 → 那一跑所在的收據頁 `#cell=<cell_id>`；**沒有一頁有這一跑的鏈**就 404 並講明 | 手機 |
| `/v/<key>.html` | GET | 配對收據那一頁（`key`＝錄影檔名去掉 `.jsonl`，或 `live`） | 手機 |
| `/qr.png`／`/qr.svg` | GET | **執行期畫的** QR | 電視 |

附帶：`/viewer.html`（收據頁）、`/phone.html`（手機頁）、`/`（現場說明頁）。

⚠ **QR 一定要執行期生成。** `vacant_hm/world3/qr.png` 是 2026-08-30 的靜態佔位圖，
而 `--bind 0.0.0.0` 之後手機要連的是展場那台機器的**區網 IP**，每次開機可能不同。
編碼器在 `ops/exhibit/twin/qr.py`（stdlib only，判準見 `tests/test_qr.py`）。

## 展場鐵律怎麼守

1. **重播零模型呼叫**：錄影是已經跑完的東西。這一支一通模型都不打，
   也沒有任何地方打得出去——它連 `urllib` 都沒 import。
   （真跑那一邊的模型呼叫是 `run_twin.py` 打的，不是這一支。）
2. **離線**：只有 stdlib ＋ repo 內模組、只綁 loopback（預設）、頁面零外部資源。
3. **無人值守**：沒人按就照排程輪播（`--dwell` 秒一格）。一輪播完把
   `events.jsonl` 截掉重來（電視的去重鍵含 `ts`，重播的 ts 是新的）。
4. **一格卡住不准卡死整批**（D2）：每一格開播之前先把整段錄影過一次
   `Folder`＋`tv_contract.validate`。收不了尾的格子（錄影斷在半路、沒有
   `run_ended`）**不播、跳過、記在 `/state.skipped` 裡講明原因**。
5. **畫面上要講明是重播**（CLAUDE.md 展場硬約束 1）：每一筆事件都帶 `mode`，
   `/state.mode` 也有。重播那條路的 `"replay"` 寫死，不提供參數改。

## 誠實邊界

1. **這一支不驗簽章，也不對觀眾宣告任何驗證結果。** 事件流本身沒有簽章。
   可驗的那一份是 `/r/<cell_id>` 那一頁，它在**觀眾自己的瀏覽器裡**從創世重算。
2. **不准把觀眾帶去看另一跑的收據。** 錄影與舊資料包可以共用 `cell_id`、鏈卻不同
   （fixture 錄影與 54 格 L-real 就是這樣）。`/r/<cell>` 只轉到**鏈頭＝電視上演的
   那一跑的 `run_ended.verdict_hash`** 的那一頁；找不到就 404 並講明。
   沒有配對收據的錄影、還沒跑完的真跑、沒給 `--live-runs` 的真跑，都落在這一條。
3. **「翻一個位元」不是電視演出來的。** `tamper` 只記下「有人要翻這一格」並把
   收據頁的網址給他；真正翻、真正重算，發生在**他手上那一頁**。
4. **`/control` 的門檻是「看得到 QR」，不是身分驗證。**
   非 loopback 綁定預設自動生一把 token，編進 QR 的網址裡；沒帶或帶錯一律 403。
   但那把 token 就印在電視上——**在場所有看得到那台電視的人都按得動它**。
   要完全關掉得明講 `--no-token`（開機橫幅會一直吼）。
5. **token 不會透過 `/state`／`/qr.png` 外流給區網上的其他人**
   （判準是 `Handler._is_same_machine`：對端位址 ＝ 本端位址）。
6. 排程順序是**確定性**的（cell_id 排序後配對），不是隨機。
7. **真跑死在半路**（沒有 `run_ended`）那一格在電視上會一直開著：這一支不替它
   編裁決（`live_events` 誠實邊界 6）。`--live-stale` 秒之後這一支回到輪播，
   但電視那一格的佇列要電視自己處理。

用法：
    python3 ops/exhibit/twin/serve_twin.py                     # 重播 recordings/*.jsonl
    python3 ops/exhibit/twin/serve_twin.py --recording a.jsonl --recording b.jsonl
    python3 ops/exhibit/twin/serve_twin.py --live runs/twin_live/lifecycle.jsonl \
        --live-runs runs/twin_live          # 真跑那一格跑完就即時打包收據
    python3 ops/exhibit/twin/serve_twin.py --bind 0.0.0.0      # 展場（自動生 token）

電視：
    world3/index.html?live=http://<展場機>:8899/live/events.jsonl&poll=2000
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import secrets
import sys
import threading
import time
from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = pathlib.Path(__file__).resolve()
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from ops.exhibit.twin import build_viewer  # noqa: E402
from ops.exhibit.twin import live_events as lelib  # noqa: E402
from ops.exhibit.twin import pair_receipts as pairlib  # noqa: E402
from ops.exhibit.twin import pack as packlib  # noqa: E402
from ops.exhibit.twin import qr as qrlib  # noqa: E402
from ops.exhibit.twin import sidecar as sidecarlib  # noqa: E402
from ops.exhibit.twin import tv_contract as tv  # noqa: E402
from vacant_network.vrun import lifecycle  # noqa: E402

TWIN = HERE.parent
#: 離線備援的錄影放這裡（`record_fixture.sh` 產生、進版控）。
RECORDINGS_DIR = TWIN / "recordings"
#: 收據頁內嵌的那一份資料包。**只給 `/r/<cell>` 用**（見誠實邊界 2），不產事件。
DEFAULT_PACK = TWIN / "twin_pack.json"
VIEWER = REPO / "examples" / "twin_viewer.html"
PHONE = TWIN / "phone.html"

#: 🔴 **觀展者的頁**（2026-09-20 人類指定：「你的 QRCODE 應該都要依照這個」）。
#: 觀眾用自己的手機、自己的 AI 生一張分身卡，卡會顯示在現場螢幕。
#: ⚠ 這跟 `phone.html`（**導播**頁）是**兩件事**：導播頁在展場那台機器上、要 token；
#:   觀展者頁在公網上、不帶 token、給觀眾。
DEFAULT_VISITOR_URL = "https://vacant-world.cosmopig.com"

#: 有人按過之後，那一格至少停這麼久才輪播——**他的選擇不可以 20 秒就被蓋掉**。
HOLD_AFTER_PRESS_S = 45.0

#: 翻一個位元是一個**瞬間動作**，不是一種狀態。留這麼多秒就過期。
#: ⚠ 舊版只能靠 `untamper` 清掉，無人值守的展場沒有人會按；實測那行字留在螢幕上
#:   4 分半，對後面每一位觀眾指著一格他們沒看到的東西。
TAMPER_TTL_S = 45.0

#: 重播一格的事件要在 `dwell` 的這個比例之內播完（剩下的留給電視演完最後一拍）。
REPLAY_FILL = 0.8

#: `--live` 的切換門檻（模組 docstring「真跑與重播怎麼切換」）。
LIVE_IDLE_S = 20.0
LIVE_STALE_S = 900.0
#: 真跑那一格 `run_ended` 之後，最多等這麼久讓 `run_twin.py` 寫完 `twin_cell.json`
#: （OFF 那一臂＋事後稽核都跑完才會寫）。等不到就照實說沒有收據。
LIVE_PACK_WAIT_S = 900.0
#: 真跑那一份收據頁的 key（`/v/live.html`）。
LIVE_BOOK = "live"

#: 兩顆導播鍵 → 那一格是哪一邊的反事實。
SIDES = ("held", "pc")

#: 分身那一格在 `/state.now` 的說法。**不套反事實那兩顆鍵的字**。
PRACTICAL_SIDE_LABEL = "數位分身"
PRACTICAL_SIDE_TEXT = "觀眾的分身自己決定做一件實務小事：這類任務沒有客觀標準，Vacant 不判對錯"
PRACTICAL_NO_RECEIPT_PAGE = (
    "這是數位分身的一跑：收據有簽（每一通都經過中介、結束時簽章），但它的 run 目錄"
    "跟著分身的檔案庫走、撤回時整個刪掉，展場這一頁沒有打包它——不帶你去看別的鏈")

#: ⚠ **鍵名用觀眾的詞。** 「介面」「扣住」「位元」是我們的詞，不是走進展場那個人的詞。
SIDE_LABEL = {
    "held": "不告訴它名字",
    "pc": "告訴它名字",
}
SIDE_TEXT = {
    "held": "客戶沒說要寫成什麼名字，只說要什麼功能",
    "pc": "客戶把要用的名字寫在需求裡了",
}

#: 與 `vacant_network/vrun/launcher.py` 的 `EXIT_ACCEPTED, EXIT_REFUSED, EXIT_VOID`
#: 同值（`tests/test_serve_twin.py` 釘住）。這裡不 import launcher：它會把整條
#: proxy／沙箱拉進展場那一支伺服器，而這裡只要三個數字。
EXIT_ACCEPTED, EXIT_REFUSED, EXIT_VOID = 0, 20, 22


def now_ms() -> int:
    return int(time.time() * 1000)


def iso_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _query_token(query: str) -> str:
    """從 query string 撈出 `t=`。

    ⚠ **故意不用 `urllib.parse`。** `venue_check.sh` 第六節用一條很笨的 grep
    擋「這一支有沒有匯入對外連線的模組」，而 `urllib` 整個名字都在它的名單上。
    """
    for part in query.split("&"):
        k, _, v = part.partition("=")
        if k == "t":
            return v.replace("+", " ")
    return ""


def exit_code_of(on_end: dict | None) -> int | None:
    """ON 那一跑的 `run_ended` → 退出碼（`launcher.exit_code` 對 ON 臂的同一條規則）。

    `None` ＝錄影裡沒有 ON 的 `run_ended`（斷在半路）：**不猜**。
    """
    if not on_end:
        return None
    if on_end.get("infra_void"):
        return EXIT_VOID
    return EXIT_REFUSED if on_end.get("refused") else EXIT_ACCEPTED


# ── 錄影 ────────────────────────────────────────────────────────────
def _rel(p: pathlib.Path) -> str:
    p = pathlib.Path(p).resolve()
    return str(p.relative_to(REPO)) if p.is_relative_to(REPO) else p.name


def load_recordings(paths) -> tuple[dict[str, dict], list[dict]]:
    """讀錄影 → `{cell_id: cell}`＋每個錄影檔的說明（`/state.recordings`）。

    ⚠ **整個檔先過 `lifecycle.validate_stream`，過不了整個檔不收**（fail-closed）。
    一個檔裡有一行壞掉代表那份錄影的來歷有問題，挑著用等於替它背書。

    ⚠ **同一格出現在兩份錄影裡：證據等級高的那份贏**（`EVIDENCE_RANK`，2026-09-24）。
      舊規則是「先載入的贏」，而 `recordings/` 是照檔名排序載入的 ⇒
      `fixture_*`（L-none，腳本交件）排在 `lreal_*`（L-real）前面，54 格全部撞 id，
      **真跑那一份一格都播不出來**，`--check` 卻兩份都說過（它一份一份驗）。
      fixture 的角色是「沒有真跑錄影時的備援」，所以真跑的格子一律蓋過它。
      同等級撞 id ⇒ 仍然先來的贏。被蓋掉／沒收的格子寫進那份錄影的 `problems`，
      不是靜靜消失。整格一起換（兩臂同一份來歷），不混兩份錄影的臂。
    """
    cells: dict[str, dict] = {}
    info: list[dict] = []
    for path in paths:
        path = pathlib.Path(path)
        rec = {"path": _rel(path), "sha256": None, "lines": 0, "cells": 0,
               "problems": [], "accepted": False}
        info.append(rec)
        try:
            raw = path.read_bytes()
        except OSError as e:
            rec["problems"].append(f"讀不到：{type(e).__name__}: {e}")
            continue
        rec["sha256"] = hashlib.sha256(raw).hexdigest()
        evs = lifecycle.read(path)
        rec["lines"] = len(evs)
        bad = lifecycle.validate_stream(evs)
        if bad:
            rec["problems"] = ["lifecycle 契約不合，整個檔不收：" + b for b in bad[:5]]
            continue
        rec["accepted"] = True
        rows, rec["sidecar"] = load_sidecar(path, evs)
        if rec["sidecar"]["problems"]:
            rec["problems"] += ["旁註不收：" + b for b in rec["sidecar"]["problems"][:3]]
        evs = sidecarlib.merge(evs, rows)
        run_cell: dict[str, str] = {}
        ignored: set[str] = set()
        local: dict[str, dict] = {}
        for e in evs:
            rid = e["run_id"]
            if e["type"] == "run_started":
                caller = e.get("caller") or {}
                cid = caller.get("cell_id") or e["task_id"]
                c = local.get(cid)
                if c is None:
                    c = local[cid] = {
                        "cell_id": cid, "recording": rec["path"], "segment": [],
                        "arms": {}, "ends": {}, "resident": caller.get("resident"),
                        "task_id": caller.get("task_id") or e["task_id"],
                        "stratum": caller.get("stratum"),
                        "declared_evidence": caller.get("declared_evidence") or "",
                        "task_kind": caller.get("task_kind"),
                    }
                if e["arm"] in c["arms"]:
                    ignored.add(rid)
                    rec["problems"].append(
                        f"{cid} 的 {e['arm']} 在這份錄影裡跑了第二次：只收第一次")
                    continue
                c["arms"][e["arm"]] = rid
                run_cell[rid] = cid
            if rid in ignored or rid not in run_cell:
                continue
            c = local[run_cell[rid]]
            c["segment"].append(e)
            if e["type"] == "run_ended":
                c["ends"][e["arm"]] = e
        for cid, c in local.items():
            on_end = c["ends"].get(packlib.ARM)
            side = c["stratum"] if c["stratum"] in SIDES else "held"
            c.update({
                "side": side,
                "explicit": side == "pc",
                "title": packlib.task_meta(c["task_id"]).get("title", "")
                if c["task_id"] else "",
                "exit_code": exit_code_of(on_end),
                "stop_reason": (on_end or {}).get("stop_reason"),
                "attempts_used": (on_end or {}).get("attempts_used"),
                "verdict_hash": (on_end or {}).get("verdict_hash"),
                # 證據等級照樣是推的：requests_seen == 0 一律 L-none。
                "evidence": None if on_end is None else packlib.evidence_level(
                    requests_seen=int(on_end.get("requests_seen") or 0),
                    declared=c["declared_evidence"]),
                "span_ms": (c["segment"][-1]["ts_ms"] - c["segment"][0]["ts_ms"])
                if c["segment"] else 0,
            })
            prev = cells.get(cid)
            if prev is not None:
                # 別的錄影檔已經有這一格：證據等級高的贏，同級先來的贏。
                if _evidence_rank(c["evidence"]) <= _evidence_rank(prev["evidence"]):
                    rec["problems"].append(
                        f"{cid} 已經在 {prev['recording']} 裡（{prev['evidence']}），"
                        f"這一份（{c['evidence']}）不收")
                    continue
                loser = next((r for r in info if r["path"] == prev["recording"]), None)
                if loser is not None:
                    loser["problems"].append(
                        f"{cid} 被 {rec['path']}（{c['evidence']}）蓋過，"
                        f"這一份（{prev['evidence']}）不播")
                    loser["cells"] -= 1
            cells[cid] = c
            rec["cells"] += 1
    return cells, info


#: 同一格撞在兩份錄影時誰贏：真跑 > 假上游 > 沒紀錄上游 > 沒有模型（fixture）。
EVIDENCE_RANK = {"L-real": 3, "L-fake": 2, "L-unknown": 1, "L-none": 0}


def _evidence_rank(level) -> int:
    return EVIDENCE_RANK.get(level, -1)     # 沒有 run_ended（推不出等級）最低


def load_sidecar(path: pathlib.Path, evs: list[dict]) -> tuple[list[dict], dict]:
    """錄影 `X.jsonl` 的旁註 → `(收下的旁註, 說明)`。**過不了就整份旁註不收**（回空清單）。

    三道：旁註契約、綁得上這份錄影裡的一跑（`sidecar.validate`）、
    有配對收據就再驗旁註的 sha256（`pair_receipts.check_sidecar`）。
    """
    sc = sidecarlib.sidecar_path(path)
    info = {"file": sc.name, "present": sc.exists(), "rows": 0,
            "accepted": False, "problems": []}
    if not sc.exists():
        return [], info
    try:
        rows = sidecarlib.read(sc)
    except (OSError, UnicodeDecodeError) as e:
        info["problems"].append(f"讀不到：{type(e).__name__}: {e}")
        return [], info
    info["rows"] = len(rows)
    bad = sidecarlib.validate(rows, lifecycle_events=evs)
    pp = pairlib.pair_path(path)
    if pp.exists():
        try:
            bad += pairlib.check_sidecar(path, json.loads(pp.read_text(encoding="utf-8")))
        except (OSError, ValueError) as e:
            bad.append(f"配對收據讀不了：{type(e).__name__}: {e}")
    if bad:
        info["problems"] = bad[:5]
        return [], info
    info["accepted"] = True
    return rows, info


def default_recordings() -> list[pathlib.Path]:
    """`recordings/*.jsonl`，**排掉旁註**（`X.sidecar.jsonl` 不是一份錄影）。"""
    return sorted(p for p in RECORDINGS_DIR.glob("*.jsonl")
                  if not sidecarlib.is_sidecar(p))


#: 錄影會被印上展場螢幕（`task_opened.prompt`），建置機的目錄結構不准跟著上去。
PATH_LEAKS = ("/Users/", "/home/", "/private/var/", "worktrees/agent-")


def check_recording(path, *, require_task_kind: bool = False) -> list[str]:
    """一份錄影能不能上展場：**lifecycle 契約 ＋ 轉出來的電視契約**，兩把都過。

    開機前（`exhibit_preflight.sh`）、錄完當下（`record_fixture.sh`）、測試都叫這一支。
    轉換走的是**同一個** `live_events.Folder`（mode 寫死 replay）——不另寫一份檢查用的轉法。
    `require_task_kind=True`（`--check --new`，`record_fixture.sh` 用）：剛錄的錄影
    每一格都要講明 `task_kind`；缺席只給 2026-09-24 之前的舊錄影。
    """
    path = pathlib.Path(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        return [f"讀不到：{type(e).__name__}: {e}"]
    bad = [f"建置機的路徑漏進錄影：{leak}" for leak in PATH_LEAKS if leak in raw]
    evs = lifecycle.read(path)
    if not evs:
        return bad + ["一行 lifecycle 都沒有"]
    bad += ["lifecycle：" + b for b in lifecycle.validate_stream(evs)]
    # 分身的旁註（有才驗）：契約＋綁定＋路徑不外漏。過不了在展場上是「沒有 postaudit」，
    # 但在開機前／錄完當下要擋下來講明，不准帶著一份壞掉的旁註上展場。
    sc = sidecarlib.sidecar_path(path)
    rows: list[dict] = []
    if sc.exists():
        sraw = sc.read_text(encoding="utf-8")
        bad += [f"建置機的路徑漏進旁註：{leak}" for leak in PATH_LEAKS if leak in sraw]
        rows = sidecarlib.read(sc)
        bad += ["旁註：" + b for b in sidecarlib.validate(rows, lifecycle_events=evs)]
    if bad:
        return bad
    try:
        tvevs = lelib.fold(sidecarlib.merge(evs, rows), verify_url="/r/{cell}",
                           mode=tv.MODE_REPLAY)
    except lelib.SchemaMismatch as e:
        return [f"lifecycle 版號不對：{e}"]
    if not tvevs:
        return ["轉不出任何電視事件"]
    bad = ["電視契約：" + b for b in tv.validate(
        tvevs, require_task_kind=require_task_kind)]
    # 配對收據：**有就一定要對**（錄影換了、收據沒換要擋得下來）。沒有則不算錯，
    # 由 `--check` 另外講明「這份錄影的格子沒有收據頁」。
    pp = pairlib.pair_path(path)
    if pp.exists():
        text = pp.read_text(encoding="utf-8")
        bad += ["配對收據：" + b for b in pairlib.check_pair(path, json.loads(text),
                                                        pack_text=text)]
    return bad


def receipt_heads(pack: dict | None) -> dict[str, str]:
    """一份資料包每一格的鏈頭（`/r/<cell>` 的判準，誠實邊界 2）。"""
    if not pack:
        return {}
    return {c["cell_id"]: h for c in pack.get("cells") or []
            if (h := pairlib.chain_head(c))}


def book(key: str, pack: dict, *, label: str, text: str | None = None) -> dict:
    """一份收據頁：`key` 決定網址（空字串＝`/viewer.html`，否則 `/v/<key>.html`）。"""
    return {"key": key, "label": label, "heads": receipt_heads(pack),
            "pack_text": text if text is not None else pairlib.dumps(pack),
            "html": None}


def load_receipt_books(paths) -> tuple[list[dict], dict[str, dict]]:
    """每一份錄影旁邊的 `X.pack.json` → 收據頁。回 `(books, {錄影路徑: 狀態})`。

    ⚠ 綁定過不了（sha256 或逐格鏈頭）⇒ **整份不收**，那一份錄影的格子就沒有收據頁，
      `/r/<cell>` 照實 404。不准「大部分對得上就先用」。
    """
    books, status = [], {}
    for path in paths:
        path = pathlib.Path(path)
        pp = pairlib.pair_path(path)
        st = {"file": pp.name, "accepted": False, "problems": []}
        status[_rel(path)] = st
        if not pp.exists():
            st["problems"].append("沒有配對收據：這份錄影的格子沒有收據頁可以帶觀眾去")
            continue
        try:
            text = pp.read_text(encoding="utf-8")
            pack = json.loads(text)
            bad = pairlib.check_pair(path, pack, pack_text=text)
        except (OSError, ValueError) as e:
            bad = [f"讀不了：{type(e).__name__}: {e}"]
        if bad:
            st["problems"] = ["配對收據不收：" + b for b in bad[:5]]
            continue
        st["accepted"] = True
        books.append(book(path.stem, pack, label=_rel(pp), text=text.strip("\n")))
    return books, status


class Playlist:
    """把格子配成「同一位居民 × 同一題 × 兩種題面」的對。

    ⚠ 配對是**資料本身的形狀**：`run_twin.py` 的排程本來就是一個居民 × 一題 ×
    兩種題面。配不成對的格子仍然留在清單裡，但 `/state` 會標 `paired: false`
    ——**不要讓畫面上出現一個不存在的對照**。
    """

    def __init__(self, cells: dict[str, dict]):
        self.cells = cells
        pairs: dict[tuple[str, str], dict] = {}
        for c in sorted(cells.values(), key=lambda c: c["cell_id"]):
            key = (c.get("resident") or "", c.get("task_id") or c["cell_id"])
            slot = pairs.setdefault(key, {"resident": c.get("resident"),
                                          "task_id": c.get("task_id"),
                                          "title": c.get("title", ""),
                                          "held": None, "pc": None})
            slot[c["side"]] = c["cell_id"]
        self.pairs = [pairs[k] for k in sorted(pairs)]

    def pair(self, i: int) -> dict:
        if not self.pairs:
            return {"resident": None, "task_id": None, "title": "",
                    "held": None, "pc": None}
        return self.pairs[i % len(self.pairs)]

    def cell_id(self, i: int, side: str) -> str | None:
        return self.pair(i).get(side)


class Stage:
    """導播台：誰在演、下一個是誰、事件檔寫到哪。所有狀態變更都走這裡。"""

    def __init__(self, cells: dict[str, dict], *, out: pathlib.Path, dwell: float,
                 base_url: str, token: str = "", visitor_url: str = "",
                 recordings: list[dict] | None = None,
                 books: list[dict] | None = None,
                 live: pathlib.Path | None = None,
                 live_runs: pathlib.Path | None = None,
                 live_idle_s: float = LIVE_IDLE_S,
                 live_stale_s: float = LIVE_STALE_S):
        self.lock = threading.RLock()
        self.pl = Playlist(cells)
        self.recordings = recordings or []
        #: 收據頁：key → book。**順序就是找的順序**：錄影自己的配對收據、真跑、最後才是
        #: `--pack` 那一份（`/viewer.html`）。反正只轉鏈頭相等的那一份，順序只影響
        #: 「兩份都有同一條鏈」時轉去哪一頁。
        self.books: dict[str, dict] = {}
        for b in books or []:
            self.books.setdefault(b["key"], b)
        self.out = out
        self.dwell = dwell
        self.base_url = base_url.rstrip("/")
        #: 🔴 觀眾掃的那個 QR 指的地方（與 `base_url` 是兩件事，不要合併）。
        self.visitor_url = visitor_url.rstrip("/")
        #: `/control` 的共享密鑰。空字串＝沒有門檻。
        self.token = token
        # 排程攤平成一條確定性的清單：同一對先扣住、再寫明，然後換下一對。
        self.flat: list[tuple[int, str]] = []
        for i, pr in enumerate(self.pl.pairs):
            for side in SIDES:
                if pr.get(side):
                    self.flat.append((i, side))
        self.cursor = 0
        self.pair_idx = 0
        self.n_emitted = 0
        self.laps = 0
        #: 已經寫進事件檔的最後一個 `ts`（毫秒）。重播與真跑共用，保證整個檔單調。
        self.last_ts_ms = 0
        self.now: dict | None = None
        self.last_control: dict | None = None
        self.skipped: list[dict] = []
        self.tamper: dict | None = None
        self.tamper_mono: float = 0.0
        self.deadline = time.monotonic() + dwell
        #: 正在重播的那一格還沒寫出去的事件：`(到期的 monotonic 秒, 電視事件)`。
        self.pending: deque[tuple[float, dict]] = deque()
        self.replay: dict | None = None
        self._truncate_deferred = False
        # ── 真跑 ───────────────────────────────────────────────────
        self.live_path = pathlib.Path(live) if live else None
        self.live_tail = lelib.Tail(self.live_path, start_at_end=True) if live else None
        #: 分身的旁註（`L.sidecar.jsonl`）：同樣從檔尾開始讀。
        self.live_side_tail = (lelib.Tail(sidecarlib.sidecar_path(self.live_path),
                                          start_at_end=True) if live else None)
        self.live_folder = (lelib.Folder(verify_url=self.verify_url("{cell}"),
                                         mode=tv.MODE_LIVE) if live else None)
        self.live_idle_s = live_idle_s
        self.live_stale_s = live_stale_s
        self.live_errors: list[str] = []
        #: 真跑那邊每一格的鏈頭（`/r/<cell>` 的判準也要看它）。
        self.live_heads: dict[str, str | None] = {}
        #: `--live-runs`：真跑那一次 `run_twin.py --out`。有它才能即時打包收據。
        self.live_runs = pathlib.Path(live_runs) if live_runs else None
        self.live_started_ms: dict[str, int] = {}          # run_id → run_started ts
        self.live_pending: dict[str, dict] = {}            # cell_id → 等打包的那一格
        self.live_cells: dict[str, dict] = {}              # cell_id → pack_cell()
        #: cell_id → `caller.task_kind`（現場看到的；分身那一格不打包收據）。
        self.live_kinds: dict[str, str] = {}
        self._was_live = False
        #: `counters` 的兩本帳（重播／現場分開數）。數的是**已經寫出去的**事件。
        self.tallies = {tv.MODE_REPLAY: lelib.Tally(), tv.MODE_LIVE: lelib.Tally()}
        self.out.parent.mkdir(parents=True, exist_ok=True)
        self.out.write_text("", encoding="utf-8")

    # ── 網址 ────────────────────────────────────────────────────
    def verify_url(self, cell_id: str) -> str:
        return f"{self.base_url}/r/{cell_id}"

    def phone_url(self, *, with_token: bool = True) -> str:
        """手機要連的那個網址。**`base_url` 是什麼，這裡就是什麼**。

        `with_token=False` 時**不帶 token**（`/state` 與 `/qr.png` 對非本機客戶端）。
        """
        base = f"{self.base_url}/phone.html"
        return f"{base}?t={self.token}" if (with_token and self.token) else base

    def qr_target(self, *, with_token: bool = True) -> str:
        """**QR 裡到底編什麼。** 設了 `--visitor-url` ⇒ 就是它，**而且不附 token**。"""
        if self.visitor_url:
            return self.visitor_url
        return self.phone_url(with_token=with_token)

    # ── 收據頁 ──────────────────────────────────────────────────
    def _shown_head(self, cell_id: str) -> str | None:
        """電視上（或稽核分頁上）這一格指的是哪一跑：那一跑 ON 的 `verdict_hash`。"""
        n = self.now or {}
        if n.get("cell_id") == cell_id and "verdict_hash" in n:
            return n["verdict_hash"]
        c = self.pl.cells.get(cell_id)
        if c is not None:
            return c.get("verdict_hash")
        return self.live_heads.get(cell_id)

    @staticmethod
    def book_url(key: str) -> str:
        return "/viewer.html" if not key else f"/v/{key}.html"

    def receipt_target(self, cell_id: str) -> tuple[str | None, str | None]:
        """`/r/<cell>` 要轉去哪一頁。回 `(網址, None)` 或 `(None, 為什麼不行)`（誠實邊界 2）。"""
        head = self._shown_head(cell_id)
        having = [b for b in self.books.values() if cell_id in b["heads"]]
        live_cell = (cell_id in self.live_heads
                     and cell_id not in self.pl.cells) or \
            ((self.now or {}).get("cell_id") == cell_id
             and (self.now or {}).get("mode") == tv.MODE_LIVE)
        if self.live_kinds.get(cell_id) == tv.KIND_PRACTICAL and cell_id not in self.pl.cells:
            return None, PRACTICAL_NO_RECEIPT_PAGE
        if head is None:
            if live_cell and cell_id in self.live_pending:
                return None, "這一跑剛結束，收據還在打包（等 run_twin 寫完這一格）"
            return None, "這一跑沒有簽收據（或還沒跑完）：沒有鏈可以帶你去驗"
        for b in having:
            if b["heads"][cell_id] == head:
                return self.book_url(b["key"]) + f"#cell={cell_id}", None
        if live_cell:
            if self.live_runs is None:
                return None, ("這是現場真跑的一格；沒有給 --live-runs，"
                              "展場機不知道它的 run 目錄在哪，收據沒有打包進收據頁")
            if cell_id in self.live_pending:
                return None, "這一跑剛結束，收據還在打包（等 run_twin 寫完這一格）"
            return None, "這一格的收據沒有打包成功（原因在 /state.live.errors）"
        if not having:
            return None, "收據頁裡沒有這一格（這份錄影沒有配對收據，或配對沒過綁定）"
        return None, ("電視上演的這一跑，鏈頭與收據頁內嵌的那一條不同"
                      "（錄影或真跑是另一次）。不帶你去看另一跑的收據。")

    def receipt_why_not(self, cell_id: str) -> str | None:
        return self.receipt_target(cell_id)[1]

    def book_html(self, key: str) -> bytes | None:
        """那一份收據頁：同一份 `twin_viewer.html`，只換內嵌的 `twin-pack`。"""
        with self.lock:
            b = self.books.get(key)
            if b is None:
                return None
            if b["html"] is None:
                b["html"] = build_viewer.with_pack(
                    VIEWER.read_text(encoding="utf-8"), b["pack_text"]).encode("utf-8")
            return b["html"]

    def _try_pack_live(self) -> None:
        """真跑那一格跑完 ⇒ 從 `--live-runs` 的 run 目錄即時打包收據。

        只收**鏈頭＝`run_ended.verdict_hash`** 的那一份；`twin_cell.json` 要是
        這一跑開始之後才寫的（`built_ms`），不然讀到的可能是上一次的格子。
        """
        if self.live_runs is None or not self.live_pending:
            return
        now_mono = time.monotonic()
        changed = False
        for cid, p in list(self.live_pending.items()):
            run_dir = self.live_runs / "runs" / cid
            meta = run_dir / "twin_cell.json"
            try:
                fresh = (meta.exists() and int(json.loads(
                    meta.read_text(encoding="utf-8")).get("built_ms") or 0)
                    >= p["since_ms"])
            except (OSError, ValueError):
                fresh = False
            if not fresh:
                if now_mono > p["deadline"]:
                    del self.live_pending[cid]
                    self.live_errors.append(
                        f"{cid}：等了 {LIVE_PACK_WAIT_S:g} 秒 run_twin 還沒寫完這一格，"
                        "收據沒有打包")
                continue
            del self.live_pending[cid]
            try:
                cell = packlib.pack_cell(run_dir)
            except Exception as e:  # noqa: BLE001 — 打包壞了要說出來，不准弄死展場
                self.live_errors.append(f"{cid}：打包收據失敗 {type(e).__name__}: {e}")
                continue
            head = pairlib.chain_head(cell)
            if head != p["head"]:
                self.live_errors.append(
                    f"{cid}：run 目錄裡的鏈頭與這一跑的 verdict_hash 不同，不收")
                continue
            self.live_cells[cid] = cell
            changed = True
        if changed:
            pack = packlib.assemble(list(self.live_cells.values()),
                                    runs_label="（現場真跑；run 目錄在展場機上）")
            text = pairlib.dumps(pack).strip("\n")
            leaks = [x for x in pairlib.PATH_LEAKS if x in text]
            if leaks:
                self.live_errors.append(f"現場收據裡有建置機路徑 {leaks}，不上收據頁")
                return
            self.books[LIVE_BOOK] = book(LIVE_BOOK, pack, label="現場真跑", text=text)

    # ── 寫檔 ────────────────────────────────────────────────────
    def _write(self, evs: list[dict]) -> None:
        """追加到事件檔。每一筆讓累計變了的事件後面緊接一筆 `counters`（真實值）。"""
        if not evs:
            return
        evs = lelib.with_counters(evs, self.tallies)
        with self.out.open("a", encoding="utf-8") as fh:
            for e in evs:
                fh.write(json.dumps(e, ensure_ascii=False, sort_keys=True) + "\n")

    def pump(self) -> int:
        """把到期的重播事件寫出去。回寫了幾筆。"""
        with self.lock:
            t = time.monotonic()
            due = []
            while self.pending and self.pending[0][0] <= t:
                due.append(self.pending.popleft()[1])
            self._write(due)
            if self.replay is not None:
                self.replay["written"] += len(due)
                self.replay["pending"] = len(self.pending)
            return len(due)

    def flush(self) -> int:
        """快轉：正在重播的那一格剩下的事件**全部**寫出去。

        換格、切到真跑、截檔之前都要先做這件事——開了沒 verdict 的格子
        會讓電視的佇列卡死（`tv_contract` 規則 6）。
        """
        with self.lock:
            rest = [e for _, e in self.pending]
            self.pending.clear()
            self._write(rest)
            if self.replay is not None:
                self.replay["written"] += len(rest)
                self.replay["pending"] = 0
                if rest:
                    self.replay["fast_forwarded"] = len(rest)
            return len(rest)

    def _plan(self, cell: dict) -> tuple[list[tuple[float, dict]], dict]:
        """整格錄影過一次 `Folder`（mode 寫死 replay），排好每一筆的播出時刻。"""
        seg = cell["segment"]
        t0 = seg[0]["ts_ms"] if seg else 0
        span = cell.get("span_ms") or 0
        budget = self.dwell * REPLAY_FILL * 1000.0
        ratio = 1.0 if span <= budget or span <= 0 else budget / span
        start = max(self.last_ts_ms + 1, now_ms())
        folder = lelib.Folder(verify_url=self.verify_url("{cell}"),
                              mode=tv.MODE_REPLAY)
        folder.floor(self.last_ts_ms)
        planned: list[tuple[float, dict]] = []
        for ev in seg:
            off = int((ev["ts_ms"] - t0) * ratio)
            for e in folder.feed(dict(ev, ts_ms=start + off)):
                planned.append((off / 1000.0, e))
        info = {
            "cell_id": cell["cell_id"], "recording": cell["recording"],
            "span_s": round(span / 1000.0, 3),
            "played_span_s": round(span * ratio / 1000.0, 3),
            "budget_s": round(budget / 1000.0, 3),
            # 壓縮比 ≤ 1：1＝原速；0.2＝五倍速。
            "compress": round(ratio, 6),
            "speedup": round(1.0 / ratio, 3) if ratio > 0 else None,
            "events": len(planned), "written": 0, "pending": len(planned),
            "last_ms": folder.last_ms,
        }
        return planned, info

    def emit(self, cell_id: str, *, why: str) -> dict:
        """開播一格。**整格過不了契約自檢就不播，而且講明原因**（D2）。"""
        with self.lock:
            self.flush()
            cell = self.pl.cells[cell_id]
            planned, info = self._plan(cell)
            bad = tv.validate([e for _, e in planned])
            if not planned:
                bad = ["錄影裡這一格一筆能轉成電視事件的都沒有"]
            if bad:
                prev = next((s for s in self.skipped if s["cell_id"] == cell_id), None)
                if prev:
                    prev["times"] += 1
                    prev["at"] = iso_now()
                    rec = prev
                else:
                    rec = {"cell_id": cell_id, "reason": bad[:4], "at": iso_now(),
                           "recording": cell["recording"], "times": 1}
                    self.skipped.append(rec)
                self.deadline = time.monotonic() + self.dwell
                return {"ok": False, "skipped": rec}
            t0 = time.monotonic()
            self.pending = deque((t0 + off, e) for off, e in planned)
            self.last_ts_ms = info.pop("last_ms")
            self.replay = info
            self.pump()
            self.n_emitted += 1
            self.now = {
                "cell_id": cell_id,
                "resident": cell.get("resident"),
                "task_id": cell.get("task_id"),
                "task_kind": cell.get("task_kind") or tv.KIND_CODE,
                # 錄下來的分身那一格（`task_kind=practical`）也不套反事實那兩顆鍵的字。
                **({"side": None, "side_text": PRACTICAL_SIDE_TEXT,
                    "side_label": PRACTICAL_SIDE_LABEL}
                   if cell.get("task_kind") == tv.KIND_PRACTICAL else
                   {"side": cell["side"], "side_text": SIDE_TEXT[cell["side"]],
                    "side_label": SIDE_LABEL[cell["side"]]}),
                "evidence": cell.get("evidence"),
                "evidence_note": packlib.EVIDENCE_TEXT.get(cell.get("evidence") or "", ""),
                "exit_code": cell.get("exit_code"),
                "stop_reason": cell.get("stop_reason"),
                "attempts_used": cell.get("attempts_used"),
                "receipt_url": self.verify_url(cell_id),
                "verdict_hash": cell.get("verdict_hash"),
                "mode": tv.MODE_REPLAY,
                "recording": cell["recording"],
                "why": why,
                "at": iso_now(),
                "n": self.n_emitted,
            }
            # 人按出來的那一格停久一點：輪播 20 秒就把他的選擇蓋掉 ＝ 白按。
            self.deadline = time.monotonic() + (
                max(self.dwell, HOLD_AFTER_PRESS_S) if why.startswith("phone")
                else self.dwell)
            self.now["receipt_available"] = self.receipt_why_not(cell_id) is None
            self._expire_tamper(cell_id)
            return {"ok": True, "now": self.now}

    # ── 排程 ────────────────────────────────────────────────────
    def advance(self) -> dict:
        """輪播：同一對先扣住、再寫明，然後換下一對。一圈播完截檔重來。"""
        with self.lock:
            if not self.flat:
                return {"ok": False, "skipped": {"reason": ["排程裡一格可播的都沒有"]}}
            if self.cursor >= len(self.flat):
                self.cursor = 0
                self._lap()
            i, side = self.flat[self.cursor]
            self.cursor += 1
            self.pair_idx = i
            return self.emit(self.pl.pair(i)[side], why="autoplay")

    def _seek(self, pair_idx: int) -> None:
        self.pair_idx = pair_idx % max(1, len(self.pl.pairs))
        for n, (i, _side) in enumerate(self.flat):
            if i == self.pair_idx:
                self.cursor = n
                return

    def _lap(self) -> None:
        """一圈播完：截掉事件檔（不讓檔案一整天無限長，D3）。

        ⚠ **截檔在新的一圈開頭**，而且上一格要**已經寫完**：還有沒寫的就先快轉、
        這一圈先不截（下一圈再截）——截掉一格剛寫出去的 verdict，電視那一格
        就永遠等不到收尾。
        """
        self.laps += 1
        if self.pending:
            self.flush()
            self._truncate_deferred = True
            return
        self._truncate_deferred = False
        self.out.write_text("", encoding="utf-8")

    # ── 真跑 ────────────────────────────────────────────────────
    def live_active(self) -> bool:
        tail = self.live_tail
        if tail is None or tail.last_line_mono is None:
            return False
        age = time.monotonic() - tail.last_line_mono
        if tail.open_runs and age < self.live_stale_s:
            return True
        return age < self.live_idle_s

    def poll_live(self) -> int:
        """tail `--live` 檔，轉出來的事件接在事件檔後面。回寫了幾筆。"""
        if self.live_tail is None:
            return 0
        with self.lock:
            # 先 lifecycle 後旁註：同一輪裡 OFF 的 run_ended 要先進 Folder，
            # 它的 postaudit 才綁得上。
            lines = self.live_tail.poll() + self.live_side_tail.poll()
            if not lines:
                return 0
            # 規則 1：先把正在重播的那一格快轉寫完，再接真跑。
            self.flush()
            self.live_folder.floor(self.last_ts_ms)
            new: list[dict] = []
            for ev in lines:
                try:
                    got = self.live_folder.feed(ev)
                except lelib.SchemaMismatch as e:
                    self.live_errors.append(str(e))
                    continue
                new.extend(got)
                if ev.get("type") == "run_started" and ev.get("arm") == packlib.ARM:
                    caller = ev.get("caller") or {}
                    cid = caller.get("cell_id") or ev["task_id"]
                    kind = caller.get("task_kind") or tv.KIND_CODE
                    self.live_kinds[cid] = kind
                    practical = kind == tv.KIND_PRACTICAL
                    side = caller.get("stratum") if caller.get("stratum") in SIDES \
                        else "held"
                    self.n_emitted += 1
                    self.live_started_ms[ev["run_id"]] = ev["ts_ms"]
                    self.now = {
                        "cell_id": cid, "resident": caller.get("resident"),
                        "task_id": caller.get("task_id") or ev["task_id"],
                        "task_kind": kind,
                        # 分身那一格沒有「告訴它名字／不告訴它名字」這回事。
                        "side": None if practical else side,
                        "side_text": PRACTICAL_SIDE_TEXT if practical else SIDE_TEXT[side],
                        "side_label": (PRACTICAL_SIDE_LABEL if practical
                                       else SIDE_LABEL[side]),
                        "evidence": None,
                        "evidence_note": "跑完才推得出來（要看這一跑實際經過中介幾通）",
                        "exit_code": None, "stop_reason": None, "attempts_used": None,
                        "receipt_url": self.verify_url(cid),
                        "receipt_available": False, "verdict_hash": None,
                        "mode": tv.MODE_LIVE, "recording": None,
                        "why": "live", "at": iso_now(), "n": self.n_emitted,
                    }
                    self._expire_tamper(cid)
                elif ev.get("type") == "run_ended" and ev.get("arm") == packlib.ARM:
                    run = self.live_folder.runs.get(ev["run_id"]) or {}
                    cid = run.get("cell_id")
                    if cid:
                        self.live_heads[cid] = ev.get("verdict_hash")
                        # 分身那一格不在 --live-runs 底下（見模組 docstring），不等它。
                        if ev.get("verdict_hash") and self.live_runs is not None \
                                and self.live_kinds.get(cid) != tv.KIND_PRACTICAL:
                            self.live_pending[cid] = {
                                "head": ev["verdict_hash"],
                                "since_ms": self.live_started_ms.get(ev["run_id"], 0),
                                "deadline": time.monotonic() + LIVE_PACK_WAIT_S}
                    if self.now and self.now.get("cell_id") == cid:
                        self.now.update({
                            "exit_code": exit_code_of(ev),
                            "stop_reason": ev.get("stop_reason"),
                            "attempts_used": ev.get("attempts_used"),
                            "evidence": packlib.evidence_level(
                                requests_seen=int(ev.get("requests_seen") or 0),
                                declared=run.get("declared_evidence") or ""),
                            "verdict_hash": ev.get("verdict_hash"),
                        })
                        self.now["receipt_available"] = \
                            self.receipt_why_not(cid) is None
            if self.live_folder.dropped:
                # 綁不上的旁註不發（不猜），但要講出來。
                self.live_errors.extend("旁註沒轉：" + d for d in self.live_folder.dropped)
                self.live_folder.dropped.clear()
            # 現場的東西一定是新的 ⇒ task_kind 一定要帶（缺席只給舊錄影）。
            bad = tv.validate(new, require_settled=False, require_task_kind=True)
            if bad:
                # 違反契約的東西不准上電視；記下來，/state 看得到。
                self.live_errors.extend(bad[:4])
                return 0
            self._write(new)
            self.last_ts_ms = max(self.last_ts_ms, self.live_folder.last_ms)
            return len(new)

    def tick(self) -> None:
        """無人值守的那一拍（`autoplay` 每 0.2 秒叫一次）。切換規則見模組 docstring。"""
        with self.lock:
            self.poll_live()
            self._try_pack_live()
            if self.now and self.now.get("mode") == tv.MODE_LIVE \
                    and not self.now.get("receipt_available"):
                self.now["receipt_available"] = \
                    self.receipt_why_not(self.now["cell_id"]) is None
            if self.live_active():
                self._was_live = True
                return
            if self._was_live:
                # 真跑閒下來了 ⇒ 馬上回到輪播，從游標原本的位置接下去。
                self._was_live = False
                self.deadline = time.monotonic()
            self.pump()
            if time.monotonic() >= self.deadline:
                self.advance()

    # ── 手機 ────────────────────────────────────────────────────
    def press(self, action: str, **kw) -> dict:
        """手機按鍵。回傳的東西會直接進 `/state`，手機拿來更新自己的畫面。"""
        with self.lock:
            self.last_control = {"action": action, "at": iso_now(), **kw}
            if action in SIDES + ("next", "resume") and self.live_active():
                return {"ok": False,
                        "error": "現在正在真跑：真跑優先，重播暫停。"
                                 f"它閒下來（最後一行之後 {self.live_idle_s:g} 秒）"
                                 "輪播會自己回來。"}
            if action in SIDES:
                cid = kw.get("cell_id") or self.pl.cell_id(self.pair_idx, action)
                if not cid or cid not in self.pl.cells:
                    # 這一對只跑過一邊。**不給按**，而且說出來。
                    return {"ok": False, "error": f"這一對沒有 {action} 那一邊"}
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
                if not cid:
                    return {"ok": False, "error": "還沒有一格可以翻"}
                why_not = self.receipt_why_not(cid)
                if why_not:
                    return {"ok": False, "error": why_not}
                self.tamper_mono = time.monotonic()
                self.tamper = {
                    "cell_id": cid,
                    "at": iso_now(),
                    "ttl_s": TAMPER_TTL_S,
                    "url": self.verify_url(cid) + "?tamper=1",
                    # ⚠ 誠實邊界 3：這裡不宣告任何驗證結果。
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
        """翻位元的狀態自己會過期（超過 TTL，或電視換格了）。"""
        if not self.tamper:
            return
        if time.monotonic() - self.tamper_mono > TAMPER_TTL_S:
            self.tamper = None
            self.tamper_mono = 0.0
            return
        if playing and self.tamper.get("cell_id") != playing:
            self.tamper = None
            self.tamper_mono = 0.0

    def mode(self) -> str:
        return tv.MODE_LIVE if self.live_active() else tv.MODE_REPLAY

    def state(self, *, with_token: bool = True) -> dict:
        with self.lock:
            self._expire_tamper((self.now or {}).get("cell_id"))
            pair = self.pl.pair(self.pair_idx)
            mode = self.mode()
            tail = self.live_tail
            live = None
            if tail is not None:
                age = (None if tail.last_line_mono is None
                       else round(time.monotonic() - tail.last_line_mono, 1))
                live = {"path": _rel(self.live_path), "active": mode == tv.MODE_LIVE,
                        "open_runs": len(tail.open_runs), "lines": tail.n_lines,
                        "last_line_age_s": age, "idle_s": self.live_idle_s,
                        "stale_s": self.live_stale_s, "errors": self.live_errors[-8:],
                        "runs": _rel(self.live_runs) if self.live_runs else None,
                        "receipts_packed": sorted(self.live_cells),
                        "receipts_pending": sorted(self.live_pending)}
            honesty = [
                "事件流沒有簽章。可驗的那一份是收據頁，它在你自己的瀏覽器裡重算。",
                "這台電視不驗簽章，所以它不會告訴你簽章對不對。",
                "AI 有沒有真的動手，看每一格的證據等級：L-none＝交件是腳本寫的，"
                "不是 AI 做的。",
            ]
            if mode == tv.MODE_REPLAY:
                honesty.insert(0, "現在播的是重播：錄下來的事件，照原本的先後與相對間隔"
                                  "壓縮播放（壓縮比在 /state.replay）。"
                                  "這條線上此刻一通 AI 都沒有打。")
            else:
                honesty.insert(0, "現在播的是現場：這一跑此刻正在進行，事件一發生就送上來。")
            return {
                "v": 2,
                "at": iso_now(),
                "mode": mode,
                "now": self.now,
                "replay": self.replay,
                "live": live,
                "switch_rule": ("有真跑（看得到還沒結束的一跑，或最後一行不到 "
                                f"{self.live_idle_s:g} 秒）就先播真跑、輪播暫停；"
                                "真跑閒下來就回到錄影輪播。"
                                if tail is not None else "沒有 --live：只播錄影。"),
                "pair": {
                    **pair,
                    "paired": bool(pair.get("held") and pair.get("pc")),
                    "index": self.pair_idx % max(1, len(self.pl.pairs)),
                    "of": len(self.pl.pairs),
                },
                "buttons": [
                    {"action": "held", "label": SIDE_LABEL["held"],
                     "text": SIDE_TEXT["held"], "cell_id": pair.get("held")},
                    {"action": "pc", "label": SIDE_LABEL["pc"],
                     "text": SIDE_TEXT["pc"], "cell_id": pair.get("pc")},
                    # ⚠ 措辭：這裡**不准預告結果**。
                    {"action": "tamper", "label": "自己驗一次收據",
                     "text": "把收據裡的一個字改掉，看它自己算出對不上",
                     "cell_id": ((self.now or {}).get("cell_id")
                                 if (self.now or {}).get("receipt_available") else None)},
                ],
                "tamper": self.tamper,
                "last_control": self.last_control,
                "skipped": self.skipped,
                "emitted": self.n_emitted,
                "laps": self.laps,
                "dwell_s": self.dwell,
                "replay_fill": REPLAY_FILL,
                "next_in_s": round(max(0.0, self.deadline - time.monotonic()), 1),
                "phone_url": self.phone_url(with_token=with_token),
                "visitor_url": self.visitor_url,
                "qr_target": self.qr_target(with_token=with_token),
                "qr_url": f"{self.base_url}/qr.png",
                "control_token_required": bool(self.token),
                "evidence_counts": self.evidence_counts(),
                "pairs": self.pl.pairs,
                # 整批格子的**原值**。⚠ 不准由 `side` 反推收下沒。
                "cells": [
                    {"cell_id": c["cell_id"], "resident": c.get("resident"),
                     "task_id": c.get("task_id"), "side": c["side"],
                     "exit_code": c.get("exit_code"), "evidence": c.get("evidence"),
                     "stop_reason": c.get("stop_reason"),
                     "attempts_used": c.get("attempts_used"),
                     "recording": c["recording"],
                     "receipt_url": f"/r/{c['cell_id']}",
                     "receipt_available": self.receipt_why_not(c["cell_id"]) is None}
                    for c in sorted(self.pl.cells.values(), key=lambda c: c["cell_id"])
                ],
                "recordings": self.recordings,
                "receipt_pages": [
                    {"key": b["key"], "url": self.book_url(b["key"]),
                     "label": b["label"], "cells": len(b["heads"])}
                    for b in self.books.values()],
                "source": {
                    "recordings": [r["path"] for r in self.recordings if r["accepted"]],
                    "live": _rel(self.live_path) if self.live_path else None,
                    "note": "電視事件只有一個產生者：live_events.Folder 吃 "
                            "vacant.lifecycle/1。沒有從 run 目錄事後推的第二條路。",
                },
                "honesty": honesty,
            }

    def evidence_counts(self) -> dict:
        out: dict[str, int] = {}
        for c in self.pl.cells.values():
            k = c.get("evidence") or "unsettled"
            out[k] = out.get(k, 0) + 1
        return dict(sorted(out.items()))


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
<p class="note">重播錄下來的事件，或轉播正在進行的真跑（/state 的 mode 會講是哪一種）。重播時這台機器一通模型都不打。</p>
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
    server_version = "serve_twin/2"

    @property
    def token(self) -> str:
        """單一真相來源是 `Stage.token`，不要在 Handler 上再存一份。"""
        return self.stage.token if self.stage else ""

    def _is_same_machine(self) -> bool:
        """請求是不是從**這台機器自己**來的（電視就是這種）。

        判準是「這條連線的對端位址 ＝ 本端位址」，不是「對端是 127.0.0.1」：
        電視連的是這台機器的區網位址，只看 loopback 會把電視自己擋在外面。
        ⚠ 這不是安全邊界，是**不要把 token 白送出去**的一道分流。
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
            url = st.qr_target(with_token=self._is_same_machine())
            try:
                if path.endswith(".svg"):
                    self._send(200, qrlib.to_svg(url).encode("utf-8"),
                               "image/svg+xml; charset=utf-8")
                else:
                    self._send(200, qrlib.to_png(url, scale=8), "image/png")
            except ValueError as e:
                # 網址太長畫不出來 ⇒ **明講**，不要吐一張掃不開的圖。
                self._json({"error": str(e), "url": url}, 500)
        elif path == "/viewer.html":
            self._file(VIEWER, "text/html; charset=utf-8")
        elif path == "/phone.html":
            self._file(PHONE, "text/html; charset=utf-8")
        elif path.startswith("/v/") and path.endswith(".html"):
            html = st.book_html(path[3:-len(".html")])
            if html is None:
                self._json({"error": "沒有這一份收據頁", "path": path}, 404)
            else:
                self._send(200, html, "text/html; charset=utf-8")
        elif path.startswith("/r/"):
            cell = path[3:]
            url, why_not = st.receipt_target(cell)
            if why_not:
                # 誠實邊界 2：不把觀眾帶去看另一跑的收據。
                self._json({"error": why_not, "cell_id": cell}, 404)
                return
            # `#` 之後的東西不會送到伺服器，所以收據頁要吃的是 fragment。
            self.send_response(302)
            self.send_header("Location",
                             url + ("&tamper=1" if "tamper=1" in query else ""))
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
            # 三個地方都收：body（手機頁）、query string（curl）、header（反向代理）。
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
        stage.tick()
        stop.wait(0.2)


def make_server(recordings, *, bind: str, port: int, out: pathlib.Path,
                dwell: float, token: str = "", quiet: bool = False,
                base_url: str = "", visitor_url: str = DEFAULT_VISITOR_URL,
                pack: dict | None = None, live: pathlib.Path | None = None,
                live_runs: pathlib.Path | None = None,
                live_idle_s: float = LIVE_IDLE_S, live_stale_s: float = LIVE_STALE_S,
                ) -> tuple[ThreadingHTTPServer, Stage]:
    """`recordings`＝lifecycle 錄影檔的路徑清單（旁邊有 `X.pack.json` 就一併載入）。
    `pack`＝`/viewer.html` 那一份（舊資料包）。`live_runs`＝真跑的 `run_twin --out`。"""
    cells, info = load_recordings(recordings)
    books, rstatus = load_receipt_books(recordings)
    for r in info:
        r["receipts"] = rstatus.get(r["path"])
    if pack:
        books.append(book("", pack, label="--pack（/viewer.html）"))
    srv = ThreadingHTTPServer((bind, port), Handler)
    host = bind if bind not in ("0.0.0.0", "") else "127.0.0.1"
    stage = Stage(cells, out=out, dwell=dwell, token=token,
                  base_url=base_url or f"http://{host}:{srv.server_address[1]}",
                  visitor_url=visitor_url, recordings=info,
                  books=books, live=live, live_runs=live_runs,
                  live_idle_s=live_idle_s, live_stale_s=live_stale_s)
    Handler.stage = stage
    Handler.quiet = quiet
    return srv, stage


#: 非 loopback 綁定卻沒給 `--token` 時，自動生一把的長度（bytes → urlsafe base64）。
AUTO_TOKEN_BYTES = 9


def resolve_token(bind: str, token: str, no_token: bool) -> tuple[str, str]:
    """決定這一次要不要有 token，以及是誰決定的。

    回 `(token, why)`，`why` ∈ {`"given"`, `"auto"`, `"off-loopback"`,
    `"off-explicit"`}。規則：明確給了就用；`--no-token` 就沒有；只綁 loopback
    就沒有；其他（展場的 `--bind 0.0.0.0`）**自動生一把**。
    為什麼是自動生不是拒絕啟動：`decisions/DECISION_20260919_EXHIBIT_UNATTENDED.md` §一。
    """
    if token:
        return token, "given"
    if no_token:
        return "", "off-explicit"
    if bind in ("127.0.0.1", "::1", "localhost", ""):
        return "", "off-loopback"
    return secrets.token_urlsafe(AUTO_TOKEN_BYTES), "auto"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="展場機上的展件伺服器：重播 lifecycle 錄影／轉播真跑（零依賴、離線）")
    ap.add_argument("--recording", action="append", default=None, metavar="LIFECYCLE.jsonl",
                    help="要重播的 lifecycle 錄影（可給多次）。"
                         f"不給＝{_rel(RECORDINGS_DIR)}/*.jsonl 全部")
    ap.add_argument("--live", default=None, metavar="LIFECYCLE.jsonl",
                    help="tail 正在真跑的 lifecycle 檔；有真跑就先播真跑")
    ap.add_argument("--live-runs", default=None, metavar="RUN_TWIN_OUT",
                    help="真跑那一次 run_twin.py 的 --out；給了才能即時打包那一格的收據")
    ap.add_argument("--live-idle", type=float, default=LIVE_IDLE_S,
                    help="真跑最後一行之後幾秒回到錄影輪播")
    ap.add_argument("--live-stale", type=float, default=LIVE_STALE_S,
                    help="一跑開著卻這麼久沒有新行 ⇒ 當它死了，回到輪播")
    ap.add_argument("--pack", default=str(DEFAULT_PACK),
                    help="收據頁那一份資料包（只給 /r/<cell> 判斷能不能帶去收據頁）")
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
                         "傳空字串就退回舊行為（QR 指導播頁 phone.html）")
    ap.add_argument("--check", action="store_true",
                    help="只驗錄影（lifecycle 契約＋電視契約），不起伺服器。0＝全過")
    ap.add_argument("--new", action="store_true",
                    help="和 --check 一起用：剛錄的錄影，每一格都要帶 task_kind"
                         "（缺席只給 2026-09-24 之前的舊錄影）")
    a = ap.parse_args(argv)

    recs = [pathlib.Path(p) for p in a.recording] if a.recording else default_recordings()
    if a.check:
        if not recs:
            print(f"✗ 沒有任何錄影（{_rel(RECORDINGS_DIR)}/*.jsonl 是空的）", file=sys.stderr)
            return 1
        n_bad = 0
        for p in recs:
            bad = check_recording(p, require_task_kind=a.new)
            n_bad += bool(bad)
            paired = pairlib.pair_path(p).exists()
            print(("✓ " if not bad else "✗ ") + _rel(p)
                  + ("（配對收據綁定過）" if paired and not bad else "")
                  + ("" if not bad else "：" + "；".join(bad[:3])),
                  file=sys.stdout if not bad else sys.stderr)
            if not paired:
                print(f"! {_rel(p)} 沒有配對收據（{pairlib.pair_path(p).name}）："
                      "播它的時候 /r/<cell> 會一律 404")
        return 1 if n_bad else 0
    pack_path = pathlib.Path(a.pack) if a.pack else None
    pack = (json.loads(pack_path.read_text(encoding="utf-8"))
            if pack_path and pack_path.exists() else None)
    out = pathlib.Path(a.out) if a.out else TWIN / "live" / "events.jsonl"
    token, why = resolve_token(a.bind, a.token, a.no_token)
    srv, stage = make_server(recs, bind=a.bind, port=a.port, out=out,
                             dwell=a.dwell, token=token, base_url=a.base_url,
                             visitor_url=a.visitor_url, pack=pack,
                             live=pathlib.Path(a.live) if a.live else None,
                             live_runs=pathlib.Path(a.live_runs) if a.live_runs else None,
                             live_idle_s=a.live_idle, live_stale_s=a.live_stale)
    for r in stage.recordings:
        mark = "✓" if r["accepted"] else "✗"
        print(f"  {mark} 錄影 {r['path']}：{r['cells']} 格、{r['lines']} 行"
              + ("" if not r["problems"] else f"；{r['problems'][0]}"))
    if not stage.flat and not a.live:
        srv.server_close()
        print("拒絕啟動：沒有任何一格可以重播，也沒有 --live。"
              f"先跑 {_rel(TWIN / 'record_fixture.sh')} 產生錄影，或用 --recording 指一份。",
              file=sys.stderr)
        return 2
    stop = threading.Event()
    threading.Thread(target=autoplay, args=(stage, stop), daemon=True).start()
    host = a.bind if a.bind != "0.0.0.0" else "127.0.0.1"
    print(f"展件伺服器 http://{host}:{srv.server_address[1]}/")
    print(f"  手機頁   {stage.phone_url()}")
    print(f"  QR       {stage.base_url}/qr.png（執行期畫的）")
    print(f"  電視接法 world3/index.html?live=http://{host}:"
          f"{srv.server_address[1]}/live/events.jsonl&poll=2000")
    print(f"  {len(stage.pl.pairs)} 對、{len(stage.pl.cells)} 格、{a.dwell:g} 秒輪播一格"
          f"（重播壓進 {a.dwell * REPLAY_FILL:g} 秒內）")
    if a.live:
        print(f"  --live {a.live}：有真跑就先播真跑（閒置 {a.live_idle:g} 秒回到重播）")
    for b in stage.books.values():
        print(f"  收據頁 {stage.book_url(b['key'])}：{len(b['heads'])} 格（{b['label']}）")
    for r in stage.recordings:
        rs = r.get("receipts") or {}
        if not rs.get("accepted"):
            print(f"  ⚠ {r['path']} 的格子沒有收據頁：{(rs.get('problems') or ['?'])[0]}")
    print("  ⚠ 這一支不驗簽章也不宣告驗證結果：可驗的那一份是收據頁（/r/<cell_id>）")
    if why == "auto":
        print(f"  ✓ /control 的 token（這次開機自動生的）：{token}")
        print("    它已經編進上面那一行手機頁的網址與 QR 裡。**重開就會換一把。**")
        print("    ⚠ 看得到電視的人都按得動——這不是身分驗證。")
    elif why == "given":
        print("  ✓ /control 要 token（`--token` 指定的），已編進手機頁的網址與 QR")
    elif why == "off-explicit" and a.bind != "127.0.0.1":
        print("  ⚠⚠ `--no-token` ＋ 非 loopback 綁定："
              "**同一個區網上的任何人都按得動這台電視**。")
    if a.bind == "0.0.0.0" and "127.0.0.1" in stage.base_url:
        print("  ⚠ 綁在 0.0.0.0 但 --base-url 還是 127.0.0.1："
              "QR 會指到手機自己的迴路位址，掃了一定連不到。用 --base-url 給區網 IP。")
    if stage.flat:
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
