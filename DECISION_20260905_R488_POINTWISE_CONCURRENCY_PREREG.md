# R488 預註冊：把曝光改成「時點量」，並用比較形式重解 `ts`

日期：2026-09-05（round759，Opus 5）
判準檔先於量具 commit。量具、結果各自獨立 commit。

## 為什麼有這一輪

R487（round758）對「自家造成的並行有沒有向正常請求收稅」**沒有答案**，兩個原因：

1. `ts` 語意沒解出來 ⇒ P-1 被 `TS_SENSITIVE` 擋下（H=start 給 1.852、H=end 給 0.712，方向相反）。
2. 就算解出來也不夠：**R487 §4 記下的反向因果沒有被 token 匹配關掉。**
   固定 `completion_tokens` 底下 `latency = ms_per_tok × tokens` ⇒ 壽命 ∝ ms/tok
   ⇒ 「本來就慢 ⇒ 活得久 ⇒ 更容易和別人重疊」這條路徑仍在，
   用「整段壽命有沒有重疊」定義的曝光在機制上是**結果的函數**。

本輪處理這兩件，順序是 P-1（解 `ts`）→ P-2（換曝光定義）。

## P-1：`ts` 語意，判準改成比較形式

### 要改什麼、憑什麼改

R487-B 的規則是**絕對邊際** `second - best >= 0.05`。
`ops/gain/r487b_margin_rule_demo.py`（已 commit 於 `4284884`）用**構造上真值就是 TS_IS_START**
的合成母體證明這個形式是錯的：latency 分佈一窄，即使 `inv_plus` 是完美的 `0.00000`，
規則照樣吐 `UNRESOLVED`，4 個裡錯 3 個。

⚠ **改判準的方向對我有利**（讓 `TS_IS_START` 更容易成立）。依既有規則，
**唯一可用的理由是語意或合成復現**——這裡用的是合成復現，且該復現在改判準之前就已 commit。
**不准以「這樣才解得出來」為理由。**

### ⚠ 揭露（後輪有權因此不採信 P-1）

- 舊規則在真實資料上的原始輸出**已知**，且**無條件保留**在 `GAIN_STATE.md` round758
  與 `ops/gain/data/r487b_ts_result.json`：

  ```
  all  (2898 對) ts=0.22291  ts_plus_lat=0.00035  ts_minus_lat=0.22912  -> TS_IS_START
  chat ( 785 對) ts=0.02038  ts_plus_lat=0.00127  ts_minus_lat=0.19236  -> TS_UNRESOLVED_BY_ID
  ```

- 因此我在設計新規則時**已經知道**兩個母體的排名方向都是 `ts_plus_lat` 最小。
  新規則若判 `TS_IS_START`，那**不是**一個獨立的確認。
- R487-B 的舊判準與舊輸出**不得刪除、不得改寫**，後輪要收回仲裁權時以舊輸出為準。

### 新規則（先寫死）

排名不變（三個候選鍵 `ts` / `ts_plus_lat` / `ts_minus_lat`，按 id 升冪的相鄰對逆序比例）。
把「邊際」從**絕對差**換成**配對符號檢定**——證據單位是 discordant pair，與本 repo
既有的配對比較同一套語意：

- 對最佳鍵 B 與次佳鍵 S，逐一相鄰 id 對分類：
  `b` ＝ S 逆序而 B 不逆序的對數；`c` ＝ B 逆序而 S 不逆序的對數。
- 雙尾二項式檢定 `p = binom_test(b, b+c, 0.5)`。
- 判 resolved 的條件（全部要成立）：
  1. `n_pairs >= 100`（不變）
  2. `best_inv <= 0.02`（不變）
  3. `b > c`
  4. `p <= 0.01`
- 任一不成立 ⇒ `TS_UNRESOLVED_BY_ID`。
- 兩個母體（all / chat-only）判決必須一致，否則 `TS_POPULATION_SENSITIVE`（不變）。

### 校準（**雙向**，缺一不可；在真實資料之前跑）

沿用 demo 的母體產生器：

- **正對照**：構造上 `TS_IS_START` 的四個母體（jitter 50/5/1/0.2 秒）。
- **負對照 A**：把 `ts` 改成 end（構造上 `TS_IS_END`）⇒ 新規則必須判 `TS_IS_END`，
  **不准判 START**。方向判錯任一個 ⇒ 判準作廢，本輪 P-1 記 `RULE_BROKEN`。
- **負對照 B**：`ts` 與 id 完全獨立的純噪音母體 ⇒ 必須判 `TS_UNRESOLVED_BY_ID`。
  若它也判得出方向，代表規則「什麼都判得出來」⇒ 判準作廢。

**預先聲明：正對照不要求 4/4 全中。** 新規則在極窄 latency 下樣本量不足時仍會（正確地）
吐 UNRESOLVED。**恢復率多少就照實寫多少**，不准為了衝 4/4 再調門檻。

### P-1 預測

`TS_IS_START`（兩個母體一致）。**這個預測有偏**，見上方揭露節。

## P-2：把曝光改成時點量 + 安慰劑對照

### 定義（先寫死）

母體：snapshot 裡的 chat 請求（`POST` 且 path 含 `/v1/chat/completions`），
且 `status_code==200`、`finish_reason=='stop'`、`completion_tokens>0`。

- 起訖時刻：H=start ⇒ `s=ts, e=ts+lat`；H=end ⇒ `s=ts-lat, e=ts`。
- **時點曝光** `C_i` ＝ **其他** chat 請求 j 滿足 `s_j < s_i < e_j` 的個數。
  只看「請求開始那一瞬間有幾個別人開著」——那一瞬間的並行度**不可能由這筆請求自己的時長造成**。
- 結果量 `ms_per_tok = latency_ms / completion_tokens`。
- 分層：`completion_tokens` 的五分位桶。桶內兩臂（`C==0` 與 `C>=1`）各需 `>=20` 列才計入。
- 彙總：各桶 `log(ratio)` 以調和樣本數加權平均，`ratio = exp(彙總)`。
- CI：對列 bootstrap 2000 次，`seed=4880`，取 2.5/97.5 百分位。

### 安慰劑（本輪的關鍵擋門）

同一個曝光函數，但把取樣時點從 `s_i` 平移到 `s_i + Δ`，`Δ ∈ {-3600, -1800, +1800, +3600}` 秒。
平移後的時點若落在觀測窗 `[min s, max e]` 之外，該列在**該安慰劑**中剔除。

理由：R486 已證 99.9% 的重疊是**客戶端自己放手後仍在跑的請求**造成的。
那些請求會在「慢時段」堆積 ⇒ 時點並行度可能只是「現在是壞時段」的標記。
安慰劑量的是**同一個壞時段**、但與這筆請求無因果關係的時點並行度。

### 判決（先寫死）

- `real_cov`（真實曝光可用列數）與每個安慰劑的覆蓋率都要 `>= 50%` 母體，
  否則該安慰劑記 `UNSCANNED`，且 **UNSCANNED 安慰劑一律視為「沒控制住」** ⇒ `PLACEBO_UNSCANNED`。
- `PERIOD_CONFOUNDED`：任一安慰劑的 `|log ratio| >= |log real ratio|`。
- `CONCURRENCY_TAXES`：真實 CI 不含 1 且 `ratio > 1` 且非 `PERIOD_CONFOUNDED`。
- `NO_TAX`：真實 CI 完整落在 `[0.90, 1.15]`（等效區間，與 R487 同）。
  ⚠ 引用時只准寫「效應小於實用邊際」，**不准寫「沒有效應」**（R487 已記過這條）。
- 其餘 ⇒ `UNRESOLVED`。

### 守門（intent=guard，不當佐證）

- G1 `EXPOSURE_DEGENERATE`：兩臂各需 `>=50` 列，否則 `UNSCANNED`。
- G2 `TS_SENSITIVE`：兩個 `ts` 假設底下都算。**P-1 若解出 `ts`，主判用解出的那一支、
  另一支列為敏感度**；P-1 若未解出，兩支判決不同即 `TS_SENSITIVE`、不採用。
- G3 覆蓋率如上。

### P-2 預測

**`PERIOD_CONFOUNDED`。** 理由（判斷，不是量測）：並行度主要由自己放手後的殘留請求構成，
那些殘留是「上一段慢」的結果，而慢時段有自相關 ⇒ 安慰劑應該也看得到關聯。

## 可證偽性自查（收官前逐條回答，不准跳過）

1. P-1 的三條門檻，有沒有哪一條在任何合成母體上都不可能為假？
2. P-2 的 `PERIOD_CONFOUNDED` 有沒有可能是**強制成立**的
   （例如安慰劑與真實用同一批列、恆等式導致 ratio 相同）？
3. `PLACEBO_UNSCANNED` 有沒有可能結構上永遠不觸發？
4. 有沒有兩條預測其實在數同一個事件？
5. **鏡像問**：就算訊號完美，判準有沒有可能仍吐不出判決（強制 UNRESOLVED）？

## 推翻條件

- P-1：負對照任一方向判錯 ⇒ `RULE_BROKEN`，P-1 本輪無結論，舊判準仍為仲裁者。
- P-2：安慰劑與真實用的列集合若不同，`|log ratio|` 比較就不是同一個母體 ⇒
  必須改成在**共同列集合**上再算一次；兩個數字都要報。
- 本輪任何結論若與主 run `g_r461_lcb3_three_arm` 的收官衝突，以主 run 為準（它是實驗，這是 infra 診斷）。

## 中止準則

`ops/gain/data/r486_gateway_snapshot_v2.json` 的 sha256 必須仍為
`060efe0ce91975269b73de61de65c4e3c7fb447bb83b3273d96a73af950ce59c`。不同 ⇒ 停，本輪不出數字。

## 不做什麼

不起／不殺任何 run；不 `git add` 主 run 目錄；不改 `gain_run.py`；不打 8766（用已落盤快照）；
不改 `max_tokens` 或 `--request-timeout-s`；不碰 `world/`／`design/`／`vacant_hm`；
不刪 R487-B 的任何判準或輸出。
