# R479：對 **R461 附錄 C.5／D.3／E.3** 做可證偽性普查——收官義務清單是最後一塊沒被普查的仲裁者

判準先行。**本檔只寫規則、事前預測、推翻條件；量測在另一個 commit。**

## 〇、合法性與誠實揭露（先寫，不藏在最後）

1. **主 run `runs/g_r461_lcb3_three_arm` 還在跑**（開場同步：`rows.jsonl` 204 列、
   OFF/CONFORM/OFF5 各 68、`infra_void=0`、`run_complete=False`）。本輪**沒有**對它跑任何分析工具，
   普查工具內建擋門 B3（`live_run_reads` 必須為 0）。
2. ⚠ **本輪不是盲測。** 落筆前我已讀過 `ops/gain/replay/paired_ci.py:306-382`、
   `ops/gain/r447_eq5_offline.py:240-266,514-520`、`ops/gain/r447_gauge_capability.py`（grep 級）。
   ⇒ **不准宣稱 `blind_hit_rate`**（R473 那條指標在本輪沒有意義）。事前預測仍寫死在判準裡，
   它擋的是「量完再改預測」，不是「事前不知情」。
3. 修 R461 的合法窗口：§四三條假說的**資料一格都還沒被讀過**。本輪即使發現缺陷也**不改**
   §三／§四／附錄 A–G 的正文、不改任何門檻／窗口／MDE／α／n／seed／worker／端點／bank。
   要修就另開附錄，且只准是「讓既有義務可執行」的加法式修正。

## 一、為什麼是 C.5／D.3／E.3

r718 的規則：**做完普查要問「收官會引用誰」，並在交棒寫「還沒被普查的是誰」。**

R461 已被普查的部分：§三／§四（R462）、§二／§六（R466）。
**沒被普查的是附錄 C.5／D.3／E.3 這三張「收官時要一起報／驗的」清單**——
而它們正是主 run 收官時逐條要照著跑的東西。清單本身若含結構強制綠燈或**根本不可執行**的條目，
收官會拿到一排看起來很完整的 ✓。

## 二、分類三格（逐字沿用 R453 §二，**不准加格**）

| 格 | 意思 |
|---|---|
| `EVALUABLE` | 證偽事件在結果空間裡構造得出來 ⇒ 命中帶資訊 |
| `FORCED_GREEN` | 寫得出恆等式**且** witness＝0 ⇒ 命中不帶資訊，收官要附恆等式與基準率 |
| `UNRESOLVED` | 兩者皆無 ⇒ 照實寫「判不出來」，不准往任何一邊倒 |

`intent`（**量測之前標**，r718 規則）：`evidence`＝收官拿它當佐證，強制綠燈是**警告**；
`guard`＝擋 infra 壞掉，強制綠燈是**設計如此**。

### 兩個**加法式布林旗標**（不是新的格，與 `class` 正交）

- `executable_as_pinned`：**照附錄釘死的那條指令跑，義務點名的那個量會不會出現在產物或 stdout 裡。**
  `False` ＝ 這條義務今天**沒有辦法執行**（不是「會不會被違反」，是「根本量不到」）。
- `premise_stale`：**義務正文陳述的那個原始碼事實，今天是不是還成立。**
  `True` ＝ 正文描述的工具狀態已過期（＝散文版的認證過期，R477 的同一型缺陷）。

⚠ `EVALUABLE` 只表示「可能為假」，**不表示這個 n 分得出來**；後者的仲裁者是 MDE。

## 三、擋門（判準不是 `rc≠0`；每一條指明**該吐哪個字串**）

| 代號 | 條件 | 判決 | rc |
|---|---|---|---|
| B1 | 每一條被普查條款的字面**在 R461 原文裡逐字找得到** | `BROKEN_PIN_NOT_IN_PREREG` | 2 |
| B2 | 每一條被引用的**原始碼字面**今天仍在該檔裡（`ast`／逐字取，不自己改寫一份） | `BROKEN_SOURCE_CLAIM_STALE` | 2 |
| B3 | `live_run_reads == 0`（不准讀主 run 任何一列） | `BROKEN_LIVE_RUN_READ` | 2 |
| B4 | 掃到的條款數 `> 0`（**第三型「安靜量不到」：掃到 0 個目標**） | `UNSCANNED` | 2 |
| B5 | 恆等式證明器**雙向**校準都過 | `BROKEN_CALIBRATION` | 2 |
| B6 | 本判準檔自己貢獻的條款數 `== 0`（防自我匹配） | `BROKEN_SELF_MATCH` | 2 |

全過且無 `BROKEN_*` ⇒ `verdict="OK"`、rc=0（**發現缺陷不改 rc**；缺陷寫在記錄裡，
rc 只反映「普查本身有沒有壞掉」）。

### B5 的雙向校準（memory：只有正對照時「什麼都判 FORCED」也會全綠）

- **正對照**（已知恆真）：`r447_eq5_offline.reconstruct` 的 `if ok_to_report / else` 兩支裡，
  `paired_gate_vs_vote` 與 `power` **同時**被指派 ⇒ 命題 `(pgv is None) == (power is None)` 恆真。
  用 `ast.get_source_segment` 逐字取出那兩支的指派、窮舉兩支求值。證明器**必須**判 `True`。
- **負對照**（自由統計量）：命題 `power is not None`（單獨一半）。證明器**必須**判 `False`。

## 四、被普查的 10 條與**事前預測**（量測前寫死）

| id | 條款（R461 原文出處） | intent | 預測 `class` | 預測 `exec_as_pinned` | 預測 `premise_stale` |
|---|---|---|---|---|---|
| C5-1 | 產物自己記的 `key` 欄位必須是 `deliv` | guard | EVALUABLE | **False** | False |
| C5-2 | CONFORM 臂 `accepted=False ∧ meets_demand=True` 的格數（≥1，基準率 40–70%） | evidence | EVALUABLE | True | False |
| D3-1 | `sampling` 必須是 `{bank:lcb3, seed:g-r461-lcb3, n:189, offset:0}` | guard | EVALUABLE | True | False |
| D3-2 | `verdict` 必須是 `RECONSTRUCTED` 才准讀數字 | guard | EVALUABLE | True | False |
| D3-3 | Δ 旁邊必須同時寫 `power.mde_at_n_pp` 與 `power.n_needed_for_5pp` | guard | **FORCED_GREEN** | True | False |
| E3-1 | `run_complete` 必須是 true（去 `summary.json` 讀，**工具自己不看**） | guard | EVALUABLE | True | **True** |
| E3-2 | `n_tasks_complete == 189` 且 `rows_file_lines == 567` | guard | EVALUABLE | True | False |
| E3-3 | `n_tasks_partial_excluded == |{task: 任一臂 infra_void}|` | guard | **UNRESOLVED** | True | False |
| E3-4 | 判 BROKEN 要看 `verdict`，不要看有沒有數字 | guard | EVALUABLE | True | False |
| E3-5 | `pz1_*_NOT_ARBITER` 不准當成 §三 C4 的失敗率引用 | guard | EVALUABLE | True | False |

### 四.1 三條預測的理由（**寫在量測之前**）

- **C5-1 `exec_as_pinned=False`**：附錄 C.2 釘死的兩條指令**沒有 `--json`**，而
  `paired_ci.py` 只在 `args.json` 為真時才落盤，**stdout 的六行 print 一個字都沒印 `key`**
  ⇒ 「產物自己記的 `key`」照釘死的指令跑**不存在**。這條義務本來是要擋
  「忘了帶 `--key deliv` ⇒ 安靜翻掉判決且 rc=0」，而它自己量不到。
- **D3-3 `FORCED_GREEN`**：見 §三 B5 正對照。`power` 與 Δ 在**同一個分支**被指派
  ⇒ 「Δ 旁邊有 power」永遠為真，witness 恆為 0。它是 `guard` ⇒ **設計如此，不是缺陷**，
  但收官**不准**把「power 有印出來」當成「檢定力有被檢查過」的證據。
- **E3-1 `premise_stale=True`**：E.3 第 1 點的正文說「這支工具**沒有任何完整性擋門**」，
  並附了 23／180／360 列都吐 `verdict=="OK"` 的表。R472 之後
  `r447_gauge_capability.py` 已有 `BROKEN_RUN_NOT_TERMINAL`／`BROKEN_NO_SUMMARY`／
  `BROKEN_ROW_ACCOUNTING` 三道擋門 ⇒ **那張表今天重跑不出來**。
  ⚠ 方向是**變安全**（洞被補了），但正文過期本身要記——`CERT_STALE` 的散文版。

### 四.2 `E3-3` 為什麼事前就判 `UNRESOLVED`（不准湊條件式恆等式）

恆等式寫得出來，但 witness 是不是 0 **要等收官時的 `infra_void` 才知道**，
而 B3 禁止本輪去讀它。memory 鐵律：**寫不出（此刻）恆等式就照嚴格規則吐 `UNRESOLVED`，
不准為了讓事前預測成真去湊條件式恆等式。**
⇒ **收官時必須對 E3-3 重判一次**：若 `infra_void == 0` 且 `n_tasks_partial_excluded == 0`，
它退化成 `0 == 0` 的零 witness 恆等式 ⇒ 當時要改記 `FORCED_GREEN`，
且**不准**把它讀成「對帳通過了」。（E.5 誠實邊界第 3 點已先說過完整恆等式沒在完整 run 上驗過。）

## 五、推翻條件（觸發了照實寫，**不准當場補判準**）

1. 任一擋門 B1–B6 觸發 ⇒ 本輪普查作廢，記 `BROKEN_*`，**不准只報沒觸發的那幾條**。
2. §四 任一條預測 MISS ⇒ **照實記 MISS，不准回頭改預測表**（R476／R477 有 MISS 的先例）。
3. 若 `paired_ci.py` 其實在 stdout 印了 `key`（我讀漏了）⇒ C5-1 的 `exec_as_pinned` 改 True，
   **且本輪不得再宣稱發現了 C5-1 這個缺陷**。
4. 若 `r447_gauge_capability.py` 的三道擋門其實不在 `HEAD` 上（我 grep 錯檔）⇒ E3-1 的
   `premise_stale` 改 False，同樣不得宣稱發現缺陷。

## 六、本輪**不做**的

不殺／不重啟主 run、不 `git add` 主 run 目錄、不起任何新 run、不改
`paired_ci.py`／`r447_eq5_offline.py`／`r447_gauge_capability.py` 任何一行、
不改 R461 §三／§四／附錄 A–G 正文、不動任何門檻。
**若 C5-1 成立，本輪只准新增一個「讓它可執行」的加法式附錄**（加 `--json`，不動門檻與判決名）。

## 七、產物

- 工具：`ops/gain/r479_r461_appendix_census.py`（`--selftest`／`--json`）
- 輸出：`ops/gain/data/r479_appendix_census.json`
- 接線：`tests/test_appendix_obligation_census_r479.py`
