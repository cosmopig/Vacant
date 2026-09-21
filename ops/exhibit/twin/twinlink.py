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

4. **`/api/queue` 這條路會漏件。** 它只回 `status='queued'`，電視那端一 claim
   就看不到了。要不漏就得走 `/api/all`（本次新增，唯讀、不 claim）。
   雲端還沒部署到有 `/api/all` 的版本時，這一支會**明講自己走的是會漏的那條路**
   （`mode: "queue_lossy"`），不會假裝抄全了。

用法：
    python3 ops/exhibit/twin/twinlink.py selftest                 # 離線自檢＋負控制
    python3 ops/exhibit/twin/twinlink.py ingest   --cloud URL --token T
    python3 ops/exhibit/twin/twinlink.py generate --endpoint http://100.119.113.56:1234/v1
    python3 ops/exhibit/twin/twinlink.py publish  --cloud URL --token T
    python3 ops/exhibit/twin/twinlink.py export   --out live/visitors.json
    python3 ops/exhibit/twin/twinlink.py serve    --port 8901      # 唯讀
    python3 ops/exhibit/twin/twinlink.py serve    --port 8901 --allow-withdraw
    python3 ops/exhibit/twin/twinlink.py withdraw --id <sub_id>   # 紙本撤回走這條
    python3 ops/exhibit/twin/twinlink.py loop     --cloud URL --token T --endpoint ...
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
    msg = ((body or {}).get("choices") or [{}])[0].get("message", {}) or {}
    usage = (body or {}).get("usage") or {}
    text = msg.get("content", "")
    return {
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

def build_view(store: TwinStore) -> dict[str, Any]:
    v = store.verify()
    people = []
    withdrawn = 0
    for c in store.roster():
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
        })
    return {
        "generated_at": _now(),
        "store_id": store.store_id,
        "chain": {"ok": v["ok"], "checked": v["checked"],
                  "head": v.get("head"), "genesis": v.get("genesis")},
        "counts": {"visitors": len(people), "events": store.count(),
                   "gaps": store.count(KIND_INGEST_GAP),
                   "errors": store.count(KIND_ERROR),
                   "withdrawn": withdrawn},
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


def export(store: TwinStore, out: pathlib.Path) -> dict[str, Any]:
    out = pathlib.Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    view = build_view(store)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(view, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(out)  # 原子換檔：螢幕不會讀到寫到一半的 JSON
    return {"ok": True, "out": str(out), "visitors": len(view["people"])}


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
          allow_withdraw: bool = False, withdraw_token: str | None = None) -> int:
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
                    self._send(build_view(st))
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

        print("7. 負控制：繞過 trigger 竄改一列，verify 必須變紅")
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
    print("selftest 全綠（含 5 個負控制）")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _p(o: Any) -> None:
    print(json.dumps(o, ensure_ascii=False, indent=2))


def main(argv: Iterable[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="twinlink — 手機→公網→DB→1003→螢幕")
    ap.add_argument("--db", default=str(DEFAULT_DB))
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

    v = s.add_parser("serve")
    v.add_argument("--port", type=int, default=8901)
    v.add_argument("--bind", default="127.0.0.1")
    v.add_argument("--allow-withdraw", action="store_true",
                   help="開 POST /withdraw/<id>（現場螢幕那台不要開）")
    v.add_argument("--withdraw-token", default=None,
                   help="給撤回加一把共用 token。**預設不加**，"
                        "理由寫在 serve() 的 docstring")

    wd = s.add_parser("withdraw", help="撤回 → 上鏈 → unlink → PERSONA_ERASED")
    wd.add_argument("--id", required=True)
    wd.add_argument("--reason", default="subject_request")

    s.add_parser("selftest")
    s.add_parser("view")

    lp = s.add_parser("loop")
    lp.add_argument("--cloud", default=DEFAULT_CLOUD)
    lp.add_argument("--token", required=True)
    lp.add_argument("--endpoint", default=None)
    lp.add_argument("--model", default=DEFAULT_MODEL)
    lp.add_argument("--interval", type=float, default=10.0)
    lp.add_argument("--rounds", type=int, default=0, help="0＝永遠（展場無人值守）")
    lp.add_argument("--out", default=str(TWIN / "store" / "visitors.json"))

    a = ap.parse_args(list(argv) if argv is not None else None)

    if a.cmd == "selftest":
        return selftest()
    if a.cmd == "serve":
        return serve(pathlib.Path(a.db), a.port, a.bind,
                     allow_withdraw=a.allow_withdraw,
                     withdraw_token=a.withdraw_token)

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
        _p(export(st, pathlib.Path(a.out))); return 0
    if a.cmd == "view":
        _p(build_view(st)); return 0
    if a.cmd == "withdraw":
        out = withdraw(st, a.id, reason=a.reason, source="cli:withdraw")
        _p(out)
        return 0 if out.get("ok") else 1
    if a.cmd == "loop":
        n = 0
        while True:
            n += 1
            r = {"round": n, "at": _now()}
            r["ingest"] = ingest(st, a.cloud, a.token)
            r["generate"] = generate(st, a.endpoint, a.model)
            r["publish"] = publish(st, a.cloud, a.token)
            r["export"] = export(st, pathlib.Path(a.out))
            print(json.dumps(r, ensure_ascii=False), flush=True)
            if a.rounds and n >= a.rounds:
                return 0
            time.sleep(a.interval)
    return 2


if __name__ == "__main__":
    sys.exit(main())
