# DECISION 2026-09-20 — 數位分身接上 append-only 真相來源，1003 存取，整條鏈接通

人類原話（2026-09-20）：

> 「現在的數位分身要接上你在 supabase 的這個數位分身服務上開個 sqlite 之類的去存資料
> 就好了啊，然後 1003 去存取他，且資料不要刪除，所以全部都接上，然後數位分身要好
> 要能用，把所有都跑一次」

---

## 一、查到的事實（先講「不存在」的那一個）

### 1-1 **沒有 supabase。一個都沒有。**

`Vacant`、`vacant-docs-web`、`vacant_hm`、`vacant-world-cloud` 四個 repo
全文搜尋 `supabase` **零命中**；環境變數、`~/.config` 也沒有。

人類說的「你在 supabase 的這個數位分身服務」實際上是
**`~/Documents/GitHub/vacant-world-cloud`**——一支自架的 Express，
部署在 **Zeabur**，網址 `https://vacant-world.cosmopig.com`，
`git log` 七個 commit、首個 commit 訊息是「init: Vacant 展場雲端收單服務」。
它**只依賴 express**，不是 supabase、不是任何 BaaS。

> 判斷：這是口語上的代稱（「雲端那個後端」），不是真的有一個 supabase 專案。
> **我沒有去申請任何 supabase 帳號，也沒有動任何憑證。**

### 1-2 這條鏈原本斷在哪

既有的東西比 repo 地圖上寫的多——**`vacant_hm/world3/bridge.js` 這一段從來沒有
出現在 `CLAUDE.md` 的程式碼地圖上**，所以「觀眾生的卡怎麼回到現場」看起來像是
完全沒做，其實做了一半：

```
觀眾手機 ──▶ vacant-world.cosmopig.com ──▶ world3/bridge.js（瀏覽器輪詢）──▶ 電視畫面
            ✅ 通                          ✅ 通                          ✅ 通
```

真正斷掉的是三件**不在畫面上、但違反硬約束**的事：

| # | 斷點 | 違反什麼 | 證據 |
|---|---|---|---|
| A | 雲端 `persist(sub)` 是**原地覆寫**：`queued→claimed→done` 蓋同一個 JSON 檔 | 「資料不要刪除」 | `server.js` L38–42（改動前） |
| B | 雲端**沒掛 volume 就歸零**，且那是唯一一份 | 離線紅線（真相來源在雲端） | 那個 repo 的 `README.md` 自己寫明 |
| C | **1003 完全不在這條鏈上**。world3 演的是 371 筆凍結重放，一通模型都不打 | 「數位分身要能用」 | `world3/index.html` 全文無 `1234`／`100.119`／`/v1/chat` |

另外：`bridge.js` 的狀態**全在瀏覽器記憶體**（那支自己寫「展場一天一開機，
不需要跨重啟持久化」），所以關掉 Chrome 就什麼都不剩。

---

## 二、做了什麼

### 2-1 本機 append-only 真相來源（新）

`ops/exhibit/twin/twinstore.py` — SQLite 事件庫。

* **append-only 是可執行的**：`UPDATE`／`DELETE` 由 SQLite trigger `RAISE(ABORT)`
  擋下。不是慣例，是寫了就炸。而且**重開 store 會把被拔掉的 trigger 補回去**。
* **狀態是摺疊不是欄位**：`current()` 走一遍事件流算出「現在」。
  要改狀態就追加一列，從不回頭改舊列。
* **雜湊鏈**：每列 `prev_sha256` 接上一列的 `row_sha256`，創世串含 `store_id`
  （兩個庫不可能長出同一條鏈）。`verify()` 退出碼 0 綠 / 1 紅。

### 2-2 接線（新）

`ops/exhibit/twin/twinlink.py` — `ingest` / `generate` / `publish` /
`export` / `serve`（唯讀）/ `loop`（無人值守）/ `selftest`。

### 2-3 雲端那一側（改）

* `vacant-world-cloud/eventlog.js`（新）— append-only 事件流。
  `node:sqlite` 可用就走 SQLite（**也有 trigger**），否則退到 JSONL，
  **開機橫幅印出實際走的是哪一條，不准用猜的**。
* `server.js`（改）— `submit`／`claim`／`result` 三處各追加一列事件；
  新增 **`GET /api/all`（唯讀、token、不 claim）**。

  > 為什麼非要 `/api/all`：`/api/queue` 只回 `status='queued'`，
  > **電視一 claim 就看不到了**。本機抄寫端如果走 queue 就會漏件，
  > 而且是「電視跑得越順漏得越多」這種最難發現的漏法。
  > `/api/all` 唯讀 ⇒ 兩個消費端可以並存。
  > 雲端還沒部署到有 `/api/all` 的版本時，`ingest` 會退到 queue
  > 並**明講 `mode: "queue_lossy"`**，不假裝抄全了。

### 2-4 架構與離線行為

```
 觀眾手機 ──▶ vacant-world.cosmopig.com ──ingest──▶ twinstore.sqlite3 ──generate──▶ 1003 LM Studio
  (公網)        郵箱：會覆寫、會歸零         唯讀     真相來源：append-only      本機，不出機殼
                       ▲                              │  │
                       └──── publish（盡力而為）──────┘  └── export/serve ──▶ 現場螢幕
```

| 斷掉的東西 | 展場還能跑嗎 | 退化成什麼 |
|---|---|---|
| 公網 | **能** | `ingest`／`publish` 停，各記 `ingest_gap`／`error`；已進庫的分身照常生成上螢幕。**新觀眾投不進來**——但那本來就需要網路（觀眾要用自己的 AI）。 |
| 1003 | **能** | `generate` 退到 `fallback_deterministic`（查表、微秒級）。**`engine` 欄位跟著變，畫面分得出來。** |
| 兩個都斷 | **能** | 螢幕讀 `export` 的本機 JSON，演已在庫裡的分身。 |

---

## 三、🔴 實跑時撞到的兩個發現

### 發現 1：雲端線上版**沒有** `/api/all`（預期內，但要記）

線上打 `/api/all?token=x` 回 **404**（`/api/queue` 同樣錯 token 回 401，
證明量具會動、路徑存在與否分得出來）。我的改動**沒有部署**——
部署＝push 到 GitHub ⇒ Zeabur 自動發布，那是生產環境決定，**留給人類**（見第六節）。

### 發現 2：🔴 **公網那一頁的個資過濾器會把日期誤判成電話號碼**

端到端實跑時，一張**完全沒有個資**的卡被線上服務退回 **422「請拿掉可識別資訊再送」**。

**根因**（`vacant-world-cloud/server.js`）：

```js
const PHONE_RE = /\+?\d(?:[\s-]?\d){7,}/;   // 8 位以上、允許空白或連字號隔開
```

`2026-09-20` 攤平就是 **2,0,2,6,0,9,2,0 ＝ 8 位數字、中間只隔連字號**，完全命中。

**重現步驟**（30 秒，不需要 token）：

```sh
curl -X POST https://vacant-world.cosmopig.com/api/submit \
  -H 'Content-Type: application/json' \
  -d '{"card_text":"需求：在 2026-10-15 之前整理好桌面"}'
# → HTTP 422 {"error":"請拿掉可識別資訊再送"}
```

**確定性重現＋擋門**：`ops/exhibit/twin/probe_pii_filter.py`
（零網路、退出碼 1 代表還有誤殺；`--live` 可加打線上對照）。

本機 13 例 ⇒ **6 例誤殺、0 例漏擋**，而且**本機與線上逐例一致**
（三例線上交叉驗證：真電話 422／含日期 422／乾淨 200）：

| 卡的內容 | 該擋？ | 實際 | |
|---|---|---|---|
| `需求：打給 0912345678` | 是 | 422 | OK |
| `需求：寄給我 a@b.com` | 是 | 422 | OK |
| `需求：在 2026-09-20 之前整理好桌面` | **否** | **422** | 🔴 |
| `需求：把 2026-01-01 到 2026-03-31 的帳整理好` | **否** | **422** | 🔴 |
| `需求：整理 2025-2026 兩年的收據` | **否** | **422** | 🔴 |
| `需求：把 1999-2024 的照片分類` | **否** | **422** | 🔴 |
| `需求：算一下 12345678 這串數字的位數` | **否** | **422** | 🔴 |
| `需求：把 2026 09 20 那天的行程排好` | **否** | **422** | 🔴 |
| `需求：整理桌面` | 否 | 200 | OK |
| `需求：把 10/15 之前的待辦列出來` | 否 | 200 | OK（斜線不在 regex 裡） |

**這在展場會怎麼出事**：卡的第一欄就叫
**「需求：我最近想完成的一件具體的小事」**——「在 X 之前做完 Y」是這一欄
最自然的寫法之一。觀眾貼上、送出，畫面回他「請拿掉可識別資訊再送」，
**但他的卡上沒有任何可識別資訊**。他不知道要拿掉什麼，旁邊沒有解說員
（展場硬約束 2）。最可能的結果是**他放棄走人**，而我們的 log 只看得到一個 422，
看不到「這個人本來要參加」。

> 那個 repo 的註解自己寫了「寬到會誤殺長流水號……寧可誤殺」。
> **日期不是長流水號**，這個取捨當初大概沒把日期算進去。
> ⚠ **我沒有修**：要放寬 regex、還是改成指出「是哪一段」被判定、
> 還是維持寧可誤殺——那是產品決定，見第六節。

---

## 四、端到端實跑（兩份，各自一鍵重跑）

### 4-1 `ops/exhibit/twin/e2e_twinchain.sh` — 整條鏈，**26/26 綠，退出碼 0**

證據：`ops/exhibit/twin/evidence_twinchain_20260920/`

三張卡 → 雲端（事件流 backend=**sqlite**，3 列）→ ingest（`mode:"all"`, `pulled:3`）
→ **1003 真模型生成 3 隻分身、`degraded:0`**（`--no-fallback`，退化就炸）
→ publish 3 筆 → 觀眾端 `/api/status` 看到 `done` → export → 驗鏈 9 列全綠。

**單發延遲（實測，同一天不同時段差很多）**：
19.4s（單獨探針）／15.6s、33.9s、37.5s（最終這一輪）／1003 負載高時有一發逾時 90s。
⚠ **不要把任何一個數字當成「展場的延遲」**——觀眾是非同步輪詢手機的，
站著等的那條線是 `fallback_deterministic`（微秒級）。

真模型的輸出（`10_visitors.json`，`engine=lmstudio:gemma-4-12b-it-qat`）：

```
· 把散在桌上的收據整理成一份清單   （氣質：慢、固執、愛乾淨）
    抵達：這裡的光有點暖。
    動手：要慢慢來，把這些亂糟糟的紙張一點點歸位。
    交付：每一個細節都對過了，現在看起來乾淨許多。
· 找出清單裡重複的名字            （氣質：好奇、跳躍、愛問為什麼）
    抵達：這裡的空間是怎麼變成這種質感的？
    動手：這些名字為什麼會跳出來兩個一樣的，好有趣喔！
    交付：瞧！那些愛玩捉迷藏的重複名字都被我揪出來了。
```

1003 上那一輪（`evidence_1003_20260920/12_visitors_from_1003.json`）：

```
· 把家裡的書按顏色排一次   （氣質：懶散、固執、有點浪漫）
    抵達：這片赭紅色的光影，讓一切都顯得有些慵懶。
    動手：嘖，明明好想就這樣躺著，但為了美感還是得動手。
    交付：看吧，這排顏色堆疊出的詩意，應該會讓你心動的。
```

**氣質真的有進到語氣裡**（「嘖，明明好想就這樣躺著」對上「懶散、固執、有點浪漫」），
不是模板填空。這是我對「數位分身要好要能用」這句話能給出的最直接的證據。

### 4-2 `ops/exhibit/twin/e2e_1003.sh` — 「1003 去存取他」，**22/22 綠，退出碼 0**

證據：`ops/exhibit/twin/evidence_1003_20260920/`

這一支**把真相來源本身放到 1003 上**（`w401@100.119.113.56:/c/Users/w401/vacant_twin/store/twinstore.sqlite3`），
由 1003 自己 ingest、自己 generate（打**它自己的 `127.0.0.1:1234`，不出機殼**）、
自己驗鏈、自己 export，再由 1003 回寫雲端。

關鍵證據：
* `07_remote_db_on_disk.txt`：`-rw-r--r-- 1 w401 197121 24576 .../twinstore.sqlite3` ＋ `rows 2`
  ——**檔案實體在 1003 的磁碟上**。
* `15_remote_appendonly.txt`：**在 1003 上**跑 UPDATE 與 DELETE，兩句都被 trigger 擋下。
* `16_remote_tamper.json`：**在 1003 上**竄改副本 ⇒ `ok:false, broken_at:2`。
* 斷網段：把 Mac 的雲端關掉（先確認 `http_code=000` 才敢說斷了），
  1003 那份現場資料**還是兩個人**，`ingest_gap` +1，鏈還是綠的。

> ⚠ **1003 的真相來源刻意留著不刪**（那正是「資料不要刪除」）。

### 4-3 五個實跑時被抓出來的量具說謊（留紀錄，因為都很容易重犯）

1. **`( cd X && node server.js & echo $! )` 拿到的是 subshell 的 PID**，
   不是 node 的。第一版的「斷網演練」殺錯對象，node 還活著、curl 照樣回 200——
   **演練是假的**。現在改成直接 `node ... &` 取 `$!`，而且
   **要輪詢確認 `http_code=000` 才敢宣稱斷網**。
   順帶：孤兒 node 佔住埠讓下一輪跑在**上一輪的殘留狀態**上（submitted 從 3 變 6）
   ⇒ 現在埠被佔就 **fail-closed 拒絕啟動**。
2. **全形「（」會被 bash 併進變數名**：`$GAPS（` 在 `set -u` 之下 unbound variable。
   中文輸出踩得到，要寫 `${GAPS}`。
3. **1003 有三種路徑方言**：`ssh` 用 `/c/...`、`scp` 用 `C:/...`、
   而 MSYS 只會轉換**裸參數**——寫在 python 字串字面值裡的 `/c/...` 不會被轉，
   於是 `unable to open database file`。
   ⚠ 這個一度造成**假綠**：竄改負控制的 inline python 失敗 ⇒ 副本沒生成 ⇒
   verify 對著不存在的檔案回 1 ⇒ `chk $? 1` 通過。
   **「紅」的原因不對，綠就不算數**——現在分兩段各自判（先證明副本真的被竄改）。
4. 🔴 **`cmd | tee f` 之後的 `$?` 是 tee 的退出碼**，而 tee 幾乎永遠回 0。
   踩到兩處：(a) python 以 `TimeoutError` 崩掉，腳本照印
   `[OK] generate 退出碼（得 0）`；(b) **「雜湊鏈驗證通過」那一行根本沒在看
   `verify` 的退出碼**——它從第一版起就是弱檢查。
   現在改成 `run <檔名> <指令…>`：先重導向落盤、取 `$?`、再 `cat`，退出碼原樣回傳。
   > 這條是本次最該記住的：它讓一個**核心判準**（鏈驗不驗得過）在四輪實跑裡
   > 一直印綠燈而沒有真的量。事後看鏈確實是綠的（`11_verify.json` 寫著 `"ok": true`，
   > 而且竄改負控制確實變紅），**但那是運氣不是驗證**。
5. **`--timeout 90` 不夠**：三張卡裡有一張在 1003 上 `TimeoutError`。
   現在預設 300 秒（`DEFAULT_GEN_TIMEOUT`）。
   ⚠ 這個數字**不是展場的互動延遲**——觀眾是非同步輪詢自己的手機，
   不是站著等這一發。

### 4-4 另一個模型層的坑：**1003 是 thinking 模式，`max_tokens` 會被思考吃光**

`max_tokens=300` 時，實測 289 個 completion token 裡 **266 個是 reasoning**，
`content` 回**空字串**。看起來像「模型不照格式回話」（會去改 prompt，改不好），
真正要動的是那個數字。

⚠ **但把數字調大只是把懸崖往後推。** 同一支 prompt 兩次實跑，reasoning 分別用掉
**1462** 與 **1597** token——`MAX_TOKENS=1600` 第一次過、第二次 `content` 空。
最終落盤的事件裡還看得到 1003 上有一發吃掉 **1808** 個 reasoning token。

所以改成**偵測特徵再升額重試一次**（`_squeezed_out`）：
`content` 空 **而且** `reasoning_tokens ≥ 額度 × 0.85` ⇒ 判定為被思考擠掉，
用 3 倍額度重試一次，並把 `budget_escalated` 寫進事件。
兩個條件缺一不可——只看 `content` 空會把「模型真的沒話說」也判成這個，
升額重試就白花一次機時（判準測試 `test_squeezed_out_needs_both_conditions`）。

`reasoning_tokens`／`completion_tokens`／`reasoning_chars`／`budget_escalated`
全部寫進事件流，日後換機器比得出來（見 `evidence_*/…_event_stream.json`）。

---

## 五、驗收與負控制

`tests/test_twinstore.py` — **35 個測試全過**。

負控制（故意弄壞，證明檢查會紅）：
* `test_update_and_delete_are_blocked`
* `test_tampering_any_column_turns_verify_red` — **四個欄位各一組**
  （`payload_json`／`source`／`kind`／`sub_id`），不是只測 payload
* `test_offline_ingest_reports_null_not_zero` ＋對照組
  `test_successful_empty_ingest_reports_zero`（真的是空才准寫 0）
* `test_fallback_is_labelled_not_disguised`、`test_no_fallback_raises_instead_of_lying`
* `test_ks1_blocks_forbidden_wording`（鐵律 1）
* `test_parser_returns_none_for_garbage` — 7 種垃圾輸入都要回 `None`
* `test_read_only_mode_cannot_write` — 唯讀端點要由 SQLite `mode=ro` 強制，
  **附對照組**（同一個檔用可寫模式開就寫得進去 ⇒ 證明剛剛擋下來的是 `mode=ro`，
  不是檔案壞了或權限不對）
* `test_escalates_at_most_once_then_falls_back` — 升額重試**只准一次**
  （無限重試會讓展場在模型壞掉時卡死）
* `test_no_escalation_when_model_merely_misformats` — 模型有回話但格式不對
  **不該**升額（升額解決不了格式問題）

**對測試本身的負控制**：把 `twinstore.py` 的 `no_delete` trigger 拿掉再跑，
`test_update_and_delete_are_blocked` 與 `test_reopening_restores_the_triggers`
**立刻紅**（`DID NOT RAISE`）。還原後 35 個全綠。
⇒ 這批測試量得動，不是形狀好看的綠燈。

**另外修掉的一個真缺陷**：`twinlink serve` 自稱唯讀，但每一次 GET 都
`TwinStore(path)` ⇒ 跑 `mkdir` ＋ `executescript(SCHEMA)`，**那是寫入**。
現在唯讀有兩層：只實作 `do_GET`，且以 `file:…?mode=ro` 開檔。

---

## 六、🔴 要人類決定的（我停在這裡，沒有自己決定）

1. **雲端要不要部署？** `vacant-world-cloud` 的改動（`eventlog.js` ＋ `/api/all`
   ＋三處事件記錄）**已寫好、本機跑過，但沒有 commit 也沒有 push**。
   push ⇒ Zeabur 自動發布 ⇒ 動到正在對外服務的生產環境。**要不要發、什麼時候發，你決定。**
2. **`VENUE_TOKEN`。** 它不在任何我讀得到的地方（只在 `mac_kiosk.sh` 裡當參數名出現）。
   沒有它就無法對**線上**服務跑 ingest／publish。端到端我是用**本機起同一份 `server.js`**
   跑完的（程式路徑完全相同），線上只驗到公開端點那一段。要對線上跑完整鏈，**給我 token**。
3. **422 誤殺要怎麼收？** 三個方向，取捨不同：
   (a) 放寬 `PHONE_RE`（例如排除 `\d{4}-\d{2}-\d{2}` 這類日期形狀）——漏擋風險升高；
   (b) 維持寧可誤殺，但**把錯誤訊息改成指出是哪一段**被判定，讓觀眾知道要改什麼；
   (c) 兩個都做。
   **我傾向 (b) 優先**（不動安全取捨、直接解決「觀眾不知道要改什麼」這個展場傷害），
   但這是產品決定。
4. **1003 在展場現場嗎？** 目前的 4-2 證明的是「真相來源可以放在 1003 並由它自己跑完」。
   如果展場那台 Linux VM 不是 1003，那就是同一套程式換一台機器跑
   （`twinstore.py`／`twinlink.py` 只用 stdlib，Mac／Windows／Linux 都跑過或可跑），
   但**模型要從哪裡來**要重新決定（走 Tailscale 打 1003 ⇒ 展場就依賴網路了，
   跟離線紅線衝突）。

---

## 七、沒做到／沒量到（明講）

* **沒有對線上服務跑完整鏈**（缺 `VENUE_TOKEN`）。線上只驗到：服務活著、
  `/api/submit` 收得下、`/api/status` 讀得到、`/api/all` 是 404（＝舊版）、
  錯 token 401、個資過濾 422。
* **沒有部署**任何東西到 Zeabur。
* **沒有接上 `world3/index.html`**。`export` 出來的 `visitors.json` 與
  `serve` 的唯讀端點已經備好，但**電視那一頁還沒有讀它的程式碼**——
  `bridge.js` 目前仍直接輪詢雲端。要讓電視改讀本機（離線紅線的最後一哩）
  需要改 `world3`，那是另一個 repo、而且會動到正在運作的展件，我沒有動。
* **沒有量「展場實際併發」**。所有數字都是 2–3 張卡的量級。
  真實展期同時十幾個人投卡時的行為**沒有量過**，不要當成量過。
* **沒有外部錨定鏈頭**。雜湊鏈證明的是「改一列看得出來」，
  **不是「竄改不可能」**——拿得到檔案的人可以整條重算。誠實邊界寫在
  `twinstore.py` 的 docstring，不要讀成做了更強的保證。
* **1003 的 `fallback_deterministic` 路徑沒有在 1003 上實跑過**
  （只在 Mac 的 selftest 跑過）。1003 上跑的兩次 generate 都是 `--no-fallback`。

---

## 八、檔案

新增（Vacant repo）：
* `ops/exhibit/twin/twinstore.py`
* `ops/exhibit/twin/twinlink.py`
* `ops/exhibit/twin/probe_pii_filter.py`
* `ops/exhibit/twin/e2e_twinchain.sh`
* `ops/exhibit/twin/e2e_1003.sh`
* `ops/exhibit/twin/serve_check.sh`
* `tests/test_twinstore.py`
* `ops/exhibit/twin/evidence_twinchain_20260920/`
* `ops/exhibit/twin/evidence_1003_20260920/`
* `ops/exhibit/twin/evidence_live_20260920/`
* `ops/exhibit/twin/evidence_serve_20260920/`

改動（`~/Documents/GitHub/vacant-world-cloud`）：
* `eventlog.js`（新）
* `server.js`（`/api/all` ＋三處事件記錄 ＋開機橫幅）
* 🔴 **已 commit 到本機分支 `feat/append-only-eventlog`（166bada），
  `main` 沒有動，也沒有 push。** push ⇒ Zeabur 自動發布，那是人類的決定。
  要發：`cd ~/Documents/GitHub/vacant-world-cloud && git checkout main &&
  git merge feat/append-only-eventlog && git push`。
  **發完先看 Zeabur 的開機 log 有沒有 `backend=sqlite`**——
  node:sqlite 要 Node ≥ 22.5，那台跑什麼版本我量不到。

### 執行期資料放哪

`.gitignore` 排除 `ops/exhibit/twin/store/` 與 `evidence_*/**.sqlite3`。
**這不是「資料可以刪」**：真相來源活在展場那台／1003 的磁碟上
（`w401@100.119.113.56:/c/Users/w401/vacant_twin/store/twinstore.sqlite3`，
刻意留著不刪），repo 裡放的是那一次跑的**人讀證據**
（`*_event_stream.json`、`04_cloud_events.jsonl`、verify／stats 輸出）。
兩者不是同一份東西。

---

## 九、追加（同日稍晚）— 缺口 F 已補：`fallback_deterministic` 在 1003 上實跑過了

第七節原本寫著：「1003 的 `fallback_deterministic` 路徑沒有在 1003 上實跑過
（只在 Mac 的 selftest 跑過）。1003 上跑的兩次 generate 都是 `--no-fallback`。」
這裡補上。

一鍵重跑：`ops/exhibit/twin/probe_fallback_1003.sh`（**18/18 綠，退出碼 0**）。
證據：`ops/exhibit/twin/evidence_1003_fallback_20260920/`。

**做法**：開一個**新** store（`store_fallback_test/twinstore.sqlite3`，
與既有真相來源 `store/twinstore.sqlite3` 完全分開、都沒有動它）；端點指到
1003 本機一個沒人聽的埠（`127.0.0.1:19191`）——**不是關掉 1234 的 LM Studio**，
測試前後都用 `curl 127.0.0.1:1234/v1/models` 確認模型還在（`02_remote_lms_before.json`／
`13_remote_lms_after.json`）。

* **正控制**：3 張卡、端點指到不通的埠 → **3/3 真的退化**（`roster` 摺疊出來
  `engine=fallback_deterministic`、`degraded_from=lmstudio:gemma-4-12b-it-qat`），
  鏈仍綠（`06_remote_verify_after_degrade.json`：`checked=6`）。
* **負控制**：同一條指令，端點指回真的 `1234`，`--no-fallback`（退化就炸）
  → **2/2 真模型回話**（`engine=lmstudio:gemma-4-12b-it-qat`，`degraded=0`，
  沒有炸），鏈仍綠（`10_remote_verify_after_negative.json`：`checked=10`）。
  **「退化路徑可用」這句話因此才算數**——不是端點永遠打不通所以看起來能退化。

**延遲量測（1003 上，兩個不同的東西，不要混講）**：

1. 純 `fallback_twin()` 查表本身（零網路、零 I/O）：20000 次疊代，
   均值 **0.87 μs／次**、中位數 ~1.0 μs、p95 ~1.0 μs、最大 6.7 μs
   （`11_remote_fallback_pure_latency.json`）。**跟 Mac 的「微秒級」一致，
   1003／Windows 上也成立。**
2. 🔴 **全路徑**（對不通端點的連線嘗試 ＋ 退化，`generate_one()` 整支）：
   5 次量測 **2017–2287 ms**，穩定落在 ~2.0–2.3 秒
   （`12_remote_degrade_path_latency.json`）。**這不是 `fallback_twin()` 慢**，
   是 1003（Windows）對已拒絕連線的埠，`connect()` 到收到 RST 之間本身就要
   約 2 秒（`WinError 10061`；裸 socket `connect()` 量測同樣是 ~2 秒，見
   `02b_dead_endpoint_confirmed.txt`）——這是這次才量到、文件裡以前沒寫的
   Windows 特性。

   這件事**沒有推翻**「`fallback_deterministic` 是微秒級」這句話（1 是真的），
   但補了一句原本沒人量過的話：**「一旦決定要退化」是微秒級，
   「發現要不要退化」不是**——`generate()` 目前逐筆循序處理，
   一張卡打一次不通的端點就要先吃掉這 ~2 秒，N 張卡全部連不到模型時，
   最壞情況接近 N × 2 秒起跳，不是攤成微秒級。展場實際互動是非同步輪詢手機
   （CLAUDE.md 已經寫明「不要把任何一個數字當成展場的延遲」），
   所以這不影響觀眾體感，但**無人值守的 `loop` 一輪要跑多久**這件事，
   之前沒人把「連線嘗試的固定成本」算進去過。

**沒動的東西**：1003 既有真相來源（`store/twinstore.sqlite3`）全程沒有寫入；
1003 的 LM Studio（`127.0.0.1:1234`）全程沒有關過、前後都探測到同一顆模型；
`store_fallback_test/`（1003 上的測試 store）刻意留著不刪。
