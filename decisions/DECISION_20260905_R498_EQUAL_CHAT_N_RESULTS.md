# R498 結果：把被分析的樣本數釘死之後，判決仍隨視窗位置翻動

判準：`DECISION_20260905_R498_EQUAL_CHAT_N_PREREG.md`（commit `8b2db52`，量測之前單獨 commit）。
量具：`ops/gain/r498_equal_chat_n.py`（selftest 13/13）、`ops/gain/r498_mutation_check.py`。
資料：`ops/gain/data/r498_equal_chat_n.json`。零 API、只讀落盤快照。

## 一 頭條

```
verdict=EQCHAT_OK  M=[364, 555]  n_windows=12  exc=0  live_reads=0  elapsed_s=68.9
calibration: {'C_POS': 'NEITHER', 'C_NEG': 'N_MATTERS'}
span_spread={'364': 0.5591, '555': 0.2297}  SPAN_UNCONTROLLED=True  n_rows_total_spread=0.6277

r489_permutation_placebo  cell=BOTH  headline=POSITION_SURVIVES  full=PLACEBO_LADDER_BROKEN
r490_leveled_placebo      cell=BOTH  headline=POSITION_SURVIVES  full=PLACEBO_LADDER_BROKEN
```

**`M` 由 R496 的視窗現算導出（G-DERIVED 對上 R497 §三 記的 364／555），
每個視窗的被分析列數 `n_sub` 恰等於該層的 M（G-EQCHAT 全數通過）。**

| M | i | lo_sub | n_rows_total | n_chat | n_sub | span_s | events | r489 | r490 |
|---|---|---|---|---|---|---|---|---|---|
| 364 | 0 | 0 | 1225 | 382 | 364 | 13015 | 10 | PLACEBO_LADDER_BROKEN | PLACEBO_LADDER_BROKEN |
| 364 | 1 | 72 | 1184 | 388 | 364 | 12259 | 10 | `EXPOSURE_DEGENERATE` | `EXPOSURE_DEGENERATE` |
| 364 | 2 | 145 | 1289 | 389 | 364 | 13880 | 6 | `UNRESOLVED` | `UNRESOLVED` |
| 364 | 3 | 218 | 1148 | 388 | 364 | 11726 | 4 | CONCURRENCY_TAXES | PRIMARY_IS_POSITIVE_CONTROL |
| 364 | 4 | 291 | 1324 | 389 | 364 | 14420 | 4 | CONCURRENCY_TAXES | PRIMARY_IS_POSITIVE_CONTROL |
| 364 | 5 | 364 | 1652 | 404 | 364 | 19245 | 6 | CONCURRENCY_TAXES | PRIMARY_IS_POSITIVE_CONTROL |
| 555 | 0 | 0 | 1923 | 586 | 555 | 20649 | 10 | PLACEBO_LADDER_BROKEN | PLACEBO_LADDER_BROKEN |
| 555 | 1 | 34 | 1947 | 592 | 555 | 20919 | 12 | PLACEBO_LADDER_BROKEN | PRIMARY_IS_POSITIVE_CONTROL |
| 555 | 2 | 69 | 2060 | 598 | 555 | 22557 | 14 | PLACEBO_LADDER_BROKEN | PRIMARY_IS_POSITIVE_CONTROL |
| 555 | 3 | 103 | 2031 | 592 | 555 | 22219 | 10 | CONCURRENCY_TAXES | PRIMARY_IS_POSITIVE_CONTROL |
| 555 | 4 | 138 | 2038 | 592 | 555 | 22311 | 10 | CONCURRENCY_TAXES | PRIMARY_IS_POSITIVE_CONTROL |
| 555 | 5 | 173 | 2270 | 601 | 555 | 25763 | 8 | CONCURRENCY_TAXES | PRIMARY_IS_POSITIVE_CONTROL |

🔴 **把 r489／r490 真正分析的那組列數釘死在 364／555 之後，判決仍然隨起始位置翻動，
方向與 R496 相同：快照前段 `PLACEBO_LADDER_BROKEN`、後段
`CONCURRENCY_TAXES`／`PRIMARY_IS_POSITIVE_CONTROL`。**
⇒ **R497 §三 提出的「翻動可能是被分析樣本數造成的」這個替代解釋，本尺答掉了：不是。**

## 二 但這只是換了一個殘留混淆，不是控制住了全部

| 設計 | 固定的是 | 浮動的是 |
|---|---|---|
| R496（等 n） | 閘道總列數（1672／2291） | **被分析列數 491→364（rho=−1.0，R497 §三）** |
| R498（本尺） | **被分析列數（364／555，逐格精確）** | 總列數（極差 62.77%）、時間跨度（極差 55.91%／22.97%） |

⇒ **兩種等化各留下不同的殘留量，而「位置會翻動判決」在兩種等化下都活下來。**
這是本輪能給的最強說法：**單一個樣本數單位（無論總列數或被分析列數）都解釋不掉它。**
⛔ **不准寫成「已經控制住混淆」**：`SPAN_UNCONTROLLED=True`（判準 §三 的併記門檻 0.25，
364 層的 0.5591 越過、555 層的 0.2297 **只差一點沒越過**）。時間跨度與總負載仍與位置共變。
⛔ 也**不准**因此讀成「R496 是對的」——R496 等錯單位這件事（R497 §三）原樣保留；
本尺是**用另一個單位重新問一次**，不是替它背書。

**還有一個更小的殘留要照實記**：本尺釘死的是 `is_chat ∧ is_analysable`（`n_sub`），
但 `r489.analyse:255` 的曝光索引是用 **`chat` 全體**建的，而 `n_chat` 仍浮動
（382→404，+5.8%；586→601，+2.6%）⇒ **釘死的不是 r489 吃進去的每一個量。**

## 三 判準外冒出的兩格，照實記、不追認、不算進計數

`EXPOSURE_DEGENERATE`（364 層 i=1）與 `UNRESOLVED`（364 層 i=2）不在判準 §三 的
頭條對照表上，兩支工具在同一格同時出現同一個字串。人眼確認：它們是 r489／r490
自己 `decide()` 的既有分支，不是量具例外（`exc=0`）。

**頭條對它們穩健，已量**：把這兩格整格拿掉重新分格，
`BOTH → POSITION_MATTERS`，兩者都仍映到 `POSITION_SURVIVES`（10 格）。
⇒ 頭條不是靠這兩格撐起來的。

## 四 預測帳（判準 §六）：6/6 全中——**這要當警訊看**

| 代號 | 預測 | 結果 |
|---|---|---|
| `Q-1` | r489 判 `POSITION_SURVIVES`（**低信心，本輪的賭注**） | **HIT** |
| `Q-2` | r489 與 r490 頭條相同（**自標最可能錯**） | **HIT**（cell 都是 BOTH） |
| `Q-3` | 至少一層 `SPAN_UNCONTROLLED` | **HIT**（0.5591 / 0.2297） |
| `Q-4` | `n_rows_total` 極差 > 10% | **HIT**（62.77%） |
| `Q-5` | 校準兩向如期 | 成立，但 **guard／校準，不是證據** |
| `Q-6` | 不出現 `UNSCANNED` | **HIT** |

⚠ **全中的三個折扣，逐條寫明**：
(a) 本檔的**動機不盲**（R497 §三 已經指出共線）；盲的只有答案。
(b) `Q-3`／`Q-4` 幾乎是機械必然（固定 chat 列數就是放掉總列數與跨度）⇒ 資訊量低。
(c) `Q-5` 是設計上必然成立的校準項。
⇒ **真正帶資訊的只有 `Q-1` 與 `Q-2` 兩條。** 同 R496 §九 那一課，不得把 6/6 當成六份證據。

## 五 承重牆／突變體：判準表 **3/4**，補充的 M4b DETECTED

```
DETECTED  M1_ONE_POSITION   verdict==BROKEN_WINDOWS   實際 BROKEN_WINDOWS
DETECTED  M2_TOTAL_ROWS     verdict==BROKEN_EQCHAT    實際 BROKEN_EQCHAT
DETECTED  M3_FORCE_SAME     兩工具 cell 都變 NEITHER  實際 兩支都 NEITHER（乾淨版都是 BOTH）
MISSED    M4_PIN_M          verdict==BROKEN_DERIVED   實際 crash（IndexError）

[補充，事後補、不計入 N/4]
DETECTED  M4b_PIN_M_FEASIBLE  M 釘成 (300,500)  ->  verdict=BROKEN_DERIVED
```

🔴 **`M4` MISSED 的原因是判準自己寫的突變體不可行，照實記，不追認進判準**：
§五 寫「把 M 寫死成 R496 的 N（1672/2291）」，但 `len(sub)=728` ⇒
`chat_windows` 取 `sub[lo_s+M-1]` 直接 IndexError ⇒ **crash 收場不算偵測到**
（memory 已記過這一條，本輪原封不動重演）。
⇒ 補了 `M4b_PIN_M_FEASIBLE`（釘成可行的錯值 300／500），實測 `BROKEN_DERIVED`
⇒ **`G-DERIVED` 確實有牙齒**，但那是**事後**補的證據，`M4` 本身仍記 MISS。
🆕 **通則（新）：突變體要先問「這個錯值在被測資料上跑得起來嗎」——
把參數釘成另一個尺度的數字，最可能的結局是 crash，而 crash 長得跟「擋門沒牙齒」一樣。**

**selftest 又抓到一次同一族的老坑**：`C7` 原本用字串比對檢查「本檔沒有自己重寫 `classify`」，
但**那行檢查自己就含有被找的字面** ⇒ 恆為真。改成 `ast` 取 `FunctionDef` 名稱集合
＋找 `R496.classify` 的 `Attribute` 節點才真的有牙齒（memory 已記過兩次，這是第三次）。

## 六 誠實邊界與下一步

1. 12 個視窗高度重疊 ⇒ **可用的是方向，不是次數**（R496 原樣沿用）。
2. **本尺不建立因果。** 它排除的是「單靠被分析樣本數」這一個解釋。
   仍與位置共變而**未被控制**的：時間跨度、總閘道負載、chat 佔比（R497 的那一條軸）。
3. **下一步（要先寫判準再量）**：目前只剩「時間跨度」與「總負載／chat 佔比」兩族殘留。
   跨度可以用「等跨度且等被分析列數」的雙重約束視窗試著再夾一次——
   但事前要先算**這份快照塞不塞得下**（等 chat 列數已經把跨度撐到 ±56%，
   再加一個約束很可能無解）⇒ **判準要先寫「無解時吐什麼」**，不能量完再訂。
4. **仍未做**：R495／R496 的承重牆刪除測試（round767 交棒第 4 項，連兩輪未做）。
