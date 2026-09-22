"""twin/twinlink — 把「觀眾手機 → 公網 → 資料庫 → 1003 → 現場螢幕」這條鏈接起來。

## 這支在架構裡承重什麼

2026-09-20 之前，這條鏈**斷在中間**：`vacant-world-cloud`（Zeabur）收得到卡，
`vacant_hm/world3/bridge.js` 也讀得到 `/api/queue`——但

* 雲端是**原地覆寫**的（`queued→claimed→done` 蓋同一個檔）、**沒掛 volume 就歸零**，
* `bridge.js` 的狀態全在**瀏覽器記憶體**（那支自己寫「展場一天一開機，不需要持久化」），
* **1003（GPU 那台）完全不在這條鏈上**——world3 演的是 371 筆凍結重放，一通模型都不打。

所以「觀眾生的那張卡」既沒有落盤的真相來源，也從來沒有真的餵給模型。這一支補那一段。

```
 觀眾手機 ──▶ vacant-world.cosmopig.com ──ingest──▶ twinstore.sqlite3 ──generate──▶ 1003 LM Studio
  (公網)         郵箱：會覆寫、會歸零          唯讀抄寫   真相來源：append-only     本機/區網算力
                        ▲                                    │  │
                        └────────── publish（盡力而為）───────┘  └── export/serve ──▶ 現場螢幕
```

## 離線紅線怎麼守（CLAUDE.md 展場硬約束 2）

| 斷掉的東西 | 展場還能不能跑 | 退化成什麼 |
|---|---|---|
| 公網（Zeabur 連不上） | **能** | `ingest`／`publish` 停，各記一列 `ingest_gap`／`error`；已經進庫的分身照常生成、照常上螢幕。**新觀眾投不進來**——但那本來就需要網路（觀眾要用自己的 AI）。 |
| 1003（模型連不上） | **能** | `generate` 退到 `fallback_deterministic`：純查表、零模型、微秒級。**畫面上標的 engine 會跟著變**，不准把退化講成真跑。 |
| 兩個都斷 | **能** | 螢幕讀 `export` 出來的本機 JSON，演已經在庫裡的分身。 |

**真相來源永遠是本機那個 SQLite**，不是雲端。這是刻意的：雲端會歸零，展場不能。

## 誠實邊界（改碼時保留）

1. **`publish` 失敗不是錯誤路徑，是常態。** 展場斷網時它會一直失敗，
   而那**不影響現場**——現場讀的是本機。失敗記一列 `error` 就好，不要重試到卡死。
2. **`engine` 欄位不是裝飾。** `lmstudio:<model>` ＝ 真的有一顆模型回了話；
   `fallback_deterministic` ＝ 查表湊出來的。畫面上兩者要分得出來，
   把後者講成前者就是鐵律 5 的展場版本。
3. **`ingest` 讀不到的不算 0。** 雲端 4xx/5xx/逾時一律記 `ingest_gap`，
   `pulled` 欄位寫 `null` 不寫 0——「沒量到」跟「量到是零」是兩件事。
4b. **一張卡的問題不可以變成整個展場的問題（2026-09-20 演練後加上）。**
   `ingest`／`generate` 對**卡層級**的例外（`CARD_LEVEL_ERRORS`）記一列 `error`
   然後做下一張；**`sqlite3` 的例外刻意不吞**——真相來源壞掉（磁碟滿、庫毀）
   要讓 loop 大聲死掉，不可以假裝成「跳過一張卡」而空轉一整天。
   ⚠ 這不是「畸形卡都處理好了」：它保證的是**別人的卡照樣上得了螢幕**，
   那張壞卡本身還是沒有分身（`error` 事件留著，可以事後查）。
   演練＋負控制：`ops/exhibit/twin/resilience_check.sh` 第 6 節。

5. **`export` 出來的不是「全部的人」，是「現在該上螢幕的人」（2026-09-21 加上）。**
   視窗（`--recent`）與退役是**展場的策展決定**，不是資料保留政策：
   `counts.total` 才是整場來過幾位，帳本上一列都沒有少。
   ⚠ **退役 ≠ 刪除，不准混講。** 刪除是撤回路徑
   （`decisions/DECISION_20260921_TWIN_CONSENT_AND_ERASURE.md`）那件事。

6. **「螢幕演過他了」我們量不到。** 退役事件裡的 `screen_confirmed` 寫死 `null`：
   `twinlink` 只知道自己把誰放進 JSON，不知道電視有沒有真的演。
   要變成 `true` 得等電視那端回報（見同一份報告的「另一側需要配合什麼」）。
   **沒量到寫 `null` 不寫 `false`。**

7. **`--db` 指到不存在的路徑 ⇒ 拒絕，不建空庫（2026-09-22 加上）。**
   `export`／`view`／`serve`／`loop` 找不到那個 SQLite 就回 `rc 5` 並說為什麼。
   在這之前它會**安靜地建一張空庫**、寫出 `people: []` 的 visitors.json、
   回 `rc 0`——於是「我沒找到庫」跟「今天沒有人來」在畫面上與退出碼上
   都長得一模一樣。要真的開新場地就明講 `--init`。
   ⚠ 寫入路徑（`ingest`／`generate`／`publish`／`withdraw`）**不擋**：
     第一次布展本來就會把庫建出來，而它們回報的是「抄了幾筆」不是「螢幕上有誰」。

8. **`people` 的順序依「觀眾按下送出的時間」，不是我們抄寫的順序。**
   排序鍵是 `submitted` payload 裡的 `ts`（雲端伺服器時鐘）。
   細節與四條誠實邊界在 `_stage_times` 的長註解；做不到的部分逐條列在
   `window.guarantee_limits` 裡，**不要只留那句漂亮的保證**。

4. **`/api/queue` 這條路會漏件。** 它只回 `status='queued'`，電視那端一 claim
   就看不到了。要不漏就得走 `/api/all`（本次新增，唯讀、不 claim）。
   雲端還沒部署到有 `/api/all` 的版本時，這一支會**明講自己走的是會漏的那條路**
   （`mode: "queue_lossy"`），不會假裝抄全了。

用法：
    python3 ops/exhibit/twin/twinlink.py selftest                 # 離線自檢＋負控制
    python3 ops/exhibit/twin/twinlink.py ingest   --cloud URL --token T
    python3 ops/exhibit/twin/twinlink.py generate --endpoint http://100.119.113.56:1234/v1
    python3 ops/exhibit/twin/twinlink.py publish  --cloud URL --token T
    python3 ops/exhibit/twin/twinlink.py export   --out live/visitors.json --recent 60
    python3 ops/exhibit/twin/twinlink.py --init export --out live/visitors.json
                                                  # 第一次布展才用：准它建一張空庫
    python3 ops/exhibit/twin/twinlink.py serve    --port 8901      # 唯讀
    python3 ops/exhibit/twin/twinlink.py serve    --port 8901 --allow-withdraw
    python3 ops/exhibit/twin/twinlink.py withdraw --id <sub_id>   # 紙本撤回走這條
    python3 ops/exhibit/twin/twinlink.py loop     --cloud URL --token T --endpoint ...

## 螢幕上該有誰（`--recent`／退役，2026-09-21）

第七天任何一次重整，電視原本會**從第一天的第一個人重演**：`build_view()` 回整個
roster 沒有上限，而 `bridge.js` 的 `seenIds` 在記憶體裡、每次載入都是空的。
300 人 × 每人 30 秒 ＝ 剛投完卡的觀眾要等 **2.5 小時**才看得到自己。

這一支這一側的解法是三件事，細節與數字的由來見第 4 節的長註解：

* `people` 依**觀眾按下送出的時間**新到舊排序 ⇒ 冷啟動先演現在在場的人
  （**這一項不需要電視配合**）；
* `--recent N`（預設 60）＋ `arriving`／`fresh` 分級 ⇒ **最後一位投卡的人在
  `people[0]`**，`N` 再小都擠不掉他。做不到的那幾件事逐條寫在
  `window.guarantee_limits`（誠實邊界 8）；
* 掉出視窗的人**寫一列退役事件上鏈**，並在 `retirement.retiring[]` 掛 180 秒，
  讓電視演得出退場（展覽設計 §5.1-7「要給結束一個形狀」）。
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Iterable

HERE = pathlib.Path(__file__).resolve()
TWIN = HERE.parent
sys.path.insert(0, str(TWIN.parents[2]))

from ops.exhibit.twin import twinvault  # noqa: E402
from ops.exhibit.twin.twinstore import (  # noqa: E402
    DEFAULT_DB, KIND_ERASED, KIND_ERROR, KIND_GENERATED, KIND_INGEST_GAP,
    KIND_NOTE, KIND_PUBLISHED, KIND_SUBMITTED, KIND_WITHDRAWN, TwinStore,
)

DEFAULT_CLOUD = "https://vacant-world.cosmopig.com"

#: **模型端點的候選，依「離線紅線」由強到弱排序。**
#:
#: 🔴 2026-09-20 實測釐清的拓樸：**展場搬去的那台實體機器就是 1003（Windows），
#:    而 `vacant-dev` 是跑在它上面的 VMware 虛擬機**（`systemd-detect-virt` ⇒ `vmware`、
#:    `ens33` 在 `192.168.76.135/24`、閘道 `192.168.76.2`）。
#:    ⇒ VM 打 `192.168.76.1:1234`（VMware 主機介面，MAC OUI `00:50:56:c0:`）
#:      與打 Tailscale 的 `100.119.113.56:1234` **回傳逐 byte 相同**
#:      （負控制：1004 的回應不同 ⇒ 這個比法有鑑別力）。
#:
#: ⚠ **為什麼順序很重要**：人類 2026-09-20 澄清展場**會有網路**（他要遠端桌面進 1003），
#:    所以這裡**不是**在解離線紅線。理由比那個窄，但仍然成立：
#:    Tailscale 是一個**額外的、會自己壞掉的依賴**（要聯絡 coordination server、
#:    會 relay、會換 IP），而主機介面是同一台實體機器內的虛擬網段。
#:    同一個後端，少一層中間人 ⇒ 少一種展期中途壞掉的方式。
#:    ⚠ **不要把這段讀成「展場離線可跑」**——那句話要靠整條鏈都在本機，不是靠這個順序。
ENDPOINT_CANDIDATES: tuple[tuple[str, str, bool], ...] = (
    ("http://127.0.0.1:1234/v1", "本機（模型就跑在這台）", False),
    ("http://192.168.76.1:1234/v1", "VMware 主機介面（同一台實體機器，不出機殼）", False),
    ("http://100.119.113.56:1234/v1", "1003 走 Tailscale（**需要網路**）", True),
)

#: 最後手段。⚠ `ssh 1003` 這個別名會解析到假位址，一律用 IP（量具說謊紀錄）。
DEFAULT_ENDPOINT = ENDPOINT_CANDIDATES[-1][0]


def resolve_endpoint(explicit: str | None = None, *, timeout: float = 3.0,
                     probe: bool = True) -> dict:
    """挑一個模型端點，並**說清楚是怎麼挑的**。

    回 `{"url", "how", "label", "needs_network", "reachable", "tried"}`。

    ⚠ **三態**：一個都探不到時 `reachable` 落 **`None`** 而不是 `False`——
      「探不到」與「探到是壞的」是兩件事，而且沒有 probe 時我們根本沒量。
      這種情況仍然回最後一個候選（讓呼叫端自己去撞真正的錯誤訊息），
      **但 `reachable=None` 會一路寫進事件流**，事後查得出來那一跑是瞎猜的。
    """
    if explicit:
        return {"url": explicit, "how": "explicit", "label": "呼叫端指定",
                "needs_network": None, "reachable": None, "tried": []}
    env = os.environ.get("VACANT_TWIN_ENDPOINT", "").strip()
    if env:
        return {"url": env, "how": "env:VACANT_TWIN_ENDPOINT", "label": "環境變數",
                "needs_network": None, "reachable": None, "tried": []}
    tried = []
    for url, label, needs_net in ENDPOINT_CANDIDATES:
        if not probe:
            break
        try:
            with urllib.request.urlopen(
                    url.rstrip("/") + "/models", timeout=timeout) as r:
                ok = 200 <= r.status < 300
        except Exception as exc:                      # noqa: BLE001
            tried.append({"url": url, "ok": False, "err": type(exc).__name__})
            continue
        tried.append({"url": url, "ok": ok})
        if ok:
            return {"url": url, "how": "probed", "label": label,
                    "needs_network": needs_net, "reachable": True, "tried": tried}
    last = ENDPOINT_CANDIDATES[-1]
    return {"url": last[0], "how": "fallback_unprobed" if not probe else "none_reachable",
            "label": last[1], "needs_network": last[2],
            "reachable": None, "tried": tried}
DEFAULT_MODEL = "gemma-4-12b-it-qat"

#: ⚠ **不要調小。** 1003 的後端是 thinking 模式：實測（2026-09-20）一發 26-token
#: 的 prompt，`max_tokens=300` 之下 completion 289 個 token 裡 **266 個是 reasoning**，
#: `content` 回空字串。額度要先養活思考，答案才吐得出來。
MAX_TOKENS = 2400

#: ⚠ **固定額度不夠，因為思考長度是變動的。** 同一支 prompt 兩次實跑，
#: reasoning 分別用掉 1462 與 **1597** token——`MAX_TOKENS=1600` 第一次過、
#: 第二次 `content` 空。把數字調大只是把懸崖往後推，不是修好。
#: 所以改成**偵測特徵再升額重試一次**：`content` 空 ＋ reasoning 幾乎把額度用完
#: ⇒ 那就是被思考擠掉的，不是模型不會照格式回話（這兩者要改的東西完全不同）。
ESCALATE_RATIO = 0.85   # reasoning_tokens ≥ 額度 × 這個比例 ⇒ 判定為被擠掉
ESCALATE_FACTOR = 3     # 重試時把額度乘這麼多倍

#: ⚠ **90 秒不夠。** 2026-09-20 實測：三張卡裡有一張在 1003 上 `TimeoutError`。
#: thinking 一發要一萬多個 reasoning token，而「被擠掉就升額重試」讓最壞情況
#: 變成 (1+ESCALATE_FACTOR) 倍；1003 同時在跑別的東西時更慢。
#: 這個數字**不是展場的互動延遲**——觀眾是非同步輪詢自己的手機，
#: 不是站著等這一發回來（那條線是 `fallback_deterministic`，微秒級）。
DEFAULT_GEN_TIMEOUT = 300.0


#: 卡上的枚舉。跟 `vacant-world-cloud/server.js` 同一份，改一邊要改兩邊。
SHAPES = ("圓潤", "修長", "厚實", "小巧", "粗獷", "方正")
TEXTURES = ("光滑", "指紋", "斑駁", "絨面")
COLORS = ("暖土", "赭紅", "奶油", "灰藍", "苔綠", "沙金")

#: 🔴 鐵律 1（KS-1）：prompt 模板禁止「你有責任／會被懲罰」類措辭。
#: 這一支的 prompt 不是實驗臂，但同一條線不給例外——`assert_ks1_clean` 可執行。
KS1_FORBIDDEN = ("你有責任", "會被懲罰", "受到懲罰", "你必須負責", "後果自負")


def assert_ks1_clean(text: str) -> None:
    """KS-1 可執行防呆。命中就炸，不要繞過。"""
    for bad in KS1_FORBIDDEN:
        if bad in text:
            raise ValueError(f"KS-1 違規：prompt 含禁語 {bad!r}")


#: 🔴 **一張卡的問題，不可以變成整個展場的問題。**
#: 這幾類例外＝「這一張卡本身有毛病」：跳過它、記一列 `error`、做下一張。
#: **`sqlite3` 的例外刻意不在裡面**——那是真相來源壞了（磁碟滿、庫毀），
#: 吞成「跳過一張卡」會讓 loop 空轉一整天而沒有人知道。那種要讓它炸出去。
#: 演練見 `ops/exhibit/twin/resilience_check.sh` 第 5、6 節。
CARD_LEVEL_ERRORS = (
    ValueError, TypeError, AttributeError, KeyError, IndexError,
    UnicodeError, OverflowError, json.JSONDecodeError,
)


def _safe_text(x: Any, limit: int = 300) -> str:
    """把任何東西變成**一定存得進事件流**的字串。

    ⚠ 為什麼需要：卡的內容可能含落單代理對（lone surrogate）——
    `json.loads('"\\ud800"')` 就會產生一個，而 Node 的 `JSON.stringify`
    會原樣逃脫回去，所以它穿得過整條雲端鏈路。那種字串 `encode("utf-8")`
    會炸，而雜湊鏈算的就是那個 encode。**連「記下這張卡壞掉」都會炸**，
    所以錯誤訊息本身要先洗過。
    """
    s = str(x).encode("utf-8", "replace").decode("utf-8", "replace")
    return s[:limit]


def _usable_sub_id(sid: Any) -> bool:
    """這個 id 拿得去當 `sub_id` 嗎（`TwinStore.append` 的前提）。"""
    return isinstance(sid, str) and bool(sid) and "\n" not in sid


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _subject_secrets(store: TwinStore, sub_id: str, *,
                     card: Any = None, card_text: Any = None) -> list[str]:
    """這位主體**不准出現在事件流裡**的字串（卡上的原文、生成的句子）。

    nonce 不在裡面：它從來不會出現在例外訊息裡，而讀它要多開一個檔。
    """
    objs: list[Any] = [{"card": card, "card_text": card_text}]
    objs.append(store.vault.open_card(sub_id) or {})
    objs.append(store.vault.open_twin(sub_id) or {})
    return twinvault.secrets_for(*objs)


def _append_error(store: TwinStore, sub_id: str, ev: dict[str, Any], *,
                  source: str, secrets: Iterable[str],
                  safe_reason: str) -> dict[str, Any]:
    """記一列 `error`——**錯誤事件本身也是上鏈的，所以它也要過原文那把尺。**

    ⚠ 為什麼需要這一層：例外訊息會逐字夾帶內容。
    `canonical_bytes` 炸在某個字元上就把那個字元印出來；雲端回的錯誤 body
    可能原樣回貼我們剛送過去的句子。把那種訊息寫進 append-only 鏈，
    等於從**錯誤路徑**把原文漏上鏈——而那一列一樣刪不掉。

    過不了尺就換成不含內容的固定說法（`reason_redacted=True`，
    **不是靜靜吞掉**：事後查得出來這裡遮過東西）。
    """
    try:
        twinvault.assert_payload_clean(ev, secrets, kind=KIND_ERROR)
    except twinvault.GUARD_ERRORS:
        ev = {"step": ev.get("step"), "reason": safe_reason,
              "reason_redacted": True, "at": _now()}
    return store.append(KIND_ERROR, sub_id, ev, source=source)


def _http_json(url: str, payload: Any = None, timeout: float = 30.0,
               headers: dict[str, str] | None = None) -> tuple[int, Any]:
    """回 `(status, parsed)`。**不吞例外**——連不上就往上丟，呼叫端決定怎麼記。"""
    data = None
    hdr = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        hdr["Content-Type"] = "application/json"
    hdr.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=hdr,
                                 method="POST" if data else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8", "replace")
        try:
            return r.status, json.loads(raw)
        except json.JSONDecodeError:
            return r.status, raw


# ---------------------------------------------------------------------------
# 1. ingest —— 雲端郵箱 → 本機真相來源
# ---------------------------------------------------------------------------

def ingest(store: TwinStore, cloud: str, token: str,
           timeout: float = 30.0) -> dict[str, Any]:
    """把雲端的投稿抄進本機。**唯讀抄寫：不 claim、不改雲端任何狀態**——
    claim 是電視那一端（`bridge.js`）的事，我們搶了它就看不到觀眾的卡。"""
    cloud = cloud.rstrip("/")
    mode = "all"
    url = f"{cloud}/api/all?token={urllib.parse.quote(token)}"
    try:
        status, body = _http_json(url, timeout=timeout)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            # 雲端還是舊版（沒有 /api/all）。退到 /api/queue——
            # 但那條路**會漏掉電視已經 claim 的件**，所以要講明白。
            mode = "queue_lossy"
            url = f"{cloud}/api/queue?token={urllib.parse.quote(token)}&since=0"
            try:
                status, body = _http_json(url, timeout=timeout)
            except Exception as e2:  # noqa: BLE001
                return _ingest_gap(store, cloud, f"{type(e2).__name__}: {e2}", mode)
        else:
            return _ingest_gap(store, cloud, f"HTTP {e.code}", mode)
    except Exception as e:  # noqa: BLE001
        return _ingest_gap(store, cloud, f"{type(e).__name__}: {e}", mode)

    items = (body or {}).get("items") if isinstance(body, dict) else None
    if not isinstance(items, list):
        return _ingest_gap(store, cloud, f"回應沒有 items 陣列：{body!r:.200}", mode)

    known = set(store.sub_ids())
    new, rejected = 0, 0
    for it in items:
        if not isinstance(it, dict):
            continue
        sid = it.get("id")
        if not isinstance(sid, str) or not sid or sid in known:
            continue
        if _usable_sub_id(sid) and _rejected_before(store, sid):
            continue   # 這張卡上一輪就記過「壞掉」了，不要每輪再記一次
        try:
            # 🔴 原文**不進 payload**。封印：原文與 nonce 落到鏈外的檔案庫，
            #    鏈上只留 commitment。`append_sealed` 會先跑兩層可執行防呆
            #    （結構閘門 ＋ `consent.assert_no_plaintext`）再寫。
            payload, secs = store.vault.seal_card(
                sid, it.get("card"), it.get("card_text"),
                ts=it.get("ts"), cloud_status=it.get("status"))
            twinvault.append_sealed(store, KIND_SUBMITTED, sid, payload, secs,
                                    source=f"cloud:{cloud}", what="card")
        except twinvault.GUARD_ERRORS as e:
            # 防呆擋下來 ⇒ **這一列不進鏈**（append-only，寧可少一張卡也不要
            # 寫進去就拿不掉）。理由寫成固定分類，**不要回貼例外訊息**——
            # 那個訊息可能含原文，而錯誤事件本身也是上鏈的。
            rejected += 1
            known.add(sid)
            store.append(KIND_ERROR, sid if _usable_sub_id(sid) else "_ingest", {
                "step": "ingest",
                "reason": "封印防呆擋下這張卡：payload 不合格，沒有寫進鏈",
                "guard": type(e).__name__,
                "vault_copy_kept": True,
                "cloud": cloud, "at": _now(),
            }, source=f"cloud:{cloud}")
            continue
        except CARD_LEVEL_ERRORS as e:
            # 🔴 一張卡進不來，不可以讓 loop 死掉。展場沒有人守著，
            # loop 一死是**所有人**的卡都不再上螢幕（演練 §6 的乾淨鄰居卡
            # 在修這段之前拿不到分身）。壞卡記一列 error，繼續做下一張。
            rejected += 1
            known.add(sid)
            _append_error(store, sid if _usable_sub_id(sid) else "_ingest", {
                "step": "ingest",
                "reason": f"{type(e).__name__}: {_safe_text(e)}",
                "rejected_id": _safe_text(sid, 120),
                "cloud": cloud, "at": _now(),
            }, source=f"cloud:{cloud}",
                secrets=_subject_secrets(store, sid, card=it.get("card"),
                                         card_text=it.get("card_text")),
                safe_reason=f"{type(e).__name__}（訊息夾帶了卡上的內容，不上鏈）")
            continue
        known.add(sid)
        new += 1
    return {"ok": True, "mode": mode, "seen": len(items), "pulled": new,
            "rejected": rejected, "lossy": mode == "queue_lossy"}


def _rejected_before(store: TwinStore, sid: str) -> bool:
    """這張卡上一輪就被記成「進不來」了嗎？

    走 `sub_id` 索引，所以是 O(這張卡的事件數) 不是 O(全庫)——
    不然斷網一整天之後每一輪都要掃幾十萬列。
    ⚠ 誠實邊界：id 本身不合法（含換行、空字串）的那種卡記在 `_ingest` 名下，
    **查不到**，於是每一輪各記一列。那是有上限的（壞卡張數×輪數），但不是零。
    """
    for e in store.events(sub_id=sid, kind=KIND_ERROR):
        if (e.get("payload") or {}).get("step") == "ingest":
            return True
    return False


def _ingest_gap(store: TwinStore, cloud: str, reason: str, mode: str) -> dict[str, Any]:
    """漏收要留痕。**`pulled` 寫 `null` 不寫 0**——沒量到不是量到零。"""
    store.append(KIND_INGEST_GAP, "_ingest", {
        "reason": reason, "cloud": cloud, "mode": mode, "at": _now(),
    }, source=f"cloud:{cloud}")
    return {"ok": False, "mode": mode, "seen": None, "pulled": None,
            "reason": reason, "lossy": True}


# ---------------------------------------------------------------------------
# 2. generate —— 真相來源 → 1003 的模型 → 真相來源
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "你是一個剛抵達「Vacant 世界」的居民。有人用一張卡把你描述出來，"
    "你要用那張卡上的氣質說話。規則：\n"
    "1. 只輸出 JSON，不要有任何其他文字、不要 markdown 圍欄。\n"
    "2. JSON 有三個鍵：arrival、working、handover，每個值都是一句中文，各不超過 30 字。\n"
    "3. arrival＝你睜開眼睛看到這個世界的第一句話。\n"
    "4. working＝你正要動手做那件事時說的一句話。\n"
    "5. handover＝你把做完的東西交出去時說的一句話。\n"
    "6. 不要自稱 AI、不要提到模型或提示詞、不要用「作為一個…」開頭。"
)


def build_prompt(card: dict[str, Any] | None, card_text: str | None) -> str:
    c = card or {}
    lines = ["這是那張卡："]
    for label, key in (("需求", "need"), ("形狀", "shape"), ("質感", "texture"),
                       ("色系", "color"), ("氣質", "vibe"), ("第一句話", "first_line")):
        v = c.get(key)
        lines.append(f"{label}：{v if v else '（沒填）'}")
    if not any(c.get(k) for k in ("need", "shape", "texture", "color", "vibe")) and card_text:
        lines.append("（欄位沒解析出來，原文如下）")
        lines.append(str(card_text)[:600])
    p = "\n".join(lines)
    assert_ks1_clean(p)
    return p


def _parse_model_json(text: str) -> dict[str, str] | None:
    """模型很愛包 ```json 圍欄或前後加廢話。抓第一個平衡的大括號區塊。"""
    if not isinstance(text, str):
        return None
    s = text.strip()
    start = s.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(s)):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(s[start:i + 1])
                except json.JSONDecodeError:
                    return None
                if not isinstance(obj, dict):
                    return None
                out = {k: str(obj[k]).strip() for k in ("arrival", "working", "handover")
                       if isinstance(obj.get(k), (str, int, float))}
                return out if len(out) == 3 and all(out.values()) else None
    return None


def fallback_twin(card: dict[str, Any] | None) -> dict[str, Any]:
    """零模型、零網路、微秒級的退路。**標明 engine，不准冒充真跑。**

    展場斷網或 1003 關機時，畫面仍然有東西可演——但它是查表湊的，
    畫面上必須讀得出差別（CLAUDE.md 展場硬約束 1 的同一條紀律）。
    """
    # ⚠ 這裡**不可以假設 card 是 dict、欄位是 str**。這一支是失效路徑：
    # 走到這裡的時候 1003 已經不通了，而「卡的形狀不對」在那一刻才第一次
    # 被碰到——`{"need": 123}` 會讓 `.strip()` 炸，然後炸穿 generate、炸掉
    # 整個 loop。實測（resilience_check.sh §6 modeldown）就是這樣死的：
    # 模型活著時一切正常，模型一斷才整支倒下去，最壞的時機。
    c = card if isinstance(card, dict) else {}
    def _f(key: str, dflt: str = "") -> str:
        v = c.get(key)
        return _safe_text(v, 600).strip() if v not in (None, "") else dflt
    need = _f("need", "一件還沒做完的小事")
    vibe = _f("vibe")
    shape = _f("shape", "圓潤")
    color = _f("color", "暖土")
    first = _f("first_line")
    return {
        "arrival": first or f"我是{shape}的那一個，{color}色。這裡就是那個世界嗎？",
        "working": f"讓我試試「{need[:18]}」。" + (f"（{vibe[:12]}）" if vibe else ""),
        "handover": "做完了，你看看對不對。",
        "engine": "fallback_deterministic",
        "model": None,
        "latency_ms": 0,
    }


def _call_model(prompt: str, endpoint: str, model: str, budget: int,
                timeout: float) -> dict[str, Any]:
    """打一發。回 `{parsed, text, usage 幾個數字}`，**不做任何退化判斷**——
    要不要退化是 `generate_one` 的事，這裡只負責誠實回報拿到什麼。"""
    url = endpoint.rstrip("/") + "/chat/completions"
    t0 = time.time()
    status, body = _http_json(url, {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.8,
        "max_tokens": budget,
    }, timeout=timeout)
    # 🔴 **LM Studio 的錯誤是用 HTTP 200 ＋ `{"error": …}` 回的**，不是 4xx。
    #    實測 2026-09-22：端點少打 `/v1` ⇒ `POST …:1234/chat/completions`
    #    ⇒ `status=200`、`body={"error":"Unexpected endpoint or method."}`、178ms。
    #    沒有這一段的話，下游看到的是「沒有 choices ⇒ content 空」，
    #    於是把它判成 `empty_content`，收據上寫「thinking 吃光額度」——
    #    **一個指向完全錯誤方向的診斷**。展場那天有人照著它去查 thinking 設定，
    #    會查一整晚，而真正要改的是一個路徑後綴。
    #    ⚠ 這三件事疊起來才是真正的危險：**靜默**（200）＋**怪錯人**（收據）
    #      ＋**不可逆**（`pending()` 排除已有 generated 事件的卡 ⇒ 救不回來）。
    api_err = (body or {}).get("error") if isinstance(body, dict) else None
    choice = ((body or {}).get("choices") or [{}])[0]
    msg = choice.get("message", {}) or {}
    usage = (body or {}).get("usage") or {}
    text = msg.get("content", "")
    return {
        # `None` ＝ 這一層沒話說（正常回應）；有字串 ＝ API 明確回報的錯誤。
        # **不要寫空字串**——空字串會被下游讀成「有錯但沒訊息」。
        "api_error": (api_err if isinstance(api_err, str)
                      else (json.dumps(api_err, ensure_ascii=False)
                            if api_err is not None else None)),
        "http_status": status,
        # ⚠ **API 自己說的那句「我撞到天花板了」。** `"length"` ＝ 輸出被切掉。
        #    沒有它的話，「思考把 JSON 吐到一半就沒了」會長得像「模型不會照格式回話」，
        #    而這兩者要改的東西完全不同（前者加額度、後者改 prompt）。
        "finish_reason": choice.get("finish_reason"),
        "parsed": _parse_model_json(text),
        "text": text,
        "budget": budget,
        "latency_ms": int((time.time() - t0) * 1000),
        "reasoning_tokens": (usage.get("completion_tokens_details") or {}).get("reasoning_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "reasoning_chars": len(str(msg.get("reasoning_content") or "")),
    }


def _squeezed_out(r: dict[str, Any]) -> bool:
    """這一發是不是「答案被思考擠掉」？

    判準要兩個條件同時成立，不是只看 content 空：
    `content` 空 **而且** reasoning 幾乎把額度用完。只看前者會把
    「模型真的沒話說」也判成這個，升額重試就白花一次機時。
    """
    # 🔴 **撞到天花板就是被擠掉，不管 content 是空的還是被切一半。**
    #    2026-09-22 實跑抓到：一張卡 reasoning 用掉 2326／2400（97%），
    #    JSON 吐到一半就沒了 ⇒ `parsed is None`、但 `text` 有字
    #    ⇒ 舊判準第一行就 `return False` ⇒ **不升額**
    #    ⇒ 32 秒機時白花、觀眾永久拿到查表版（`pending()` 不會再撿它）。
    #    「content 空」與「content 被截斷」是**同一個病的兩種長相**，
    #    而 `finish_reason == "length"` 是 API 自己講出來的那句話。
    #    ⚠ 這個函式只在 `parsed is None` 時被問，所以這裡不會誤殺解析得出來的回應。
    if r.get("finish_reason") == "length":
        return True
    if str(r.get("text") or "").strip():
        return False
    rt = r.get("reasoning_tokens")
    if not isinstance(rt, int):
        return False   # 量不到就不要猜——沒量到不等於成立
    return rt >= r["budget"] * ESCALATE_RATIO


def generate_one(card: dict[str, Any] | None, card_text: str | None,
                 endpoint: str, model: str, timeout: float = DEFAULT_GEN_TIMEOUT,
                 allow_fallback: bool = True) -> dict[str, Any]:
    t0 = time.time()
    try:
        # ⚠ `build_prompt` 要在 try **裡面**。它在外面的時候，一張
        # `card` 不是物件的卡（雲端回 `"card": "整理桌面"`）會在這裡
        # 直接 AttributeError 炸穿整個 loop——**連 fallback 都走不到**，
        # 而 fallback 存在的全部意義就是「出事了也要有東西上螢幕」。
        prompt = build_prompt(card, card_text)
        r = _call_model(prompt, endpoint, model, MAX_TOKENS, timeout)
        escalated = False
        if r["parsed"] is None and _squeezed_out(r):
            # 只重試一次。重試無限次會讓展場在模型壞掉時卡死，
            # 而 fallback 本來就在後面接著。
            escalated = True
            r = _call_model(prompt, endpoint, model,
                            MAX_TOKENS * ESCALATE_FACTOR, timeout)

        if r["parsed"] is None and r.get("api_error"):
            # API 層就回錯了——**這不是模型的問題，不准怪到 thinking 頭上**。
            why = (f"API 回報錯誤（HTTP {r.get('http_status')}）：{r['api_error']}"
                   f"｜端點={endpoint}"
                   + ("　🔴 端點少了 `/v1`？候選端點都長這樣："
                      f"{ENDPOINT_CANDIDATES[0][0]}"
                      if not str(endpoint).rstrip('/').endswith('/v1') else ""))
            if not allow_fallback:
                raise ValueError(why)
            out = fallback_twin(card)
            out["engine"] = "fallback_deterministic"
            out["degraded_from"] = f"lmstudio:{model}"
            out["degrade_kind"] = "api_error"      # ← **不是** empty_content
            out["degrade_reason"] = why
            out["latency_ms"] = int((time.time() - t0) * 1000)
            out["reasoning_tokens"] = r["reasoning_tokens"]
            out["budget_escalated"] = False
            return out

        if r["parsed"] is None:
            # 講清楚是「空的」還是「有字但格式不對」——兩者要修的東西不同。
            why = (f"模型 content 是空的（thinking 吃光額度；"
                   f"reasoning_tokens={r['reasoning_tokens']}／budget={r['budget']}"
                   f"{'，已升額重試過' if escalated else ''}）"
                   if not str(r["text"]).strip()
                   else f"模型回應解析不出 arrival/working/handover：{str(r['text'])[:200]!r}")
            if not allow_fallback:
                raise ValueError(why)
            out = fallback_twin(card)
            out["engine"] = "fallback_deterministic"
            out["degraded_from"] = f"lmstudio:{model}"
            # 🔴 `degrade_reason` 夾帶模型原始回應（可能逐字複誦卡上的字）
            #    ⇒ **它不上鏈**，只有 `degrade_kind` 上鏈（`twinvault` 檔頭 5）。
            out["degrade_kind"] = ("empty_content" if not str(r["text"]).strip()
                                   else "unparseable")
            out["degrade_reason"] = why
            out["latency_ms"] = int((time.time() - t0) * 1000)
            out["reasoning_tokens"] = r["reasoning_tokens"]
            out["budget_escalated"] = escalated
            return out

        out = dict(r["parsed"])
        out.update({"engine": f"lmstudio:{model}", "model": model,
                    "latency_ms": int((time.time() - t0) * 1000),
                    "endpoint": endpoint, "raw_len": len(str(r["text"])),
                    # thinking 後端的實況留一份：日後換機器要比得出來
                    "reasoning_tokens": r["reasoning_tokens"],
                    "completion_tokens": r["completion_tokens"],
                    "reasoning_chars": r["reasoning_chars"],
                    "max_tokens": r["budget"],
                    # 🔴 升額重試過的那一發要留痕：它是**同一個模型的真回答**
                    # （不是退化），但「第一次被擠掉」本身是後端狀態的證據。
                    "budget_escalated": escalated})
        return out
    except Exception as e:  # noqa: BLE001
        if not allow_fallback:
            raise
        out = fallback_twin(card)
        out["degraded_from"] = f"lmstudio:{model}"
        out["degrade_kind"] = type(e).__name__
        out["degrade_reason"] = f"{type(e).__name__}: {e}"
        out["latency_ms"] = int((time.time() - t0) * 1000)
        return out


def _seal_generated(store: TwinStore, sid: str, twin: dict[str, Any],
                    source: str) -> dict[str, Any]:
    """把生成結果寫上鏈：**三句話進檔案庫，鏈上只有 commitment ＋量測欄位。**

    防呆擋下來的時候不是「跳過這張卡」——跳過的話 `pending()` 下一輪又撿它起來，
    展場一天就是幾萬次模型呼叫。改成退回**確定性 fallback**（零觀眾文字，
    一定過得了防呆）再封一次；連那個都過不了就是我們自己的碼壞了，讓它炸出去。
    """
    try:
        payload, secs = store.vault.seal_twin(sid, twin)
        return twinvault.append_sealed(store, KIND_GENERATED, sid, payload, secs,
                                       source=source, what="twin")
    except twinvault.GUARD_ERRORS as e:
        store.append(KIND_ERROR, sid, {
            "step": "generate_seal",
            "reason": "封印防呆擋下這份生成結果，改用確定性 fallback",
            "guard": type(e).__name__, "at": _now(),
        }, source="local:fallback")
        safe = fallback_twin(None)
        safe["degrade_kind"] = "seal_guard"
        payload, secs = store.vault.seal_twin(sid, safe)
        return twinvault.append_sealed(store, KIND_GENERATED, sid, payload, secs,
                                       source="local:fallback", what="twin")


def generate(store: TwinStore, endpoint: str = DEFAULT_ENDPOINT,
             model: str = DEFAULT_MODEL, limit: int = 0,
             timeout: float = DEFAULT_GEN_TIMEOUT,
             allow_fallback: bool = True) -> dict[str, Any]:
    todo = store.pending(KIND_GENERATED)
    # 撤回過的人不再生成。**不是過濾掉「看起來不想要的資料」**——
    # 是那個人已經說了「刪掉我」，再拿他的卡去打模型就是沒在聽。
    todo = [s for s in todo
            if (store.current(s) or {}).get("status") not in ("withdrawn", "erased")]
    if limit:
        todo = todo[:limit]
    done, degraded, failed = 0, 0, 0
    for sid in todo:
        cur = store.current(sid) or {}
        try:
            twin = generate_one(cur.get("card"), cur.get("card_text"),
                                endpoint, model, timeout, allow_fallback)
        except CARD_LEVEL_ERRORS as e:
            if not allow_fallback:
                raise      # 量測模式：要炸就讓它炸，不要偷偷補一張
            # 最後一道網。**照樣寫一列 generated**（engine 標退化）：
            # 不寫的話這張卡每一輪都會再被撿起來、再炸一次，展場一天下來
            # 就是幾萬列 error，而螢幕上始終少一個人。
            failed += 1
            _append_error(store, sid, {
                "step": "generate",
                "reason": f"{type(e).__name__}: {_safe_text(e)}", "at": _now(),
            }, source="local:fallback",
                secrets=_subject_secrets(store, sid),
                safe_reason=f"{type(e).__name__}（訊息夾帶了卡上的內容，不上鏈）")
            twin = fallback_twin(None)
            twin["degraded_from"] = f"lmstudio:{model}"
            twin["degrade_kind"] = type(e).__name__
            twin["degrade_reason"] = f"卡的內容算不出分身：{type(e).__name__}: {_safe_text(e, 120)}"
        if twin.get("engine") == "fallback_deterministic":
            degraded += 1
        _seal_generated(store, sid, twin,
                        f"1003:{endpoint}" if "lmstudio" in str(twin.get("engine"))
                        else "local:fallback")
        done += 1
    return {"ok": True, "generated": done, "degraded": degraded, "failed": failed,
            "remaining": len(store.pending(KIND_GENERATED))}


# ---------------------------------------------------------------------------
# 3. publish —— 真相來源 → 回寫雲端（盡力而為）
# ---------------------------------------------------------------------------

def publish(store: TwinStore, cloud: str, token: str,
            limit: int = 0, timeout: float = 30.0) -> dict[str, Any]:
    """把生成結果回寫雲端，讓觀眾的手機看得到。

    **失敗是常態不是事故**：展場斷網時這裡一路失敗，而現場完全不受影響
    （螢幕讀本機）。所以不重試到卡死，記一列 `error` 就往下一筆。
    """
    cloud = cloud.rstrip("/")
    todo = store.pending(KIND_PUBLISHED)
    # 撤回過的不回寫。雲端那一份我們刪不到（沒有 delete 路由，`twinvault`
    # 誠實邊界 2），但至少不要在人家說了「刪掉我」之後又送一份新的過去。
    todo = [s for s in todo
            if (store.current(s) or {}).get("generated_seq")
            and (store.current(s) or {}).get("status") not in ("withdrawn", "erased")]
    if limit:
        todo = todo[:limit]
    ok, fail = 0, 0
    for sid in todo:
        cur = store.current(sid) or {}
        twin = cur.get("twin") or {}
        verdict = twin.get("handover") or twin.get("arrival") or "（分身已抵達）"
        try:
            status, body = _http_json(f"{cloud}/api/result", {
                "token": token, "id": sid,
                "verdict": str(verdict)[:120],
                "matched": str(twin.get("working") or "")[:120],
            }, timeout=timeout)
            if status != 200:
                raise RuntimeError(f"HTTP {status}: {body!r:.160}")
            store.append(KIND_PUBLISHED, sid,
                         {"cloud": cloud, "http": status, "at": _now()},
                         source=f"cloud:{cloud}")
            ok += 1
        except Exception as e:  # noqa: BLE001
            _append_error(store, sid, {
                "step": "publish", "reason": f"{type(e).__name__}: {_safe_text(e)}",
                "cloud": cloud, "at": _now(),
            }, source=f"cloud:{cloud}",
                secrets=_subject_secrets(store, sid),
                safe_reason=f"{type(e).__name__}"
                            "（雲端回的訊息夾帶了分身的句子，不上鏈）")
            fail += 1
    return {"ok": fail == 0, "published": ok, "failed": fail,
            "note": "publish 失敗不影響現場：螢幕讀的是本機真相來源"}


# ---------------------------------------------------------------------------
# 4. export / serve —— 真相來源 → 現場螢幕
# ---------------------------------------------------------------------------
#
# 🔴 **為什麼這一節有一個「視窗」（2026-09-21 加上）**
#
# 在這之前 `build_view()` 回**整個 roster、沒有上限**，而電視那一端
# （`vacant_hm/world3/bridge.js`）用**記憶體內**的 `seenIds` 去重、
# `spawnQueue.shift()` 一次生一個、每人約 30 秒（**估計值**，見下面 `DEFAULT_RECENT`
# 的註解 1——程式裡沒有這個常數）。
# 兩件事湊起來的後果：
#
#   看門狗 reload／kiosk `Restart=always`／斷電／有人按 F5
#     ⇒ `seenIds` 清空 ⇒ **整個 roster 重新排隊**
#     ⇒ 第七天有 300 人時，剛投完卡的觀眾排在 300 個人後面 ≈ **2.5 小時**
#
# 不是崩潰，是排隊。**磁碟不是問題**（實測 600 人＝1MB、605 bytes/event、線性）。
#
# 這一節解的是「螢幕上該有誰」。它由三個東西構成，判準都是**觀眾體驗**：
#
# | 名字 | 是什麼 | 誰被它影響 |
# |---|---|---|
# | `--recent N` | 策展參數：世界裡同時「有人」的規模 | 環境感，不影響保證 |
# | 排序 newest-first | 冷啟動（reload／斷電）先演現在在場的人 | **修掉「從第一天第一個人重演」** |
# | `arriving`／`fresh` 分級 | 剛投卡的人要插隊（電視那端照這個欄位決定誰先上台） | 展件的核心體驗 |
#
# ⚠ **保證與 `N` 無關**：`people` 依**送出時間**新到舊排序，而 `shown = live[:k]`
#   且 `k ≥ 1` ⇒ 最後一位投卡的人在索引 0，`N` 再小都擠不掉他。`N` 只決定他後面
#   還跟著幾個人。判準在
#   `tests/test_twin_recent_window.py::test_the_person_who_just_submitted_is_first`
#   與 `::test_a_backlog_generated_now_cannot_bury_the_person_who_just_submitted`。
#
# 🔴 **這句話 2026-09-21 那一版是假的**，而且它被寫進產品 JSON 給展件讀。
#   當時排序鍵是 `generated_seq or submitted_seq`，而 seq 是**事件寫進本機的當下**
#   才指派的 ⇒ 斷線積壓的 50 張卡一補進來，剛投卡那位就掉到第 50 位。
#   根因、修法與**做不到的那四件事**寫在 `_stage_times` 的長註解與
#   `window.guarantee_limits`。不准再把它縮回一句漂亮的話。

#: 視窗大小的預設。**這是策展參數不是安全參數**（保證不靠它，見上）。
#:
#: 為什麼是 60：
#: 1. 螢幕節奏**估計** 30 秒／人。
#:    ⚠ **這是估計值，不是從程式裡抄來的常數**——查過了：電視那一端
#:    （`vacant_hm/world3/index.html`）一位訪客要走完 `startVisitor` →
#:    `visitor_spawn` → 成形 → `finishVisitor` 好幾個模式，**沒有一個
#:    「每人幾秒」的常數**可以引。（`exhibit_boot.sh --dwell 30` 看起來像，
#:    但那是 `serve_twin.py` 那個**另一個展件**的換格秒數，不是這條線。）
#:    所以下面推出來的 60 是**量級**不是精算；真要定得準，得去電視那端量
#:    「投卡到分身站上台」的實際秒數（見報告「另一側需要配合什麼」）。
#: 2. 冷啟動（reload／斷電／F5）時電視會把整個視窗重走一遍 ⇒ 60 × 30 秒 ＝ **30 分鐘**
#:    才把世界填滿。因為是 newest-first，觀眾在意的那幾位落在**第一分鐘**，
#:    30 分鐘是「世界長回原本的厚度」要多久，不是「觀眾要等多久」。
#: 3. 再大就沒有意義：`bridge.js` 一次生一個，視窗比「冷啟動走得完的量」大的那一截，
#:    在下一次 reload 之前根本輪不到。
#: ⚠ 展場可以調。`--recent 0` ＝ 關掉視窗（回到舊行為，**也不會有人退役**）。
DEFAULT_RECENT = 60

#: 「剛來的」有多新才算剛來。預設 900 秒（15 分鐘）。
#:
#: 這個數字是從**同一個檔案裡的常數推出來的**，不是拍的：觀眾投卡到分身上得了螢幕，
#: 最壞情況 ＝ `DEFAULT_GEN_TIMEOUT`(300s) 的第一發 ＋ 升額重試的第二發（再 300s）
#: ＋ `loop --interval`(10s) 的一輪 ≈ **610 秒**。900 秒把那個最壞情況整個蓋住還有餘裕，
#: 所以「卡在生成裡十分鐘」的那個人，一生出來仍然算 `fresh`、仍然插隊。
DEFAULT_FRESH_WINDOW_S = 900.0

#: `fresh` 的人多到超過視窗時，視窗最多撐到 `recent × 這個倍數`。
#:
#: 什麼時候會發生：**模型掛掉**。`fallback_deterministic` 是微秒級的，
#: 積壓的 300 張卡會在一秒內全部變成 `generated` ⇒ 全部都 `fresh`。
#: 那時候誠實的做法不是假裝塞得下（物理上 300 人 × 30 秒就是 2.5 小時），
#: 而是**撐大到 3 倍、其餘記成 `waiting` 讓畫面講得出來**。
#: ⚠ 被這個上限切掉的人**不退役**——他們還沒輪到，不是「演完了」。
FRESH_OVERFLOW_FACTOR = 3

#: 退役之後，那個人的「告別」還要在 `retirement.retiring[]` 裡掛多久。
#: 180 秒 ＝ `loop --interval` 預設 10 秒的 18 輪，也 ＝ 6 個 30 秒的展示格。
#: 給電視那端足夠的機會把退場演出來，**即使中間被看門狗 reload 打斷一次**。
RETIRE_GRACE_S = 180.0

#: `retiring[]` 一次最多掛幾個人的告別。
#:
#: 為什麼需要上限：**大批退役是會發生的**，而且第一次一定會發生——展場那台庫裡
#: 已經有幾百人，這個改動上線後的第一次 `export` 會一口氣退掉視窗外的所有人
#: （實測 600 人 ⇒ 一輪退 540 個，`retiring[]` 沒上限時那份 JSON 是 182 KB）。
#: 電視在 180 秒的寬限裡最多演得下 `180 ÷ 30 ＝ 6` 格，給兩倍餘裕 ⇒ 12。
#:
#: ⚠ **超出的人不是靜靜消失**：`retirement.retiring_pending` 會講出還有幾位，
#:   電視那端要用一句集體的交代（「另有 N 位同時退場」）代替 N 次個別退場。
#:   帳本上每一位都有自己那一列，事後查得到。
RETIRE_SHOW_MAX = 12

#: 退役事件寫在 `KIND_NOTE` 裡的標記。
#: ⚠ **為什麼不開一個新 kind**：`twinstore.py` 的 `KINDS` 是別人的檔案，
#:   而且展場那台已經在跑的庫不會因此重算。用 `note` ＋ 標記欄位，
#:   舊庫直接相容，`verify()` 也照樣從創世走到鏈頭。
RETIRE_MARK = "retired"


def _day_bounds(now_ms: int) -> tuple[int, int]:
    """回「今天」的起點（UTC 毫秒）與時區偏移（分鐘）。

    ⚠ **刻意用本機時區不是 UTC**：展場在 UTC+8，用 UTC 午夜切會在早上八點
    （展期正中間）把「今天來過幾位」歸零。偏移一起吐出去，事後查得出來
    那一份 JSON 的「今天」是哪一段。
    """
    dt = datetime.fromtimestamp(now_ms / 1000).astimezone()
    start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    off = start.utcoffset()
    return int(start.timestamp() * 1000), int((off.total_seconds() // 60) if off else 0)


def _clock_ms(v: Any) -> int | None:
    """payload 裡那個 `ts` 能不能當毫秒時間戳用。

    ⚠ `isinstance(True, int)` 為真 ⇒ **布林要先踢掉**（同 `attest.py` 的紀律）。
    ⚠ 封印過的卡 `seal_card()` 會把非數字的 `ts` 存成截斷字串，那種一律不採。
    """
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return int(v)


def _stage_times(store: TwinStore) -> dict[str, dict[str, Any]]:
    """每個人的「投卡時間」與「可上台時間」。一次掃完，不是每人一次查詢。

    走 `events(kind=...)`（吃 `ix_twin_event_kind` 索引），依 seq 遞增 ⇒
    **後面的蓋前面的**，所以拿到的是**最後一次** generated。

    🔴 **`submitted_ms` 是觀眾按下送出的時間，不是我們抄寫的時間（2026-09-22 修正）。**

    在這之前，排序鍵是 `generated_seq or submitted_seq`，而**那兩個 seq 都是
    事件寫進本機的當下才指派的**，跟觀眾什麼時候按送出無關。後果不是理論的：

      公網斷三小時 ⇒ 50 張卡卡在雲端郵箱 ⇒ 網路回來，一輪 `ingest` 把 51 張
      （含剛投卡那位）全抄進來 ⇒ `generate()` 依 `pending()`（seq 遞增）從最舊
      的開始生 ⇒ **那 50 張的 `generated_seq` 全都大於剛投卡那位的
      `submitted_seq`** ⇒ 他排第 50 位，以每人 30 秒估 ＝ **25 分鐘**。

    而「剛投卡的人永遠在 `people[0]`」這句話是寫進產品 JSON（`window.guarantee`）
    給展件讀的。做不到的保證不准留著（鐵律 5 的展場版本）。

    所以送出時間改讀 `submitted` payload 裡的 `ts`——那是**雲端**寫的
    （`vacant-world-cloud` 的 `createSub()`：`ts: now`，伺服器時鐘的毫秒），
    也就是觀眾按下送出的那一刻。

    ⚠ **誠實邊界（改碼時保留）**：
    1. 沒有 `ts` 的卡（本機造的、示範資料、2026-09 之前的舊列）**退回用抄寫
       時間**排序 ⇒ 上面那個失效模式在那些卡身上仍然成立。數量吐在
       `window.submit_ts_from_ingest`，不要猜也不要藏。
    2. `ts` 比現在還晚的（雲端時鐘超前、或那個數字根本壞掉）**夾到 `now_ms`**：
       一張卡不可能在未來投進來，而不夾的話一個年份寫錯的 `ts` 會把那個人
       **永久釘在 `people[0]`**，展場再也沒有人上得了台。
    3. `generated_ms` 是**本機**時鐘。它只拿來算 `tier`／`age_s`，
       **不參與排序**——把兩個時鐘混在同一個排序鍵裡，就是第 1 點的另一種寫法。
    4. 代價：**重新生成不會讓人重新插隊**（他的送出時間沒變）。那是刻意的：
       他不是新來的觀眾，而讓生成時間驅動順序正是積壓卡能埋掉新人的原因。
    """
    out: dict[str, dict[str, Any]] = {}
    for e in store.events(kind=KIND_SUBMITTED):
        p = e["payload"] if isinstance(e["payload"], dict) else {}
        cloud_ms = _clock_ms(p.get("ts"))
        d = out.setdefault(e["sub_id"], {})
        d["submitted_seq"] = e["seq"]
        d["ingested_ms"] = e["ts_unix_ms"]
        # 🔴 **送出一定在抄寫之前。** 夾到抄寫時間，不是夾到 `now`：
        #    夾到 `now` 的話，一個年份寫錯的 `ts` 還是會贏過所有真的剛投卡的人
        #    （now > now-5s），那個人就被永久釘在 people[0]。
        if cloud_ms is None:
            d["submitted_ms"] = e["ts_unix_ms"]
            d["submit_ts_source"] = "ingest"
        elif cloud_ms > e["ts_unix_ms"]:
            # 雲端時鐘超前（幾秒是常態）或那個數字壞了。兩者分不出來
            # ⇒ 一律退回抄寫時間，而且**數出來**，不要安靜發生。
            d["submitted_ms"] = e["ts_unix_ms"]
            d["submit_ts_source"] = "clamped"
        else:
            d["submitted_ms"] = cloud_ms
            d["submit_ts_source"] = "cloud"
    for e in store.events(kind=KIND_GENERATED):
        d = out.setdefault(e["sub_id"], {})
        d["generated_seq"] = e["seq"]
        d["generated_ms"] = e["ts_unix_ms"]
    return out


def _retired_index(store: TwinStore) -> dict[str, dict[str, Any]]:
    """已經退役的人 → 那一列退役事件。**純讀**，一個位元組都不寫。"""
    out: dict[str, dict[str, Any]] = {}
    for e in store.events(kind=KIND_NOTE):
        p = e.get("payload")
        if isinstance(p, dict) and p.get("twinlink_event") == RETIRE_MARK:
            out[e["sub_id"]] = {"at_ms": e["ts_unix_ms"], "seq": e["seq"], **p}
    return out


def _tier(entry: dict[str, Any], now_ms: int, fresh_window_s: float) -> str:
    """`arriving`（投了卡、分身還沒生出來）／`fresh`（剛上得了台）／`ambient`。"""
    if entry["generated_ms"] is None:
        return "arriving"
    return ("fresh" if now_ms - entry["generated_ms"] <= fresh_window_s * 1000
            else "ambient")


def build_view(store: TwinStore, *,
               recent: int = DEFAULT_RECENT,
               fresh_window_s: float = DEFAULT_FRESH_WINDOW_S,
               retire_grace_s: float = RETIRE_GRACE_S,
               record_retire: bool = False,
               now_ms: int | None = None) -> dict[str, Any]:
    """算出「現在螢幕上該有誰」。

    `record_retire=False` 時**完全不寫**（`serve`／`view` 走這條，庫是唯讀開的）。
    `export`／`loop` 傳 `True`，那時掉出視窗的人會被**寫一列退役事件上鏈**——
    退役不是靜靜消失，是帳本上的一件事（展覽設計 §5.1-7「要給結束一個形狀」）。

    ⚠ **退役 ≠ 刪除。** 一列事件都沒有少，`verify()` 照樣從創世走到鏈頭；
      退役只代表「不再上螢幕」。刪除是 `DECISION_20260921_TWIN_CONSENT_AND_ERASURE.md`
      的撤回路徑，跟這裡是兩件事，不要混講。
    """
    v = store.verify()
    withdrawn = 0
    now_ms = int(now_ms if now_ms is not None else time.time() * 1000)
    day_start_ms, tz_off_min = _day_bounds(now_ms)
    times = _stage_times(store)
    retired = _retired_index(store)

    cands: list[dict[str, Any]] = []
    n_from_ingest = n_clamped = 0
    for c in store.roster():
        t = times.get(c["sub_id"], {})
        gen_ms = t.get("generated_ms")
        # 🔴 排序鍵＝**觀眾按下送出的時間**（見 `_stage_times` 的長註解）。
        #    夾限已經在 `_stage_times` 裡做掉了（送出一定在抄寫之前）。
        sub_ms = t.get("submitted_ms") or 0
        if t.get("submit_ts_source") == "ingest":
            n_from_ingest += 1
        elif t.get("submit_ts_source") == "clamped":
            n_clamped += 1
        cands.append({
            "cur": c, "sid": c["sub_id"],
            # 同毫秒才輪到 seq 當決勝局（兩支手機同一毫秒送出是會發生的，
            # 而「誰在前面」必須是全序，不然畫面講不出一個確定的順序）。
            "key_seq": t.get("submitted_seq") or 0,
            "generated_ms": gen_ms, "submitted_ms": sub_ms,
            "submit_ts_source": t.get("submit_ts_source"),
            "stage_ms": gen_ms if gen_ms is not None else sub_ms,
        })
    # 🔴 新到舊，依**送出時間**。不是 seq，也不混 generated_ms（本機時鐘）。
    cands.sort(key=lambda x: (x["submitted_ms"], x["key_seq"]), reverse=True)

    live = [x for x in cands if x["sid"] not in retired]

    if recent <= 0:
        # 明示的關窗：回到舊行為，而且**不退役任何人**。
        shown, waiting, retire_now, hard_cap = live, [], [], 0
    else:
        hard_cap = max(1, recent * FRESH_OVERFLOW_FACTOR)
        # ⚠ **不可以只數前綴**（2026-09-22 隨排序鍵一起改）。排序鍵改成送出時間
        #   之後，`arriving`／`fresh` 不再保證是排序後的連續前綴：一個 30 分鐘前
        #   投卡、卡在生成裡、剛剛才生出來的人是 `fresh`，卻排在 20 分鐘前投卡
        #   而早就生完的 `ambient` 後面。照前綴數會**低估**要保留的人數。
        n_must = sum(1 for x in live
                     if _tier(x, now_ms, fresh_window_s) in ("arriving", "fresh"))
        k = min(hard_cap, max(recent, n_must))
        shown, rest = live[:k], live[k:]
        # 掉出視窗但**還沒輪到**的（被 hard_cap 切掉的 fresh）不退役。
        retire_now = [x for x in rest
                      if _tier(x, now_ms, fresh_window_s) == "ambient"]
        waiting = [x for x in rest
                   if _tier(x, now_ms, fresh_window_s) != "ambient"]

    if record_retire and retire_now:
        for x in retire_now:
            twin = (x["cur"].get("twin") or {})
            rec = {
                "twinlink_event": RETIRE_MARK,
                # 「給結束一個形狀」：退場時他說的那一句，就是他交件時說的那一句。
                "farewell": twin.get("handover") or twin.get("arrival"),
                "reason": f"場次輪替：畫面只留最近 {recent} 位",
                "recent": recent,
                "stage_ms": x["stage_ms"],
                # ⚠ 用 `now_ms` 不用 `_now()`：退役事件的時間戳、payload 裡的 `at`、
                #    以及 `retiring[]` 的 `age_s` 必須來自**同一個時鐘**，
                #    不然寬限期會算在兩個不同的時間軸上（測試注入時鐘就會炸出來）。
                "at": datetime.fromtimestamp(now_ms / 1000, timezone.utc).isoformat(),
                # 🔴 我們**量不到**螢幕到底演過他沒有。沒量到寫 null 不寫 false。
                #    要變成真的，電視那端得回報（見報告「另一側需要配合什麼」）。
                "screen_confirmed": None,
            }
            # ⚠ `sqlite3` 的例外刻意**不吞**（檔頭誠實邊界 4b）：真相來源壞掉
            #    要讓 loop 大聲死掉，不可以假裝成「這個人沒退成」而每輪再試一次。
            store.append(KIND_NOTE, x["sid"], rec, source="local:twinlink.retire",
                         ts_unix_ms=now_ms)
            retired[x["sid"]] = {"at_ms": now_ms, "seq": None, **rec}

    people = []
    for x in shown:
        c = x["cur"]
        twin = c.get("twin") or {}
        gone = c.get("status") in ("withdrawn", "erased")
        if gone:
            withdrawn += 1
        people.append({
            "id": c["sub_id"],
            # 🔴 撤回過的人，畫面上什麼都不留。原文已經 `unlink()` 了，
            #    這裡再把它當成「剛好讀不到」而留個空位也不對——狀態要講出來。
            "card": None if gone else c.get("card"),
            "arrival": None if gone else twin.get("arrival"),
            "working": None if gone else twin.get("working"),
            "handover": None if gone else twin.get("handover"),
            # 🔴 engine 一定要出到畫面層：真模型跟退化查表不可以長得一樣
            "engine": twin.get("engine"),
            "latency_ms": twin.get("latency_ms"),
            "status": c.get("status"),
            "errors": len(c.get("errors") or []),
            # 原文到底在不在檔案庫裡（撤回之後是 False）；沒有封印過的舊卡是 None。
            "card_available": c.get("card_available"),
            # ⚠ 舊列的原文在鏈上拿不掉。這個旗標**不准隱藏**。
            "plaintext_on_chain": bool(c.get("plaintext_on_chain")),
            # 🔴 電視靠這兩個欄位決定「誰先上台」。`arriving`／`fresh` 要插隊。
            "tier": _tier(x, now_ms, fresh_window_s),
            "stage_ms": x["stage_ms"],
            "age_s": (None if x["stage_ms"] is None
                      else round((now_ms - x["stage_ms"]) / 1000, 1)),
        })

    in_grace = sorted(
        ({"id": sid,
          "farewell": r.get("farewell"),
          "reason": r.get("reason"),
          "at": r.get("at"),
          "age_s": round((now_ms - r["at_ms"]) / 1000, 1),
          "screen_confirmed": r.get("screen_confirmed")}
         for sid, r in retired.items()
         if now_ms - r["at_ms"] <= retire_grace_s * 1000),
        key=lambda d: d["age_s"])
    # 演得下的才掛出去；剩下的用一個數字交代（見 RETIRE_SHOW_MAX 的註解）。
    retiring, retiring_pending = in_grace[:RETIRE_SHOW_MAX], len(in_grace) - RETIRE_SHOW_MAX

    n_today = sum(1 for x in cands
                  if x["submitted_ms"] is not None and x["submitted_ms"] >= day_start_ms)
    tiers = [p["tier"] for p in people]

    return {
        "generated_at": _now(),
        "store_id": store.store_id,
        "chain": {"ok": v["ok"], "checked": v["checked"],
                  "head": v.get("head"), "genesis": v.get("genesis")},
        "counts": {
            # `visitors` 維持原意＝`people` 的長度（相容既有消費端）
            "visitors": len(people),
            "shown": len(people),
            # 撤回／抹除過的人（他們的畫面欄位全是 None，但位子還在 people 裡）
            "withdrawn": withdrawn,
            # 🔴 畫面要講得出「今天來過 N 位」靠這兩個
            "total": len(cands),
            "today": n_today,
            "retired": len(retired),
            "waiting": len(waiting),
            "arriving": tiers.count("arriving"),
            "fresh": tiers.count("fresh"),
            "ambient": tiers.count("ambient"),
            "events": store.count(),
            "gaps": store.count(KIND_INGEST_GAP),
            "errors": store.count(KIND_ERROR),
        },
        "day": {"start_utc_ms": day_start_ms, "tz_offset_minutes": tz_off_min,
                "note": "用展場本機時區切日，不是 UTC（UTC 會在早上八點歸零）"},
        # 🔴 **庫裡所有人的 id，不受視窗影響。這一欄不是拿來演的。**
        #
        # 為什麼非有不可：電視那端（`vacant_hm/world3/bridge.js`）有一本
        # 「公網來的卡待對帳帳本」，而它的核銷條件寫死是**「本機視圖的
        # `people[]` 裡真的看得到那個 id」**（`reconcile(localIds)`，
        # `localIds` 只從 `subsFromView(data).people` 來）。
        #
        # 視窗一加上去，那個不變式就被我打破了：一張卡進得了庫、卻排不進
        # 最近 60 位（例如**生成卡住的那一位**——他是 `arriving`、永遠不退役，
        # 但只要前面壓了 60 個更新的人就進不了畫面），電視就**永遠核銷不掉**，
        # 帳本只增不減、每 15 秒重送一次。
        #
        # ⚠ 所以核銷要對的是**這一欄**不是 `people`。`people` 是「該上螢幕的人」，
        #   `roster_ids` 是「庫裡有誰」——兩件事，不要混用：
        #   拿 `roster_ids` 去生分身 ＝ 把視窗整個繞掉，第七天又從第一個人重演。
        # ⚠ 含**已退役**的人（退役 ≠ 不存在），所以它只增不減 ⇒ 大小隨人數線性。
        "roster_ids": [x["sid"] for x in cands],
        "window": {
            "recent": recent,
            "fresh_window_s": fresh_window_s,
            "hard_cap": hard_cap,
            "order": "newest_submitted_first",
            "order_key": ("觀眾按下送出的時間（雲端 submitted.ts），"
                          "同一毫秒才看抄寫序號"),
            # 有幾位的送出時間是**退回用抄寫時間**算的（見 guarantee_limits 第 3 條）
            "submit_ts_from_ingest": n_from_ingest,
            # 雲端 ts 比抄寫時間還晚（時鐘超前或數字壞掉）⇒ 退回抄寫時間的有幾位
            "submit_ts_clamped": n_clamped,
            "guarantee": ("people 依**觀眾按下送出的時間**新到舊排序 ⇒ "
                          "最後一位投卡的人在 people[0]，recent 再小都擠不掉他；"
                          "積壓的舊卡即使現在才抄進來、現在才生成，也排不到他前面。"),
            "guarantee_limits": [
                "這是這份 JSON 的**陣列順序**，不是「螢幕幾秒內演到他」——"
                "電視那端演多快，twinlink 量不到。",
                "同一毫秒投卡的第 2、3 位只能依序排在他後面，"
                "不可能三個人同時是 people[0]。",
                "沒有雲端時間戳的卡（本機造的、示範卡、2026-09 之前的舊列）"
                "**退回用抄寫時間**排序，這個保證在那些卡身上不成立；"
                "有幾張在 window.submit_ts_from_ingest。",
                "重新生成不會讓人重新插隊（送出時間沒變）——刻意的，"
                "他不是新來的觀眾。",
            ],
        },
        "retirement": {
            "one_way": True,
            "grace_s": retire_grace_s,
            "retired_total": len(retired),
            "retiring": retiring,
            # >0 ⇒ 大批退役：電視要改演**一句集體的交代**，不是 N 次個別退場。
            "retiring_pending": max(0, retiring_pending),
            "bulk": retiring_pending > 0,
            "recorded_here": bool(record_retire),
            "honesty": ("退役＝不再上螢幕，**不是刪除**：事件流一列沒少、"
                        "verify 照樣從創世走到鏈頭。刪除是撤回路徑那件事。"),
        },
        "screen_contract": {
            "spawn_order": "people 已經排好序，照陣列順序生就對了",
            "jump_queue": ["arriving", "fresh"],
            "cold_start": ("重整／斷電之後把整個 people 快轉補齊（不要每人等 30 秒），"
                           "之後才回到一次一位的節奏"),
            "play_exit_for": "retirement.retiring[]（演完才算交代過，不要靜靜移除）",
            "bulk_exit": ("retirement.bulk 為 true ⇒ 改演一句集體的交代，"
                          "數字在 retirement.retiring_pending"),
            "caption_counts": "counts.today / counts.total / counts.waiting",
            # 🔴 電視那端的待對帳帳本要用 roster_ids 核銷，**不是** people
            "reconcile_against": "roster_ids",
            "never_spawn_from": ("roster_ids —— 那是「庫裡有誰」不是「該上螢幕的人」，"
                                 "拿它生分身等於把視窗繞掉"),
        },
        "people": people,
        "honesty": "engine=lmstudio:* 才是真的有模型回話；fallback_deterministic 是離線查表。",
        "erasure_honesty": (
            "原文與 nonce 住在鏈外的檔案庫，撤回時真的 unlink()，"
            "刪除證明（被刪位元組的 sha256）簽上鏈。"
            "鏈記的是「我們記下我們刪了」，不是「世上沒有副本」；"
            "雲端郵箱那一份目前刪不到（沒有 delete 路由）。"
            "plaintext_on_chain=true 的那幾位是 2026-09-21 之前進來的，"
            "他們的原文在 append-only 鏈上，拿不掉。"),
    }


# ---------------------------------------------------------------------------
# 4b. withdraw —— 撤回 → 上鏈 → 原文 unlink() → PERSONA_ERASED
# ---------------------------------------------------------------------------

def withdraw(store: TwinStore, sub_id: str, *, reason: str = "subject_request",
             source: str = "local:withdraw") -> dict[str, Any]:
    """觀眾撤回同意。**帳本永不刪除，原文真的刪掉。**

    三件事按這個順序（順序本身是規格）：
    1. `withdrawn` 一列進 append-only 帳本 ＋ 簽章鏈 `CONSENT_WITHDRAW`
       ——先宣告，才看得見「宣告了但沒做」這個狀態（`consent.py` 誠實邊界 2）；
    2. 鏈外檔案庫的原文與 **nonce** 一起 `unlink()`
       ——只刪原文留 nonce ＝ 沒刪（`consent.py` 誠實邊界 4）；
    3. `erased` 一列（帶被刪位元組的 sha256）＋ 簽章鏈 `PERSONA_ERASED`。

    冪等：已經 erased 的再呼叫一次回 `already=True`，不會多寫。
    """
    cur = store.current(sub_id)
    if cur is None:
        # 不認識的 id **不寫任何一列**。寫了的話，公網上任何人掃一遍
        # 就能把 append-only 帳本灌到爆，而那條鏈刪不掉。
        return {"ok": False, "sub_id": sub_id, "reason": "unknown_id"}
    if cur.get("erased_seq"):
        return {"ok": True, "sub_id": sub_id, "already": True,
                "status": cur.get("status")}

    residual = twinvault.legacy_plaintext_seqs(store, sub_id)
    store.append(KIND_WITHDRAWN, sub_id, {
        "v": 1, "reason": str(reason)[:120], "at": _now(),
    }, source=source)
    rec = store.vault.withdraw(sub_id, reason=str(reason)[:120])
    ev = {
        "v": 1,
        "signed": rec["signed"],
        "withdraw_hash": rec.get("withdraw_hash"),
        "erase_hash": rec.get("erase_hash"),
        "erased": rec["erased"],
        "cloud_copy": rec["cloud_copy"],
        # ⚠ 舊鏈的原文拿不掉。**這幾個 seq 要跟著刪除證明一起留下來**，
        #   不然「已刪除」這三個字在那幾位身上就是假的。
        "residual_plaintext_seqs": residual,
        "fully_erased": not residual,
        "problems": rec["problems"],
        "at": _now(),
    }
    store.append(KIND_ERASED, sub_id, ev, source=source)
    return {"ok": True, "sub_id": sub_id, "already": False, **ev}


def export(store: TwinStore, out: pathlib.Path, *,
           recent: int = DEFAULT_RECENT,
           fresh_window_s: float = DEFAULT_FRESH_WINDOW_S,
           record_retire: bool = True,
           now_ms: int | None = None) -> dict[str, Any]:
    """寫出螢幕讀的那份 JSON。**這是唯一會寫退役事件的路徑**（`loop` 走它）。"""
    out = pathlib.Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    view = build_view(store, recent=recent, fresh_window_s=fresh_window_s,
                      record_retire=record_retire, now_ms=now_ms)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(view, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(out)  # 原子換檔：螢幕不會讀到寫到一半的 JSON
    return {"ok": True, "out": str(out),
            "visitors": len(view["people"]),
            "total": view["counts"]["total"],
            "today": view["counts"]["today"],
            "retired": view["counts"]["retired"],
            "waiting": view["counts"]["waiting"],
            "window": view["window"]}


WITHDRAW_PAGE = """<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>撤回我的分身</title>
<style>
 body{font:16px/1.7 system-ui,"Noto Sans TC",sans-serif;margin:0;padding:24px;
      background:#141210;color:#efe9e1;max-width:34rem}
 h1{font-size:1.3rem;margin:0 0 .6rem}
 code{background:#262220;padding:.1rem .35rem;border-radius:4px}
 button{font:inherit;padding:.7rem 1.4rem;margin-top:1rem;border:0;border-radius:8px;
        background:#c2502f;color:#fff}
 .note{color:#b7ada2;font-size:.9rem}
</style></head><body>
<h1>撤回我的分身</h1>
<p>代號 <code>__ID__</code>　目前狀態：<code>__STATUS__</code></p>
<p>按下去會發生三件事，而且每一件都留得下證據：</p>
<ol>
<li>「你撤回了」寫進<strong>永不刪除</strong>的帳本（也簽進同意鏈）。</li>
<li>你打的那段原文與它的 nonce <strong>從檔案庫真的刪掉</strong>。</li>
<li>刪掉的位元組 sha256 簽上鏈，成為<strong>刪除證明</strong>。</li>
</ol>
<p class="note">誠實邊界：鏈記的是「我們記下我們刪了」，不是「世上沒有副本」。
雲端收件那一份目前刪不到。你手機上的截圖我們也管不到。</p>
<form method="POST" action="__ACTION__"><button type="submit">確定撤回</button></form>
<p class="note">這一頁不會自己動手：撤回是 POST，光是打開這一頁什麼都沒發生。</p>
</body></html>"""


def _html_escape(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def serve(store_path: pathlib.Path, port: int, bind: str = "127.0.0.1", *,
          allow_withdraw: bool = False, withdraw_token: str | None = None,
          recent: int = DEFAULT_RECENT,
          fresh_window_s: float = DEFAULT_FRESH_WINDOW_S) -> int:
    """唯讀 HTTP ＋（可選）一條撤回用的寫入路徑。

    **唯讀那一側有兩層，都是硬的，而且沒有因為加了撤回而變鬆**：
    1. `do_GET` 沒有任何寫入路徑；
    2. `TwinStore(..., read_only=True)` ⇒ SQLite 以 `mode=ro` 開檔。
       第 2 層是必要的——預設建構子會 `mkdir` ＋ `executescript(SCHEMA)`，
       那是寫入，等於**每次 GET 都在對真相來源動手**。

    **撤回另開一條**（`do_POST`），而且：

    · 預設**關著**（`--allow-withdraw` 才開）。現場螢幕那台跑的還是純唯讀。
    · 它自己開一個**可寫**的 `TwinStore`，不碰唯讀那一個。
    · `GET /withdraw/<id>` 只是一張確認頁，**不寫任何東西**——
      不然瀏覽器預抓／爬蟲／聊天軟體展開連結就會把人家的分身刪掉。

    ## token 要不要？（2026-09-21 想過了，結論寫在這裡）

    **預設不要共用 token。** 理由：公網頁上印著「你可以隨時要求我們刪除」，
    而共用 token 只有工作人員有 ⇒ 觀眾自己撤回不了 ⇒ 那句話還是假的。
    `sub_id` 本身就是能力憑證（觀眾手機上才有那個代號）。

    誠實邊界：**id 猜得到的話，別人可以撤回你的分身。** 那是破壞不是洩漏——
    失敗方向朝「刪掉了不該刪的」，而不是「該刪的沒刪」，
    在這件事上是可以接受的那一邊。要更嚴的場地加 `--withdraw-token`。

    ⚠ **這條路 `record_retire=False` 寫死**（第三層唯讀）。它照樣**回報**
      已經記在帳本上的退役，但不會自己記新的——庫是 `mode=ro` 開的，
      記了也只會炸。「誰在螢幕上」這件事在這裡跟 `export` 算出來一樣，
      差別只在**誰有權把退役寫下來**：只有 `export`／`loop`。
    """
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class H(BaseHTTPRequestHandler):
        def _send(self, obj: Any, code: int = 200) -> None:
            b = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b)

        def _send_html(self, html: str, code: int = 200) -> None:
            b = html.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def _sub_id(self) -> str | None:
            path = self.path.split("?")[0]
            if not path.startswith("/withdraw/"):
                return None
            sid = urllib.parse.unquote(path[len("/withdraw/"):])
            return sid or None

        def _token_ok(self) -> bool:
            if not withdraw_token:
                return True
            q = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            given = (self.headers.get("X-Vacant-Token")
                     or (q.get("token") or [""])[0])
            return given == withdraw_token

        def do_GET(self) -> None:  # noqa: N802
            st = TwinStore(store_path, read_only=True)
            try:
                p = self.path.split("?")[0]
                if p in ("/", "/visitors.json"):
                    self._send(build_view(st, recent=recent,
                                          fresh_window_s=fresh_window_s,
                                          record_retire=False))
                elif p == "/verify":
                    self._send(st.verify())
                elif p == "/stats":
                    self._send({"events": st.count(), "visitors": len(st.sub_ids()),
                                "store_id": st.store_id})
                elif p.startswith("/withdraw"):
                    sid = self._sub_id()
                    if sid is None:
                        self._send({"error": "用 /withdraw/<你的代號>",
                                    "enabled": allow_withdraw}, 404)
                        return
                    cur = st.current(sid)
                    if cur is None:
                        self._send({"error": "unknown_id", "id": sid}, 404)
                        return
                    # **唯讀**：只是一張確認頁，按鈕才是 POST。
                    q = urllib.parse.urlsplit(self.path).query
                    action = urllib.parse.quote(sid, safe="")
                    self._send_html(
                        WITHDRAW_PAGE
                        .replace("__ID__", _html_escape(sid))
                        .replace("__STATUS__", _html_escape(str(cur.get("status"))))
                        # 🔴 `__ACTION__` 也要過 escape。`q` 是**原始 query string**，
                        #   而這一行把它塞進 HTML 屬性 ⇒ 反射式 script 注入。
                        #   實跑重現（2026-09-21）：
                        #     GET /withdraw/v1?a="><script>alert(1)</script>
                        #     → <form … action="/withdraw/v1?a="><script>alert(1)</script>">
                        #   `__ID__`／`__STATUS__` 本來就過了，只有這一個漏掉。
                        #   ⚠ 而這一頁正是「觀眾決定要不要刪掉自己」的那一頁——
                        #     能改寫它＝能對觀眾謊報按下去會發生什麼。比一般 XSS 嚴重。
                        .replace("__ACTION__", _html_escape(
                            "/withdraw/" + action + (f"?{q}" if q else ""))))
                else:
                    self._send({"error": "只有 /visitors.json /verify /stats"
                                         " /withdraw/<id>"}, 404)
            finally:
                st.close()

        def do_POST(self) -> None:  # noqa: N802
            sid = self._sub_id()
            if sid is None:
                self._send({"error": "只有 POST /withdraw/<id>"}, 404)
                return
            if not allow_withdraw:
                self._send({"error": "這一台沒開撤回（唯讀端點）。"
                                     "要開請用 --allow-withdraw；"
                                     "現場也可以走紙本＋CLI withdraw。"}, 405)
                return
            if not self._token_ok():
                self._send({"error": "token 不符"}, 403)
                return
            # 有人可能 POST 帶 body；讀掉它，不然 keep-alive 的下一個請求會錯位。
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                n = 0
            if n > 0:
                self.rfile.read(min(n, 1 << 16))
            st = TwinStore(store_path)     # ← 撤回是寫入，另開一個可寫的
            try:
                out = withdraw(st, sid, source="serve:withdraw")
            finally:
                st.close()
            self._send(out, 200 if out.get("ok") else 404)

        def log_message(self, *a): pass  # noqa: D102, ANN002

    srv = ThreadingHTTPServer((bind, port), H)
    print(f"twinlink serve（唯讀）http://{bind}:{port}/visitors.json  db={store_path}"
          f"  withdraw={'開' if allow_withdraw else '關'}"
          f"{'（需 token）' if withdraw_token else ''}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


# ---------------------------------------------------------------------------
# 5. selftest —— 離線自檢＋負控制
# ---------------------------------------------------------------------------

def selftest() -> int:
    import tempfile
    fails: list[str] = []

    def chk(name: str, cond: bool, extra: str = "") -> None:
        print(("  [OK] " if cond else "  [紅] ") + name + (f" — {extra}" if extra else ""))
        if not cond:
            fails.append(name)

    with tempfile.TemporaryDirectory() as td:
        db = pathlib.Path(td) / "s.sqlite3"
        st = TwinStore(db)

        print("1. append-only 的牙齒")
        st.append(KIND_NOTE, "x", {"a": 1}, source="selftest")
        st.append(KIND_NOTE, "x", {"a": 2}, source="selftest")
        try:
            st.conn.execute("UPDATE twin_event SET source='駭' WHERE seq=1")
            chk("UPDATE 被擋", False, "竟然沒炸")
        except Exception as e:  # noqa: BLE001
            chk("UPDATE 被擋", "append-only" in str(e), str(e)[:60])
        try:
            st.conn.execute("DELETE FROM twin_event WHERE seq=1")
            chk("DELETE 被擋", False, "竟然沒炸")
        except Exception as e:  # noqa: BLE001
            chk("DELETE 被擋", "append-only" in str(e), str(e)[:60])

        print("2. 雜湊鏈（正控制：乾淨的鏈要綠）")
        chk("verify 綠", st.verify()["ok"] is True)

        print("3. 摺疊出狀態，不改舊列")
        st.append(KIND_SUBMITTED, "v1", {"card": {"need": "整理桌面"}}, source="selftest")
        chk("status=submitted", (st.current("v1") or {})["status"] == "submitted")
        st.append(KIND_GENERATED, "v1", {"arrival": "嗨", "engine": "x"}, source="selftest")
        chk("status=generated", (st.current("v1") or {})["status"] == "generated")
        st.append(KIND_PUBLISHED, "v1", {"http": 200}, source="selftest")
        chk("status=published", (st.current("v1") or {})["status"] == "published")
        chk("三次狀態變化＝三列事件，舊列一列沒少",
            len(list(st.events(sub_id="v1"))) == 3,
            f"實得 {len(list(st.events(sub_id='v1')))}")

        print("4. KS-1 可執行防呆（負控制：禁語必須炸）")
        try:
            assert_ks1_clean("你有責任把這件事做完")
            chk("KS-1 攔禁語", False, "竟然沒炸")
        except ValueError:
            chk("KS-1 攔禁語", True)
        chk("KS-1 放行乾淨 prompt",
            build_prompt({"need": "整理桌面"}, None) is not None)

        print("5. 離線退路（1003 不通也要出得了分身）")
        fb = generate_one({"need": "整理桌面", "shape": "圓潤", "color": "暖土"}, None,
                          endpoint="http://127.0.0.1:1/v1", model="nope", timeout=2.0)
        chk("斷線回 fallback", fb["engine"] == "fallback_deterministic", fb.get("degrade_reason", "")[:50])
        chk("fallback 有三句", all(fb.get(k) for k in ("arrival", "working", "handover")))
        chk("fallback 有標 degraded_from", bool(fb.get("degraded_from")))

        print("6. 斷線 ingest 記 gap 而不是回 0")
        r = ingest(st, "http://127.0.0.1:1", "t", timeout=2.0)
        chk("pulled 是 null 不是 0", r["pulled"] is None, repr(r["pulled"]))
        chk("留下 ingest_gap 一列", st.count(KIND_INGEST_GAP) == 1)

        print("7. 視窗：積壓 120 人的第七天，剛投卡的那一位在哪裡")
        # 先把上面測試用的 v1 退掉不算，另外造一批。
        base_ms = int(time.time() * 1000) - 7 * 86400_000
        for i in range(120):
            sid = f"day1_{i:03d}"
            st.append(KIND_SUBMITTED, sid, {"card": {"need": f"事{i}"}},
                      source="selftest", ts_unix_ms=base_ms + i * 1000)
            st.append(KIND_GENERATED, sid,
                      {"arrival": "嗨", "working": "做", "handover": f"交件{i}",
                       "engine": "fallback_deterministic"},
                      source="selftest", ts_unix_ms=base_ms + i * 1000 + 500)
        st.append(KIND_SUBMITTED, "剛剛那位", {"card": {"need": "現在投的"}},
                  source="selftest")
        st.append(KIND_GENERATED, "剛剛那位",
                  {"arrival": "我剛到", "working": "做", "handover": "交了",
                   "engine": "fallback_deterministic"}, source="selftest")

        # 負控制（證明這個量法有鑑別力）：照**舊的**排序（提交順序）去找他，
        # 他排在一百多位之後——量得到「被埋掉」這件事，綠燈才有意義。
        # ⚠ 這批 `day1_*` 的 payload 沒有雲端 `ts` ⇒ 送出時間退回用抄寫時間
        #   （`_stage_times` 誠實邊界 1）。這裡刻意保持原樣：selftest 要走得到
        #   那條退路，不然那條退路永遠沒被跑過。
        old_pos = st.sub_ids().index("剛剛那位")
        chk("負控制：舊排序會把他埋在第 100 位之後", old_pos >= 100, f"舊排序 index={old_pos}")

        view = build_view(st, recent=10, record_retire=False)
        chk("剛投卡的人在 people[0]", view["people"][0]["id"] == "剛剛那位",
            view["people"][0]["id"])
        chk("他被標成 fresh", view["people"][0]["tier"] == "fresh",
            view["people"][0]["tier"])
        chk("視窗真的有上限", len(view["people"]) == 10, str(len(view["people"])))
        chk("total 講得出整場來過幾位", view["counts"]["total"] == 122,
            str(view["counts"]["total"]))
        chk("關窗（recent=0）＝舊行為，全部都在",
            len(build_view(st, recent=0, record_retire=False)["people"]) == 122)

        print("8. 退役：看得見、上鏈、而且不是刪除")
        before_events = st.count()
        view = build_view(st, recent=10, record_retire=True)
        # 122 人 − 視窗 10 ＝ 112 掉出去，**全部都是 `ambient`**（day1_* 是七天前的）。
        # ⚠ 2026-09-22 之前這裡寫的是 111：排序鍵是 seq 的時候，第 3 節那位 `v1`
        #   雖然是**剛剛才投卡**的，卻因為 seq 舊而排不進視窗、被記成 `waiting`。
        #   排序鍵改成送出時間之後他排得進來了 ⇒ 掉出去的變成 112。
        #   數字變了不是退步，是那個「剛投卡卻排在後面」的洞被補起來了。
        chk("掉出視窗的人被寫成退役事件", view["counts"]["retired"] == 112,
            str(view["counts"]["retired"]))
        chk("掉出去的都是 ambient（沒有人是被 hard_cap 切掉的 fresh）",
            view["counts"]["waiting"] == 0, str(view["counts"]["waiting"]))

        # 🔴 「還 fresh 但排不進視窗的人不退役」這個不變式仍然要有人守。
        #    上面那一輪量不到它（掉出去的全是 ambient），所以另外造一次尖峰：
        #    一秒內湧入 4 位（模型掛掉、fallback 微秒級生完就是這個形狀），
        #    視窗只留 1 位 ⇒ 硬上限 3 位 ⇒ 塞不下的是 **fresh**，
        #    他們要記成 `waiting` 而**不是**退役（還沒輪到 ≠ 演完了）。
        surge = [f"尖峰{i}" for i in range(4)]
        for sid in surge:
            st.append(KIND_SUBMITTED, sid, {"card": {"need": "一秒內湧入"}},
                      source="selftest")
            st.append(KIND_GENERATED, sid,
                      {"arrival": "到", "working": "做", "handover": "交",
                       "engine": "fallback_deterministic"}, source="selftest")
        v2 = build_view(st, recent=1, record_retire=True)
        chk("尖峰：塞不下的 fresh 記成 waiting", v2["counts"]["waiting"] >= 1,
            f"waiting={v2['counts']['waiting']}")
        retired_ids = {e["sub_id"] for e in st.events(kind=KIND_NOTE)
                       if isinstance(e.get("payload"), dict)
                       and e["payload"].get("twinlink_event") == RETIRE_MARK}
        shown_ids = {q["id"] for q in v2["people"]}
        waiting_surge = [sid for sid in surge if sid not in shown_ids]
        chk("負控制：這一輪真的有人被擠出畫面（不然上一條沒在測東西）",
            bool(waiting_surge), f"擠出去 {len(waiting_surge)} 位")
        chk("被擠出畫面的 fresh **一個都沒有**被寫成退役",
            not (set(waiting_surge) & retired_ids),
            f"誤退役：{sorted(set(waiting_surge) & retired_ids)}")
        chk("退役有寫進帳本（事件變多不是變少）", st.count() > before_events,
            f"{before_events} → {st.count()}")
        chk("畫面拿得到告別詞（不是靜靜消失）",
            bool(view["retirement"]["retiring"])
            and all(r["farewell"] for r in view["retirement"]["retiring"]))
        chk("螢幕演過沒有＝沒量到，寫 null 不寫 false",
            all(r["screen_confirmed"] is None for r in view["retirement"]["retiring"]))
        chk("退役 ≠ 刪除：鏈還是綠的", st.verify()["ok"] is True)
        chk("退役 ≠ 刪除：那個人的事件一列沒少",
            len(list(st.events(sub_id="day1_000"))) >= 2)
        # 負控制：`record_retire=False` 的那一條路**一列都不可以寫**
        n0 = st.count()
        build_view(st, recent=5, record_retire=False)
        chk("負控制：唯讀路徑一列都沒寫", st.count() == n0, f"{n0} → {st.count()}")
        # 負控制：退役是單向的——重新生成不會把他撈回螢幕
        st.append(KIND_GENERATED, "day1_000",
                  {"arrival": "我又來了", "working": "做", "handover": "交",
                   "engine": "fallback_deterministic"}, source="selftest")
        again = build_view(st, recent=10, record_retire=False)
        chk("負控制：退役的人重新生成也不會回到螢幕",
            all(p["id"] != "day1_000" for p in again["people"]))

        print("9. 負控制：繞過 trigger 竄改一列，verify 必須變紅")
        # 用**生連線**改，不能用 TwinStore——`__init__` 會把 trigger 補回去
        # （那是好性質：重開就恢復守衛），但也因此在這裡改不動。
        st.close()
        import sqlite3 as _s
        raw = _s.connect(str(db))
        raw.isolation_level = None
        raw.execute("PRAGMA writable_schema=ON")
        raw.execute("DELETE FROM sqlite_master WHERE type='trigger'")
        raw.execute("PRAGMA writable_schema=OFF")
        raw.close()
        raw = _s.connect(str(db))
        raw.isolation_level = None
        raw.execute("UPDATE twin_event SET payload_json='{\"a\":999}' WHERE seq=1")
        raw.close()

        # 驗鏈要用一個**不會重跑 SCHEMA** 的讀法，否則 trigger 被補回來
        # 不影響結果，但我們要驗的就是「資料被改過會不會抓到」。
        st2 = TwinStore(db)
        v = st2.verify()
        chk("竄改後 verify 變紅", v["ok"] is False, v.get("reason", ""))
        chk("指得出第一個壞掉的 seq", v["broken_at"] == 1, repr(v["broken_at"]))
        st3 = TwinStore(db)
        try:
            st3.conn.execute("UPDATE twin_event SET source='x' WHERE seq=1")
            chk("重開 store 會把 trigger 補回去", False, "竟然改得動")
        except Exception as e:  # noqa: BLE001
            chk("重開 store 會把 trigger 補回去", "append-only" in str(e))
        st3.close()
        st2.close()

    print()
    if fails:
        print(f"selftest 紅：{len(fails)} 項失敗 → {fails}")
        return 1
    print("selftest 全綠（含 9 個負控制）")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _p(o: Any) -> None:
    print(json.dumps(o, ensure_ascii=False, indent=2))


#: 真相來源不存在時的退出碼。0（好了）／1（selftest 或 withdraw 紅）／2（不認得的
#: 子命令）都已經有主人，所以另開一個，讓 `vacant-exhibit.service` 的 journal 上
#: 分得出「跑壞了」跟「根本沒找到庫」。
RC_NO_STORE = 5

#: 這幾條子命令**讀**真相來源，而且輸出直接決定螢幕上有誰。
#:
#: 🔴 為什麼要 fail-closed（2026-09-22 獨立覆核抓到的缺陷 C）：
#:    `TwinStore()` 的建構子會 `mkdir` ＋ `executescript(SCHEMA)` ——
#:    也就是說 `--db` 打錯一個字、`VACANT_TWIN_DB` 忘了設、systemd 的
#:    `WorkingDirectory` 不對，全都會**安靜地建出一個空庫**，然後
#:    `export` 寫出一份 `people: []` 的 visitors.json、電視演一個空世界、
#:    而退出碼是 **0（綠）**。
#:    展場最可能犯的錯，正好落在綠的那一格 —— 而「今天沒有人來」跟
#:    「我沒找到那個庫」在畫面上長得一模一樣。這個 repo 的紀律是
#:    **沒量到寫 null 不寫 0**，在退出碼這一層就是：拒絕，不要回綠。
#:    要真的開新場地就明講 `--init`。
STORE_READING_CMDS = ("export", "view", "serve", "loop")


def _refuse_missing_store(db: str, cmd: str) -> int:
    """庫不在 ⇒ 印一段人看得懂的拒絕，回 `RC_NO_STORE`。**一個位元組都不寫。**"""
    print(json.dumps({
        "ok": False,
        "refused": "no_store",
        "cmd": cmd,
        "db": str(db),
        "why": ("真相來源不存在。這一支**不會**替你建一個空庫再回綠——"
                "那會讓『我沒找到庫』看起來跟『今天沒有人來』一樣。"),
        "fix": [
            f"路徑打錯了？現在指的是：{db}",
            "VACANT_TWIN_DB 設了嗎（twin_loop.sh／systemd unit 都吃這一個）？",
            "真的要開一張新的空庫（第一次布展）⇒ 加 --init。",
        ],
        "rc": RC_NO_STORE,
    }, ensure_ascii=False, indent=2), file=sys.stderr, flush=True)
    return RC_NO_STORE


def _add_window_args(q: argparse.ArgumentParser, *, can_retire: bool) -> None:
    """把視窗參數掛上去。**四個子命令共用同一份**，不然會漂成兩套預設值。"""
    q.add_argument("--recent", type=int, default=DEFAULT_RECENT,
                   help=(f"螢幕上同時留幾位（預設 {DEFAULT_RECENT}）。"
                         "0＝關掉視窗（回到舊行為，也不會有人退役）。"
                         "⚠ 最後一位投卡的人在 people[0]，這個值擠不掉他"
                         "（做不到的部分見 window.guarantee_limits）。"))
    q.add_argument("--fresh-window", type=float, default=DEFAULT_FRESH_WINDOW_S,
                   dest="fresh_window",
                   help=(f"幾秒內生成的算「剛來的」（預設 {DEFAULT_FRESH_WINDOW_S:.0f}）。"
                         "這一群一定進得了畫面，而且電視那端要讓他們插隊。"))
    if can_retire:
        q.add_argument("--no-retire", action="store_true",
                       help="算視窗但**不把退役寫上鏈**（演練／稽核用；展場不要開）")


def main(argv: Iterable[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="twinlink — 手機→公網→DB→1003→螢幕")
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--init", action="store_true",
                    help=("允許在 --db 指的檔案還不存在時**建一張新的空庫**。"
                          "預設不准（見 STORE_READING_CMDS 的長註解）："
                          "不給這個旗標，路徑打錯就一定紅，不會安靜地演空世界。"))
    s = ap.add_subparsers(dest="cmd", required=True)

    for name in ("ingest", "publish"):
        q = s.add_parser(name)
        q.add_argument("--cloud", default=DEFAULT_CLOUD)
        q.add_argument("--token", required=True)
        q.add_argument("--timeout", type=float, default=30.0)
        if name == "publish":
            q.add_argument("--limit", type=int, default=0)

    g = s.add_parser("generate")
    # 預設 None ⇒ 由 `resolve_endpoint()` 探測。
    # ⚠ 原本預設是 `DEFAULT_ENDPOINT`＝候選裡**唯一需要網路**的那一個，
    #   而 `resolve_endpoint()` 一個產品呼叫點都沒有（2026-09-21 批判者查到）。
    #   「擋門存在、沒接上去」——那正是這個 repo 在抓的病。
    g.add_argument("--endpoint", default=None)
    g.add_argument("--model", default=DEFAULT_MODEL)
    g.add_argument("--limit", type=int, default=0)
    g.add_argument("--timeout", type=float, default=DEFAULT_GEN_TIMEOUT)
    g.add_argument("--no-fallback", action="store_true",
                   help="模型不通就炸，不要退化（量測用，展場不要開）")

    e = s.add_parser("export")
    e.add_argument("--out", default=str(TWIN / "store" / "visitors.json"))
    _add_window_args(e, can_retire=True)

    v = s.add_parser("serve")
    v.add_argument("--port", type=int, default=8901)
    v.add_argument("--bind", default="127.0.0.1")
    v.add_argument("--allow-withdraw", action="store_true",
                   help="開 POST /withdraw/<id>（現場螢幕那台不要開）")
    v.add_argument("--withdraw-token", default=None,
                   help="給撤回加一把共用 token。**預設不加**，"
                        "理由寫在 serve() 的 docstring")
    _add_window_args(v, can_retire=False)   # 唯讀：沒有 --no-retire，因為它從不記

    wd = s.add_parser("withdraw", help="撤回 → 上鏈 → unlink → PERSONA_ERASED")
    wd.add_argument("--id", required=True)
    wd.add_argument("--reason", default="subject_request")

    s.add_parser("selftest")
    _add_window_args(s.add_parser("view"), can_retire=False)

    lp = s.add_parser("loop")
    lp.add_argument("--cloud", default=DEFAULT_CLOUD)
    lp.add_argument("--token", required=True)
    lp.add_argument("--endpoint", default=None)
    lp.add_argument("--model", default=DEFAULT_MODEL)
    lp.add_argument("--interval", type=float, default=10.0)
    lp.add_argument("--rounds", type=int, default=0, help="0＝永遠（展場無人值守）")
    lp.add_argument("--out", default=str(TWIN / "store" / "visitors.json"))
    _add_window_args(lp, can_retire=True)

    a = ap.parse_args(list(argv) if argv is not None else None)

    if a.cmd == "selftest":
        return selftest()

    # 🔴 fail-closed：讀真相來源的那幾條路，庫不在就拒絕（缺陷 C，2026-09-22）。
    #    `ingest`／`generate`／`publish`／`withdraw` 不在這裡擋——它們是寫入路徑，
    #    第一次布展本來就會把庫建出來，而且它們回報的是「抄了幾筆」不是「螢幕上有誰」。
    if a.cmd in STORE_READING_CMDS and not a.init \
            and not pathlib.Path(a.db).is_file():
        return _refuse_missing_store(a.db, a.cmd)

    if a.cmd == "serve":
        return serve(pathlib.Path(a.db), a.port, a.bind,
                     allow_withdraw=a.allow_withdraw,
                     withdraw_token=a.withdraw_token,
                     recent=a.recent, fresh_window_s=a.fresh_window)

    st = TwinStore(a.db)
    # **端點在這裡解析一次**，而且要講出來挑了哪一個。
    # 靜靜挑一個跟靜靜用預設值一樣糟——事後查不出那一跑打的是哪個端點。
    if a.cmd in ("generate", "loop"):
        _ep = resolve_endpoint(a.endpoint)
        a.endpoint = _ep["url"]
        print(json.dumps({"endpoint_resolved": _ep}, ensure_ascii=False),
              file=sys.stderr, flush=True)
    if a.cmd == "ingest":
        _p(ingest(st, a.cloud, a.token, a.timeout)); return 0
    if a.cmd == "generate":
        _p(generate(st, a.endpoint, a.model, a.limit, a.timeout,
                    allow_fallback=not a.no_fallback)); return 0
    if a.cmd == "publish":
        _p(publish(st, a.cloud, a.token, a.limit, a.timeout)); return 0
    if a.cmd == "export":
        _p(export(st, pathlib.Path(a.out), recent=a.recent,
                  fresh_window_s=a.fresh_window,
                  record_retire=not a.no_retire)); return 0
    if a.cmd == "view":
        # `view` 是給人看現況的，**不寫**（跟 serve 同一條紀律）。
        _p(build_view(st, recent=a.recent, fresh_window_s=a.fresh_window,
                      record_retire=False)); return 0
    if a.cmd == "withdraw":
        out = withdraw(st, a.id, reason=a.reason, source="cli:withdraw")
        _p(out)
        return 0 if out.get("ok") else 1
    if a.cmd == "loop":
        # 🔴 視窗要**真的傳到 loop 的 export**。這裡漏掉的話就是
        #    「旗標存在、產品路徑沒接上去」——展場跑的正是 loop。
        #    判準：tests/test_twin_recent_window.py::test_loop_cli_passes_the_window
        n = 0
        while True:
            n += 1
            r = {"round": n, "at": _now()}
            r["ingest"] = ingest(st, a.cloud, a.token)
            r["generate"] = generate(st, a.endpoint, a.model)
            r["publish"] = publish(st, a.cloud, a.token)
            r["export"] = export(st, pathlib.Path(a.out), recent=a.recent,
                                 fresh_window_s=a.fresh_window,
                                 record_retire=not a.no_retire)
            print(json.dumps(r, ensure_ascii=False), flush=True)
            if a.rounds and n >= a.rounds:
                return 0
            time.sleep(a.interval)
    return 2


if __name__ == "__main__":
    sys.exit(main())
