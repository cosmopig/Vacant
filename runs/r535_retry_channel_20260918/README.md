# R535 歸檔：重試回饋走哪一條管道才真的進得了模型的輸入

> **一句話（驗得到什麼、驗不到什麼）**
> 外人可以**自己重算**本輪的三個交付數字，並用跑的時候就簽好的 ed25519 收據鏈
> 證明重算用的 wire 原始位元組沒有被事後換過；外人**驗不動**的是隱藏測試套件
> 的執行結果（只有 `scores_*.json` 這一個來源，本歸檔只做內部一致性檢查，沒有
> 重跑那些測試），也**重現不了**模型那一端的行為本身（同一顆模型、同一台機器
> 再跑一次不會逐字相同）。**這不是「完全可驗證」。**

- 發射 commit `af0f0ff`｜`plan_sha256` `7a3accf9…c658e`｜`bank_manifest` `5e727b2e…c0794`
- 預註冊（判準寫在量測之前）：[`decisions/DECISION_20260919_R535_RETRY_CHANNEL_PREREG.md`](../../decisions/DECISION_20260919_R535_RETRY_CHANNEL_PREREG.md)
- 收官判定器：[`ops/gain/r535/state_r535.py`](../../ops/gain/r535/state_r535.py)
- 本歸檔的離線重算器：[`ops/gain/verify_r535_archive.py`](../../ops/gain/verify_r535_archive.py)
- 跑的時候用的驅動與題庫：[`ops/gain/r535/`](../../ops/gain/r535/)

## 一、這一輪在量什麼

`vacant run` 的可見驗收沒過，就把失敗原文交回 agent 再試（最多 3 次）。回饋有
兩條投遞管道：**寫檔進工作區**（`--feedback-into file`）與**塞進 argv**
（`--feedback-into prompt`）。2026-09-18 把 wire 解開之後看到：`file` 這條管道
的回饋文字，在第 2、3 次嘗試的請求裡出現次數是 **0**。

本輪在一個為此設計的 90 題微型題庫上，用同一顆模型（`gemma-4-12b-it-qat`）、
同一台機器、同一條 argv，四臂 × 90 題 ＝ **360 格**，量「換一條管道會不會改變
**客戶最後拿到的東西**」。

| 臂 | 意思 |
|---|---|
| `RS` | 重抽（resample），不給回饋，每次重置工作區 |
| `RF` | 重改（revise）＋回饋**寫檔**進工作區 |
| `RP` | 重改（revise）＋回饋**塞進 argv** |
| `PC` | 天花板對照：工作區直接給 `TASK_explicit.md`（**是另一個 TASK**，不進觸發率分母） |

主指標 **`M1 ≡ accepted ∧ hidden 全過`**（拒交強制 0）。
口徑：本輪講的是**可究責性**（讓依賴有根據）。

## 二、三個數字（預註冊 §〇 寫死，收官照這三個講）

以下每一個都可以用 `ops/gain/verify_r535_archive.py` 從本目錄重算。

### 數字 1 — `M7_file` 與 `M7_name`（RF 臂，第 ≥2 次嘗試的 wire）

| 層 | `M7_name`（**檔名**出現在請求裡） | `M7_file`（**回饋內容**出現在請求裡） |
|---|---|---|
| S1 | 46/46 ＝ **1.000** | 1/46 ＝ **0.022**（`s1_04_toc__RF`）|
| S2 | 22/22 ＝ **1.000** | 0/22 ＝ **0.000**（rule-of-three 上界 3/22 ＝ 0.136）|

兩個數字合起來才是那句精確的話：**「看見了檔名，沒有讀內容」**。
單看任何一個都說不出這件事——`M7_file = 0` 也可能只是「沒看到」。

⚠ **`M7_file` 是單邊的**：命中 0 只說明那幾條特徵字串沒出現在請求 body 裡，
**不說明 agent 沒有以任何方式受到那個檔的影響**。
⚠ `null` 不進分母（鐵律 3）：S1 有 4 格、S2 有 18 格沒有第 2 次嘗試，S2 另有
一格 `wire_unmappable`（index 有 66 列而 attempts 累計說 65 通，對不起來）
——那一格記 `null`，**不記 0**。

### 數字 2 — 第 1 次嘗試的可見失敗率（＝閘門作用點的實測值）

| 層 | RS＋RF＋RP 合併 | 門檻（低於它就 `NOT_TRIGGERED`）|
|---|---|---|
| S1 | 138/150 ＝ **0.920** | < 0.60 |
| S2 | 70/120 ＝ **0.583** | < 0.30 |

PC 不在分母：它的工作區是另一個 TASK，混進來會把天花板當基線。

### 數字 3 — H1 的點估計與 95% 區間（RP − RF，量 `M1`）

| 層 | 均差 | 95% bootstrap 區間 | b（RP 贏）| c（RF 贏）| McNemar exact p | Holm 調整後 |
|---|---|---|---|---|---|---|
| **S1**（n=50）| **+0.860** | **[+0.760, +0.940]** | 43 | 0 | 2.27e-13 | 4.55e-13 |
| S2（n=40）| +0.400 | [+0.225, +0.550] | 17 | 1 | 1.45e-04 | 1.45e-04 |

`state_r535.py` 對兩層都判 `CONFIRMED_POSITIVE`。
**這是對 `gemma-4-12b-it-qat` ＋ pi 0.85.1 ＋ 本題庫的結論，不可外推。**
S1／S2 **分開報，任何情況下不合併**（兩對題跨層共用參考解）。

## 三、怎麼驗（零模型呼叫、零網路）

```bash
python3 ops/gain/verify_r535_archive.py --archive runs/r535_retry_channel_20260918
```

它做十三件事，每一件單獨判綠／紅／na（實跑全綠，C1 的 22 項數字逐項對上）：

| | 檢查 | 靠什麼 |
|---|---|---|
| A1 | 逐檔 sha256 | `SHA256SUMS`（5,128 個檔） |
| A2 | 計畫釘值 | `sha256(plan.jsonl)` ＝ 發射釘值 ＝ `reconcile.json` 記的值 |
| A3 | 題庫釘值 | 360 格 `cell.json` 的 `bank_manifest_sha256` ＝ repo 內 `ops/gain/r535/bank_manifest.json` 的 sha256 |
| A4 | 360 格齊不齊 | plan／目錄／`cells.jsonl`／`scores` 四邊同一個集合 |
| A5 | **ed25519 收據鏈** | `vacant/vrun/verify_receipts.py`（repo 裡唯一那把尺）逐格驗 360 條鏈 |
| A6 | **wire ↔ 簽章 綁定** | `index.jsonl` 重算的 `wire_digest` ＝ `run_RUN-ON.json` 記的值 ＝ 收據 payload 的 `conversation_sha256` |
| A7 | **wire 位元組** | `wire.tar.gz` 解出的 body，sha256 逐個命中 `index.jsonl`（10,578 個可驗；另 50 通上游沒回話記 `null`）|
| A8 | 原始 ↔ 衍生 對帳 | `run_RUN-ON.json`（launcher 落盤）vs `scores_*.json`（評分器算的） |
| A9 | **未入帳的 wire body** | 18 個落盤卻沒進 index 的 body（半路被砍的呼叫）——問它們有沒有帶回饋原文 |
| B1 | 數字 1 重算 | 從 `.req.bin` 位元組重跑 needle，逐格比對 `cell.json` |
| B2 | 數字 2 重算 | 從 `run_RUN-ON.json` 的 `attempts[0].accepted`，再與 `scores` 對算 |
| B3 | 數字 3 重算 | b/c、McNemar exact、Holm、bootstrap 全部自己算 |
| C1 | 與 `state_r535.py` 對帳 | 22 項數字逐項比 |

### M7 為什麼**不是**「相信我們」

`M7_file`／`M7_name` 是唯一必須看**原始位元組**的數字。只給 `cell.json` 的話，
外人只能相信我們當時 grep 的結果。所以本歸檔把那些位元組整包帶進來了，
而且它們被一條**跑的時候就簽好**的鏈綁住：

```
receipts_RUN-ON.ndjson（逐格 ed25519 簽章鏈，vacant/logbook.py 的 hash-chain）
  └─ payload.conversation_sha256
       == sha256(json.dumps([[req_sha, resp_sha], …], separators=(",",":")))
          （vacant/vrun/wireproxy.py::wire_digest，逐字）
       └─ 那串 sha256 逐筆寫在 wire_RUN-ON/index.jsonl
            └─ 每一個 .req.bin／.resp.bin 的實際位元組（wire.tar.gz）
```

換一個位元組 ⇒ index 的 sha256 對不上；改 index ⇒ `wire_digest` 對不上；
改 `wire_digest` ⇒ 簽章紅。**「事後挑對自己有利的 body」這件事是簽章擋得住的。**
A5／A6／A7 三條就是在走這條鏈。

**這條鏈有兩個缺口，歸檔自己把它們印出來**（不是註腳，是 A7／A9 的輸出）：

1. **50 通「上游沒回話」**：`index.jsonl` 的 `response_sha256` 記 `null`
   （42 通 `BrokenPipeError`、8 通 `ConnectionResetError`）。`null` 不是 0，
   那 50 通不進分母。可驗的 body 因此是 10,578 個，不是 10,664。
2. **18 個 body 落盤了卻沒有 index 列**（散在 16 格）。`wireproxy` 的順序是
   先寫 body、打上游、寫回應、**最後才寫 index 列並 `requests_seen += 1`**，
   所以半路被砍的那一通會留下 body 而不進帳——因而也**不進 `wire_digest`、
   不進簽章**。這對 `M7_file` 是一個真的單邊缺口：那份請求可能已經送出去了。
   A9 就是在問「那些沒進帳的 RF 請求裡有沒有回饋原文」，實跑答案是**沒有**
   （只有 3 個帶著 `VACANT_FEEDBACK.md` 這個**檔名**，那已經計在 `M7_name`
   的 100% 裡）⇒ `M7_file` 沒有被這個缺口低估。

## 四、目錄裡有什麼

| 路徑 | 個數 | 是什麼 |
|---|---:|---|
| `plan.jsonl`／`plan_receipt.ndjson`／`plan_receipt.pub.json` | 3 | 發射前釘死「跑哪 360 格」的計畫與它的簽章 |
| `reconcile.json` | 1 | 收官對帳（360 格每格都要有一列或明寫 void）；`verdict` ＝ `OK` |
| `scores_20260919T065151Z.json` | 1 | 評分器產物：逐格可見／隱藏結果、逐次 `by_attempt` |
| `interim_S1.json`／`interim_S2.json` | 2 | 期中看（只看一次，只能停不能改門檻）——兩層都 `CONTINUE` |
| `cells.jsonl` | 1 | 逐格一列的跑況摘要 |
| `probes.jsonl`／`probe_baseline.json`／`preflight.jsonl` | 3 | 後端探針與發射前檢查 |
| `driver_s0..s3.jsonl` | 4 | 四條並行流的驅動日誌 |
| `cells/<cell>/cell.json` | 360 | **衍生量的來源**：`m7_*`／`f3_*`／`f6`／`wire_digest`／逐次 `attempts` |
| `cells/<cell>/run/run_RUN-ON.json` | 360 | **原始跑況**（launcher 落盤）：逐次 `accepted`、`feedback.text`、`requests_seen_cumulative` |
| `cells/<cell>/run/receipts_RUN-ON.{ndjson,pub.json}` | 720 | ed25519 簽章鏈與公鑰 |
| `cells/<cell>/run/visible_RUN-ON*.json` | 711 | 逐次可見驗收的原始判決（逐 case） |
| `cells/<cell>/run/wire_RUN-ON/index.jsonl` | 360 | **簽章蓋得到的那本帳**，5,314 列：`call_id`／`request_sha256`／`response_sha256`／位元組數／狀態 |
| `cells/<cell>/run/_frozen_RUN-ON*/` | 1,585 | **逐次嘗試的交付物快照**：`solution.py`／`TASK.md`／`VACANT_FEEDBACK.md`／`test_visible.py` |
| `cells/<cell>/run/_origin/TASK.md` | 90 | PC 臂用的 `TASK_explicit.md` 原件 |
| `cells/<cell>/{io.jsonl,tools.jsonl,run/rows.jsonl}` | 924 | 事件流、工具呼叫解析、逐格一列 |
| `wire.tar.gz` | 1 | **10,664 個原始 body**（5,332 個 call_id × req/resp；130 MB → 8.1 MB，確定性打包）|
| `SHA256SUMS` | 1 | 逐檔 sha256 |
| `NOT_IN_REPO.json` | 1 | **沒有進 repo 的東西**：在哪、多大、為什麼、怎麼取得 |

合計 **21.6 MB**。沒帶的東西（pi 的設定與 session 逐字稿、活工作區、
launcher console 輸出、第一次評分的 `scores.json`）全部記在
[`NOT_IN_REPO.json`](NOT_IN_REPO.json)，含檔數、位元組、`manifest_sha256`
與取得方式。⚠ 原機是 `/var/tmp`，**不保證長期存在**；長期的那一份是這裡。

## 五、驗不到什麼（不要讀成「完全可驗證」）

1. **隱藏套件的執行結果只有一個來源。** `hidden_pass` 只寫在 `scores_*.json`
   裡。歸檔帶了交付物（`_frozen_*/solution.py`）與題庫（`ops/gain/r535/bank/`），
   所以**重跑得出來**，但那要執行別人寫的碼，是稽核者的決定，不是重算器的預設。
   本歸檔只做內部一致性檢查（逐 case 的 `ok` 數 ＝ `passed`）。
2. **模型那一端不可重現。** 同一顆模型、同一台機器再跑一次不會逐字相同。
   可驗的是「**這一次**跑出來的東西沒有被事後改過」，不是「再跑一次也會這樣」。
3. **`M7_file` 是單邊量**（見數字 1 的警語）。
4. **`suitegauge` 的單邊保證**：`hidden` 全過 ≠ 做對了（擋得住已知壞解 ≠ 涵蓋
   真需求）。`M1` 量的是「兩套驗收都過了」。
5. **wire 鏈的兩個缺口**：50 通上游沒回話、18 個 body 沒進帳（見 §三）。
   第二個對 `M7_file` 是單邊缺口，A9 實測沒有踩到，但那是**這一輪的實測**，
   不是結構保證。
6. **一個沒解的資料問題**：46 格（S1）與 23 格（S2）的 `RS`／`PC` 出現
   `attempts_used ≠ 1`（不變式 I-4 破）。`state_r535.py` 只出聲、不改狀態，
   本歸檔照抄這個態度——**這件事還沒收，不要當成沒有。**
7. **檢定力**：預註冊 §七 事前算好，+10 pp 的真效果在 n=50 只有 0.086 的檢定力。
   本輪觀測到的是 +86 pp 那個尺度，但「沒顯著」在更小的效果上與「效果不是 0」
   仍然相容。
