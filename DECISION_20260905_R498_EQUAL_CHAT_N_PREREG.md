# R498 判準：等 **chat 列數** 滑動視窗——把「視窗位置」與「被分析樣本數」拆開

**寫在量測之前，單獨 commit。round768（2026-09-05 UTC 08:0x）。**
零 API，只讀落盤快照 `ops/gain/data/r486_gateway_snapshot_v2.json`。

## 〇 為什麼是這一題（動機是 R497 §三，本檔已知那個發現）

R496 造的是**等閘道總列數**視窗，並據此判「翻動不是樣本量造成的」。
R497 §三 量出：`r489_permutation_placebo.analyse` 只吃 `is_chat(r)` 再取 `is_analysable(r)`，
而在 R496 那批總列數固定的視窗裡，**被分析的 chat 列數仍隨起始位置單調下降**
（N=1672 層 491→364、N=2291 層 636→555，兩層 rho ＝ **−1.0**）。
⇒ R496 等錯了單位；「位置」與「被分析 n」在那批視窗上**完全共線**，分不開。

本尺把固定的單位換成**被分析的 chat 列數**，讓總列數與時間跨度浮動。
⚠ **本檔的動機不是盲的**（我已看過 R497 §三）；盲的是 §六 那些預測的**答案**——
等 chat 列數之後判決還翻不翻，我事前不知道。

## 一 母體（導出，不是挑的）

1. rows ＝ 快照裡 `ts` 非 None 的列按 `ts` 排序（與 R495／R496／R497 逐字同一條路徑）。
2. `sub` ＝ `[r for r in rows if R489.is_chat(r) and R489.is_analysable(r)]`（沿用被測檔自己的過濾器）。
3. 兩層的 chat 列數 **由 R496 的視窗導出**，與 R496 從 R495 導出 N 的做法逐字平行：
   `M_SMALL` ＝ R496 N=1672 那六個視窗裡 `len(sub∩window)` 的**最小值**；
   `M_LARGE` ＝ R496 N=2291 那六個視窗裡的最小值。
   ⇒ 實作必須**現算**這兩個數（不得寫死），並與 R497 記下的 `364` / `555` 逐字比對（G-DERIVED）。
4. 每層 6 個左緣，在 **`sub` 的索引上**等距；視窗 ＝ `rows` 中落在
   `[sub[lo].ts, sub[lo+M-1].ts]` 的全部列（傳給 probe 的是完整列，probe 自己再過濾）。
   ⇒ **12 個視窗**，每個視窗的 `len(sub∩window)` 必須恰為 M（G-EQCHAT）。

## 二 待判量

對 `probe_r489`／`probe_r490`（**直接 import R495 那兩支，不重寫**）各跑 12 個視窗，
用 **`R496.classify` 原封不動**分格（NEITHER／POSITION_MATTERS／N_MATTERS／BOTH／
NEW_CELL_UNIFORM_SHIFT／UNSCANNED_EQN）——不新增語意、不新增可調參數。

另外**逐視窗記錄並報出**（觀測量，不是判準）：
`n_rows_total`、`n_chat`、`n_sub`、`span_s`、`events_in_window`。

## 三 判準（量測之前定義）

**頭條**（對 `r489` 與 `r490` 各判一次，兩個都要報）：

- `POSITION_SURVIVES` ＝ 該工具的格 ∈ {`POSITION_MATTERS`, `BOTH`}
  ⇒ **在被分析樣本數固定之後，判決仍隨視窗位置翻動** ⇒ 樣本數解釋不掉它。
- `POSITION_GONE` ＝ 該工具的格 ∈ {`NEITHER`, `NEW_CELL_UNIFORM_SHIFT`}
  ⇒ 固定 n 之後翻動消失 ⇒ **與「翻動是被分析樣本數造成的」相容**（相容 ≠ 證實，見 §七）。
- `N_ONLY` ＝ 格 ＝ `N_MATTERS`（層內恆定、層間不同）。
- `UNSCANNED` ＝ 格 ＝ `UNSCANNED_EQN`。

**跨度擋門不是頭條、但必須先報**：若任一層的 `span_s` 極差 / 該層中位數 > 0.25
⇒ 頭條旁邊必須併記 `SPAN_UNCONTROLLED`（R496 那次是 ±5%／±2%，本尺不保證）。
⛔ `SPAN_UNCONTROLLED` **不會**讓判決作廢，但**不准**在沒併記它的情況下引用頭條。

## 四 擋門（任一觸發 ⇒ verdict 取第一個 blocker）

| 代號 | 內容 | intent |
|---|---|---|
| `G-DERIVED` | 現算的 `(M_SMALL, M_LARGE)` == `(364, 555)`（R497 §三 記錄值） | guard |
| `G-EQCHAT` | 12 個視窗每個的 `n_sub` 恰等於該層的 M | guard |
| `G-WINDOWS` | 視窗數 == 12、每層 6 個、左緣嚴格遞增 | guard |
| `G-REPRO` | 連跑兩次，兩工具的格與 12 個 verdict 逐字相同 | guard |
| `G-EXC` | 例外率 == 0（R494 附錄 L 第四型） | guard |
| `G-CAL` | `C_POS`（恆回同一判決）必須落 `NEITHER`；`C_NEG`（回層別字母）必須落 `N_MATTERS` | evidence |
| `G-LIVE` | `live_reads == 0`（沿用 R495 `_guarded_open`） | **guard，設計上強制綠燈 ⇒ 不是證據**；牙齒在 selftest |

## 五 承重牆／突變體（發車前跑，判準寫死「該變的是哪個量」；不是 rc≠0）

| 代號 | 突變（在被測函式**內部**生效） | 必須被看見的量 |
|---|---|---|
| `M1_ONE_POSITION` | 每層只取 1 個左緣 | `G-WINDOWS` ⇒ `BROKEN_WINDOWS` |
| `M2_TOTAL_ROWS` | 改回用**總列數**切視窗（即退化成 R496 的單位） | `G-EQCHAT` ⇒ `BROKEN_EQCHAT` |
| `M3_FORCE_SAME` | 每個視窗的 verdict 強制等於全視窗 verdict | 兩工具的格必須變成 `NEITHER` |
| `M4_PIN_M` | 把 M 寫死成 R496 的 N（1672/2291） | `G-DERIVED` ⇒ `BROKEN_DERIVED` |

⚠ `M3` 的判準寫「格變成 `NEITHER`」而不是「verdict 改判」——
memory：突變後外層字串不變的假測試要挑「那個會變的量」。

## 六 事前預測（答案是盲的）

| 代號 | 預測 | 自評 |
|---|---|---|
| `Q-1` | `r489` 判 `POSITION_SURVIVES` | 低信心，**這就是本輪的賭注** |
| `Q-2` | `r489` 與 `r490` 的頭條**相同**（兩支同進退） | 中 |
| `Q-3` | 至少一層觸發 `SPAN_UNCONTROLLED`（跨度極差 > 25%） | 中高 |
| `Q-4` | 12 個視窗的 `n_rows_total` 極差 > 10%（總列數真的浮動了） | 高 |
| `Q-5` | `G-CAL` 兩向如期（`C_POS`=NEITHER、`C_NEG`=N_MATTERS） | guard／校準，**不是證據** |
| `Q-6` | 不出現 `UNSCANNED`（M=364 遠大於 `2*MIN_PER_ARM`） | 中高 |

🔴 **自標最可能錯的一條：`Q-2`。** 理由：R495／R496 兩輪裡 r489 與 r490 的格已經
不只一次不一致（R495：r489 MOVABLE 4 次、r490 只 2 次且走到不同判決）。

## 七 事前寫死的推翻條件與誠實邊界

1. ⛔ **`POSITION_GONE` 不等於「翻動是樣本數造成的」。** 固定 n 同時也改變了視窗的
   時間跨度與總列數 ⇒ 只是**相容**。要寫成因果需要本尺沒有的設計。
2. ⛔ **`POSITION_SURVIVES` 不等於「R496 是對的」。** R496 的錯在**單位**，
   本尺就算救回同方向的結論，R497 §三 那句「R496 等錯單位」**原樣保留**。
3. 12 個視窗高度重疊 ⇒ **可用的是方向，不是次數**（R496 已記，原樣沿用）。
4. 冒出判準沒有的格 ⇒ 照實記、人眼確認、不算進計數、**不當場補判準**。
5. 判準與結果分開 commit；結果不得回頭改本檔。

## 八 不做什麼

- 不動主 run `g_r461_lcb3_three_arm`（活著；不 `git add` 它的目錄）。
- 不修那條梯子（round762 裁決）。本尺只描述它的敏感度。
- 不新增可調參數：M 由 §一.3 導出、分格用 R496 原函式、跨度門檻 0.25 是
  **報告用的併記門檻**不是判決門檻（§三 已寫明它不讓判決作廢）。
