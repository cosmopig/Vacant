# R502 預註冊：組成軸（chat 佔比）是不是一條**自由**的軸？三重約束下的梯子判決

判準先行。本檔在任何 R502 量測之前 commit。工具：`ops/gain/r502_triple_constrained_ladder.py`。

## 〇 為什麼要問這件事（前提，可被推翻）

round770 交棒第 2 項：R501 夾住了「被分析的 chat 列數 ∧ 時間跨度」，但 **R497 量到的組成軸
（chat 佔比 31%→24%）沒夾**，所以 R501 結果檔明文禁止寫「混淆已控制」。本輪要問的是那條軸。

🔴 **本輪動手前已知的數字（不是本輪量的，是 R501 已公布產物 `ops/gain/data/r501_dual_constrained_ladder.json`
的既有欄位，我在寫這份判準之前就算過，照實揭露）**：R501 那 12 個視窗的 chat 佔比是

```
M=364: 0.2971 0.3001 0.2971 0.2826 0.2945 0.2967   極差/最小 = 0.0619
M=555: 0.2886 0.2851 0.2695 0.2739 0.2734 0.2681   極差/最小 = 0.0765
```

⇒ **「R501 那組釘死左緣的組成極差 ≤ 0.10」在寫這份判準之前就已經知道為真＝強制綠燈，
本輪不准把它當佐證。** 有內容的問題只有下面這一個。

## 一 定義（沿用既有，不重寫＝不製造第二套語意）

- 母體 `R498.analysable`（chat ∧ analysable）、層別 `R498.derive_M` ⇒ M ∈ {364, 555}（現算，`M_EXPECTED` 對不上 ⇒ `BROKEN_DERIVED`）
- 切片跨度 `R499.spans_for(sub, M)`；等跨度帶 = 以第 i 個切片當最短跨度、收 `[s, s(1+τ)]` 的索引集合 J（同 `R499P.best_dispersion` 的帶）
- 分散度 `disp = min_adjacent_gap / even_gap`，`even_gap = room/(K-1)`（R501 §一.6，已證明有牙齒）
- **組成量** `share_j = M / n_rows_total_j`，`n_rows_total_j` = 該視窗在閘道**全部**列上的列數
- `spread(x) = (max(x) - min(x)) / min(x)`
- 常數全部沿用，**新增旋鈕零**：`τ = τ_span = τ_comp = 0.10`（R499 梯階）、`K = 6`、`DISP_MIN = 0.5`

🆕 **結構事實（要寫進結果）**：M 固定 ⇒ `share = M/n_total` ⇒ **夾住組成 ≡ 夾住閘道總列數**，
而閘道總列數正是 **R496** 夾的那個單位。所以「三重約束」＝ R496 的單位 ∧ R498 的單位 ∧ 跨度，同時成立。

## 二 要判什麼（兩段，第二段以第一段為條件）

### 第一段：組成軸是不是被前兩條約束**強制**的（`FORCED_BY_OTHERS`）

對每一層，掃過所有可行的等跨度帶 J（`|J| ≥ K` 且 `max_min_gap(J,K)/even_gap ≥ DISP_MIN`）：

- **`COMP_FORCED_BY_OTHERS`**：**每一個**可行帶的**全帶** `spread(share over J) ≤ τ`。
  帶內任何 K 子集的極差不可能超過全帶極差 ⇒ 這條約束在這份資料上**不可能為假** ⇒
  ⛔ **收官不准把「組成也夾住了」寫成第三份證據**，只能寫「它是前兩條的推論」。
- **`COMP_FREE`**：找得到 **witness**——某個可行帶裡存在一組 K 個左緣，`disp ≥ DISP_MIN`
  且 `spread(share) > τ`。witness 的左緣、share、disp 必須具名落盤。
- **`COMP_UNRESOLVED_SEARCH`**（事前就宣告的第三格）：有某個帶的全帶極差 > τ（⇒ 上界擋不住），
  但下述**有界搜尋**找不到 witness。搜尋是不完備的 ⇒ **不准寫成 FORCED**。

**witness 搜尋（決定性、有界，事前寫死）**：對每個可行帶 J，令 `G = ceil(DISP_MIN * even_gap)`；
對 J 的每一個起點 j0，用貪婪法取 `gap ≥ G` 的前 K 個左緣（取不滿 K 就跳過），算 `spread(share)`。
任一組 `> τ` 即為 witness。複雜度 O(|J|²)。

### 第二段：三重約束下的梯子判決（**只在第一段判 `COMP_FREE` 時才跑**）

選左緣的規則（`best_dispersion` 的巢狀版本，對「≤ τ」方向是**完備**的，不是搜尋）：
對每個等跨度帶 J，再對每個 `c = share_j (j∈J)` 取組成子帶 `J' = {j∈J : c ≤ share_j ≤ c(1+τ)}`，
在 J' 上跑 `max_min_gap(J', K)`；全域取 `disp` 最大者。取不到 ⇒ `BROKEN_TRIPLE_INFEASIBLE`。

拿選出的 12 個視窗重跑 `R495.probe_r489` / `R495.probe_r490`，用 `R496.classify` 分格，
`headline` 映射沿用 R501 §一.8（`POSITION_MATTERS|BOTH → POSITION_SURVIVES`；
`NEITHER|NEW_CELL_UNIFORM_SHIFT → POSITION_GONE`；`N_MATTERS → N_ONLY`；其餘 `UNSCANNED`）。

## 三 事前預測（evidence 與 guard 分開標；guard 的綠燈不准當佐證）

| # | 預測 | intent | 信心 | 為什麼 |
|---|---|---|---|---|
| P1 | 第一段判 **`COMP_FREE`** | evidence | 中高 | R501 釘死那組已經到 0.0619／0.0765＝τ 的 62%／77%，而那組只是全帶的一個 K 子集；全帶候選有數百個，極差再撐開 30% 應該做得到 |
| P2 | 三重約束下**兩支 probe 的 headline 都是 `POSITION_SURVIVES`** | evidence | 高 | R496／R498／R501 三次換單位都是這一格 |
| P3 | 三重約束的 `disp` **嚴格小於** R501 雙重約束的（364: 0.6731、555: 0.9827），至少一層 | evidence | 中 | 多加一條約束會砍掉候選 |
| P3′ | 三重 `disp ≤` 雙重 `disp`（兩層皆是） | **IDENTITY** | — | 加約束只會縮小可行集 ⇒ 不可能為假 ⇒ **窮舉斷言，不是證據** |
| P4 | 校準落 `C_POS=NEITHER`、`C_NEG=N_MATTERS` | guard | 高 | 沿用 R501，防 infra |
| P5 | `live_reads == 0`、`n_exceptions == 0` | guard | 高 | G-LIVE 保住盲測 |

**乾淨那一格事前寫死（R499 的教訓、R501 已驗證這樣做突變表才不會集體失效）**：
乾淨執行預期 `verdict = TRIWIN_OK`、`comp_axis = COMP_FREE`、兩支 headline 皆 `POSITION_SURVIVES`。

## 四 突變表（每個突變體都要有看得見它的夾具；事前寫死乾淨判決與預期偵測器）

旗標 `R502_MUTANT`，**在被測函式內部**讀（memory：寫在模組層永遠不生效）。

| 突變體 | 改什麼 | 預期被誰看見 |
|---|---|---|
| `M1_COMP_TAU_HUGE` | 第二段的 τ_comp 改 10.0（組成約束失效） | 選出的左緣退回 R501 釘死那組 ⇒ `comp_binding` 由 true 翻 false |
| `M2_COMP_IGNORE` | 第二段跳過組成子帶（直接用 R501 選法） | `BROKEN_EQCOMP`（若組成約束真的有咬） |
| `M3_SHARE_CONST` | `share_for` 回常數 | 第一段翻成 `COMP_FORCED_BY_OTHERS` |
| `M4_FORCE_SAME` | 視窗判決一律 = 全母體判決 | cell 落 `NEITHER` ⇒ headline `POSITION_GONE` |
| `M5_DISP_IGNORE` | 第二段不要求 `disp ≥ DISP_MIN` | `BROKEN_DISPERSION` |
| `M6_ONE_POSITION` | 每層只留 1 個左緣 | `BROKEN_WINDOWS` |

**`M2`／`M5` 若在真資料上判 `MISSED`，寫成「該約束在這份資料上零承重」，不准調門檻讓它變綠。**

## 五 擋門（任一觸發 ⇒ verdict 就是那個字串，不是 `TRIWIN_OK`）

`BROKEN_DERIVED`（M 對不上）／`BROKEN_WINDOWS`（不是 2×K 個）／`BROKEN_EQCHAT`（`n_sub ≠ M`）／
`BROKEN_EQSPAN`（`span_spread > τ`）／`BROKEN_EQCOMP`（`comp_spread > τ`）／
`BROKEN_DISPERSION`（`disp < DISP_MIN`）／`BROKEN_TRIPLE_INFEASIBLE`／`BROKEN_EXCEPTIONS`／
`BROKEN_CALIBRATION`／`BROKEN_LIVE_READ`。

## 六 推翻條件（觸發了照實寫，**不准當場補判準去修**）

1. 第一段判 `COMP_FORCED_BY_OTHERS` ⇒ **P1 MISS**，且 §〇 的整個問題被推翻：組成軸不是自由的，
   R501 那句「組成軸沒夾」在**這個母體與這組約束下**是無從夾起的，收官要照 R492 的寫法記成
   「這個合取項由前兩條承重」，**不是**「我們控制了三個混淆」。
2. 第一段判 `COMP_UNRESOLVED_SEARCH` ⇒ 記 UNRESOLVED，**不准**降級成 FORCED。
3. 第二段判 `BROKEN_TRIPLE_INFEASIBLE` ⇒ 三重約束塞不下，照 R499 的作法把「塞不下」當結論寫，
   下一輪才談要不要放寬（放寬要另開判準）。
4. headline 若不是 `POSITION_SURVIVES` ⇒ P2 MISS，**先查 M4/M6 是不是誤觸**再談是不是真發現。

## 七 不做什麼

- 不改那條梯子本身（round762 裁決）。
- 不改 `r489.analyse:255` 的曝光索引母體不一致（交棒第 4 項，另開判準）。
- 不起任何 gain_run（§7 一端點一 run；主 run `g_r461_lcb3_three_arm` 在跑，
  `launch_eq5_seed2.sh` 在等它收官）。
