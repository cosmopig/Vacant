# R447：把「Context size has been exceeded」400 歸因——判準寫在量測之前

（2026-09-04 11:5x UTC，Opus 5，round707。這是
`DECISION_20260904_R447_FABLE_AUDIT_RETRY_RULING.md` §二(d) 唯一留下的開放問題。
**本檔在跑任何量測腳本之前寫定並 commit**；量完不准回頭改判準——只准照實記
「觸發了哪一條」與「冒出了哪一類事前沒想到的」。零 API，只讀 `calls.jsonl`。）

## 一、要回答什麼

`runs/g_r447_conform_lcb2/calls.jsonl` 有一通 `OFF5 / lcb_3779 / gen / attempt=1`
在 292574 ms 之後收到 `HTTP 400 body={"error":"Context size has been exceeded."}`。
8766 唯讀查到 gemma 在 1004 的 `loaded_context_length = 262144`，兩者對不上。

**這個問題不影響 r447 的任何實驗判決**（P-Z1..P-Z8 都不依賴它）。做它的理由是：
收官報告要嘛具名寫出原因，要嘛寫「未歸因」——現在是後者，本輪試著換成前者。

## 二、候選假說

| 代號 | 假說 |
|---|---|
| H-A | 端點的**靜態** context 上限遠小於 262144（設定／量化版本不同），15k 級就爆 |
| H-B | 並行 slot 均分 context：失敗當下有別的請求在飛，該通只分到一小塊 |
| H-C | 400 是**生成前**的預檢（prompt + max_tokens > n_ctx），與實際生成長度無關 |
| H-D | 8765 中轉自己的上限／路由到另一個節點（我們看不見的那台） |

## 三、量測量（全部從 calls.jsonl 算，另附 launch.log）

1. `T_max_ok` ＝ 全 run 成功 gen 通的 `usage.total_tokens` 最大值。
2. `T_fail` ＝ 失敗那通的總 token 估計。它沒有 `usage`（失敗通不落 usage），所以：
   - `P_fail`：prompt 全文有落盤 ⇒ 用**成功通的 chars→prompt_tokens 迴歸**校準後估。
     校準品質要一起報（殘差中位數／最大值），校不準就不准用。
   - `C_fail`：completion 未知 ⇒ 用 (a) 同題近同延遲的成功通、(b) 全 run 中位 tok/s × 292.574 s
     兩條路各估一次，取兩者張成的區間 `[T_fail_lo, T_fail_hi]`。
3. `retry_usage`：同 (arm, task_id, role) 的重試那通若成功，它的 `usage.total_tokens`。
4. `overlap_self`：把每通的區間寫成 `[ts_ms − latency_ms, ts_ms]`（記憶：`ts_ms` 是**結束**時刻），
   問失敗那通與我們自己的哪些通重疊。
5. `lat_median_ok`：成功 gen 通的延遲中位數。

## 四、判決規則（事前）

- **R6（最強、優先於 R1/R2）**：若 (3) 的重試通成功且 `total_tokens ≥ T_fail_lo`
  ⇒ **`STATIC_CEILING_REFUTED_BY_RETRY`**。同一份 prompt、幾分鐘內、同等量級的 token
  能過，靜態上限就不可能是原因 ⇒ H-A、H-C 出局，留下 H-B／H-D（本輪的資料分不開這兩個）。
- **R1**：若 `T_max_ok > T_fail_hi` ⇒ `STATIC_CEILING_REFUTED_BY_MAX`。
- **R2**：若 `T_max_ok < T_fail_lo` 且存在整數冪次 L ∈ {8192,16384,32768,65536,131072}
  使 `T_max_ok < L ≤ T_fail_hi` ⇒ `STATIC_CEILING_CONSISTENT(L)`（**consistent 不是 confirmed**）。
- **R3**：以上皆非 ⇒ `INCONCLUSIVE_MAGNITUDE`。
- **R5（H-C）**：若 `lat_fail > 10 × lat_median_ok` ⇒ `PREFLIGHT_REFUTED`（400 不是生成前預檢，
  那通確實生成了很久）。否則 `PREFLIGHT_NOT_REFUTED`。
- **R4（H-B）**：`overlap_self = true/false`。**false 不等於沒有並行**——別的客戶端打同一個
  中轉我們看不見。所以 R4 只能單向支持 H-B，不能反證，收官必須這樣寫。

## 五、事前預期會冒出來的第三類

若失敗那通的 **prompt 本身**就異常大（例如 `P_fail` 是全 run 前 1%），那它就不是「輸出失控」
而是「輸入失控」，屬於事前沒列的第五個假說。冒出來就**照實加寫一節、人眼確認、不當場改上面的判準**。

## 六、本輪不做什麼

- **不打 1234、不改 8766 任何設定、不重跑那通**（run 還活著；SPEC_GAIN §7 一端點一 run）。
- 結論若是 H-B／H-D 二選一分不開，就寫「narrowed to {H-B, H-D}」，**不准挑一個當結論**。

---

## 七、量測中途冒出來的第五個假說 H-E（判準寫在算它之前）

§四 跑完得到 `STATIC_CEILING_REFUTED_BY_MAX` ＋ `PREFLIGHT_REFUTED` 之後，
8766 的**唯讀**明細（`/api/requests`、`/api/events`，本輪才發現這兩個端點存在）冒出兩件
§二 完全沒列的事實：

1. `/api/events`：gemma **每小時被 unload／load 一次**（1004 上的排程，我們不控制）。
   ⇒ 一個 run 橫跨多個「載入世代」。
2. `/api/requests?only_errors=true`：24h 內有 **21 通** `Context size has been exceeded`，
   而 r447 的 `calls.jsonl` 只記到 1 通。

⇒ **H-E：每請求的有效 context 不是 262144，而是隨「載入世代」變動**（例如某次
load 用了較小的 context）。這是 §五 講的「冒出來就照實加寫一節、不當場改上面的判準」。
§四 R1/R5/R6 的判決**不因本節改變**。

### 判準（在跑之前寫死）

把 `/api/events` 相鄰兩個 `loaded` 之間切成世代；每個世代算兩件事：
`max_ok_total` ＝ 我們成功 gen 通的 `usage.total_tokens` 最大值；`n_ctx400` ＝ 該世代的 400 通數。

- **E-KILL**：若存在**任一世代**同時有 (a) 一通 context-exceeded 400 且
  (b) 一通成功且 `total_tokens > T_fail_hi`（21791）⇒ **H-E 被推翻**，
  因為同一個載入世代不可能既容得下 21791 又在 15850 就爆。
- **E-SUPPORT**：若所有出現 400 的世代其 `max_ok_total` 都 `< T_fail_hi`，
  且至少一個沒出 400 的世代 `max_ok_total > T_fail_hi` ⇒ **H-E 得到支持（不是證實）**。
- 其餘 ⇒ `E-INCONCLUSIVE`。

**先驗風險自曝**：世代切割用的 `/api/events` 只有 100 筆上限，蓋不到的時段一律標
`epoch_unknown` 並排除，**排除幾通要具名寫出來**，不准安靜丟。

## 八、H-F「殭屍請求佔住 KV cache」——判準寫在算它之前

§七 的世代表跑完之後，把 21 通 context-400 的伺服器端延遲乘上 LCB 兩個 run 的
成功通中位速率（73.11 tok/s），得到的「爆掉時已生成量」量級是 **2,615 到 380,287**，
橫跨三個數量級 ⇒ **拒絕點不是固定 token 數**，而且明顯分兩群：

- **長群**（server lat 550–5202 s，est 40k–380k）：這群用「真的跑到 262144」就解釋得完
  （長生成本來就會變慢，est 會高估）。
- **短群**（server lat 36–293 s，est 2.6k–21.4k）：**任何合理速率都到不了 262144**
  （最快觀測速率 ≈76 tok/s × 293 s ≈ 22k）。這群需要別的解釋。

**H-F**：客戶端 380 s／600 s 逾時之後，**伺服器端那通還活著**（實測最久 5202 s），
它佔著 KV cache；接下來的請求只分得到剩下的一小塊，於是在 2–20k 就被判「context 爆了」。
⇒ 這是 H-B（並行分割）的一個具體版本，而且**並行的來源是我們自己丟掉的殭屍請求**，
所以 §四 R4 在 `calls.jsonl` 上看不到——客戶端早就不認那通了。

### 判準（在算之前寫死）

對每通 context-400，用 `/api/requests` 數「起始時刻落在別的 gemma 推論請求
`[ts, ts+lat]` 區間內」的通數 `n_inflight`（只算 `latency_ms > 0` 的推論通，
排除 0 秒的監控輪詢）。同一段期間對**成功**的推論通算同一個統計當**基準率**。

- **F-SUPPORT**：短群 **≥5/6** 通 `n_inflight ≥ 1`，**且**同期成功通的基準率 **< 50%**。
- **F-REFUTED**：短群 **≥2** 通 `n_inflight == 0`。
- 其餘 ⇒ `F-INCONCLUSIVE`。

**基準率那一項是刻意加的**：§七 的 `E-SUPPORT` 事後看幾乎沒有鑑別力
（全歷史只有一個世代 `max_ok > T_fail_hi`，所以「沒有反例」是結構性的、不是證據）。
不想再收一個空洞的支持。
