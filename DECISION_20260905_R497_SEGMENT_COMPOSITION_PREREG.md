# R497 判準：閘道快照的「前段 vs 後段」差在哪——組成軸的篩除普查

**寫在量測之前，單獨 commit。round768（2026-09-05 UTC 07:5x）。**
目標 run 目錄：無（本尺零 API、只讀落盤快照 `ops/gain/data/r486_gateway_snapshot_v2.json`）。

## 〇 為什麼是這一題

R496（commit `7f60da9`）在**等列數**滑動視窗上測到：R489／R490 的頭條判決
翻的方向對起始位置幾乎單調——**快照前段給 `PLACEBO_LADDER_BROKEN`、後段給
`CONCURRENCY_TAXES`／`PRIMARY_IS_POSITIVE_CONTROL`**，N=1672 與 N=2291 兩層都一樣。
R496 自己寫了「前段／後段為什麼不同，本輪零量測，不准現在寫成解釋」。
GAIN_STATE round767 交棒第 2 項就是這一條。本尺答的是**「哪些組成軸跟著位置動」**，
**不是**「為什麼」。

## 一 母體（不新造視窗）

`import ops.gain.r496_equal_n_windows as R496` 並呼叫 `R496.index_windows(len(rows))`，
rows ＝ 快照裡 `ts` 非 None 的列按 `ts` 排序（與 R495／R496 逐字同一條路徑）。
⇒ **12 個視窗**（N=1672×6、N=2291×6），與 R496 的 `windows` 逐格相同（G-WINDOWS 擋門）。

## 二 待判量：15 條組成統計量，事前分兩類

**分類在量測之前釘死。理由是語意（這個量是不是梯子自己量的那個東西的函數），不是數字。**

`EXOGENOUS`（需求的組成：誰在打、打什麼、打多大；不是伺服器快慢的函數）

| 代號 | 定義 |
|---|---|
| `share_chat` | `path` 含 `/chat/completions` 的列佔比 |
| `share_other_client` | `client_ip` != 全快照眾數 client_ip 的列佔比 |
| `n_distinct_client_ip` | 視窗內相異 `client_ip` 個數 |
| `share_model_gemma` | `model == "gemma-4-12b-it-qat"` 的列佔比 |
| `share_model_null` | `model is None` 的列佔比 |
| `share_machine_1004` | `machine == "1004"` 的列佔比 |
| `events_in_window` | 視窗 ts 跨度內的 load/unload 事件數 |
| `share_error` | `error` 非 None 的列佔比 |
| `share_status_non200` | `status_code != 200` 的列佔比 |
| `mean_prompt_tokens` | 非 null `prompt_tokens` 的平均（輸入大小由呼叫端決定） |
| `share_stream` | `stream == 1` 的列佔比 |

`ENDOGENOUS`（是梯子在量的那組時間量的函數 ⇒ 就算它跟著位置動，也**不能**當解釋，
那接近同義反覆——見 memory「壽命 ∝ ms/tok ⇒ 曝光是結果的函數」）

| 代號 | 定義 |
|---|---|
| `median_latency_ms` | 非 null `latency_ms` 中位數 |
| `mean_completion_tokens` | 非 null `completion_tokens` 平均 |
| `median_ms_per_tok` | `latency_ms / completion_tokens`（兩者皆非 null 且 tok>0）中位數 |

校準（兩向，缺一不可）

| 代號 | 類 | 定義 | 事前期望 |
|---|---|---|---|
| `C_POS` | 校準 | 視窗內 `ts` 平均 | 必須 `POSITION_TRACKING`（構造上單調） |
| `C_NEG` | 校準 | `sha256(str(id))` 首個十六進位字元為偶數的列佔比 | 必須 **不是** `POSITION_TRACKING`（只依賴 id、與 ts 無關） |

## 三 判準：每條統計量的分類（量測之前定義）

對每一層（N=1672、N=2291）各 6 個視窗，把統計量對**視窗起始索引 `lo`** 算 Spearman rho。

1. 若該統計量的來源欄位在**全快照**每一列都是 null／不存在 ⇒ `STAT_UNSCANNED`
   （「安靜量不到」型二：不准安靜記成 0 或 NOT_TRACKING）。
2. 否則若該統計量在 12 個視窗上**變異為 0** ⇒ `STAT_DEGENERATE`
   （沒有變異可供偵測 ≠ 沒有訊號）。
3. 否則若 **兩層都** `|rho| >= 0.9` **且兩層 rho 同號** ⇒ `POSITION_TRACKING`。
4. 否則 ⇒ `NOT_TRACKING`。

**頭條判決**（只數 `EXOGENOUS` 那 11 條）：
- 有 ≥1 條 `POSITION_TRACKING` ⇒ `EXO_AXES_TRACK`（並逐條具名）
- 0 條 ⇒ `NO_EXO_AXIS_TRACKS`

### 三.1 基準率，以及**這把尺的力氣在哪一邊**（必須連寫）

k=6 時 `|rho| >= 0.9` ⇔ Σd² ∈ {0, 2} ⇒ 每層每方向 6/720，
兩層同號 ⇒ 隨機排列虛無下 `2 × (6/720)² ≈ 1.4e-4`。
⛔ **但這不是 p 值，也不准當顯著性用**：12 個視窗高度重疊（R496 已記），
統計量在相鄰視窗間高度自相關 ⇒ 真實的偶然單調機率遠高於 1.4e-4，本尺**沒有**量它。
⇒ **本尺是篩除工具，力氣在否定方向**：判 `NOT_TRACKING` 的軸，
**不可能**解釋一個兩層都近乎單調的翻動 ⇒ 可以被排除。
判 `POSITION_TRACKING` 只代表**進入候選名單**，**不准寫成「找到原因」**——
所有跟時間單調變動的東西彼此混淆，本尺不分辨它們。

## 四 擋門（任一觸發 ⇒ `verdict` 取第一個 blocker，不出頭條）

| 代號 | 內容 | intent |
|---|---|---|
| `G-WINDOWS` | 視窗數 == 12 且逐格 `(N,i,lo,hi)` 與 `R496.index_windows` 相同 | guard |
| `G-REPRO` | 同一輸入連跑兩次，15 條分類逐條相同 | guard |
| `G-EXC` | 例外率 == 0（R494 附錄 L 的第四型：例外被吞會長得像「不可達」） | guard |
| `G-CAL` | `C_POS == POSITION_TRACKING` 且 `C_NEG != POSITION_TRACKING` | evidence |
| `G-LIVE` | `live_reads == 0`（沿用 R495 的 `_guarded_open`） | **guard，設計上強制綠燈 ⇒ 不是證據**；牙齒在 selftest |
| `G-COUNT` | `EXOGENOUS` 恰 11 條、`ENDOGENOUS` 恰 3 條（實作與判準同一張表） | guard |

## 五 承重牆／突變體（發車前必須 4/4 DETECTED，判準寫死「該變的是哪個量」）

| 代號 | 突變 | 必須被看見的量 |
|---|---|---|
| `M1_ONE_WINDOW` | `index_windows` 只取每層 1 個位置 | `G-WINDOWS` ⇒ `BROKEN_WINDOWS` |
| `M2_CNEG_TIME` | 讓 `C_NEG` 改用 `ts` 而非 `id` 雜湊 | `C_NEG` 變 `POSITION_TRACKING` ⇒ `BROKEN_CALIBRATION` |
| `M3_RHO_ONE_TIER` | 只看 N=1672 那層就判 `POSITION_TRACKING`（放掉「兩層同號」） | `exo_tracking` 具名清單**必須改變** |
| `M4_SWALLOW_NULL` | 關掉 `STAT_UNSCANNED`，並注入一條來源欄位全 null 的統計量 | 該條必須從 `STAT_UNSCANNED` 掉成 `NOT_TRACKING` |

⚠ 突變體一律在被測函式**內部**生效（memory：寫在模組層永遠不生效）。
⚠ 判準不是「rc≠0」，是上表右欄那個具體的量。

## 六 事前預測（盲；本尺尚未看過任何組成分佈）

| 代號 | 預測 | 自評 |
|---|---|---|
| `P-1` | 頭條 ＝ `EXO_AXES_TRACK`（≥1 條外生軸跟著位置動） | 中高 |
| `P-2` | `share_other_client`（別人的請求佔比）是 `POSITION_TRACKING` | 中 |
| `P-3` | `events_in_window`（load/unload）**不是** `POSITION_TRACKING`（memory：1004 每小時一次 ⇒ 大致均勻） | 中高 |
| `P-4` | ≥1 條 `ENDOGENOUS` 是 `POSITION_TRACKING`（梯子量的就是這些） | 高 |
| `P-5` | `C_POS` TRACKING 且 `C_NEG` 不 TRACKING | guard／校準，**不是證據** |
| `P-6` | 15 條裡 `STAT_UNSCANNED` ＋ `STAT_DEGENERATE` 合計 ≤ 2 | 中 |
| `P-7` | 被判 `NOT_TRACKING` 的外生軸 ≥ 4 條（否定方向真的篩掉東西） | 中 |

🔴 **我自標最可能錯的一條：`P-2`。** 理由：我沒看過 client_ip 的分佈，
也不知道非本 run 的流量是不是集中在某幾個小時；「別人的請求」很可能是零星突發而非單調趨勢。

## 七 事前寫死的推翻條件與誠實邊界

- 若頭條 ＝ `NO_EXO_AXIS_TRACKS`：**不准**寫成「所以是內生的／所以梯子是對的」。
  正確的寫法是「本尺列的 11 條外生軸都不能解釋這個翻動，候選要往別處找」。
- 若冒出判準沒有的第六種格（例如某條同時 `STAT_DEGENERATE` 又被要求分類）：
  **照實記、人眼確認、不算進計數、不當場補判準**。
- **本尺不建立因果**，第三.1 節那段限制要原樣抄進結果與 GAIN_STATE。
- 判準與結果分開 commit；結果不得回頭改本檔。

## 八 不做什麼

- 不動主 run `g_r461_lcb3_three_arm`（活著，PID 2895311；不 `git add` 它的目錄）。
- 不修那條梯子（round762 裁決，R495／R496 已重申）。
- 不新增可調參數：門檻只有 `|rho| >= 0.9`，它是由「k=6 時 Σd²∈{0,2}」導出的，
  不是掃出來的（三.1 已寫導出過程）。
