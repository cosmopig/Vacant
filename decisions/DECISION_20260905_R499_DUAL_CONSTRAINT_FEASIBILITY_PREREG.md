# R499 預註冊：雙重約束（等被分析列數 ∧ 等時間跨度）視窗設計，**先算塞不塞得下**

判準先行。本檔在任何量測之前 commit；結果另一個 commit。
上游：round768 交棒第 2 項（「殘留只剩兩族：時間跨度、總負載／chat 佔比」）＋
R498（`DECISION_20260905_R498_EQUAL_CHAT_N_PREREG.md`）記的 `SPAN_UNCONTROLLED=True`。

## 〇、這一輪要答的問題

R496 固定閘道總列數、R498 固定被分析列數，兩種等化下「視窗位置會翻動 r489／r490 的頭條判決」
都活下來。剩下沒被夾住的是**時間跨度**（R498 實測極差 0.5591／0.2297）。

自然的下一步是「等跨度 ∧ 等被分析列數」的雙重約束視窗。**但這份快照不一定塞得下**
（memory：「換家族要先算塞不塞得進去再挑暖的」）。所以本輪**不做**那個設計，
本輪只答一個可行性問題：

> 在 `r486_gateway_snapshot_v2.json` 上，存不存在一組視窗，同時滿足
> (a) 每個視窗恰含 M 筆**被分析**列、(b) 各視窗跨度彼此相近到宣稱得上「控制住」、
> (c) 左緣位置**分得夠開**（否則答不了「位置會不會翻動判決」）？

## 一、定義（量測之前寫死）

1. **母體**：`ops/gain/data/r486_gateway_snapshot_v2.json` 的 `rows`，丟掉 `ts is None`，依 `ts` 升冪。
2. **被分析列 `sub`**：沿用被測檔自己的過濾器 `R489.is_chat ∧ R489.is_analysable`
   （**經 `R498.analysable` 呼叫，不自己重寫一份**——memory：不准自己改寫一份運算式）。
3. **層 M**：由 `R498.derive_M` **現算**（G-DERIVED），必須對上 R497 §三 記的 `(364, 555)`；
   對不上 ⇒ `BROKEN_M_DRIFT`。
4. **候選視窗**：`sub` 上長度恰為 M 的連續切片，左緣 `j ∈ [0, room]`，`room = len(sub) - M`。
   跨度 `span(j) = sub[j+M-1].ts - sub[j].ts`。**跨度必須 > 0**，否則 `BROKEN_NONPOS_SPAN`。
5. **跨度容差 τ**：對一組被選中的視窗，`spread_min = (max span - min span) / min span`。
   ⚠ **這個分母與 R498 報的 `(max-min)/median` 不同**（R498 用 median）。刻意選 min：
   `median >= min` ⇒ `spread_median <= spread_min` ⇒ **本判準比 R498 的報法更嚴、是保守方向**。
   兩個都要報，並在輸出上斷言該不等式（附 §四 P6）。
6. **位置分散度**：被選中視窗的左緣 sub-index 極差除以 `room`，記 `pos_spread ∈ [0,1]`。
7. **設計要求**（照 R496／R498 的形狀，不另訂）：每層 `K = 6` 個視窗。
8. **可行性求解（精確，不是啟發式）**：對層 M 與容差 τ，
   對每個候選 `i` 當作最小跨度，令 `J = { j : span(i) <= span(j) <= span(i)*(1+τ) }`；
   若 `|J| >= K`，該帶可達的位置分散度 `= (max(J) - min(J)) / room`（取 min/max 兩端＋任意 K-2 個填充）。
   `achievable(M, τ) = max` over 所有這種帶；無任何帶滿足 `|J|>=K` ⇒ `achievable = None`。

## 二、常數（量測之前釘死，本輪不准調）

- `K_PER_TIER = 6`
- `SPREAD_MIN = 0.5`（左緣要蓋掉至少一半的可用行程，才談得上「位置分得開」）
- `TOL_HEADLINE = 0.10`（頭條容差：跨度極差不超過最短視窗的 10%）
- `TOL_LADDER = (0.05, 0.10, 0.20, 0.30, 0.50, 0.75, 1.00, 2.00)`（頻譜，逐級都要報）

## 三、判決

- `DUAL_FEASIBLE`：**兩層都** `achievable(M, TOL_HEADLINE) >= SPREAD_MIN`。
- `DUAL_INFEASIBLE`：否則（含 `achievable = None`）。
- `BROKEN_M_DRIFT` / `BROKEN_NONPOS_SPAN` / `BROKEN_LIVE_READ` / `BROKEN_EXC`：infra 壞掉，
  **不是** `DUAL_INFEASIBLE`（memory：「安靜量不到」要跟「量到 0」分得開）。

### 三-A、**無解時吐什麼**（handover 明文要求，量測前寫）

判 `DUAL_INFEASIBLE` 時，交付物**不是**一句「做不到」，而是：

1. **頻譜表**：`TOL_LADDER` 每一級 × 每一層的 `achievable`（含 `None`）。
2. **機制量**：`span(j)` 對 `j` 的 Spearman rho（每層各一），用來說明是不是密度單調變化造成的。
3. **兩個相反的誤讀都要在 GAIN_STATE 明文擋掉**：
   - ⛔ 不准寫成「位置其實沒影響／R498 的翻動被解釋掉了」——本輪**沒有**量任何判決。
   - ⛔ 不准寫成「R498 是對的／混淆已控制」——本輪只證明**這個夾法在這份快照上做不做得到**。
4. **停手規則**：判 INFEASIBLE 就**不准**當場放寬 `SPREAD_MIN` 或 `TOL_HEADLINE` 去湊出 FEASIBLE。
   頻譜表本身就是交付物；要不要改設計是**下一輪帶著判準**來做的事。

## 四、預測（事前，含 intent 與自評信心；memory：round768 自評方向整個反了，本輪照記不修飾）

| # | 預測 | intent | 信心 |
|---|---|---|---|
| P1 | 頭條 `DUAL_INFEASIBLE` | evidence | 高 |
| P2 | `achievable(364, 0.10) < 0.20`（不只是低於 0.5，而是嚴重不足） | evidence | 中 |
| P3 | `achievable(M, τ)` 對 τ **單調不減** | **guard（IDENTITY，事前宣告：可行集隨 τ 變大只會變大 ⇒ 結構強制綠燈，不是證據）** | — |
| P4 | 兩層的 `rho(span vs j)` **皆 > 0**（跨度隨位置變長＝密度下降，接上 R497 的 chat 佔比 31%→24%） | evidence | 高 |
| P5 | `live_reads == 0` | guard | — |
| P6 | 所有回報的視窗組滿足 `spread_median <= spread_min`（§一.5 的不等式） | **guard（IDENTITY）** | — |

⚠ P3／P6 事前標為結構強制綠燈 ⇒ **收官不准把它們算成證據**（memory：`FORCED_GREEN` 要先標 intent）。

## 五、校準（雙向，缺一不可）

- `C_POS`：合成快照，**等間隔到達** ⇒ 任何等 M 視窗跨度相同 ⇒ 必須吐 `DUAL_FEASIBLE`。
- `C_NEG`：合成快照，中途速率變 10 倍 ⇒ 必須吐 `DUAL_INFEASIBLE`。

只有正對照時「什麼都判 FEASIBLE」也會全綠 ⇒ 兩個都要。

## 六、突變體（每個都要**在真資料上跑得起來**；memory：釘成另一尺度的數字會 crash＝長得像沒牙齒）

| id | 改什麼 | 必須被看見的方向 |
|---|---|---|
| `M1_NO_SPREAD_REQ` | `SPREAD_MIN = 0.0` | 頭條翻成 `DUAL_FEASIBLE` |
| `M2_TOL_HUGE` | `TOL_HEADLINE = 1e9` | 頭條翻成 `DUAL_FEASIBLE` |
| `M3_UNSORTED` | 不依 `ts` 排序 | 吐 `BROKEN_NONPOS_SPAN`（**不是** crash） |
| `M4_BAND_K2` | 帶內只要求 `|J| >= 2` | `achievable(M, 0.10)` 至少一層**嚴格變大** |

`M4` 若 MISSED ⇒ 表示「K=6」這道加嚴在這份資料上零承重，**照實記成發現**，不改判準
（memory：加嚴條款一個都沒加＝真資料上零承重，是結果不是 bug）。

## 七、推翻條件

- 若真的判 `DUAL_FEASIBLE`：本檔 §〇 的前提（「不一定塞得下」）被推翻，下一輪應直接造那個設計。
- 若 `rho` 有任一層 <= 0：P4 的機制故事（密度單調下降）被推翻，
  INFEASIBLE 就得換一個解釋，**不准沿用 R497 的敘事**。
- 若 `M` 現算對不上 (364, 555)：整條 R496→R498→R499 的層別定義漂移，先修那個再談。
