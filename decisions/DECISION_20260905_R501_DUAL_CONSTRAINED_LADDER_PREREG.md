# R501 判準：雙重約束（等被分析列數 ∧ 等跨度）視窗下，梯子判決還翻不翻？

**量測之前寫，單獨 commit。** 2026-09-05 UTC，round770。

## 〇 為什麼是這一輪

- R496 固定閘道總列數 ⇒ R497 量出被分析的 chat 列數仍 rho=-1.0 ⇒ 等錯單位。
- R498 改成固定**被分析 chat 列數** ⇒ 兩支 probe 都 `BOTH` / `POSITION_SURVIVES`，
  但 `span_uncontrolled=True`（tier 364 跨度極差 **0.5591**、tier 555 **0.2297**）
  ⇒ **只是換了殘留混淆**，round769 交棒明文不准寫成「已控制混淆」。
- R499 回答「等被分析列數 ∧ 等跨度」塞不塞得下：**`DUAL_FEASIBLE`**
  （τ=0.10 下 tier 364 achievable=0.794、tier 555=0.9827），
  且事後尺證明左緣還能等距鋪開（`frac_of_even` 0.6731／0.9827）。
- ⇒ 本輪把那個設計**真的造出來並跑梯子判決**。這是 round769 交棒第 2 項。

⚠ **本輪不動梯子本身**（round762 裁決）。只換視窗設計，重問同一個判決。

## 一 設計（量測之前釘死）

1. 快照：`ops/gain/data/r486_gateway_snapshot_v2.json`，`ts is not None` 後依 `ts` 排序。
2. 母體保真：`analysable` **直接沿用 `R498.analysable`**（＝`R489.is_chat ∧ R489.is_analysable`），
   不自己寫第二份（memory：母體保真要用被測檔自己的過濾器）。
3. 兩層 `M`：**現算**，用 `R498.derive_M`（G-DERIVED）。必須等於 `(364, 555)`，否則 `BROKEN_DERIVED`。
4. 容差 `TAU = 0.10`。**這個值是 R499 頭條就在用的那一階**，不是本輪看完結果挑的。
5. 左緣（`sub` 索引空間）**釘死字面值**，來自 `r499_posthoc_dispersion` τ=0.10 的輸出：
   - `M=364`：`[0, 49, 98, 147, 196, 248]`
   - `M=555`：`[0, 34, 68, 102, 136, 170]`
   ⚠ 釘死不等於可信 ⇒ **G-PINNED**：本尺要用 `R499_POSTHOC.best_dispersion(spans, 0.10, 6)`
   **現場重算**一次，與上面的字面值**逐元素相同**才准用；不同 ⇒ `BROKEN_PINNED`。
   （「量完再挑」的反面：釘死 + 可重算驗證。）
6. 🔴 **修掉 R499 §一.6 的鬆**（round769 交棒第 2(b) 項）：
   分散度不再用 `pos_spread=(max-min)/room`（只管兩端、中間可以全部重合），
   改用 **`disp = min_adjacent_gap(edges) / even_gap`**，`even_gap = room/(K-1)`，`room = len(spans)-1`。
   門檻 `DISP_MIN = 0.5`。
   ⚠ **`intent: guard`，不是證據。** R499 已公布這兩個數（0.6731／0.9827），
   本門檻在這份資料上**必然通過** ⇒ 它擋的是 infra（左緣被改成群聚），不是拿來支持任何結論。
   它存在的理由是：**`K=6` 在 R499 舊判準下零承重（`M4_BAND_K2` MISSED），這條讓 K 有牙齒。**
7. 等跨度擋門：每層內 `(max(span)-min(span))/min(span) <= TAU`，否則 `BROKEN_EQSPAN`。
   ⚠ 這是 R498 沒有的那道；R498 實測 0.5591／0.2297 ⇒ R498 的視窗**過不了本尺的這道門**。
8. 判決分格：**直接用 `R496.classify`**，headline 映射直接用 `R498` 那份語意
   （`POSITION_MATTERS|BOTH → POSITION_SURVIVES`；`NEITHER|NEW_CELL_UNIFORM_SHIFT → POSITION_GONE`；
   `N_MATTERS → N_ONLY`）。不重寫＝不製造第二套語意。
9. 校準：`C_POS`（永遠回同一個判決）必須落 `NEITHER`；`C_NEG`（回層別字母）必須落 `N_MATTERS`。
   任一不符 ⇒ `BROKEN_CALIBRATION`。
10. `G-LIVE`：`live_reads` 必須為 `0`，否則 `BROKEN_LIVE_READ`。

## 二 乾淨判決預期落哪一格（round769 交憗第 2(c) 項，突變表的前提）

🔴 **這一段必須寫在突變表之前，否則整張突變表會像 R499 那樣集體失效。**

- **預期乾淨頭條：兩支 probe 都 `POSITION_SURVIVES`（cell `BOTH` 或 `POSITION_MATTERS`）。**
- 根據：R496（總列數）、R498（chat 列數）兩種等化單位下都是 `POSITION_SURVIVES`，
  且 R498 的 cell 是 `BOTH`（層內、層間都變）。信心：**中**。
- ⇒ **可被突變體看見的方向是「翻離 POSITION_SURVIVES」**（往 `POSITION_GONE`／`N_ONLY`／`BROKEN_*`）。
  往 `POSITION_SURVIVES` 翻的突變體在本輪**結構上不可能被看見**，一個都不要放進表。

## 三 預測（事前，收官逐條記 HIT/MISS）

| 代號 | 預測 | 信心 | intent |
|---|---|---|---|
| `P1` | 頭條：兩支 probe 都 `POSITION_SURVIVES` | 中 | evidence |
| `P2` | `blockers` 為空（`verdict == DUALWIN_OK`） | 中 | guard |
| `P3` | `M == (364,555)`、`n_analysable == 728` | 高 | guard |
| `P4` | 兩層的 `span_spread <= 0.10`（＝等跨度真的做到了） | 高 | guard |
| `P5` | 兩層的 `disp` 分別 ≈ `0.6731` / `0.9827`（重算 R499 事後值） | 高 | guard |
| `P6` | **至少一支 probe 的 cell 與 R498 的 `BOTH` 不同** | **低（本輪的賭注）** | evidence |

`P6` 說明：R498 的 `BOTH` 有一部分可能來自跨度差 0.5591 的那層。跨度被夾住之後
若 cell 掉成 `POSITION_MATTERS`（層間不再差）或 `N_MATTERS`，那是有資訊的。
**我事前賭「不會變」的機率比較高 ⇒ P6 預測『會變』是低信心的一注**，照實記。

## 四 兩個相反的誤讀（事前擋掉，收官逐字檢查）

- ⛔ **若判 `POSITION_SURVIVES`，不准寫成「已排除跨度混淆、位置效應是真的」。**
  夾住的是**跨度與被分析 n 兩個軸**，還有 R497 量到的組成軸（chat 佔比 31%→24%）沒夾。
  正確寫法：「在同時等被分析 n 與等跨度的視窗下，位置仍翻得動判決」。
- ⛔ **若判 `POSITION_GONE`，不准寫成「R498/R496 的結論被推翻、位置其實沒影響」。**
  正確寫法：「位置的翻動在夾住跨度後消失 ⇒ 先前的翻動至少有一部分由跨度承載」，
  且要併記 `disp`（左緣鋪開程度）——群聚的左緣本來就比較不容易看到層內差異。
- ⛔ 不准寫「R496 是對的／R498 白做」。三輪換的是**等化單位**，是同一條敏感度曲線上的點。

## 五 突變表（方向已由 §二 定死：只放「翻離 POSITION_SURVIVES 或觸發 blocker」的）

環境變數 `R501_MUTANT`，**一律在被測函式內部生效**（memory：寫模組層等於沒突變）。

| 代號 | 改什麼 | 預期被哪個量看見 |
|---|---|---|
| `M1_ONE_POSITION` | 每層只留 1 個左緣 | `BROKEN_WINDOWS`（n_windows≠12） |
| `M2_R498_EDGES` | 左緣換回 R498 的等距左緣（不管跨度） | `BROKEN_PINNED`＋`BROKEN_EQSPAN` |
| `M3_PIN_SHIFT` | 釘死左緣整體 +1 | `BROKEN_PINNED`（G-PINNED 重算對不上） |
| `M4_FORCE_SAME` | 每個視窗的判決強制＝全視窗判決 | cell 掉成 `NEITHER` ⇒ headline `POSITION_GONE` |
| `M5_CLUSTERED` | 左緣改成 R499 舊解法的群聚形狀（`[0,1,2,3,4,289]` 型） | `BROKEN_DISPERSION`（disp < 0.5） |

⚠ **判準：突變體「crash 收場」不算偵測到**（memory）。每格要吐出上表指名的那個字串／量。
⚠ `M5` 就是 §一.6 那道新門檻的牙齒測試；`M5` MISSED ⇒ 照實寫「`disp` 門檻在真資料上零承重」，
**不准當場改門檻去救**。

## 六 推翻條件（事前）

- 若 `verdict != DUALWIN_OK` ⇒ 頭條寫 blocker 名稱，**不准報 cell／headline**（那些數字沒有意義）。
- 若 `disp` 重算與 R499 事後值不符 ⇒ 表示 R499 事後尺或本尺其中一個錯了，
  **停在這裡寫 `BROKEN_PINNED`，不要繼續往下解釋判決。**
- 若 `M5` MISSED ⇒ §一.6 的加嚴在這份資料上零承重，照 R499 `M4_BAND_K2` 的前例照實記，
  下一輪才准討論要不要換形式。

## 七 產物

- 尺：`ops/gain/r501_dual_constrained_ladder.py`（`--selftest` / `--json`）
- 資料：`ops/gain/data/r501_dual_constrained_ladder.json`
- 結果：`DECISION_20260905_R501_DUAL_CONSTRAINED_LADDER_RESULTS.md`（**另一個 commit**）
