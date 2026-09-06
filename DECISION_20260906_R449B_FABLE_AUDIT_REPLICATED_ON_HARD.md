# R449B 稽核：EQ5 在 LCB v2 難題上——判定 REPLICATED_ON_HARD

（2026-09-06，Fable 5.1 稽核輪。零 API；只讀 `runs/g_r449_eq5_lcb2/`（rows 120 行 sha8 `9b813a30`）。
判準是 `DECISION_20260906_R449B_EQ5_LCB2_PREREG.md` 在發射前寫死的三態規則，本文件只套用。
仲裁量取 `ops/gain/analyze_eq5.py --json` 的欄位；另以自寫配對 McNemar 與 bootstrap（seed 449，B=10000）獨立重算。）

## 一、效力前提 G-1..G-5

| # | 前提 | 實際 | 裁決 |
|---|---|---|---|
| G-1 | schema 相容 | `eq5_schema_precheck` ⇒ `SCHEMA_COMPATIBLE`，reasons `[]` | 綠 |
| G-2 | 收官資料 | `run_terminal=true`、`run_complete=true`、`broken_reasons=[]`、processed 120＝measured 120＋void 0 | 綠 |
| G-3 | 落盤欄位與離線重算一致 | `same_choice_effective` 與 `accepted ∧ (gate_sha==vote_sha)` 逐筆相同 **120/120** | 綠 |
| G-4 | 處置沒漂 | r448 runner sha `21f1f75` → r449b runner sha `63f20d5`，在 vacant-dev 上 `git diff` 三個檔（gain_run／brain_cline／codebench）**空**；`dirty=true` 的內容全是 `??` 的 runs/ 未追蹤資料，沒有任何 tracked 檔被改 | 綠（分類 (a) 都談不上：零差異） |
| G-5 | 不被旗標騙 | `equal_budget_comparison_valid=false`（EQ5-only 結構性為 false） | 如預期 |

## 二、九條事前預測逐條

| # | 預測 | 仲裁欄位 | 窗 | 實際 | 裁決 |
|---|---|---|---|---|---|
| P-1 | Δ 點估計 > 0 | `paired.delta_pp` | > 0 | **+8.33pp** | HIT |
| **P-2（主判準）** | 95% CI 下界 > 0 | `paired.ci95_lo_pp` | > 0 | **+0.30**（上界 +13.78） | **HIT** |
| P-3 | discordant 數 | `paired.n_discordant` | ≥ 15 | 20 | HIT |
| P-4 | 預算恰好 5 | `calls_per_task`／`budget_all_exactly_5` | 5.00／true | 5.00／true，120 列全部 `calls_used=5` | HIT |
| P-5 | void 率 | `void_rate_pp` | ≤ 5% | 0 | HIT |
| P-6 | 閘門 deliv% | `gate.deliv_pp_denom_measured` | [58, 82] | 70.83 | HIT |
| P-7 | 多數決 deliv% | `vote.deliv_pp_denom_measured` | [51, 75] | 62.50 | HIT |
| P-8 | 拒交率 | 100 − `gate.coverage_pp` | [2, 18] | 6.67（落在 MBPP+ 側 6–7%） | HIT |
| P-9 | 兩規則選到同一份（有效） | `same_choice_effective_rate_pp` | [5, 35] | 22.5（raw 25.0，`false_same_choice_n`=3） | HIT |

`verdict_four_cell = GATE_RULE_WINS`；`paired.b_gate_only=15`、`c_vote_only=5`、`p_mcnemar_exact=0.0414`。
兩個分母一併列：閘門 measured 70.83%、accepted 75.89%（85/112）。

**獨立重算**（rows.jsonl 逐列）：gate 85/120、vote 75/120、b=15、c=5、Δ=+8.33pp、McNemar 精確 p=0.0414、
percentile bootstrap 95% [+1.67, +15.83]——與 analyzer 一致；analyzer 的配對區間下界 +0.30 比 bootstrap 保守，
**仲裁以 analyzer 欄位為準**。

## 三、狀態：REPLICATED_ON_HARD

P-1 ∧ P-2 成立、未觸發 `NOT_REPLICATED_ON_HARD`（c<b、Δ>0）、G-1..G-4 全綠、P-4 HIT。事前寫死的准講句：

> 三個 run（兩批 MBPP+ 371 題、一批 LCB v2 難題 120 題）、同一組 5 份候選、同樣 5 通呼叫，
> 「跑客戶自己的驗收測資、交第一份通過的、全不通過就不交」的交付都高於「五份投票取多數」，
> 三次的 95% 區間下界都在 0 以上。

| | r446（MBPP+） | r448（MBPP+） | **r449b（LCB v2）** |
|---|---|---|---|
| 閘門 | 75.47% | 77.09% | **70.83%** |
| 多數決 | 71.43% | 73.58% | **62.50%** |
| b / c | 24 / 9 | 21 / 8 | **15 / 5** |
| p | 0.0135 | 0.0241 | **0.0414** |
| Δ | +4.04 [+1.08, +7.01] | +3.50 [+0.81, +6.47] | **+8.33 [+0.30, +13.78]** |

**仍不准講**（預註冊 §一 與 §六 逐條沿用）：≥5pp 的實務增益（r449b 下界 +0.30）；「系統打贏系統」；
外推到 LCB／MBPP+ 以外；把三個 run 併成 n=862；把 r449b 當 r447 的複製（同一批 120 題、不同設計）。

## 四、必須一起讀的三件事

1. **下界只有 +0.30pp。** 事前檢定力表說 n=120 在效果成立時只有 18–53% 機會讓下界過 0；這次過了，
   但是貼著線過。R448 §六 第二條的限定語「僅在 MBPP+ 量級的題目上」**這次不必加**，
   可是它的另一半仍成立：n=120 的 MDE 是 8.33pp，`power.n80_if_true_effect_is_observed=29` 對、
   `n_needed_halfwidth_5pp=278` 題——要把區間收到 ±5pp 需要的題數 LCB v2 沒有。
2. **難題上多數決確實變強了**（R440Z：OFF5 對 OFF +12.5pp），閘門仍多交付 8.33pp。
   但 R449B §八-6 的兩個解釋（「LCB 的可見測資較鬆」vs「難題上篩選較沒用」）本 run 分不開，照原文帶著。
3. **拒交 8 題全部五份皆錯**（本輪以 hidden_check 逐份重放 40 份候選，8/8 全 False）。
   `lcb_3763` 在其中（兩規則全滅，屬於已知量具問題題）；`lcb_3613` 兩規則皆錯但被閘門接受；
   排除這兩題重算：gate 85/118、vote 75/118、Δ=+8.47pp、b/c 不變 15/5——主結論用**含**的版本（§六-g）。

## 五、與 r447 的逐題四格（描述性，同一批 120 題、不同設計；不是複製）

r447（CONFORM vs OFF5）→ r449b（gate vs vote）：tie→tie 86；conform→gate 6；conform→tie 10；tie→gate 7；
off5→gate 2；off5→tie 4；off5→vote 2；tie→vote 3。同候選設計把 r447 的 [−0.83, +15.0] 收成 [+0.30, +13.78]
——區間變窄且下界過 0，是方法學陳述（生成噪音被消掉），不是新的效果宣稱。

## 六、其他

- 收據鏈 720 條 `verify_chain(who)` 為真；120 列的 `receipt_head` 119 個出現在後續條目的 `prev_hash`，
  最後 1 個等於鏈的 `head()`——全部在鏈上。
- 無損性：本 run 的 rows 不帶逐份 visible／hidden 對照欄位，無法像 r447 那樣直接數「可見沒過但隱藏過」；
  拒交 8 題的 40 份全錯是同一性質的間接證據，但不能寫成 0/120。
- runner `dirty=true` 的誠實邊界照 R449B §四 記：內容是未追蹤的 runs/ 資料，tracked 檔零改動（vacant-dev 上驗）。

## 七、推翻條件

- 若任何後續 EQ5 run（任一題庫）出現 c ≥ b ⇒ §三 的話降為「三次中兩次」。
- 若 lcb2 的 `visible_check` 被證明比 MBPP+ base suite 鬆到足以解釋 8.33pp 的大部分 ⇒ §四-2 的兩個解釋要拆開重講。
