# R487 預註冊：自家造成的並行，到底有沒有向「正常請求」收稅？

**寫於 2026-09-05 04:4x UTC，量測之前。** 本檔內容在跑任何 R487 量具之前 commit。
所有門檻、判別量、推翻條件都在下面寫死；量完不准回改本檔（要改另開修訂節並說明理由，
且理由只准是語意或合成復現，不准是結果數字）。

## 為什麼是這個問題

R486（round757）證明了長請求的排隊是**自家造成的**：客戶端在 600s 放手 → 去送下一題 →
伺服器沒放掉舊的那筆 → 兩筆搶同一張卡。`own_client 0.774–1.000、foreign ≤0.004`，
54.2% 的牆鐘時間有 ≥2 個 chat 請求同時開著。

**但「有並行」不等於「並行有代價」。** 這是兩件事：

- 若並行**有稅**：那 6 筆失控請求除了自己吃掉 45.3% 的伺服器時間，還在拖慢其他 780 筆。
  ⇒ 動 `max_tokens`（讓請求根本長不到那麼長）買到的是**全域**吞吐。
- 若並行**沒稅**（伺服器把它排在佇列裡不佔算力、或時間片切得夠好）：那失控請求只花掉
  自己的時間，別人不受影響。⇒ 動 `max_tokens` 只買回它自己那 45.3%，**「失控請求霸佔顯卡」
  這個故事是錯的**，交棒不准再那樣寫。

⚠ 本檔**不是**改 `max_tokens` 的授權，也不准套用到在跑的 run（`g_r461_lcb3_three_arm`）。
本輪零模型呼叫、不起不殺任何 run。

## 資料來源（唯讀、已落盤，本輪不再抓）

`ops/gain/data/r486_gateway_snapshot_v2.json`（round757 逐 id 補抓版；v1 有 690 個 id 缺口，
**不准引用 v1**）。rows 2899、events 500、窗口 9.055 小時。

## 事前查過的規模事實（不是結果，是樣本數）

- chat 列（`method=POST` 且 `path` 含 `/v1/chat/completions`）：**786**
- REF（見下定義）：**728**，`model` 只有 `gemma-4-12b-it-qat` 一種、`client_ip` 只有一個
  ⇒ **模型分層在本資料上退化成單格**，判準照樣寫成「(model × token 分位)」但實際只有 token 維度。
- 窗口內 load/unload 事件：**16**（8 loaded ／ 8 unloaded，全是 gemma）。

以上四個數字是在寫本檔之前查的，屬於樣本規模；**曝光率、ms/tok、任何組間比較都還沒算過。**

## 定義（寫死）

- **chat 列**：`method=='POST'` 且 `'/v1/chat/completions' in path`。
- **壽命區間**：`ts` 的語意（起始／結束）在 R486 未解出 ⇒ 沿用 R486 修訂 A，**兩個假設各算一次**：
  - H=start：`[ts, ts + latency_ms/1000]`
  - H=end：`[ts - latency_ms/1000, ts]`
- **REF**：chat 列且 `completion_tokens >= 1` 且 `latency_ms > 0` 且 `error is None` 且 `status_code == 200`。
- **ms/tok** ＝ `latency_ms / completion_tokens`。
- **曝光 E1（頭條）**：存在另一筆 chat 列 j≠i，其區間與 i 的區間**重疊長度 > 0 秒** ⇒ `EXPOSED`，否則 `UNEXPOSED`。
- **曝光 E2（次要，一併輸出）**：`overlap_frac_i` ＝ i 的壽命中「至少一筆別的 chat 開著」的時間佔比；
  `>= 0.5` ⇒ EXPOSED2、`< 0.05` ⇒ UNEXPOSED2、中間**丟棄**。
- **分層（頭條）**：`completion_tokens` 的五分位，切點由**整個 REF** 算出（兩組共用同一組切點）。
- **分層（預註冊敏感度）**：在每個 token 五分位內再依 `prompt_tokens` 中位數二分 ⇒ 10 格。

### 為什麼要分層（這一條是本輪最重要的方法論）

round757 的教訓 #4：**「佔比 ≥ 固定門檻」型的判準，遇到「長度不同的區間包不包含某事件」
這種問題，幾乎一定是強制綠燈——事前要先算虛無期望再訂門檻。** 同一個病在這裡換一件衣服：
**活得久的請求本來就更容易碰到別人**，所以「曝光組比較慢」可能純粹是「曝光組本來就比較長」。
⇒ 不做時長匹配的組間比較在這裡**沒有意義**。

匹配變數選 `completion_tokens` 而不是 `latency_ms`：latency 是**結果本身**，拿結果做匹配等於
把要測的效應匹配掉。`completion_tokens` 是「模型決定吐幾個字」，**假設**它不受爭用影響。
⚠ 這個假設的失效模式要寫進誠實邊界：若爭用會讓請求被截斷（`finish_reason=='length'`）
或提早停，token 數就變成部分後處理量。輸出要一併報 `finish_reason` 分佈供後輪檢查。

## 估計量

每格 c：`L_c = ln(median(ms/tok | EXPOSED, c)) - ln(median(ms/tok | UNEXPOSED, c))`
權重 `w_c = n_exp,c * n_unexp,c / (n_exp,c + n_unexp,c)`
彙總 `L = Σ w_c L_c / Σ w_c`，**ratio = exp(L)**。
CI：格內對兩組**各自**重抽（有放回）2000 次、seed 固定 `487`、百分位 95% CI。
可用格 = 兩組各 `>= 10` 筆的格。

## 預測（每條都標 intent，並寫出「什麼情況它會是假的」）

### P-1 頭條（intent=evidence）：並行有沒有向正常請求收稅

- `CONCURRENCY_TAXES`：`ratio >= 1.20` **且** CI 下界 `> 1.00`
- `NO_TAX`：CI 完全落在 `[0.90, 1.15]` 內
- `UNRESOLVED`：以上皆非
- `UNSCANNED`（**不是** UNRESOLVED）：可用格 `< 3`，或 `n_exposed_total < 30`，或 `n_unexposed_total < 30`

**我事前的預測：`CONCURRENCY_TAXES`。** 理由：一張卡上兩筆生成必然互搶。
**會是假的情況**：ratio 落在 1.0 附近（伺服器把第二筆排進佇列、不切時間片 ⇒ 排隊的那筆全部
成本記在自己頭上，鄰居不受影響）。這是完全可能的實情，也正是本輪要分辨的。
**天花板風險（事前寫下）**：若並行度太高導致 `UNEXPOSED` 幾乎不存在 ⇒ 判 `UNSCANNED`，
照實寫「這份資料答不了」，**不准事後換定義去湊出一個判決**。E2 是**事前**就宣告要一併輸出的
第二種曝光定義，不是事後備案；頭條永遠是 E1。

### P-2 守門（intent=guard）：時長偏誤是真的存在（＝分層有必要）

`exposure_rate(最高 token 五分位) - exposure_rate(最低 token 五分位) >= 0.10` ⇒ `DURATION_BIAS_PRESENT`
否則 `DURATION_BIAS_ABSENT`。
**它不是強制綠燈**：若曝光率整體貼近 1.0（天花板）或貼近 0，差值會 ≈0 ⇒ 可以為假。
intent=guard ⇒ 即使為真也**不當作 P-1 的佐證**，只用來說明分層是否必要。

### P-3（intent=evidence）：修好 R486 P-2 —— 模型重載到底有沒有超出隨機

**R486 的 P-2（`RELOAD_CONTRIBUTES`）本輪正式撤回為證據**：round757 已自證它是強制綠燈
（6 個目標區間、時長匹配 Poisson 期望 0.761、門檻卻寫 0.30 ⇒ 結構上不可能有反例）。
這裡改成**跟時長匹配的虛無比**，並且把母體從 6 筆換成**全部 chat 列**（有檢定力）：

- `λ` ＝ 窗口內事件數 / 窗口秒數（窗口＝ rows 的 `[min ts, max ts]`，事件只取落在窗口內的）
- 每列虛無命中機率 `p_i = 1 - exp(-λ * d_i)`，`d_i` ＝該列壽命秒數
- `E = Σ p_i`，`O` ＝ 區間內至少含一個事件的列數，`z = (O - E)/sqrt(Σ p_i(1-p_i))`，雙尾常態 p
- `RELOAD_EXCESS`：`O/E >= 1.5` 且 `p < 0.05`
- `RELOAD_AS_CHANCE`：`0.67 <= O/E <= 1.5`
- `RELOAD_DEFICIT`：`O/E < 0.67` 且 `p < 0.05`
- `UNRESOLVED`：以上皆非
- `UNSCANNED`：窗口內事件 `< 5`（已知＝16，仍保留擋門）

**我事前的預測：`RELOAD_AS_CHANCE`**（round757 的短請求命中率 2.05% 已經完全被時長解釋）。

### 全域擋門：兩個 `ts` 假設要一致

P-1／P-2／P-3 的判決在 H=start 與 H=end 底下**必須相同**，否則該條記 `TS_SENSITIVE` 且**不採用**。
（沿用 R486 修訂 A。）

### 全域擋門：分層敏感度

P-1 在「token 五分位」與「token 五分位 × prompt 中位二分」兩種分層下判決必須相同，
否則 P-1 降級為 `UNRESOLVED` 並記 `STRAT_SENSITIVE`。

## 中止準則

- 資料檔 sha256 與 round757 記錄不符 ⇒ 停，寫進 STATE，不出判決。
- 量具 selftest 未全過、或任一突變體行為與預註冊不符 ⇒ 停，不跑真資料。

## 這一輪不會做的事

- 不改 `gain_run.py`、不改任何門檻檔、不動 `world/`／`design/`／`vacant_hm`。
- 不 `git add` 主 run 目錄（run 活著 ⇒ 未追蹤＝對 stash/checkout/reset 免疫）。
- 不改 `max_tokens`、不改 `--request-timeout-s`。**本檔只產生知識，不產生設定變更。**
