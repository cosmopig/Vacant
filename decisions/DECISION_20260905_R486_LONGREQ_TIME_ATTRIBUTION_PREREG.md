# R486 預註冊：長請求的伺服器端時間去了哪裡——生成、排隊、還是模型重載

**日期**：2026-09-05 UTC（round757）　**模型**：Opus 5
**狀態**：判準，寫在任何量測之前。本檔 commit 之後才准跑量具。

## 這是在答誰的問題

R485（round756）§3 證明了：客戶端在 `--request-timeout-s 600` 放手之後，
**伺服器端仍記到 5618s / 6014s 的壽命**，客戶端看不見的伺服器時間合計 238.4 分鐘。
R485 自己寫了誠實邊界：

> 強度要說準：證明的是「閘道上的壽命遠超過放手時刻」，**沒有**證明「斷線後仍在生成」——
> 仍成立的替代解釋是**一直排在佇列裡**。分辨要查佇列資訊，本輪沒查。

**本輪就是去分辨。** 這件事決定 `--request-timeout-s` 該調大、調小、還是不該碰，
也決定 R485 提的「改 `max_tokens`」是不是對的候選。

## 不動的東西

- 不起任何 gain_run；不殺、不碰在跑的 `runs/g_r461_lcb3_three_arm`（PID 2895311）。
- 8766 **只讀**（`GET /api/requests`、`/api/events`、`/api/status`）。不關、不卸載、不改設定。
- 不改 `gain_run.py`、不改任何門檻檔、不 `git add` 主 run 目錄。

## 資料來源與快照

- `GET /api/requests`（`machine`／`since`／`until`／`after_id`／`limit` 分頁）→ 落盤成快照 JSON。
- `GET /api/events?limit=...` → 模型 loaded／unloaded 事件，落盤成快照 JSON。
- 兩份快照都記 sha256；量具**只讀快照檔**，不在判決路徑上打網路（可重放）。

## 已知的結構事實（判準寫作當下已確認，非本輪量測結果）

- `gain_run.py` **依序送出、不併發**（`grep ThreadPoolExecutor` → 三處註解明寫「依序送出」）
  ⇒ 主 run 自己的請求**在結構上不可能互相重疊**。
  ⇒ 任何重疊只可能來自**別的客戶端**。這一點直接製造了下面 P-1b 的空綠燈風險。
- `/api/requests` 欄位：`ts, latency_ms, prompt_tokens, completion_tokens, finish_reason,`
  `status_code, error, model, machine, client_ip, path, stream, id`。
- 1004 上目前只有 `gemma-4-12b-it-qat` 是 loaded（`/api/status`，唯讀）。

## 步驟 0：`ts` 語意必須由資料決定，不准沿用記憶

記憶寫「8766 的 `ts` 是起始時刻」。本輪**不引用**，重新解一次：

- H_start：區間 `[ts, ts + latency_ms/1000)`
- H_end　：區間 `[ts - latency_ms/1000, ts)`

判別量：`id` 是落盤時序號 ⇒ **結束時刻**應對 `id` 單調不減。
兩個假設各算一次「結束時刻對 id 的反序對數」`inversions`。

- 只有一個假設 `inversions == 0` ⇒ 採用它，記 `TS_RESOLVED_{START,END}`。
- 兩個都 0，或兩個都 >0 ⇒ `TS_AMBIGUOUS` ⇒ **P-1／P-2／P-3／P-4 一律 UNRESOLVED**，
  照實寫「本輪分辨不出來」。

## 目標母體

`TARGETS` ＝ 快照中滿足全部條件的列：`machine=="1004"`、`path` 含 `chat/completions`、
`model` 含 `gemma`、`latency_ms >= 600000`（＝客戶端放手點）。

**型三「安靜量不到」擋門（P-0）**：量具必須輸出 `rows_scanned`、`chat_rows`、
`events_scanned`、`n_targets`。
- 任一為 0 ⇒ `BROKEN`（不是「沒有問題」）。
- `n_targets < 5` ⇒ 全部下游判 **`UNSCANNED`**，**不准**寫成「排隊被排除」。
（intent: guard）

## 預測與判準

### P-1 排隊（intent: evidence）

對每個目標請求，算 `overlap_frac` ＝ 它的區間內、**至少有一個別的** chat/completions
請求（任何模型、任何客戶端、同一台 1004）同時開著的時間佔比。
`queue_share` ＝ `overlap_frac >= 0.50` 的目標請求佔比。

- `queue_share >= 0.50` ⇒ **`QUEUE_LIVE`**（排隊是真的候選）
- `queue_share <= 0.10` ⇒ **`QUEUE_RULED_OUT`**
- 其他 ⇒ `UNRESOLVED`

### P-1b 基準率擋門：`QUEUE_RULED_OUT` 有沒有可能是空綠燈（intent: guard）

因為主 run 結構上不自我重疊，若快照窗口內**根本沒有別的客戶端的 chat 請求**，
那 P-1 的 `QUEUE_RULED_OUT` 就是**結構強制綠燈**，不是證據。

量 `n_foreign_chat` ＝ 窗口內 `client_ip` 不等於主 run 客戶端 IP、或 `model` 不是 gemma
的 chat/completions 請求數（兩種算法都輸出：`n_foreign_by_ip`、`n_foreign_by_model`）。

- `n_foreign_chat == 0` ⇒ P-1 一律改記 **`FORCED_GREEN`**，收官不得引用為證據。
- `n_foreign_chat > 0` ⇒ P-1 的判決可以引用，並在報告寫出這個基準率數字。

### P-2 模型重載（intent: evidence）

`reload_share` ＝ 區間內含有 1004 上任何模型 `loaded` 或 `unloaded` 事件的目標請求佔比。

- `>= 0.30` ⇒ **`RELOAD_CONTRIBUTES`**
- `== 0.0` ⇒ **`RELOAD_RULED_OUT`**
- 其他 ⇒ `UNRESOLVED`

**基準率擋門**：若 `events_scanned` 涵蓋的時間範圍沒有蓋住目標請求的時間範圍
（`events_min_ts > targets_min_start`），`RELOAD_RULED_OUT` 改記 `UNSCANNED_EVENT_WINDOW`。

### P-3 是不是在生成（intent: evidence）

參考帶：**短的成功** gemma chat 請求（`latency_ms < 600000`、`completion_tokens >= 200`、
`status_code == 200`）的 `ms_per_tok` 的中位數與 p90。

目標請求中 `completion_tokens` 有值且 `> 0` 的子群：
`generating_consistent` ＝ `ms_per_tok <= ref_p90 * 1.5`。

- 子群 `< 3` 筆 ⇒ **`UNSCANNED`**（**事前預期這很可能發生**：400 context-exceeded
  很可能沒有 token 記錄）
- 子群 ≥3 且 `share >= 0.70` ⇒ **`GENERATING`**
- 子群 ≥3 且 `share <= 0.30` ⇒ **`NOT_GENERATING`**
- 其他 ⇒ `UNRESOLVED`

### P-4 並行度天花板（intent: evidence；**與 P-1 不獨立，收官要寫明**）

`max_concurrency` ＝ 整個快照窗口內 1004 上同時開著的 chat/completions 請求數的最大值。

- `== 1` ⇒ **`SERIAL_NO_QUEUE`**（端點在這段時間裡從來沒有兩個請求同時在飛）
- `>= 2` ⇒ **`CONCURRENT_OBSERVED`**，附上並行度分佈

⚠ P-4 與 P-1 在數同一件事的兩面（都出自同一組區間）。**兩個都記、不合併**，
但收官只准把它們算成**一項**證據。

## 推翻條件（事前寫死；觸發就照實寫，不准當場補判準去修）

1. **T-1**：`TS_AMBIGUOUS` ⇒ 本輪什麼都答不了，照實寫，下輪改用別的判別量。
2. **T-2**：`n_targets < 5` ⇒ `UNSCANNED`。**不准**因此宣稱「沒有長請求問題」。
3. **T-3**：若 P-1 判 `QUEUE_RULED_OUT` 而 P-1b 判 `FORCED_GREEN`
   ⇒ R485 §3 的替代解釋**仍未被排除**，收官要寫「本輪沒能分辨」。
4. **T-4**：若 P-3 `UNSCANNED` 且 P-1 `QUEUE_RULED_OUT` 且 P-2 `RELOAD_RULED_OUT`
   ⇒ 三個排除加起來**不等於**「在生成」（那是消去法，不是正面證據）。
   收官只准寫「排隊與重載都沒看到；在不在生成本輪沒有正面證據」。
5. **T-5**：量具的 selftest 或任一突變體 crash 收場（而非吐出具名判決）⇒ 該次不算偵測到。

## 量具與自檢要求（照 r706／r695／r699 的規則）

- 量具 `ops/gain/r486_longreq_attrib.py`，`--selftest` 用合成夾具。
- 夾具**不得**由被測模組自己的 helper 導出（r699）；區間與事件分開手寫。
- 一致性擋門的兩個量不得同源（r695）；夾具要能**只翻其中一個**。
- 突變體一律在**被測函式內部**生效（r700），不准寫在模組層。
- 每個突變體都要有看得見它的夾具；**單調性方向要先算**（r756 M7 的教訓：
  `overlap_frac` 門檻改小只會讓 QUEUE 更容易成立 ⇒ 能看見它的方向是 `QUEUE_RULED_OUT` 那邊）。
- 突變體的判準要寫**該變的那個量**，不准只寫 `rc != 0`。

## 這一輪不做什麼

- 不改 `--request-timeout-s`、不改 `max_tokens`、不改任何 run 設定。
  本輪只產出「時間去了哪裡」的答案；要不要動參數是**下一輪**、要另開 DECISION。
- 不對「別人的 qwen 請求」下結論（只看得到它出現在同一台機器上）。

---

## 修訂 A（2026-09-05 UTC，**仍在任何量測之前**；理由是合成復現，不是結果數字）

寫夾具的時候發現步驟 0 的判別量**結構上沒有解析度**：

`gain_run.py` 依序送出 ⇒ 單一客戶端的請求**開始時刻與結束時刻同時單調遞增**
⇒ H_start 與 H_end 的「反序對數」**兩個都是 0** ⇒ 必然 `TS_AMBIGUOUS`。
合成夾具（六筆首尾相接的長請求）逐字復現了這件事。

⚠ **舊判別量無條件保留**（`ts_inversions` 照樣輸出、照樣報），後輪要收回仲裁權隨時可以。
本修訂**不放寬**任何門檻，方向是**對自己更嚴**：

**修訂內容：不再依賴解出 `ts` 語意。P-1／P-2／P-3／P-4 一律在 H_start 與 H_end
兩個假設底下各算一次，只有兩邊**判決相同**時才採用該判決；不同就記
`TS_SENSITIVE` ＝ `UNRESOLVED`。**

- 這比原判準嚴格：原本解出一個語意就下判決，現在要兩個語意都給同一個答案。
- `ts_verdict`（原 D0a）降級為**附註**，仍輸出，但不再是下游的閘門。
- 新增輸出 `by_hypo`：每個假設底下的完整數字，兩邊都要在報告裡列出。
- 推翻條件 **T-1 改寫**：`TS_AMBIGUOUS` 本身不再讓全部下游 UNRESOLVED；
  真正讓下游 UNRESOLVED 的是**兩個假設判決不一致**（記 `TS_SENSITIVE`）。
