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

## 九、結果（三組判準各自的判決，全部照事前規則）

### §四（主判準）

```
verdict                STATIC_CEILING_REFUTED_BY_MAX        （R1；R6 沒點火，見下）
R5                     PREFLIGHT_REFUTED   lat_ratio 16.74  （292.574 s vs 成功通中位 17.478 s）
T_max_ok               34529  （CONFORM lcb_3674；同 run、同 server_model、失敗後 +150.1 分）
T_fail_lo / T_fail_hi  15850.2 / 21790.8
P_fail_est             531.2  （chars→prompt_tokens 線性校準 n=496、殘差中位 30.68／最大 247.4）
retry                  attempt=2 成功，total_tokens 6656 < T_fail_lo ⇒ **R6 依規則不點火**
overlap_self           false（但這一項無鑑別力，見 §八）
rows/calls             calls.jsonl 499 行
```

**H-A（靜態上限小於 262144）與 H-C（生成前預檢）出局。** R6 沒點火要照實寫：
重試通只生成 6069 tokens 就自然停了，**沒有**證明「同尺寸能過」。真正推翻靜態上限的是
`T_max_ok = 34529`，另外 `17574`（失敗前 53.9 分、同 run）也已經超過 `T_fail_lo`。

### §七（H-E：載入世代）

`E-SUPPORT`——但**這個支持幾乎沒有鑑別力，要當成沒有**：全歷史 51 個世代裡
`max_ok_total > T_fail_hi` 的只有 **1 個**（09-04 09:07Z，34529），所以「出 400 的世代沒有大成功通」
是結構性的、不是證據。`epoch_unknown` 排除了 5900 通成功通（早於 `/api/events` 500 筆能回溯的最早
`loaded` 事件 09-01 06:58Z）、0 通 400。
⇒ **H-E 未解決**，改用 `ops/gain/ctx_epoch_watch.py` 前瞻性攢（每輪一筆，≥6 個世代才判）。
第一筆：世代 09-04 09:07Z、`loaded_context_length = 262144`。

### §八（H-F：殭屍請求）

`F-REFUTED`——短群 6 通裡有 **2 通** `n_inflight == 0`，事前寫的是「≥2 通為 0 就推翻」。

**但殘差要照實記，因為它沒死透**：短群 **4/6** 通在起始時正好有一通**超長**請求在飛
（5187 s、3812 s、5202 s、936+550+3812 s），而同期 1984 通成功推論通的基準率只有 **14.0%**；
二項尾機率 `P(≥4 of 6 | p=0.140) = 0.00455`。
⇒ **本輪的判決仍是 F-REFUTED**（事前規則就是事前規則）。
⚠ **下輪不准把門檻就地改成「≥4/6」**——那個數字已經被本節的結果污染了。
要復活 H-F 只能用**新資料**（r447 剩下的題、或下一個 LCB run）重測，判準寫在看數字之前。

### 本輪真正立起來的事實（與假說無關，直接量到的）

1. **21 通伺服器端 `Context size has been exceeded`，客戶端只認得 6 通。**
   逐通用起始時刻對上（Δ < 1.5 s，21/21 全中），**其中 15 通在 `calls.jsonl` 裡寫的是
   `TimeoutError: timed out`**——因為客戶端 380 s／600 s 就放手，而伺服器端那通還要跑
   550–5202 s 才吐 400。19 通在 `g_r443_gemma_lcb`（E3）、2 通在 r447、**MBPP 的三個 run 一通都沒有**。
2. **8766 有 `/api/requests`（含 `only_errors`、`since/until`、`status_code`、`finish_reason`、
   伺服器端 `latency_ms`）與 `/api/events`（模型 load/unload）兩個唯讀端點**，本輪才發現。
   它的 `ts` 是**起始**時刻（用我們自己的通逐筆對過：`server.ts ≈ client.ts_ms − latency_ms`，差 ~1 s）。
3. **gemma 在 1004 每小時被 unload／load 一次**（排程，不是我們觸發），一個 run 橫跨多個世代。
4. 21 通 400 的「爆掉時已生成量」估計橫跨 2,615–380,287（三個數量級）
   ⇒ **拒絕點不是固定 token 數**。長群（≥40k）用「真的跑到 262144」就解釋得完
   （長生成會變慢、est 高估）；**短群（2.6k–21.4k）到今天沒有解釋**。

### 收官要怎麼寫這一條（取代「400 的來源未歸因」）

> r447 的 400 **不是**靜態 context 上限、**不是**生成前預檢（兩者都有事前判準、都被推翻）。
> 它屬於一群 21 通同類事件的「短群」，該群沒有解釋；「殭屍請求佔住 KV cache」這個具體機制
> 在事前判準下被推翻（但留了一個 p=0.005 的殘差，要用新資料重測）。
> **這通失敗對 P-Z1..P-Z8 沒有影響**：它是 OFF5 臂的一通 gen，重試成功，`infra_void` 仍為 0。

### 對實驗本身的意涵（不改任何判決，只是把話講清楚）

- **`TimeoutError` 在 gemma+LCB 上不是「連線抖動」**，至少 15 通已證實是伺服器端的
  context 事件。往後 run 的失敗分類要把這兩者當同一類寫，或去 8766 對一次。
- **MBPP 三個 run（r444/r445/r446）0 通**：這是 LCB 題型（長輸出）的性質，不是端點壞了。
  r446 的收官結論不受影響。
