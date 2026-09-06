# R449C：EQ5 的**第三個題庫**——`runs/g_r449c_eq5_lcb3`（LCB v3，189 題）

**日期**：2026-09-06　**輪次**：round449c（Opus 撰寫、待 Fable 稽核）
**狀態**：預註冊。**本檔在 run 發射之前、在任何 r449c 資料存在之前定稿。**
**授權**：本檔即 R440G 閘門所需的那一份——它授權 `runs/g_r449c_eq5_lcb3`
這一個 run 名字，與 seed `g-r449c-eq5-lcb3`，其他都不授權
（外加 §九-4 那個零 API 的量具 run 名 `eq5lcb3_probe`）。
**編號**：`R449` 被 `DECISION_20260905_R449_PEEREXEC_ARCHITECTURE_AUDIT.md` 用掉、
`R449B` 被 `DECISION_20260906_R449B_EQ5_LCB2_PREREG.md` 用掉；本檔用 **R449C**，
與 peerexec 那件事沒有關係，是 R449B 的下一個題庫。

---

## 一、要解的問題：**這條規則的優勢是規則的性質，還是那兩個題庫的性質？**

EQ5 的規則對比——同一組 5 份候選、同樣 5 通呼叫，
「跑客戶自己的驗收測資、交第一份通過的、全不通過就不交」對上「五份投票取多數」
——目前有三個 run，三次都是閘門贏、三次的 95% 區間下界都在 0 以上：

| | r446（MBPP+ 371） | r448（MBPP+ 371） | r449b（LCB v2 120） |
|---|---|---|---|
| seed | `g-r212-route-20260828` | `g-r448-eq5-seed2` | `g-r449-eq5-lcb2` |
| 閘門 deliv | 280/371＝75.47% | 286/371＝77.09% | 85/120＝**70.83%** |
| 多數決 deliv | 265/371＝71.43% | 273/371＝73.58% | 75/120＝**62.50%** |
| b / c / n_d | 24 / 9 / 33 | 21 / 8 / 29 | **15 / 5 / 20** |
| p（精確 McNemar） | 0.0135 | 0.0241 | **0.0414** |
| Δ | +4.04pp [+1.08, +7.01] | +3.50pp [+0.81, +6.47] | **+8.33pp [+0.30, +13.78]** |

（來源：`DECISION_20260906_R448_FABLE_AUDIT_REPLICATED.md` §三、
`DECISION_20260906_R449B_FABLE_AUDIT_REPLICATED_ON_HARD.md` §三。）

**但這三個 run 只站在兩批題目上。** r446 與 r448 是**同一批 371 題**（換 seed 不換題），
r449b 是 lcb2 的 120 題。也就是說：「閘門規則多交付」這件事的題目維度上，
現在的樣本數是 **2**，不是 3。R448 §四 那句「不能外推到別的題庫」在 r449b 之後
只鬆到「MBPP+ 與 LCB v2」，再往外仍然是空的。

`lcb3` 是**第三批題目**：189 題，與 lcb2 的 120 題**零交集**（§九-1 逐項驗過），
是目前手上最大的一個非 MBPP+ 樣本，而且它已經被 r461 用**獨立抽樣**的三臂設計跑過一次
（`runs/g_r461_lcb3_three_arm`），所以本 run 的每一格窗都有同題庫的實測錨。

### ⚠ 這**不是**難題複製——先寫死，免得收官時被讀成那個

`DECISION_20260906_R461_FABLE_AUDIT.md` §二-2 逐字寫過：

> **lcb3 比 lcb2 容易得多**：OFF 失敗率 27.5%（lcb2 是 49.2%），已回到 MBPP+ 的量級（31.8%）。
> ……**本 run 不能當「難題複製」讀**，它更像 MBPP+ 難度的第二個題庫複製。

所以本 run 的定位是——**第三個題庫、MBPP+ 難度量級、n=189**。它答的問題是
「換一批題目，這條規則還贏不贏」，**不是**「題目更難的時候還贏不贏」。
後者的證據到今天仍然只有 r449b 一個 run（lcb2，120 題，難度 49.2%），
**本 run 不管落在哪一格都不會讓那一格變成兩個 run**。§六 的狀態名刻意寫成
`REPLICATED_ON_LCB3` 而不是任何帶「HARD」的字，就是為了讓這件事在狀態名裡就看得見。

### 為什麼是這一格而不是別格

同一個題庫、同一個模型、同一個端點上，r461 已經量到兩件事（`DECISION_20260906_R461_FABLE_AUDIT.md` §一）：

- **OFF5 對 OFF ＝ +6.35pp、p=0.0501、[+1.06, +12.17]** ⇒ 多數決在這個題庫上**是有用的**
  （MBPP+ 上它只值 +0.81pp）。對手不弱。
- **CONFORM 對 OFF5 ＝ +1.59pp、p=0.6636、[−3.17, +6.35] ⇒ unresolved。**
  那是**獨立抽樣**的估計量（兩臂各抽自己的候選，生成噪音混在差值裡）。

EQ5 的同候選設計把生成噪音整個消掉，在**同一批 189 題**上問同一個方向、噪音小得多的問題。
所以本 run 也順帶回答「r461 那個 unresolved 是效果不存在，還是設計太吵」——
這與 r449b 對 r447 做的事逐字同構（r449b 把 r447 的 [−0.83, +15.0] 收成 [+0.30, +13.78]）。

### 它硬化什麼、不硬化什麼（估計量宣稱，收官不准放大）

**硬化的**：在 189 題 LeetCode medium／hard 題（LCB v3，2023-05-07 → 2024-08-10）上，
「閘門規則 vs 多數決規則」在**同一組候選**上的方向與幅度。

**不硬化的（逐條寫死，收官不准借用）**：

1. **不是「Vacant 這個系統贏了 OFF5」。** EQ5 答的是「給定同一組候選，哪一條選擇規則
   交付得多」。「兩個各自獨立抽樣的系統誰贏」是 r445／r447／r461 的估計量。
   R446 §二 的禁令逐條沿用。
2. **不是出貨形態的成本結論。** EQ5 的閘門臂花 5.00 通呼叫（不早停）；出貨形態會早停
   ——**在這個題庫上 r461 實測 CONFORM 是 1.55 通**。成本面仍以 r461／r447／r445 為準。
3. **不是 r461 的重複。** 本 run 與 `runs/g_r461_lcb3_three_arm` 跑的是**同一批 189 題**
   （§九-1 有離線驗證），但**設計不同**：r461 是三臂獨立抽樣，本 run 是同候選規則對比。
   同題不同設計 ⇒ 兩者**不是獨立樣本**，也**不是**互為複製。見 §七。
4. **不是「≥5pp 的實務增益」。** 三次的下界（+1.08／+0.81／+0.30）都遠低於 5pp 線。
   n=189 的 MDE 是 5.29–5.82pp（§五），本 run 不預期改變這一點。
5. **不是難題複製，也不是「LCB 代表所有難題」。** 見上一節；量具只覆蓋 12/189（§八-1）。

---

## 二、run 名字、指令與「唯一的差別」

run 目錄：**`runs/g_r449c_eq5_lcb3`**（本檔只授權這一個名字，外加 §九-4 的 `eq5lcb3_probe`）。
seed：**`g-r449c-eq5-lcb3`**（§九-2 驗過：這顆 seed 沒有出現在 43 個 `runs/*/summary.json` 的任何一個裡）。

```
--out runs/g_r449c_eq5_lcb3 --n 189 --offset 0 --arms EQ5 --bank lcb3
--seed g-r449c-eq5-lcb3 --models gemma-4-12b-it-qat --probe-sample 0
--request-timeout-s 600 --review-timeout-s 380
--decision DECISION_20260906_R449C_EQ5_LCB3_PREREG.md
```

與前面三條 EQ5（r446／r448／r449b）的逐項對照——**只有題庫、題數與 seed 三格不同**：

| 項 | r446 / r448 | r449b | **r449c** |
|---|---|---|---|
| `--arms` | EQ5 | EQ5 | EQ5（逐字相同的臂，一行碼沒動） |
| **`--bank`** | evalplus | lcb2 | **lcb3** |
| **`--n` / `--offset`** | 371 / 0 | 120 / 0 | **189 / 0** |
| **`--seed`** | `g-r212-route-20260828` / `g-r448-eq5-seed2` | `g-r449-eq5-lcb2` | **`g-r449c-eq5-lcb3`** |
| `--models` | gemma-4-12b-it-qat | 相同 | 相同 |
| `--probe-sample` | 0（有參考解的全驗） | 0 | 0 |
| request policy | timeout 600 / retries 4 / backoff 2.0 / review 380×2 | 相同 | 逐項相同 |
| agent pool | 6 個 agent／1 個模型家族（`POOL` 未動） | 相同 | 相同 |

與 r461（同題庫）的對照——**只有臂與 seed 不同**：

| 項 | r461 | **r449c** |
|---|---|---|
| `--bank` / `--n` | lcb3 / 189 | lcb3 / 189（**同一批 189 題**，§九-1 驗過） |
| `--arms` | OFF,CONFORM,OFF5（三臂獨立抽樣） | **EQ5（同候選、兩條規則）** |
| `--seed` | `g-r461-lcb3` | `g-r449c-eq5-lcb3` |
| `--review-timeout-s` | 未給（summary 記 `review_timeout_s: 60`） | **380**（沿用三條 EQ5；EQ5 沒有評審呼叫，這格對本 run 不作用，登記是為了指令逐字可比） |

發射器：`ops/gain/launch_eq5_lcb3.sh`（等 `PRIOR_RUN` 退出，SPEC_GAIN §7 一端點一 run；
預設 `PRIOR_RUN=runs/g_r449_eq5_lcb2`，該 run 的 `summary.json` 已經
`run_terminal=true`，所以預設情況下發射器走的是「已 terminal ⇒ 直接往下」那條路）。
**發射由稽核 session 之外的人執行；本檔只出檔案與指令。**

預估成本：189 題 × 5 通＝**945 次生成呼叫**，$0（8765 中轉）。牆鐘有硬錨：
r461 的 **OFF5 臂在同一個題庫、同一個模型、同一個池上就是 945 通，實測 `wall_s=38432.5`
＝10.7 小時**。本 run 的呼叫數逐字相同 ⇒ **粗估 10–13 小時**
（EQ5 每題多跑一次沙箱驗收，計算量在 CPU 側，不佔 GPU）。

---

## 三、事前註冊的預測（P-1..P-9）——先寫死，收官逐條判 HIT／MISS

仲裁量一律取 `python3 ops/gain/analyze_eq5.py --run runs/g_r449c_eq5_lcb3 --json ...`
輸出 JSON 的欄位，**欄位名逐字寫在下表第三欄**（記憶鐵律：判準要指名它讀哪個 key，
不准靠「工具印了什麼字串」）。

| # | 預測 | 仲裁欄位 | 窗 | 錨在哪 |
|---|---|---|---|---|
| **P-1** | Δ＝閘門 − 多數決 的**點估計** > 0 | `paired.delta_pp` | **> 0** | 三個 EQ5 run 都是正的（+4.04／+3.50／+8.33）；同題庫獨立抽樣 r461 CONFORM vs OFF5 也是正的（+1.59pp，但 unresolved） |
| **P-2** | **95% CI 下界 > 0（＝本 run 的主判準）** | `paired.ci95_lo_pp` | **> 0** | 三次下界都過 0（+1.08／+0.81／+0.30）。**但 n=189、且本題庫的獨立抽樣差只有 +1.59pp ⇒ 見 §五 的檢定力，這一格事前只有 35–47% 的機會會中** |
| **P-3** | discordant pair 數 | `paired.n_discordant` | **≥ 12** | 同候選 ÷ 獨立抽樣的 discordant 率比值：MBPP+ 是 8.36%/10.78%＝**0.776**（§九-7 用 r444＋r445 的 rows 重算 40/371＝10.78%），lcb2 是 16.67%/20.00%＝**0.833**。把 0.78–0.83 套到 r461 在**本題庫**實測的 11.11%（b=12 c=9，21/189）⇒ 預期 **8.7–9.3%** ⇒ E[n_d]≈16.4–17.5，P(n_d≥12)≈90%（§五） |
| **P-4** | 預算恰好 5 | `calls_per_task` ＝ **5.00** 且 `budget_all_exactly_5` ＝ **true** | 結構性 | `arm_eq5` 不早停；r446／r448／r449b 都是 5.00，862 列全部 `calls_used=5` |
| **P-5** | infra_void 率 | `void_rate_pp` | **≤ 5%** | **r461 在同題庫同模型上三臂全部 `infra_void=0`**（1427 通呼叫）；r444/r445/r446/r447/r448/r449b 皆 0 |
| **P-6** | 閘門 deliv%（主分母 measured） | `gate.deliv_pp_denom_measured` | **[68, 92]%** | r461 CONFORM 在**同一批 189 題**上 152/189＝**80.42%**；EQ5 的閘門與 CONFORM 選擇語意逐字元相同（差別只在早停，早停不改變選到誰）。窗＝80.4 ± 12（n=189 的 95% CI 半寬約 5.7pp，再留換 seed 的生成噪音） |
| **P-7** | 多數決 deliv%（主分母 measured） | `vote.deliv_pp_denom_measured` | **[67, 91]%** | r461 OFF5 在同一批 189 題上 149/189＝**78.84%**；窗＝78.8 ± 12，同上理由 |
| **P-8** | 閘門拒交率＝100 − coverage | `gate.coverage_pp` | 拒交 **[2, 16]%** | **四個錨這次難得一致**：r461 CONFORM 在本題庫拒交 15/189＝**7.94%**（拒交條件與 EQ5 逐字相同：五份都沒通過 `visible_check`），MBPP+ EQ5 是 7.01%／6.20%，lcb2 EQ5 是 6.67%。n=189、p=7.9% 的抽樣半寬約 3.8pp ⇒ [4.1, 11.7]；窗再往兩側各放一段給換題庫的餘裕 ⇒ [2, 16] |
| **P-9** | 兩條規則選到同一份（有效值） | `same_choice_effective_rate_pp` | **[10, 40]%** | 三個 EQ5 run 是 **20.49／20.22／22.50%**——跨兩個題庫、三顆 seed 幾乎不動。n=189、p=21% 的抽樣半寬約 5.8pp ⇒ [15, 28]；窗放寬到 [10, 40] 給換題庫的餘裕。lcb3 難度回到 MBPP+ 量級 ⇒ **不像 r449b 那樣事前把窗往下開** |

**無條件一併印、一併判、不准挑一個的次要量**（看過數字之後不准選分母——r444 那次
兩個分母給出相反判決）：

- `gate.deliv_pp_denom_measured` **與** `gate.deliv_pp_denom_accepted`（兩個分母都列）
- `same_choice_rate_pp`（raw）與 `false_same_choice_n`
- `paired.b_gate_only` / `paired.c_vote_only` / `paired.p_mcnemar_exact` / `paired.ci95_hi_pp`
- `power.mde_at_n_pp` / `power.n80_if_true_effect_is_observed` / `power.n_needed_halfwidth_5pp`
- `verdict_four_cell`

### ⚠ `analyze_eq5.py` 自己印的 `prereg` 區塊**不是本 run 的仲裁者**

那支工具的 `PREREG` 常數逐字編碼的是 **R446** 的窗（`P-R446-*`），而 R446 的窗是為
**MBPP+ 的 371 題**訂的。本 run 換了題庫與題數，**下面五格事前就知道它可能印錯**：

| 工具會印 | 它的窗 | 本檔的窗 | 為什麼不同 |
|---|---|---|---|
| `P-R446-2` 拒交率 | [3, 13] | **[2, 16]**（P-8） | 兩邊都放寬一段給換題庫的餘裕；本題庫的錨 7.94% 兩個窗都蓋得住，差別只在邊界 |
| `P-R446-3` 閘門 deliv% | [68, 84] | **[68, 92]**（P-6） | r461 實測 80.42% 只比 84 低 3.6pp，正常波動就會掉出去 |
| `P-R446-4` 多數決 deliv% | [64, 80] | **[67, 91]**（P-7） | r461 實測 78.84% 只比 80 低 1.2pp，**這一格掉出去的機會相當高** |
| `P-R446-5` same_choice_effective | [40, 95] | **[10, 40]**（P-9） | 三個 EQ5 run 實測都在 20–23%，那個窗在 r446 自己身上就 MISS 過 |
| `P-R446-7` n_d | ≥ 15 | **≥ 12**（P-3） | 那是 n=371 的窗；n=189 的 E[n_d] 只有 16.4–17.5 |

同理，工具的 `overturn_conditions_triggered` 會因為「閘門 deliv% 掉出 [68,84]」而印出
**R446 §六-3**——那條是 MBPP+ 371 題的窗，**本 run 不適用**；本 run 的對應條在 §六-(c)。

⇒ 收官時：`analyze_eq5.py` 的輸出用來取**數字**，HIT／MISS 由**本檔上表**判。
**不准為了讓工具印出正確字串而去改 `analyze_eq5.py` 的 `PREREG`**——那支常數是
r446 的事前註冊，改它等於改別人的事前註冊（該檔第 48 行自己寫著
「這些數字的仲裁者是那份 DECISION，不是本檔；改這裡等於改事前註冊 ⇒ 不准」）。

---

## 四、效力前提 G-1..G-5（不是預測，是「這份資料算不算數」的擋門）

任一條紅 ⇒ **先修／先揭露，不判 replication**（狀態＝`INVALID`，見 §六）。

| # | 前提 | 怎麼驗 | 事前已知的狀況 |
|---|---|---|---|
| **G-1** | analyzer 讀得懂 runner 寫的 rows | `python3 ops/gain/eq5_schema_precheck.py --run runs/g_r449c_eq5_lcb3` ⇒ `SCHEMA_COMPATIBLE` | r446／r448／r449b 上各實測過一次 |
| **G-2** | 帳對得上、且是收官資料 | `broken_reasons` ＝ `[]`；`summary.arms.EQ5.terminal` ＝ true；`measured + infra_void == processed` | r449b：120+0=120、terminal true |
| **G-3** | 落盤欄位與離線重算一致 | 每一列都有 `same_choice_effective`，且與 `accepted ∧ (gate_code_sha256==vote_code_sha256)` 逐筆相同（`analyze_eq5` 的 `landed`／`bad_eff` 區塊） | r448 是這道擋門第一次被評估，r449b 上 120/120 通過；本 run 沿用同一條 |
| **G-4** | 處置定義沒有漂掉（R680 Q2） | `git diff 63f20d580c87cf5c44d11f4c54f1d66220eabb6e <r449c 的 runner_git.sha> -- ops/gain/gain_run.py ops/gain/brain_cline.py vacant/codebench.py`，逐項分類 (a) 只影響分析／文件 (b) 影響臂行為 | **基線＝r449b 的 runner sha `63f20d580c87cf5c44d11f4c54f1d66220eabb6e`**（從 `runs/g_r449_eq5_lcb2/summary.json` 讀出，§九-6）。本檔寫作時 worktree HEAD＝`b3c8514`（feat/v2-four-stages），**b3c8514 是 round452／452b 的 SuiteSpec／entry_point 改動，它碰過 `ops/gain/gain_run.py` 與 `vacant/codebench.py`** ⇒ **這條 diff 事前就知道非空，收官必須逐項分類，不准引用本格當成「已經驗過」** |
| **G-5** | 不被長得像的旗標騙 | `summary.equal_budget_comparison_valid` **預期是 false** | 它的定義只看 `ON` 與 `OFF5` 兩臂（`gain_run.py:1394-1399`），EQ5-only 的 run 結構上永遠 false（r449b、r461 實測都是 false）。EQ5 的等預算證據是 P-4，不是這個旗標 |

**G-4 的兩條誠實邊界**：

1. r446／r447／r448／r449b／r461 的 `runner_git.dirty` 都是 **true**——它們跑的時候
   工作目錄有未提交的改動，所以那幾版的位元組**無法只憑 sha 完全還原**。這是既有的設計缺口
   （R680 Q2 的 BROKEN 情形的弱化版）。R449B 稽核 §一 G-4 查證過 r449b 那次的 dirty
   內容全是 `??` 的 `runs/` 未追蹤資料、tracked 檔零改動——**那是逐次查證的結果，不是這個欄位的通性**。
   本 run 大機率也會是 dirty＝true，**發射時把 dirty 記下來並逐項查證，不要沿用 r449b 的結論**。
2. 本 run 與 r449b 之間**一定隔著 round450–452b 的改動**（`b3c8514` 已經動過
   `gain_run.py`／`codebench.py`）。R449B 那次 G-4 是「三個檔 diff 空」的幸運情形，
   **本 run 不會是**。收官若把 G-4 判綠，必須附上逐項分類表，不准只寫「綠」。

---

## 五、事前檢定力：**n=189 仍然答不出 MBPP+ 量級的效果，這件事寫在資料之前**

用 repo 既有的 `ops/gain/replay/paired_ci.diff_ci`（round656 已雙向驗證）與二項列舉投影。
q＝discordant 率、p_b＝b/(b+c)。演算法與可重跑指令在 §九-3；下表是**實測輸出**。

| 情境 | P(`ci95_lo_pp > 0`)＝P-2 HIT | P(c≥b) | P(n_d<12) | E[n_d] |
|---|---|---|---|---|
| **A｜MBPP+ 的 EQ5 效果原樣搬過來**（q=8.4%, p_b=.725） | **34.9%** | 4.3% | 12.2% | 15.9 |
| **B｜按獨立抽樣比例縮放到 lcb3**（q=8.7%, p_b=.725） | **36.3%** | 4.0% | 9.6% | 16.4 |
| C｜q=8.7%, p_b=.571（r461 獨立抽樣的 12/9） | 5.2% | 32.5% | 9.6% | 16.4 |
| D｜q=11.1%（＝r461 實測的 discordant 率）, p_b=.725 | 46.6% | 2.2% | 1.0% | 21.0 |
| E｜q=11.1%, p_b=.571 | 6.2% | 29.4% | 1.0% | 21.0 |
| F｜效果在本題庫變弱（q=8.7%, p_b=.60） | 8.2% | 24.5% | 9.6% | 16.4 |
| G｜**真效果為 0**（q=8.4%） | 1.4% | 55.0% | 12.2% | 15.9 |
| H｜**真效果為 0**（q=11.1%） | 1.5% | 54.4% | 1.0% | 21.0 |

MDE（`power_paired.mde_at_n`，雙尾 α=0.05）：

| q | E[n_d]（四捨五入） | 最小可偵測 b−c | MDE |
|---|---|---|---|
| 8.4% | 16 | 10（分割 13/3） | **5.29pp** |
| 8.7% | 16 | 10（分割 13/3） | **5.29pp** |
| 11.1% | 21 | 11（分割 16/5） | **5.82pp** |

N₈₀（真效果＝觀測值時，80% 檢定力需要的 discordant pair 數，`power_paired.n_needed_for_power`）：
**p_b=.725 ⇒ 37 對**；**p_b=.571（r461 獨立抽樣的比例）⇒ 387 對**。
換算成題數（除以 q）：p_b=.725 時 q=8.4% ⇒ **440 題**、q=8.7% ⇒ **425 題**、q=11.1% ⇒ **333 題**；
p_b=.571 時 q=8.7% ⇒ **4448 題**。

**事前結論，寫在資料之前，收官不准改口**：

> **n=189 對這個效果量仍然是檢定力不足的（UNDERPOWERED）。**
> 如果本題庫上的真效果就是 MBPP+ 量到的 +3.5–4pp、discordant 率也照搬 8.4%，
> 本 run 有 **34.9%** 的機會讓 95% 區間下界過 0——也就是說，**即使效果完全成立，
> 最可能的結果（≈65%）是 UNRESOLVED。** 就算 discordant 率放大到 11.1%
> （＝r461 在本題庫上獨立抽樣的實測值），機會也只到 **46.6%**。
> 相對地，MDE 在 n=189 下是 **5.29–5.82pp**——比 r449b 的 9.17pp 好了將近一半，
> 但仍然高於我們預期的 3.5–4pp 效果。

檢定力不足的直接後果（一併事前寫死）：

- **UNRESOLVED 是本 run 最可能的落點，它不是失敗，也不是「效果不存在」。**
  收官若落在那一格，**不准**寫成「lcb3 上打平」「換個題庫就沒優勢」。
- 要把「效果在本題庫不成立」講出口，需要的是 **NOT_REPLICATED_ON_LCB3**
  （方向翻轉，在情境 A／B／D 下事前機率只有 2.2–4.3%；但在 C／E／F 下有 24.5–32.5%
  ——**這正是本 run 值得跑的原因，見下**），不是 UNRESOLVED。
- 想在這個題庫上把 P-2 推到 80%，需要 **333–440 題**（p_b=.725）而 **lcb3 只有 189 題**
  ⇒ 光靠這一顆 bank 做不到。這句話事前就成立，**不是收官時為了解釋結果才算的**。

**為什麼明知檢定力不足還要跑**：因為情境 C／E（p_b=.571，取自 r461 在**本題庫**獨立抽樣
量到的 12/9）與情境 A／B（p_b=.725，取自 MBPP+ 的 EQ5）給出**天差地遠的方向翻轉機率**
（32.5%／29.4% 對 4.3%／4.0%）。也就是說：**這一次「方向會不會翻」不是幾乎不可能，
而是取決於哪一組錨才是對的，而那正是這個 run 要問的事。**
r449b 那次事前方向翻轉只有 1.5–10.3%，本 run 有一組合理的錨把它推到 30% 上下
——這是三個 EQ5 run 至今第一次，真的有機會拿到 `NOT_REPLICATED_*`。
**這一段就是「不要為了有成效去挑對自己有利的設定」的具體兌現**：
明知最可能拿到的是 UNRESOLVED、且這一次翻盤機率不低，還是照跑，
並且事前就把三個狀態的措辭全部寫死。

---

## 六、決策規則（**在任何 r449c 資料之前寫死**）：三個狀態

前提：G-1..G-4 全綠。任一紅 ⇒ 狀態 `INVALID`，先修或先揭露，**不准**先判。

| 狀態 | 觸發條件（照順序判，先命中者為準） | 收官准講的話 |
|---|---|---|
| `INVALID` | G-1..G-4 任一紅；或 **P-4 MISS**（有任一列 `calls_used ≠ 5`） | 「這個 run 不當資料用」——P-4 MISS 是實作缺陷不是結果 |
| **`NOT_REPLICATED_ON_LCB3`** | `paired.c_vote_only ≥ paired.b_gate_only`　**或**　`paired.delta_pp ≤ 0` | 「閘門規則的優勢在第三個題庫上方向翻轉／打平」。R448 §四 那句話要加限定語「**只在 MBPP+ 與 LCB v2 上量到**」，並要同時報四個 run（r446／r448／r449b／r449c）的 b/c 對照。展場與任何對外文字在有進一步資料之前**不得**把 EQ5 的結論講成一般性質 |
| **`REPLICATED_ON_LCB3`** | P-1 HIT **且** P-2 HIT（等價於 `verdict_four_cell == GATE_RULE_WINS`） | 「四個 run（兩批 MBPP+ 371 題、一批 LCB v2 120 題、一批 LCB v3 189 題）、同一組候選、同樣 5 通呼叫，閘門規則的交付都高於多數決，四次的 95% 區間下界都在 0 以上。」**必須同時講**：lcb3 **不是難題**（OFF 失敗率 27.5%，MBPP+ 量級），所以這是**第三個題庫**的複製，**不是第二次難題複製**；難題證據仍然只有 r449b 一個 run。**仍不准**講 ≥5pp、不准講「系統贏」、不准外推到 MBPP+／LCB v2／LCB v3 以外的題庫 |
| **`UNRESOLVED`** | 其餘（典型：`delta_pp > 0` 但 `ci95_lo_pp ≤ 0`，即 `RULED_OUT` 或 `NON_INFERIOR_BUT_UNRESOLVED`） | 「**沒量出來**，不是沒有差異」——必須**同時**報 `power.mde_at_n_pp`、`power.n80_if_true_effect_is_observed` 與 §五 的事前檢定力表（round678 §六 的兩句話規則）。**並且**把 R448 §四 的宣稱範圍寫成「MBPP+ 與 LCB v2 上顯著；LCB v3 上同號但未解析」 |

### 邊界情況（事前寫死，避免收官當場挑）

- **(a) P-2 HIT 但 P-3 MISS（n_d < 12）**：判 `REPLICATED_ON_LCB3`，但**必須**在同一句話裡
  標注「配對數低於事前窗口」並報 N₈₀。不准只寫狀態名。
- **(b) P-1 HIT、P-2 MISS、且 `paired.b_gate_only > paired.c_vote_only`**：這是
  `UNRESOLVED`，**不是** `NOT_REPLICATED_ON_LCB3`。方向沒翻，只是這一次沒把 0 排除掉，
  而 §五 已經事前算出那是最可能發生的事（≈53–65%）。
- **(c) P-6／P-7 MISS**：不改變狀態判定，但要先查是不是**處置漂了**——EQ5 的閘門與
  CONFORM 只差早停，掉出 [68,92] 代表兩者在這個題庫上行為不一致 ⇒ 先查實作再解讀。
  （工具會依 R446 的 [68,84]／[64,80] 印出 §六-3；**那條不是本 run 的判準**，見 §三 末。
  P-7 特別容易被工具誤判：錨值 78.84% 距離工具窗上緣只有 1.2pp。）
- **(d) P-8 MISS**：照實記，並指出落在四個錨（6.20／6.67／7.01／7.94%）的哪一側或兩者之外；
  拒交率變化會同時改變 coverage 與兩個分母，要把兩個分母都列。
- **(e) P-9 MISS**：不改變狀態判定，但要說明對比結構變了（>40% ⇒ 兩條規則更常選到同一份；
  <10% ⇒ 更少），並列出四個 run 的 raw／effective 對照。
  **若 `same_choice_effective_rate_pp` > 95%**，照 R446 §六-1 的語意處理：
  這個比較沒有對比，結論只准寫「測不出來」，**不准**寫成「等預算下打平」。
- **(f) P-5 MISS 但 void ≤ 20%**：資料仍可判，但主結論必須附 void 敏感度——把 void 那幾題
  分別當成「全歸閘門贏」與「全歸多數決贏」兩個極端各算一次，兩端都報。
  void > 20% ⇒ §十 的中止準則已經觸發，資料不進結論。
- **(g) 有題目兩條規則都判失敗、且懷疑是量具問題**：先查量具不查模型（§八-1／§八-3），
  並且**不准**在收官時把那些題挑掉——挑題會變成 R440B 那個死過一次的逆向選擇器。
  要報的是「含」與「排除」兩個版本，且主結論用**含**的那個。
  **注意 lcb2 的兩題已知量具問題（`lcb_3763`／`lcb_3613`）不在本 run 的池內**
  （v2∩v3=∅，§九-1 驗過）——本題庫**沒有**任何已登記的 KNOWN_BAD 題，
  這代表「還沒找到」不代表「沒有」（§八-3）。
- **(h) 落在 `REPLICATED_ON_LCB3` 而且 `paired.delta_pp` 大於 r449b 的 +8.33pp**：
  **不准**寫成「效果在容易的題庫上更大」。§五 已事前指出 n=189 的 MDE 是 5.29–5.82pp，
  能被判顯著的點估計本來就會被截斷在 MDE 以上（winner's curse）；跨 run 比幅度要報區間重疊，不報點估計大小。

### 事前寫死的禁令（違反＝本輪失敗）

1. **看到數字之後改窗、改仲裁欄位、改狀態定義** ⇒ 一律不准。要改只能由後續輪次／人類
   在**下一個** run 之前改，且舊窗要留著讓人收回仲裁權。
2. **不准**把 r446 ∪ r448 ∪ r449b ∪ r449c 併成 `n=1051` 當獨立樣本去宣稱顯著。
   r446/r448 之間是同一批 371 題（完全重疊），r449b 與 r449c 題目零交集但**題庫不同**
   （難度分佈不同）⇒ 併起來的東西沒有一個母體對得上它。
3. **不准**用任何併庫數字取代 r449c 自己的 P-1／P-2 判定。**§六 的仲裁者只有 r449c 自己。**
4. **不准**在 `UNRESOLVED` 的情況下寫「兩條規則等價」「打平」「換題庫就沒優勢」。
5. **不准**把本 run 與 `runs/g_r461_lcb3_three_arm` 的數字當成「複製」或「兩個獨立樣本」——
   同一批 189 題、不同設計（§七）。
6. **不准**把本 run 的任何結果算進「難題」那一格。lcb3 的 OFF 失敗率 27.5% 是 MBPP+ 量級
   （R461 §二-2），難題證據只有 r449b 一個 run，本 run 落在哪一格都不改變這句話。

---

## 七、與 r461 的關係：同題、不同設計，**不是**獨立樣本、**不是**複製

`CRITERION_20260903_R680_POOL_PRECONDITIONS.md` 的 **Q1** 要求可併的兩個 run
`task_id` 集合交集＝∅。本 run 與 r461 的交集是 **189（完全重疊，§九-1 驗過）**
⇒ **Q1 MISS**。而且兩者連估計量都不同：

| | r461 | r449c |
|---|---|---|
| 設計 | 三臂各自抽自己的候選 | 同一組 5 份候選餵兩條規則 |
| 差值裡含不含生成噪音 | **含** | **不含**（同候選消掉） |
| 對比的東西 | 兩個系統（CONFORM vs OFF5） | 兩條選擇規則（gate vs vote） |
| 呼叫數 | CONFORM 1.55／題、OFF5 5.00／題 | 兩條規則共用同一組 5 通 |

**准做的（描述性，且必須標成描述性）**：

- **逐題跨 run 四格**：同一個 `task_id` 在 r461（CONFORM vs OFF5）與 r449c（gate vs vote）
  各自的贏家。這是完全重疊帶來的唯一好處，也是它的正確用法（r449b 對 r447 做過同一件事）。
- 把 r461 的 +1.59pp [−3.17, +6.35]（獨立抽樣、含生成噪音）與 r449c 的區間並列，
  用來說明**同候選設計把噪音消掉之後區間有沒有變窄**——這是方法學陳述，不是效果宣稱。

**不准做的**：把兩者的 n 加起來、把 r461 當成 r449c 的「先前證據」去做任何形式的合併推論、
或者說「lcb3 上量了兩次都同號」（那是同一批題目量了兩次）。

另外，lcb3 與 lcb2／lcb v1 的交集是 **0**（§九-1 驗過），所以本 run 對 r447／r449b／E3
**是**題目層級的獨立樣本——但那三個是**別的題庫**，難度分佈不同，
禁令 §六-2 仍然禁止把 n 加起來。

---

## 八、誠實邊界（沿用 `DECISION_20260904_R461_LCB3_REPLICATION_PREREG.md` 附錄 A.2／F.3、
R461 收官 §二，與 `DECISION_20260906_R449B_EQ5_LCB2_PREREG.md` §八）

這幾條是**題庫本身**的性質，換一條臂不會讓它們消失，收官必須原樣帶著：

1. **量具只覆蓋 12/189 ＝ 6.3%。** LCB 沒有官方參考解；
   `ops/gain/data/lcb_v3_probe_solutions.json` 是 round728（R461）**手寫並用真的
   `hidden_check` 逐題驗過**的 12 題，選題規則是「按 `task_id` 升冪取前 12 題、
   寫不出來照實記」（R461 附錄 A.1；實際 12/12 全部寫出，放棄 0 題 ⇒ 沒有存活者篩選）。
   **其餘 177 題的隱藏測資沒有參考解證明「正解會通過」。**
   ⇒ 「本 run 的量具兩個方向都對」這句話的實際覆蓋率是 **6.3%**，不是 100%。
   （`--probe-sample 0` 的意思是「不抽樣、有解的全驗」，不是「189 題全驗」——
   `probe_instrument` 先篩有參考解的題目再取前 `sample` 個，所以印出來的是 12/12。）
2. **`verify_lcb_bank --version v3` 會印 `probe_coverage: 0/189`，那是報告工具的路徑寫死，
   不是真實覆蓋率**（R461 附錄 F.3-1：該工具只讀 `lcb_probe_solutions.json`，
   而 v3 的手寫解在 `lcb_v3_probe_solutions.json`）。**收官引用覆蓋率時要寫 12/189，
   並註明這件事**，否則會把「工具讀錯檔」講成「這個題庫沒有量具」。
   本輪**不修** `verify_lcb_bank.py`（沿用 R461 §五.4 的判準：改量具要另開判準）。
3. **本題庫沒有任何登記在案的 KNOWN_BAD 題——那是「還沒找到」不是「沒有」。**
   `ops/gain/check_bank_precision.py` 的 `KNOWN_BAD` 只有 `lcb`／`lcb2` 兩鍵
   （內容都是 `lcb_3613`／`lcb_3763`），**沒有 `lcb3` 這一鍵**；而 v2∩v3=∅ ⇒
   那兩題不在本 run 池內（§九-1 驗過）。R461 附錄 A.2-1 查過
   `verify_lcb_bank --version v3` 的 `float_5dp_suspects` 是空的
   ⇒ **R440T 那個特定失效模式沒出現，但那只排除一種模式。**
   R440T 的教訓（`instrument N/N` 被讀成綠燈，實際兩題對任何解都必然失敗）
   在 v3 上**尚未被排除**。
4. **污染定界對 v3 比對 v1／v2 更弱，而且弱在整個題庫不是單一題。**
   `LiveCodeBenchLoader` 的 docstring 逐字寫著：v3 的日期視窗是
   **2023-05-07 → 2024-08-10**，**189 題全部不晚於 2024-08-10**
   ⇒ v1／v2 用的那句「本 bank 都在 2024-08 之後」**對 v3 為假**（R460 C3）。
   ⇒ 本 run **不准**宣稱「題目晚於模型訓練截止」。
   （v2 的對照是只有 `lcb_3026` 一題早於視窗；v3 是**全部**。）
   誠實邊界的上位句仍然是 R440 那條：**本 bank 只能宣稱「MBPP+ 之外、附日期戳」，
   不能宣稱零污染。**
5. **量具假象的上界＝23 題。** R461 §六-2 的能力下界在本題庫上已經量過一次：
   r461 的三臂裡「任一臂至少通過過一次」的題數是 **166/189 ＝ 87.8%**，
   未被示範的 **23 題**是「量具假象」的上界，不是「壞了 23 題」（§九-7 可重算）。
   本 run 收官時要重算同一個數字（EQ5 的兩條規則上「任一份候選通過過」）並與 166 並列。
6. **n=189 只辨得出 ~5.3–5.8pp 級的不對稱**（§五 的 MDE）。
   「不顯著」不等於「等效」——這是本 run 事前就知道的主要限制。
7. **與 r461 共用同一批 189 題 ⇒ 不是獨立樣本**（§七）。
   跟它的數字比較是「同一批題目換一個設計」，不是複製。
8. **LCB 的 `visible_check` 是題目附的範例測資，比 MBPP+ 的 base suite 鬆。**
   閘門規則的全部力量來自 `visible_check` 的鑑別力 ⇒ 若本 run 的閘門優勢與 MBPP+ 不同，
   「LCB 的可見測資比較鬆」與「這個題庫上篩選比較有用／沒用」兩個解釋在本 run 的資料裡
   **分不開**。收官不准只寫其中一個。（要分開需要另一個設計：同題庫、加強 visible 套件，
   那不在本 run 範圍。）
9. **難度組成是 medium 135／hard 54**（R461 附錄 A.4 的**實測**值；該檔 §二 原本寫的
   152/37 是作者自己回推算錯，附錄已更正，同一個錯誤也讓它把 v2 寫成 55/120，
   **v2 實際是 72/120**）。引用難度組成時要用附錄 A.4 的實測值，不要用 §二 的預測值。

---

## 九、自我驗證（發射前做完，指令逐條可重跑；全部零 API、零 ssh）

**指令跑在哪裡（照實記）**：本檔在 worktree
`/Users/cosmopig/Documents/GitHub/Vacant/.claude/worktrees/agent-a79214b8e2d91a093`
（branch `feat/v2-four-stages`，HEAD `b3c8514`）寫成。
需要讀 `runs/` 的 (1)(2)(6)(7) 在主 checkout
`/Users/cosmopig/Documents/GitHub/Vacant` 跑（worktree 沒有 `runs/`）；
需要讀本 DECISION 檔的 (4)(5) 在 worktree 跑。
(3) 只吃 `ops/gain/replay/paired_ci.py`（sha256 `9db4dee4…`）與
`ops/gain/power_paired.py`（sha256 `e05d95c3…`），**兩份在兩個 checkout 逐位元組相同**
（本檔驗過），所以跑哪一邊輸出一樣。本節每段指令都寫成
`cd <repo root> && …`，合併回 `main` 之後兩邊都能直接重跑。

**(1) 題目集合：本 run 的 seed 與 r461 取到的是同一批 189 題**——這是 §一-3 與 §七 的證據，
順便驗 v2∩v3=∅ 與量具 12 題都在池內：

```bash
cd /Users/cosmopig/Documents/GitHub/Vacant && .venv/bin/python - <<'PY'
import sys, json, hashlib; sys.path.insert(0,'.')
from ops.gain.gain_run import load_tasks
a=[t["task_id"] for t in load_tasks("lcb3","g-r461-lcb3",189,offset=0)]
b=[t["task_id"] for t in load_tasks("lcb3","g-r449c-eq5-lcb3",189,offset=0)]
r461=set(json.loads(l)["task_id"] for l in open("runs/g_r461_lcb3_three_arm/rows.jsonl",encoding="utf-8") if l.strip())
print("len",len(a),len(b)); print("set_equal",set(a)==set(b)); print("order_identical",a==b)
print("r461_rows_set_equal", r461==set(a))
v2=set(t["task_id"] for t in load_tasks("lcb2","g-r440-lcb2",120,offset=0))
print("v2_v3_intersection", len(v2 & set(a)))
sol=json.load(open("ops/gain/data/lcb_v3_probe_solutions.json",encoding="utf-8"))
print("v3_probe_solutions", len(sol), "in_pool", sum(1 for k in sol if k in set(a)))
print("bank_sha16", hashlib.sha256(open("ops/gain/data/lcb_bank_v3.jsonl","rb").read()).hexdigest()[:16])
print("lcb2_known_bad_in_pool", {x: x in set(a) for x in ("lcb_3026","lcb_3763","lcb_3613")})
PY
```

實測輸出（2026-09-06）：

```
len 189 189
set_equal True
order_identical False
r461_rows_set_equal True
v2_v3_intersection 0
v3_probe_solutions 12 in_pool 12
bank_sha16 bd3dffebb1b16bc7
lcb2_known_bad_in_pool {'lcb_3026': False, 'lcb_3763': False, 'lcb_3613': False}
```

⇒ 換 seed **不換題**（`LiveCodeBenchLoader` 的 seed 只打亂順序、不抽樣，189 題全取）；
r461 的 rows 就是這 189 題；lcb2 的三題已知問題題**都不在**本 run 池內。

**(2) seed 新鮮度：`g-r449c-eq5-lcb3` 沒有出現在任何一個 `runs/*/summary.json` 裡**：

```bash
cd /Users/cosmopig/Documents/GitHub/Vacant && python3 - <<'PY'
import glob, json
files=sorted(glob.glob("runs/*/summary.json"))
seeds={}
for f in files:
    try: seeds.setdefault(json.load(open(f)).get("seed"), []).append(f)
    except Exception: pass
print("summary.json 檔數:", len(files))
for s in sorted(map(str, seeds)): print(" ", s, len(seeds[s if s!='None' else None]))
print("g-r449c-eq5-lcb3 已被用過:", "g-r449c-eq5-lcb3" in seeds)
PY
```

實測：**43 個** `summary.json`，出現過的 seed 是
`42`／`g-off-failure-rate-20260901`／`g-r212-route-20260828`(21)／`g-r440-lcb2`／
`g-r442-lcb`／`g-r448-eq5-seed2`／`g-r449-eq5-lcb2`／`g-r454-scale2-20260901`／
`g-r461-lcb3`(2)／`g-smoke-20260820`(13)；**`g-r449c-eq5-lcb3` 不在其中**。
發射器 `ops/gain/launch_eq5_lcb3.sh` 把這個檢查做成發射前的硬擋
（`abort_seed_not_fresh`），**不是**跟單一個舊 seed 比字串。

**(3) 事前檢定力（§五 的表）**：

```bash
cd /Users/cosmopig/Documents/GitHub/Vacant && .venv/bin/python - <<'PY'
import sys, math; sys.path.insert(0,'.')
from ops.gain.replay.paired_ci import diff_ci
from ops.gain.power_paired import mde_at_n, n_needed_for_power
N=189
def bmin(m):
    for b in range((m//2)+1, m+1):
        if diff_ci(b, m-b, N)["lo"] > 0: return b
    return None
def pmf(k,n,p):
    if p<=0 or p>=1: return 1.0 if ((p<=0 and k==0) or (p>=1 and k==n)) else 0.0
    return math.exp(math.lgamma(n+1)-math.lgamma(k+1)-math.lgamma(n-k+1)
                    +k*math.log(p)+(n-k)*math.log1p(-p))
def stats(q,pb,mmax=90):
    pw=flip=nd12=0.0
    for m in range(mmax+1):
        pm=pmf(m,N,q)
        if pm<1e-14: continue
        if m<12: nd12+=pm
        bm=bmin(m)
        if bm is not None: pw+=pm*sum(pmf(b,m,pb) for b in range(bm,m+1))
        flip+=pm*sum(pmf(b,m,pb) for b in range(0,m//2+1))
    return pw,flip,nd12,q*N
for q,pb,lab in [(0.084,.725,"A q=8.4% p_b=.725"),(0.087,.725,"B q=8.7% p_b=.725"),
                 (0.087,.571,"C q=8.7% p_b=.571"),(0.111,.725,"D q=11.1% p_b=.725"),
                 (0.111,.571,"E q=11.1% p_b=.571"),(0.087,.60,"F q=8.7% p_b=.60"),
                 (0.084,.50,"G null q=8.4%"),(0.111,.50,"H null q=11.1%")]:
    pw,flip,nd12,ed=stats(q,pb)
    print(f"{lab}: P(lo>0)={pw*100:.1f}%  P(c>=b)={flip*100:.1f}%  P(n_d<12)={nd12*100:.1f}%  E[n_d]={ed:.1f}")
for q in (0.084,0.087,0.111): print(f"MDE@189 q={q}: {mde_at_n(N,q)['mde_pp']:.2f}pp")
print("N80 p_b=.725:", n_needed_for_power(.725), " p_b=.571:", n_needed_for_power(.571))
PY
```

實測輸出（逐字，即 §五 的表）：

```
A q=8.4% p_b=.725: P(lo>0)=34.9%  P(c>=b)=4.3%  P(n_d<12)=12.2%  E[n_d]=15.9
B q=8.7% p_b=.725: P(lo>0)=36.3%  P(c>=b)=4.0%  P(n_d<12)=9.6%  E[n_d]=16.4
C q=8.7% p_b=.571: P(lo>0)=5.2%  P(c>=b)=32.5%  P(n_d<12)=9.6%  E[n_d]=16.4
D q=11.1% p_b=.725: P(lo>0)=46.6%  P(c>=b)=2.2%  P(n_d<12)=1.0%  E[n_d]=21.0
E q=11.1% p_b=.571: P(lo>0)=6.2%  P(c>=b)=29.4%  P(n_d<12)=1.0%  E[n_d]=21.0
F q=8.7% p_b=.60: P(lo>0)=8.2%  P(c>=b)=24.5%  P(n_d<12)=9.6%  E[n_d]=16.4
G null q=8.4%: P(lo>0)=1.4%  P(c>=b)=55.0%  P(n_d<12)=12.2%  E[n_d]=15.9
H null q=11.1%: P(lo>0)=1.5%  P(c>=b)=54.4%  P(n_d<12)=1.0%  E[n_d]=21.0
MDE@189 q=0.084: 5.29pp
MDE@189 q=0.087: 5.29pp
MDE@189 q=0.111: 5.82pp
N80 p_b=.725: 37  p_b=.571: 387
```

MDE 的分割細節（同一支模組，`mde_at_n(189, q)` 的完整回傳）：
q=8.4%／8.7% ⇒ `{'n_disc_expected': 16, 'min_gap': 10, 'min_split': [13, 3], 'mde_pp': 5.29}`；
q=11.1% ⇒ `{'n_disc_expected': 21, 'min_gap': 11, 'min_split': [16, 5], 'mde_pp': 5.82}`。

**(4) 量具（零 API，跑到模型呼叫之前就退出）**：

```bash
cd <repo root 含本 DECISION 檔> && .venv/bin/python \
  ops/gain/gain_run.py --out /tmp/eq5lcb3_probe --n 189 --arms probe --bank lcb3 \
  --seed g-r449c-eq5-lcb3 --probe-sample 0 \
  --decision DECISION_20260906_R449C_EQ5_LCB3_PREREG.md
```

實測輸出（2026-09-06，本機零 API）：

```
預註冊閘門通過：DECISION_20260906_R449C_EQ5_LCB3_PREREG.md 授權 eq5lcb3_probe
189 題（lcb3　offset=0　題序 [0, 189)）　輸出 /tmp/eq5lcb3_probe
── 量具驗證（先答已知答案）
   參考解通過 12/12　壞解被擋 12/12
   可見閘門（CONFORM 決策量具）參考解通過 12/12　樁被擋 12/12　覆蓋 12/12
EXIT_CODE=0
```

在 `--arms probe` 的分支 `return`（`gain_run.py:1353`）——**一次模型呼叫都沒有**
（沒有印出「模型池預檢」那一段）。這三行 `12/12` 就是 §八-1 那條 6.3% 覆蓋率的具體形狀：
**分母是 12 不是 189**。

⚠ 真正發射時 `--arms EQ5` 會多吃一道硬擋（`gain_run.py:1338-1352`）：
`visible_n < n` ⇒ 停。本 run 的 `n`＝有參考解的題數＝12，`visible_n`＝12 ⇒ 12≥12，過。
**這道擋門比較的是 12 對 12，不是 12 對 189**——§八-1 那條 6.3% 覆蓋率的邊界
不會被它擋下來，所以必須靠本檔寫出來。
（`--out /tmp/eq5lcb3_probe` 這個名字寫在本行是**故意的**：R440G 閘門檢查的是
`pathlib.Path(--out).name` 有沒有出現在 DECISION 內文裡，所以量具指令要能跑，
`eq5lcb3_probe` 就必須出現在本檔。這也是為什麼量具指令屬於預註冊的一部分。）

順帶實測到 R440G 閘門有牙齒：把 `--out` 改成沒註冊的名字（`/tmp/eq5lcb3_probe_notreg`）時，
它印

```
拒絕啟動：DECISION_20260906_R449C_EQ5_LCB3_PREREG.md 內文沒有寫到 run 名字「eq5lcb3_probe_notreg」——先把 run 名字與預測寫進 DECISION 再跑
```

並以 rc=1 停住，**一題都沒載**（`/tmp/eq5lcb3_probe_notreg` 沒有被建出來）。

⚠ 誠實邊界：**把這段證據寫進本檔，就讓它自己不可重跑了**——R440G 的判準是
「`Path(--out).name` 是否為 DECISION 內文的子字串」，而 `eq5lcb3_probe_notreg`
現在已經在內文裡（就在上面那個 code block），所以同一條指令再跑一次**不會**再被擋。
這不是本輪的缺陷，是 R440G 這道閘門的結構性性質
（R449B §九-4 做過同一個示範——它把 `eq5lcb2_probe_head` 抄進了內文——但**沒有**記下這個副作用；
本檔補上）：
它擋的是「run 名字沒寫進預註冊」，而**任何把拒絕訊息抄進預註冊的動作都會解除那次拒絕**。
要重現這一格，請換一個沒出現在本檔的名字。

**(5) 發射器語法與一致性**：

```bash
bash -n ops/gain/launch_eq5_lcb3.sh
.venv/bin/python -m pytest tests/test_r449c_launcher_prereg.py -q
```

`tests/test_r449c_launcher_prereg.py` 釘住的是**發射器與本檔不准漂開**：
run 名字、seed、`--n 189 --offset 0`、`--arms EQ5`、`--bank lcb3`、模型、
`--probe-sample 0`、request policy、`--decision` 指到本檔、等待字串錨在行首、
seed 不在任何 `runs/*/summary.json` 裡、九條預測的仲裁欄位名真的存在於
`analyze_eq5.py` 的輸出 dict 裡（grep 原始碼），以及五個突變檢查
（改 seed／拿掉錨／把探針數改成 1／題庫掉回 lcb2／新鮮度退回比字串
都必須讓對應的測試變紅）。
**本檔的測試刻意不寫任何「`runs/` 目錄不存在」的斷言**——
`tests/test_r448_launcher_prereg.py` 那樣寫過，run 真的跑完之後它就永遠是紅的。

**(6) G-4 的基線 sha（從已收官的 run 讀出，不是靠記憶）**：

```bash
cd /Users/cosmopig/Documents/GitHub/Vacant && .venv/bin/python -c "
import json
for r in ('g_r449_eq5_lcb2','g_r448_eq5_mbpp_seed2','g_r461_lcb3_three_arm'):
    s=json.load(open(f'runs/{r}/summary.json'))
    print(r, s.get('seed'), s.get('runner_git'), s.get('run_terminal'))"
```

實測：

```
g_r449_eq5_lcb2 g-r449-eq5-lcb2 {'sha': '63f20d580c87cf5c44d11f4c54f1d66220eabb6e', 'dirty': True, 'branch': 'feat/v2-four-stages'} True
g_r448_eq5_mbpp_seed2 g-r448-eq5-seed2 {'sha': '21f1f7545bf6776aaa73e357ea35cad191111c4a', 'dirty': True, 'branch': 'feat/v2-four-stages'} True
g_r461_lcb3_three_arm g-r461-lcb3 {'sha': '5288a2d6c4405ef307a3bda4b6e02a6c98748b4d', 'dirty': True, 'branch': 'feat/v2-four-stages'} True
```

⇒ G-4 基線＝**`63f20d580c87cf5c44d11f4c54f1d66220eabb6e`**；
`runs/g_r449_eq5_lcb2` 的 `run_terminal=true` ⇒ 發射器的預設 `PRIOR_RUN` 合法。

**(7) §三 P-3 的錨與 §八-5 的能力下界（都從 rows 重算，不引用他人數字）**：

```bash
cd /Users/cosmopig/Documents/GitHub/Vacant && .venv/bin/python - <<'PY'
import json, collections
for run in ("g_r444_conform_mbpp","g_r445_conform_mbpp_ext","g_r461_lcb3_three_arm"):
    rows=[json.loads(l) for l in open(f"runs/{run}/rows.jsonl",encoding="utf-8") if l.strip()]
    by=collections.defaultdict(dict)
    for r in rows: by[r["task_id"]][r["arm"]]=r
    b=c=n=0
    for t,d in by.items():
        if "CONFORM" in d and "OFF5" in d:
            n+=1
            x,y=bool(d["CONFORM"].get("meets_demand")),bool(d["OFF5"].get("meets_demand"))
            if x and not y: b+=1
            if y and not x: c+=1
    print(run,"n",n,"b",b,"c",c,"n_d",b+c,"rate_pp",round(100*(b+c)/n,2))
    if run=="g_r461_lcb3_three_arm":
        demo=sum(1 for t,d in by.items() if any(bool(v.get("meets_demand")) for v in d.values()))
        print("  能力下界 任一臂通過過一次:",demo,"/",len(by),"未示範",len(by)-demo)
PY
```

實測：

```
g_r444_conform_mbpp n 179 b 9 c 4 n_d 13 rate_pp 7.26
g_r445_conform_mbpp_ext n 192 b 18 c 9 n_d 27 rate_pp 14.06
g_r461_lcb3_three_arm n 189 b 12 c 9 n_d 21 rate_pp 11.11
  能力下界 任一臂通過過一次: 166 / 189 未示範 23
```

r444＋r445 合起來是 371 題、n_d=40 ⇒ **10.78%**，與 R449B §三 P-3 引用的數字一致
（本檔重算過，不是抄的）；r461 的 b/c=12/9 與 `DECISION_20260906_R461_FABLE_AUDIT.md` §一
逐字一致。

**(8) analyzer 與 schema 尺自檢**（收官前會再對真 rows 跑一次 `--run`）：

```bash
.venv/bin/python ops/gain/analyze_eq5.py --selftest
.venv/bin/python ops/gain/eq5_schema_precheck.py --selftest
```

---

## 十、中止準則（跑之中就適用，不是收官才想）

- 任一時刻 `infra_void` > 20% ⇒ 中止，寫進 GAIN_STATE，**不補跑**。
- 任一次中途 summary 的 `calls_per_task` ≠ 5.00 ⇒ **實作缺陷**，中止，不當資料用。
- 端點連續失敗導致 rows 停止成長 > 60 分鐘 ⇒ 中止並記錄（**不改條件重跑**）。
- 牆鐘超過 **20 小時**（§二 的錨是 10.7 小時）⇒ 不自動中止，但要記錄並查端點，
  因為那代表這一次的每通呼叫比 r461 的 OFF5 慢了將近一倍，可能有別的 run 在搶端點。
- 若發現本 run 與任何其他 `gain_run.py` 同時在跑（違反 SPEC_GAIN §7 一端點一 run）
  ⇒ 立刻中止本 run 並作廢它已經產出的資料。發射器已經擋在前面
  （等待迴圈＋發射前重做單 run 檢查），這是第二道。

**跑之中不准算 Δ／b／c／CI／四格判定。** 中途只准看：rows 行數、`infra_void`、
`calls_per_task`、行程是否活著。任何中途看過的數字，收官時要逐條揭露。

---

## 十一、新增可調參數

**0**。

- `--bank lcb3` 與 `--n 189` 不是新旋鈕——逐字沿用 `runs/g_r461_lcb3_three_arm`
  在 `DECISION_20260904_R461_LCB3_REPLICATION_PREREG.md` §四 註冊過的那一組，
  題庫檔（sha256 前 16 碼 `bd3dffebb1b16bc7`）、189 題全部不動。
- seed 換一顆不是旋鈕，它是「換一批候選抽樣」的定義（在 LCB loader 上它只換候選、不換題目，
  §九-1 驗過）；新 seed 的字串寫死在本檔與發射器，兩邊由
  `tests/test_r449c_launcher_prereg.py` 釘住，且發射器會掃過所有
  `runs/*/summary.json` 確認它沒被用過。
- `k=5` 與 `arm_eq5` 一行碼沒動；閾值、逾時、模型池全部沿用。
- 區間、MDE、N₈₀、±5pp 實務門檻全部沿用既有模組（`paired_ci`／`power_paired`），
  一個常數都沒動。

---

## 十二、口徑（展覽是唯一交付物，措辭是紅線）

- 本 run 的結果若上展場，措辭是**可究責性／讓依賴有根據**，
  這三個詞不准出現：「信任」「防止」「保證」。
- 本 run 是**真模型、真資料**（189 題 LeetCode medium／hard 題、gemma-4-12b-it-qat），
  不是機制模擬；展場的秒級互動仍然跑 `vacant/entrycost.py` 的機制模擬，
  兩者在畫面上必須分開標示，不准混講。
- 展場若要用 §六 `REPLICATED_ON_LCB3` 那句話，必須連 R440P §五 的第一條邊界一起講：
  **整件事建立在「需求可以被編譯成可執行的驗收測資」**；驗收測資不是真需求子集的
  場合，拒交會殺掉好答案。在 LCB 上還要多講 §八-8：這裡的可見測資只有題目附的範例。
- **不准對觀眾說「連難題都成立」。** 本題庫不是難題（§一）。
- **UNRESOLVED 不准上展場當成任何一種結論。** 「沒量出來」對外行觀眾就是「沒有」，
  在畫面上放一個量不出來的東西只會製造誤解。

---

## 十三、本檔自己的推翻條件

1. 若收官時發現 `analyze_eq5.py` 對 r449c 與對 r446／r448／r449b 的**同名欄位語意不同**
   （例如 `deliv` 口徑被改過），本檔 §三 的所有錨值失效，跨 run 不可比，
   先修可比性再談任何狀態。
2. 若 G-4 的 diff 出現 (b) 類改動（碰到 `arm_eq5`／`meets_demand`／`behavior_signature`／
   `extract_code`／`LiveCodeBenchLoader`／請求政策），r449c 就**不是**在跑
   r446/r448/r449b 跑的那條臂——§六 的四個狀態全部不適用，收官只能報 r449c 自己的數字
   並寫明處置變了。**本檔寫作當下 HEAD（`b3c8514`）與 r449b 的 runner sha
   （`63f20d5`）之間隔著 round450–452b 對 `gain_run.py`／`codebench.py` 的改動，
   這一條不是假設性的**（§四 G-4）。
3. 若 §五 的檢定力表被發現算錯（例如 `diff_ci` 的邊界語意與本檔假設不同），
   §六 邊界 (b) 的「方向沒翻 ≠ 效果消失」仍然成立（它只依賴定性事實），
   但表裡的百分比要重算，且「n=189 檢定力不足」這個結論要重新確認而不是沿用。
4. 若發射時 `--bank lcb3` 載到的不是 §九-1 那 189 個 `task_id`（例如題庫檔被改，
   sha256 前 16 碼不再是 `bd3dffebb1b16bc7`），本 run 與 r461 的同題關係破裂，
   §七 整節作廢，收官前必須先重算。
5. 若後續有人在 v3 上找到 KNOWN_BAD 型的量具問題題（§八-3），本檔 §六-(g) 的
   「含／排除兩個版本」處置照樣適用，但 §八-3 那句「沒有登記在案」要改寫成實際情況，
   而且要回頭檢查那些題有沒有落在本 run 的 discordant pair 裡。
6. 若 R461 稽核 §四 的第二條推翻條件被觸發（lcb3 建庫紀錄顯示它混入了與 MBPP+ 重疊
   或 2023 前的題目），§八-4 的污染邊界要重寫，而「第三個題庫」這個定位本身要重新確認。
