# R449C 稽核：EQ5 在 lcb3（189 題）——判定 UNRESOLVED：同號（+4.23pp、b/c=13/5）但下界 −0.66 沒過 0

（2026-09-07，Fable 5.1 稽核輪。零 API；只讀 `runs/g_r449c_eq5_lcb3/`（rows 189 行 sha8 `57753571`）。
判準是 `DECISION_20260906_R449C_EQ5_LCB3_PREREG.md` 在發射前寫死的三態規則與邊界情況，本文件只套用。
仲裁量取 `analyze_eq5.py --json` 欄位；另以自寫配對 McNemar 與 bootstrap（seed 449，B=10000）獨立重算。）

## 一、效力前提 G-1..G-5

| # | 實際 | 裁決 |
|---|---|---|
| G-1 | `SCHEMA_COMPATIBLE` | 綠 |
| G-2 | `run_terminal=true`、`run_complete=true`、`broken_reasons=[]`、processed 189＝measured 189＋void 0 | 綠 |
| G-3 | `same_choice_effective` 與離線重算逐筆相同 189/189 | 綠 |
| G-4 | r449b sha `63f20d5` → r449c sha `b5daa07`，四檔 `--stat`：`gain_run.py` 34 行（round451，只在 `probe_instrument` 量具路徑，分類 (a)）、`vacant/checks.py` 34 行（round452b 沙箱模板加 `__vacant_ns`）；預註冊寫死的 (b) 判別：本 run 946 份候選碼含 `__vacant_ns` 者 **0** ⇒ 分類 (a)；`brain_cline.py`／`codebench.py` 零差異。`dirty=true` 內容為 runs/ 未追蹤資料（R453／R454 驗證者在 run 期間查過 vacant-dev tracked 檔零改動） | 綠（附分類表） |
| G-5 | `equal_budget_comparison_valid=false` | 如預期 |

## 二、九條事前預測逐條

| # | 仲裁欄位 | 窗 | 實際 | 裁決 |
|---|---|---|---|---|
| P-1 | `paired.delta_pp` | > 0 | **+4.23** | HIT |
| **P-2（主判準）** | `paired.ci95_lo_pp` | > 0 | **−0.66**（上界 +7.68） | **MISS** |
| P-3 | `paired.n_discordant` | ≥ 12 | 18 | HIT |
| P-4 | `calls_per_task`／`budget_all_exactly_5` | 5.00／true | 5.00／true，189 列全 5 | HIT |
| P-5 | `void_rate_pp` | ≤ 5% | 0 | HIT |
| P-6 | `gate.deliv_pp_denom_measured` | [68, 92] | 83.07 | HIT |
| P-7 | `vote.deliv_pp_denom_measured` | [67, 91] | 78.84 | HIT |
| P-8 | 100 − `gate.coverage_pp` | [2, 16] | 5.29 | HIT |
| P-9 | `same_choice_effective_rate_pp` | [10, 40] | 24.34（raw 24.87，false 1） | HIT |

`paired.b_gate_only=13`、`c_vote_only=5`、`p_mcnemar_exact=0.0963`、`verdict_four_cell=NON_INFERIOR_BUT_UNRESOLVED`。
兩個分母：閘門 measured 83.07%、accepted 87.71%（157/179）。

**獨立重算**：gate 157/189、vote 149/189、b=13、c=5、Δ=+4.23pp、McNemar 精確 p=0.0963、percentile bootstrap [0.00, +8.47]
——與 analyzer 一致；仲裁以 analyzer 的配對區間（−0.66）為準。

## 三、狀態：UNRESOLVED（邊界情況 (b)）

P-1 HIT、P-2 MISS、且 b（13）> c（5）⇒ 預註冊 §六-(b) 逐字：**這是 UNRESOLVED，不是 NOT_REPLICATED_ON_LCB3**。方向沒翻，
只是這一次沒把 0 排除掉；§五 事前就算出這是最可能的結果（效果成立時 P(下界>0) 只有 35–47%）。

依 §六 必報：`power.mde_at_n_pp=5.29`、`power.n80_if_true_effect_is_observed=38` 對（本 run 18 對）、`power.n_needed_halfwidth_5pp=189`；
事前檢定力表情境 A–H 見預註冊 §五。**准講的話**：「沒量出來，不是沒有差異。」**R448 §四 的宣稱範圍改成**：
「閘門規則贏多數決——MBPP+（兩個 seed）與 LCB v2 上顯著；LCB v3 上同號（+4.23pp）但未解析。」

四個 run 並列（同候選、同 5 通）：

| | r446 MBPP+ | r448 MBPP+ | r449b LCB v2 | **r449c LCB v3** |
|---|---|---|---|---|
| 閘門／多數決 | 75.47／71.43 | 77.09／73.58 | 70.83／62.50 | **83.07／78.84** |
| b / c | 24 / 9 | 21 / 8 | 15 / 5 | **13 / 5** |
| Δ [95%] | +4.04 [+1.08, +7.01] | +3.50 [+0.81, +6.47] | +8.33 [+0.30, +13.78] | **+4.23 [−0.66, +7.68]** |
| p | 0.0135 | 0.0241 | 0.0414 | **0.0963** |

四次 b 都大於 c（73/27 合計；**不准併成 n=1051 做檢定**，預註冊禁令 2）。

## 四、其他觀察（描述性）

- 拒交 10 題：以 hidden_check 逐份重放 50 份候選，**10/10 五份全錯**——拒交規則的前提在第四個題庫真跑成立。
- 收據鏈 1134 條 `verify_chain` 為真；189 列 `receipt_head` 全在鏈上。
- 與 r461（同一批 189 題、三臂獨立抽樣）逐題四格：tie→tie 155；conform→gate 4；conform→tie 7；conform→vote 1；off5→tie 9；tie→gate 9；tie→vote 4。
  r461 的 CONFORM vs OFF5 是 +1.59 [−3.17, +6.35]；同候選設計把區間收成 [−0.66, +7.68]——變窄，但這次沒窄到過 0（方法學陳述，不是效果宣稱）。
- lcb3 難度確實回到 MBPP+ 量級（閘門 83%、多數決 79%）；這是**第三個題庫**、**不是第二次難題複製**，難題證據仍只有 r449b。

## 五、推翻條件

- 若日後在 lcb3 上以新 seed 重跑 EQ5 得 c ≥ b ⇒ 本文件 §三「同號」要改成「三次同號、一次翻轉」。
- 若合併 lcb2＋lcb3 建成 ≥300 題的新 bank 並預註冊後跑出下界 > 0 ⇒ §三 的宣稱範圍可加回 LCB v3；在那之前不准。
