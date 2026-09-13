# R449B：EQ5 第一次跑在**難題**上——`runs/g_r449_eq5_lcb2`

**日期**：2026-09-06　**輪次**：round449b（Opus 撰寫、待 Fable 稽核）
**狀態**：預註冊。**本檔在 run 發射之前、在任何 r449b 資料存在之前定稿。**
**授權**：本檔即 R440G 閘門所需的那一份——它授權 `runs/g_r449_eq5_lcb2`
這一個 run 名字，與 seed `g-r449-eq5-lcb2`，其他都不授權。
**編號**：`R449` 這個號碼已經被 `DECISION_20260905_R449_PEEREXEC_ARCHITECTURE_AUDIT.md`
（peerexec 架構稽核）用掉了，本檔用 **R449B**，兩件事沒有關係。

---

## 一、要解的問題：**題目變難的時候，篩選還打不打得贏投票？**

目前唯一站得住的正結果是 EQ5 的規則對比：同一組 5 份候選、同樣 5 通呼叫，
「跑客戶自己的驗收測資、交第一份通過的、全不通過就不交」比「五份投票取多數」
多交付 3–4 個百分點。它已經在**兩顆 seed** 上成立
（`DECISION_20260906_R448_FABLE_AUDIT_REPLICATED.md`）：

| | r446（seed `g-r212-route-20260828`） | r448（seed `g-r448-eq5-seed2`） |
|---|---|---|
| 閘門 deliv | 280/371＝75.47% | 286/371＝77.09% |
| 多數決 deliv | 265/371＝71.43% | 273/371＝73.58% |
| b / c / n_d | 24 / 9 / 33 | 21 / 8 / 29 |
| Δ | **+4.04pp [+1.08, +7.01]** p=0.0135 | **+3.50pp [+0.81, +6.47]** p=0.0241 |

**但兩次都是 MBPP+。** R448 稽核 §四 自己寫死了那句「仍不能講」的第三條：
**不准外推到別的題庫**；§六 的推翻條件第二條逐字是

> 若在 LCB 上跑 EQ5（同候選設計）而 CI 跨 0 ⇒ §四 的話要加「僅在 MBPP+ 量級的題目上」。

**這條到今天沒有任何資料可以判**——EQ5 從沒在 LCB 上跑過。本 run 就是去把它變成可判的。

### 為什麼「難題」是這一格而不是別格

R440Z 收官（`DECISION_20260905_R440Z_WRAPUP_LCB2.md` §三）在同一個題庫、同一個模型上
量到一件**與 MBPP+ 相反**的事：

- MBPP+ 上 OFF5 對 OFF 是 +0.81pp（沒用）；
- **LCB v2 上 OFF5 對 OFF 是 +12.5pp（p=0.0081，有用）**。

也就是說：**多數決這個對手在難題上是變強的**，不是變弱。所以「篩選贏投票」這件事
在難題上並不是自動成立——它在 MBPP+ 上贏的那 3.5–4pp，有可能被一個真的會用的
self-consistency 吃掉。這正是值得花一次機時去問的問題。

反過來，R440Z 也量到 CONFORM 對 OFF5 在 LCB v2 上是 **+6.67pp、p=0.15、[−0.83, +15.0]
——unresolved**。那是**獨立抽樣**的估計量（兩臂各自抽自己的候選，生成噪音混在差值裡）。
EQ5 的同候選設計把生成噪音整個消掉，是在同一批題目上問同一個方向、但**噪音小得多**的
問題。所以本 run 也順帶回答「r447 那個 unresolved 是效果不存在，還是設計太吵」。

### 它硬化什麼、不硬化什麼（估計量宣稱，收官不准放大）

**硬化的**：在 120 題 LeetCode 中高難度題上，「閘門規則 vs 多數決規則」在**同一組候選**上
的方向與幅度。

**不硬化的（逐條寫死，收官不准借用）**：

1. **不是「Vacant 這個系統贏了 OFF5」。** EQ5 答的是「給定同一組候選，哪一條選擇規則
   交付得多」。「兩個各自獨立抽樣的系統誰贏」是 r445／r447 的估計量。
   R446 §二 的禁令逐條沿用。
2. **不是出貨形態的成本結論。** EQ5 的閘門臂花 5.00 通呼叫（不早停）；出貨形態會早停
   （LCB v2 上 r447 量到 1.71 通）。成本面仍以 r447／r445 為準。
3. **不是 r447 的重複。** 本 run 與 `runs/g_r447_conform_lcb2` 跑的是**同一批 120 題**
   （§九 有離線驗證），但**設計不同**：r447 是三臂獨立抽樣，本 run 是同候選規則對比。
   同題不同設計 ⇒ 兩者**不是獨立樣本**，也**不是**互為複製。見 §七。
4. **不是「≥5pp 的實務增益」。** 兩次 MBPP+ 的上界（+7.0／+6.5）跨過 5pp 線、
   下界（+0.8／+1.1）遠低於它。n=120 的區間只會更寬，本 run 不預期改變這一點。
5. **不是「LCB 代表所有難題」。** LCB v2 是 LeetCode 競賽題，量具只覆蓋 12/120（§八-1）。

---

## 二、run 名字、指令與「唯一的差別」

run 目錄：**`runs/g_r449_eq5_lcb2`**（本檔只授權這一個名字）。
seed：**`g-r449-eq5-lcb2`**（§九-2 驗過：這顆 seed 沒有出現在 `runs/*/summary.json` 的任何一個裡）。

```
--out runs/g_r449_eq5_lcb2 --n 120 --offset 0 --arms EQ5 --bank lcb2
--seed g-r449-eq5-lcb2 --models gemma-4-12b-it-qat --probe-sample 0
--request-timeout-s 600 --review-timeout-s 380
--decision DECISION_20260906_R449B_EQ5_LCB2_PREREG.md
```

與前面兩條 EQ5（r446／r448）的逐項對照——**只有題庫、題數與 seed 三格不同**：

| 項 | r446 / r448 | **r449b** |
|---|---|---|
| `--arms` | EQ5 | EQ5（逐字相同的臂，一行碼沒動） |
| **`--bank`** | **evalplus** | **lcb2** |
| **`--n` / `--offset`** | **371 / 0** | **120 / 0** |
| **`--seed`** | `g-r212-route-20260828` / `g-r448-eq5-seed2` | **`g-r449-eq5-lcb2`** |
| `--models` | gemma-4-12b-it-qat | 相同 |
| `--probe-sample` | 0（全題量具） | 0 |
| request policy | timeout 600 / retries 4 / backoff 2.0 / review 380×2 | 逐項相同 |
| agent pool | 6 個 agent／1 個模型家族（`POOL` 未動） | 相同 |

與 r447（同題庫）的對照——**只有臂不同**：

| 項 | r447 | **r449b** |
|---|---|---|
| `--bank` / `--n` | lcb2 / 120 | lcb2 / 120（**同一批 120 題**，§九-1 驗過） |
| `--arms` | OFF,CONFORM,OFF5（三臂獨立抽樣） | **EQ5（同候選、兩條規則）** |
| `--seed` | `g-r440-lcb2` | `g-r449-eq5-lcb2` |

發射器：`ops/gain/launch_eq5_lcb2.sh`（等 `PRIOR_RUN` 退出，SPEC_GAIN §7 一端點一 run；
預設 `PRIOR_RUN=runs/g_r448_eq5_mbpp_seed2`，該 run 的 `summary.json` 已經
`run_terminal=true`，所以預設情況下發射器走的是「已 terminal ⇒ 直接往下」那條路）。
**發射由稽核 session 之外的人執行；本檔只出檔案與指令。**

預估成本：120 題 × 5 通＝600 次生成呼叫。LCB 題目比 MBPP+ 長，r447 三臂 120 題
（約 925 通）跑了一個晚上；本 run 約 600 通 ⇒ **粗估 4–7 小時**，$0（8765 中轉）。

---

## 三、事前註冊的預測（P-1..P-9）——先寫死，收官逐條判 HIT／MISS

仲裁量一律取 `python3 ops/gain/analyze_eq5.py --run runs/g_r449_eq5_lcb2 --json ...`
輸出 JSON 的欄位，**欄位名逐字寫在下表第三欄**（記憶鐵律：判準要指名它讀哪個 key，
不准靠「工具印了什麼字串」）。

| # | 預測 | 仲裁欄位 | 窗 | 錨在哪 |
|---|---|---|---|---|
| **P-1** | Δ＝閘門 − 多數決 的**點估計** > 0 | `paired.delta_pp` | **> 0** | MBPP+ EQ5 兩次 +4.04／+3.50；同題庫獨立抽樣 r447 CONFORM vs OFF5 +6.67pp（同號） |
| **P-2** | **95% CI 下界 > 0（＝本 run 的主判準）** | `paired.ci95_lo_pp` | **> 0** | r446 [+1.08,+7.01]、r448 [+0.81,+6.47] 兩次下界都過 0。**但 n 從 371 掉到 120 ⇒ 見 §五 的檢定力，這一格事前只有 18–42% 的機會會中** |
| **P-3** | discordant pair 數 | `paired.n_discordant` | **≥ 15** | 同候選設計的 discordant 率 ÷ 獨立抽樣的 discordant 率，在 MBPP+ 上是 8.36%/10.78%＝**0.78**；把這個比例套到 r447 在**本題庫**實測的 20.00%（b=16 c=8，24/120）⇒ 預期 ≈15.5% ⇒ E[n_d]≈18.6，P(n_d≥15)≈85% |
| **P-4** | 預算恰好 5 | `calls_per_task` ＝ **5.00** 且 `budget_all_exactly_5` ＝ **true** | 結構性 | `arm_eq5` 不早停；r446 1855/371、r448 1855/371 都是 5.00，742 列全部 `calls_used=5` |
| **P-5** | infra_void 率 | `void_rate_pp` | **≤ 5%** | r447（同題庫同模型）0；r444/r445/r446/r448 皆 0 |
| **P-6** | 閘門 deliv%（主分母 measured） | `gate.deliv_pp_denom_measured` | **[58, 82]%** | r447 CONFORM 在**同一批 120 題**上 84/120＝**70.0%**；EQ5 的閘門與 CONFORM 選擇語意逐字元相同（差別只在早停，早停不改變選到誰）。窗＝70.0 ± 12（n=120 的 95% CI 半寬約 8.4pp，再留換 seed 的生成噪音） |
| **P-7** | 多數決 deliv%（主分母 measured） | `vote.deliv_pp_denom_measured` | **[51, 75]%** | r447 OFF5 在同一批 120 題上 76/120＝**63.33%**；窗＝63.3 ± 12，同上理由 |
| **P-8** | 閘門拒交率＝100 − coverage | `gate.coverage_pp` | 拒交 **[2, 18]%** | **這一格的兩個錨互相矛盾，窗必須同時蓋住**：直覺說「題目變難 ⇒ 五份全不過可見驗收的機會變多 ⇒ 拒交率比 MBPP+ 高」（MBPP+ EQ5 是 7.01%／6.20%），**但 r447 在這個題庫上實測只有 5.83%**（CONFORM 的拒交條件與 EQ5 逐字相同：五份都沒通過 `visible_check`）。理由是 LCB 的 `visible_check` 只有題目附的範例測資，比 MBPP+ 的 base suite 鬆。**事前不挑一邊**：窗蓋住 [2,18]，收官照實記落在哪 |
| **P-9** | 兩條規則選到同一份（有效值） | `same_choice_effective_rate_pp` | **[5, 35]%** | MBPP+ 兩次 20.49%／20.22%。難題上候選更發散（多數決分桶更碎）＋拒交更多（拒交不算「選到同一份」，AMEND-1）⇒ **預期比 MBPP+ 低**，窗往下開 |

**無條件一併印、一併判、不准挑一個的次要量**（看過數字之後不准選分母——r444 那次
兩個分母給出相反判決）：

- `gate.deliv_pp_denom_measured` **與** `gate.deliv_pp_denom_accepted`（兩個分母都列）
- `same_choice_rate_pp`（raw）與 `false_same_choice_n`
- `paired.b_gate_only` / `paired.c_vote_only` / `paired.p_mcnemar_exact`
- `power.mde_at_n_pp` / `power.n80_if_true_effect_is_observed` / `power.n_needed_halfwidth_5pp`
- `verdict_four_cell`

### ⚠ `analyze_eq5.py` 自己印的 `prereg` 區塊**不是本 run 的仲裁者**

那支工具的 `PREREG` 常數逐字編碼的是 **R446** 的窗（`P-R446-*`），而 R446 的窗是為
**MBPP+** 訂的。本 run 換了題庫，**下面三格事前就知道它會印錯**：

| 工具會印 | 它的窗 | 本檔的窗 | 為什麼不同 |
|---|---|---|---|
| `P-R446-3` 閘門 deliv% | [68, 84] | **[58, 82]**（P-6） | 難題上通過率本來就低；r447 實測 70.0% 只比 68 高 2pp，正常波動就會掉出去 |
| `P-R446-4` 多數決 deliv% | [64, 80] | **[51, 75]**（P-7） | r447 OFF5 實測 63.33%，**已經在 [64,80] 之外** |
| `P-R446-5` same_choice_effective | [40, 95] | **[5, 35]**（P-9） | MBPP+ 實測就只有 20% 左右，那個窗在 r446 自己身上就 MISS 過 |

同理，工具的 `overturn_conditions_triggered` 會因為「閘門 deliv% 掉出 [68,84]」而印出
**R446 §六-3**——那條是 MBPP+ 的窗，**本 run 不適用**；本 run 的對應條在 §六-3。

⇒ 收官時：`analyze_eq5.py` 的輸出用來取**數字**，HIT／MISS 由**本檔上表**判。
**不准為了讓工具印出正確字串而去改 `analyze_eq5.py` 的 `PREREG`**——那支常數是
r446 的事前註冊，改它等於改別人的事前註冊（該檔自己寫著「改這裡等於改事前註冊 ⇒ 不准」）。

---

## 四、效力前提 G-1..G-5（不是預測，是「這份資料算不算數」的擋門）

任一條紅 ⇒ **先修／先揭露，不判 replication**（狀態＝`INVALID`，見 §六）。

| # | 前提 | 怎麼驗 | 事前已知的狀況 |
|---|---|---|---|
| **G-1** | analyzer 讀得懂 runner 寫的 rows | `python3 ops/gain/eq5_schema_precheck.py --run runs/g_r449_eq5_lcb2` ⇒ `SCHEMA_COMPATIBLE` | r446／r448 上各實測過一次 |
| **G-2** | 帳對得上、且是收官資料 | `broken_reasons` ＝ `[]`；`summary.arms.EQ5.terminal` ＝ true；`measured + infra_void == processed` | r448：371+0=371、terminal true |
| **G-3** | 落盤欄位與離線重算一致 | 每一列都有 `same_choice_effective`，且與 `accepted ∧ (gate_code_sha256==vote_code_sha256)` 逐筆相同（`analyze_eq5` 的 `landed`／`bad_eff` 區塊） | r448 是這道擋門第一次真的被評估並通過；本 run 沿用同一條 |
| **G-4** | 處置定義沒有漂掉（R680 Q2） | `git diff <r448 的 runner_git.sha> <r449b 的 runner_git.sha> -- ops/gain/gain_run.py ops/gain/brain_cline.py vacant/codebench.py`，逐項分類 (a) 只影響分析／文件 (b) 影響臂行為 | 本檔寫作時 HEAD `97d20c7`；r448 跑的是 `21f1f75`（dirty=true）。**本檔寫作當下工作目錄裡有另一個 session 正在改 `ops/gain/gain_run.py`（peerexec／suitegauge 那條線，把 `probe_instrument` 的兩個方向改走 `vacant.suitegauge.gauge_suite`）**——那是**量具**路徑不是**臂**路徑，事前分類為 (a)；但 **發射時間點的 HEAD 一定不同，收官必須重跑這條 diff 並重新分類**，不准引用本格 |
| **G-5** | 不被長得像的旗標騙 | `summary.equal_budget_comparison_valid` **預期是 false** | 它的定義只看 `ON` 與 `OFF5` 兩臂（`gain_run.py:1394-1399`），EQ5-only 的 run 結構上永遠 false。EQ5 的等預算證據是 P-4，不是這個旗標 |

**G-4 的一條誠實邊界**：r446／r447／r448 的 `runner_git.dirty` 都是 **true**——它們跑的時候
工作目錄有未提交的改動，所以那幾版的位元組**無法只憑 sha 完全還原**。這是既有的設計缺口
（R680 Q2 的 BROKEN 情形的弱化版），本檔照實記，不用 mtime／git log 去猜然後當成量測。
本 run 大機率也會是 dirty＝true（同一個工作目錄有並行 session），**發射時把 dirty 記下來，
不要當成沒發生**。

---

## 五、事前檢定力：**n=120 很可能答不出來，這件事寫在資料之前**

用 repo 既有的 `ops/gain/replay/paired_ci.diff_ci`（round656 已雙向驗證）與二項列舉投影。
q＝discordant 率、p_b＝b/(b+c)。演算法與可重跑指令在 §九-3。

| 情境 | P(`ci95_lo_pp > 0`)＝P-2 HIT | P(c≥b) | P(n_d<15) | E[n_d] |
|---|---|---|---|---|
| **A｜MBPP+ 的效果原樣搬過來**（q=8%, p_b=.725） | **18.1%** | 10.3% | 94.4% | 9.6 |
| **B｜難題上 discordant 依比例放大**（q=15.5%, p_b=.725） | **41.5%** | 3.0% | 15.0% | 18.6 |
| C｜q=15.5%, p_b=.667（r447 獨立抽樣的 16/24） | 22.9% | 8.9% | 15.0% | 18.6 |
| D｜q=20%（＝r447 實測的 discordant 率）, p_b=.725 | 52.8% | 1.5% | 1.1% | 24.0 |
| E｜q=20%, p_b=.667 | 29.6% | 5.9% | 1.1% | 24.0 |
| F｜效果在難題上變弱（q=15.5%, p_b=.60） | 9.2% | 22.6% | 15.0% | 18.6 |
| G｜**真效果為 0**（q=8%） | 1.1% | 56.5% | 94.4% | 9.6 |
| H｜**真效果為 0**（q=15.5%） | 1.5% | 54.6% | 15.0% | 18.6 |

**事前結論，寫在資料之前，收官不准改口**：

> **n=120 對這個效果量是檢定力不足的（UNDERPOWERED）。**
> 如果難題上的真效果就是 MBPP+ 量到的 +3.5–4pp、discordant 率也照搬 8%，
> 本 run 有 **18%** 的機會讓 95% 區間下界過 0——也就是說，**即使效果完全成立，
> 最可能的結果（≈82%）是 UNRESOLVED。** 就算難題把 discordant 率放大到 15.5–20%
> （這是本 run 比較可能的情境，見 P-3 的錨），機會也只到 **42–53%**。
> 相對地，MDE 在 n=120、q=15.5% 下是 **9.17pp**——本 run 只辨得出 9pp 級的差異，
> 而我們預期的效果是 3.5–7pp。

檢定力不足的直接後果（一併事前寫死）：

- **UNRESOLVED 是本 run 最可能的落點，它不是失敗，也不是「效果不存在」。**
  收官若落在那一格，**不准**寫成「LCB 上打平」「難題上沒有優勢」。
- 要把「效果在難題上不成立」講出口，需要的是 **NOT_REPLICATED_ON_HARD**
  （方向翻轉，在情境 A–E 下事前機率只有 1.5–10.3%），不是 UNRESOLVED。
- N₈₀（真效果＝觀測值時，80% 檢定力需要的 discordant pair 數）＝**37 對**（p_b=.725）
  或 **68 對**（p_b=.667）⇒ 換算成題數：q=8% 時要 **463 題**、q=15.5% 時要 **239 題**、
  q=20%＋p_b=.667 時要 **340 題**。**LCB v2 只有 120 題** ⇒ 想在這個題庫上把 P-2
  推到 80%，光靠這一顆 bank 做不到（要嘛併 lcb3 的 189 題新題，要嘛接受 UNRESOLVED）。
  這句話事前就成立，**不是收官時為了解釋結果才算的**。

**為什麼明知檢定力不足還要跑**：因為 R448 §六 的推翻條件問的是**方向**——
「若在 LCB 上跑 EQ5 而 CI 跨 0 ⇒ §四 的話要加『僅在 MBPP+ 量級的題目上』」。
CI 跨 0 這件事本 run 有 ~60–80% 會發生，那個限定語幾乎一定要加上；
但**方向翻轉**（P(c≥b) 只有 1.5–10.3%）才是真正的新資訊，而那一格只有跑了才知道。
**這一段就是「不要為了有成效去挑對自己有利的設定」的具體兌現**：
明知最可能拿到的是 UNRESOLVED，還是照跑，並且事前就把 UNRESOLVED 的措辭寫死。

---

## 六、決策規則（**在任何 r449b 資料之前寫死**）：三個狀態

前提：G-1..G-4 全綠。任一紅 ⇒ 狀態 `INVALID`，先修或先揭露，**不准**先判。

| 狀態 | 觸發條件（照順序判，先命中者為準） | 收官准講的話 |
|---|---|---|
| `INVALID` | G-1..G-4 任一紅；或 **P-4 MISS**（有任一列 `calls_used ≠ 5`） | 「這個 run 不當資料用」——P-4 MISS 是實作缺陷不是結果 |
| **`NOT_REPLICATED_ON_HARD`** | `paired.c_vote_only ≥ paired.b_gate_only`　**或**　`paired.delta_pp ≤ 0` | R448 §六 第二條推翻條件**兌現且更強**：不只要加「僅在 MBPP+ 量級的題目上」，還要寫「在 LCB v2 難題上方向翻轉／打平」。要同時報三個 run（r446／r448／r449b）的 b/c 對照。展場與任何對外文字在有進一步資料之前**不得**把 EQ5 的結論講成一般性質 |
| **`REPLICATED_ON_HARD`** | P-1 HIT **且** P-2 HIT（等價於 `verdict_four_cell == GATE_RULE_WINS`） | 「三個 run（兩批 MBPP+、一批 LCB v2 難題）、同一組候選、同樣 5 通呼叫，閘門規則的交付都高於多數決，三次的 95% 區間下界都在 0 以上。」**仍不准**講 ≥5pp、不准講「系統贏」、不准外推到 LCB／MBPP+ 以外的題庫 |
| **`UNRESOLVED`** | 其餘（典型：`delta_pp > 0` 但 `ci95_lo_pp ≤ 0`，即 `RULED_OUT` 或 `NON_INFERIOR_BUT_UNRESOLVED`） | 「**沒量出來**，不是沒有差異」——必須**同時**報 `power.mde_at_n_pp`、`power.n80_if_true_effect_is_observed` 與 §五 的事前檢定力表（round678 §六 的兩句話規則）。**並且**按 R448 §六 第二條，把 R448 §四 那句話改成「僅在 MBPP+ 量級的題目上」 |

### 邊界情況（事前寫死，避免收官當場挑）

- **(a) P-2 HIT 但 P-3 MISS（n_d < 15）**：判 `REPLICATED_ON_HARD`，但**必須**在同一句話裡
  標注「配對數低於事前窗口」並報 N₈₀。不准只寫狀態名三個字。
- **(b) P-1 HIT、P-2 MISS、且 `paired.b_gate_only > paired.c_vote_only`**：這是
  `UNRESOLVED`，**不是** `NOT_REPLICATED_ON_HARD`。方向沒翻，只是這一次沒把 0 排除掉，
  而 §五 已經事前算出那是最可能發生的事（≈58–82%）。
- **(c) P-6／P-7 MISS**：不改變狀態判定，但要先查是不是**處置漂了**——EQ5 的閘門與
  CONFORM 只差早停，掉出 [58,82] 代表兩者在這個題庫上行為不一致 ⇒ 先查實作再解讀。
  （工具會依 R446 的 [68,84] 印出 §六-3；**那條不是本 run 的判準**，見 §三 末。）
- **(d) P-8 MISS**：照實記，並指出落在「MBPP+ 側（≈6–7%）」還是「r447 側（≈5.8%）」
  還是兩者之外；拒交率變化會同時改變 coverage 與兩個分母，要把兩個分母都列。
- **(e) P-9 MISS**：不改變狀態判定，但要說明對比結構變了（>35% ⇒ 兩條規則更常選到同一份；
  <5% ⇒ 更少），並列出三個 run 的 raw／effective 對照。
  **若 `same_choice_effective_rate_pp` > 95%**，照 R446 §六-1 的語意處理：
  這個比較沒有對比，結論只准寫「測不出來」，**不准**寫成「等預算下打平」。
- **(f) P-5 MISS 但 void ≤ 20%**：資料仍可判，但主結論必須附 void 敏感度——把 void 那幾題
  分別當成「全歸閘門贏」與「全歸多數決贏」兩個極端各算一次，兩端都報。
  void > 20% ⇒ §十 的中止準則已經觸發，資料不進結論。
- **(g) 只有 `lcb_3763`／`lcb_3613` 兩題出現異常**（例如兩條規則都判失敗）：
  先查量具不查模型（§八-3），並且**不准**在收官時把這兩題挑掉——挑題會變成
  R440B 那個死過一次的逆向選擇器。要報的是「含這兩題」與「排除這兩題」兩個版本，
  且主結論用**含**的那個。

### 事前寫死的禁令（違反＝本輪失敗）

1. **看到數字之後改窗、改仲裁欄位、改狀態定義** ⇒ 一律不准。要改只能由後續輪次／人類
   在**下一個** run 之前改，且舊窗要留著讓人收回仲裁權。
2. **不准**把 r446 ∪ r448 ∪ r449b 併成 `n=862` 當獨立樣本去宣稱顯著。r446/r448 之間
   是同一批 371 題（完全重疊），r449b 與它們題目零交集但**題庫不同**（難度分佈不同）
   ⇒ 併起來的東西沒有一個母體對得上它。
3. **不准**用任何併庫數字取代 r449b 自己的 P-1／P-2 判定。**§六 的仲裁者只有 r449b 自己。**
4. **不准**在 `UNRESOLVED` 的情況下寫「兩條規則等價」「打平」「難題上沒有優勢」。
5. **不准**把本 run 與 `runs/g_r447_conform_lcb2` 的數字當成「複製」或「兩個獨立樣本」——
   同一批 120 題、不同設計（§七）。

---

## 七、與 r447 的關係：同題、不同設計，**不是**獨立樣本、**不是**複製

`CRITERION_20260903_R680_POOL_PRECONDITIONS.md` 的 **Q1** 要求可併的兩個 run
`task_id` 集合交集＝∅。本 run 與 r447 的交集是 **120（完全重疊，§九-1 驗過）**
⇒ **Q1 MISS**。而且兩者連估計量都不同：

| | r447 | r449b |
|---|---|---|
| 設計 | 三臂各自抽自己的候選 | 同一組 5 份候選餵兩條規則 |
| 差值裡含不含生成噪音 | **含** | **不含**（同候選消掉） |
| 對比的東西 | 兩個系統 | 兩條選擇規則 |

**准做的（描述性，且必須標成描述性）**：

- **逐題跨 run 四格**：同一個 `task_id` 在 r447（CONFORM vs OFF5）與 r449b（gate vs vote）
  各自的贏家。這是完全重疊帶來的唯一好處，也是它的正確用法。
- 把 r447 的 +6.67pp [−0.83,+15.0]（獨立抽樣、含生成噪音）與 r449b 的區間並列，
  用來說明**同候選設計把噪音消掉之後區間有沒有變窄**——這是方法學陳述，不是效果宣稱。

**不准做的**：把兩者的 n 加起來、把 r447 當成 r449b 的「先前證據」去做任何形式的合併推論、
或者說「LCB 上量了兩次都同號」（那是同一批題目量了兩次）。

另外，r447／r449b 與 E3（LCB v1，91 題）共用 91 題 ⇒ 對 E3 也不是獨立樣本（R440Z §五-5）。

---

## 八、誠實邊界（逐條沿用 `DECISION_20260904_R440Z_LCB2_PREREG.md` §五 與 R440Z 收官 §五）

這五條是**題庫本身**的性質，換一條臂不會讓它們消失，收官必須原樣帶著：

1. **量具只覆蓋 12/120。** LCB 沒有官方參考解；`ops/gain/data/lcb_probe_solutions.json`
   是 round441 手寫並用真的 `hidden_check` 逐題驗過的 12 題。
   **其餘 108 題的隱藏測資沒有參考解證明「正解會通過」。**
   ⇒ 「本 run 的量具兩個方向都對」這句話的實際覆蓋率是 **10%**，不是 100%。
   （`--probe-sample 0` 的意思是「不抽樣、有解的全驗」，不是「120 題全驗」——
   `probe_instrument` 先篩有參考解的題目再取前 `sample` 個，所以印出來的是 12/12。）
2. **`lcb_3026` 的 contest_date 是 2023-08-26**，比 v1 的視窗早一年，
   **污染定界對它無效**（round440y-b）。它在本 run 的 120 題內（§九-1 驗過）。
3. **`lcb_3763`（separateSquares）浮點假陽性仍在池內**；`lcb_3613` 也在
   `check_bank_precision` 的 `KNOWN_BAD`。兩題都在本 run 的 120 題內。
   **若這兩題兩條規則全滅，先查量具不查模型**（處置見 §六 邊界 (g)）。
4. **n=120 只辨得出 ~9–10pp 級的不對稱**（§五 的 MDE）。
   「不顯著」不等於「等效」——這是本 run 事前就知道的主要限制。
5. **與 r447 共用同一批 120 題、與 E3 共用 91 題 ⇒ 都不是獨立樣本**（§七）。
   跟它們的數字比較是「同一批題目換一個設計」，不是複製。

第六條，本檔自己加的：

6. **LCB 的 `visible_check` 是題目附的範例測資，比 MBPP+ 的 base suite 鬆。**
   閘門規則的全部力量來自 `visible_check` 的鑑別力 ⇒ 若本 run 的閘門優勢比 MBPP+ 小，
   「LCB 的可見測資比較鬆」與「難題上篩選比較沒用」兩個解釋在本 run 的資料裡
   **分不開**。收官不准只寫其中一個。（要分開需要另一個設計：同題庫、加強 visible 套件，
   那不在本 run 範圍。）

---

## 九、自我驗證（發射前做完，指令逐條可重跑；全部零 API、零 ssh）

**(1) 題目集合：本 run 的 seed 與 r447 取到的是同一批 120 題**——這是 §一-3 與 §七 的證據：

```bash
cd /Users/cosmopig/Documents/GitHub/Vacant && .venv/bin/python - <<'PY'
import sys, json; sys.path.insert(0,'.')
from ops.gain.gain_run import load_tasks
a=[t["task_id"] for t in load_tasks("lcb2","g-r440-lcb2",120,offset=0)]
b=[t["task_id"] for t in load_tasks("lcb2","g-r449-eq5-lcb2",120,offset=0)]
r447=set(json.loads(l)["task_id"] for l in open("runs/g_r447_conform_lcb2/rows.jsonl",encoding="utf-8") if l.strip())
print("len",len(a),len(b)); print("set_equal",set(a)==set(b)); print("order_identical",a==b)
print("r447_rows_set_equal", r447==set(a))
print("known_gauge_issues_in_pool", {x: x in set(a) for x in ("lcb_3026","lcb_3763","lcb_3613")})
PY
```

實測輸出：`len 120 120` / `set_equal True` / `order_identical False` /
`r447_rows_set_equal True` / `{'lcb_3026': True, 'lcb_3763': True, 'lcb_3613': True}`。
（`ops/gain/data/lcb_bank_v2.jsonl` sha256 前 16 碼 `b98f027213e2469a`，與 R440Z §一 一致。）

**(2) seed 新鮮度：`g-r449-eq5-lcb2` 沒有出現在任何一個 `runs/*/summary.json` 裡**：

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
print("g-r449-eq5-lcb2 已被用過:", "g-r449-eq5-lcb2" in seeds)
PY
```

實測：42 個 `summary.json`，出現過的 seed 是
`42`／`g-off-failure-rate-20260901`／`g-r212-route-20260828`(21)／`g-r440-lcb2`／
`g-r442-lcb`／`g-r448-eq5-seed2`／`g-r454-scale2-20260901`／`g-r461-lcb3`(2)／
`g-smoke-20260820`(13)；**`g-r449-eq5-lcb2` 不在其中**。
發射器 `ops/gain/launch_eq5_lcb2.sh` 把這個檢查做成發射前的硬擋
（`abort_seed_not_fresh`），**不是**跟單一個舊 seed 比字串。

**(3) 事前檢定力（§五 的表）**：

```bash
cd /Users/cosmopig/Documents/GitHub/Vacant && .venv/bin/python - <<'PY'
import sys, math; sys.path.insert(0,'.')
from ops.gain.replay.paired_ci import diff_ci
from ops.gain.power_paired import mde_at_n, n_needed_for_power
N=120
def bmin(m):
    for b in range((m//2)+1, m+1):
        if diff_ci(b, m-b, N)["lo"] > 0: return b
    return None
def pmf(k,n,p):
    if p<=0 or p>=1: return 1.0 if ((p<=0 and k==0) or (p>=1 and k==n)) else 0.0
    return math.exp(math.lgamma(n+1)-math.lgamma(k+1)-math.lgamma(n-k+1)
                    +k*math.log(p)+(n-k)*math.log1p(-p))
def stats(q,pb,mmax=70):
    pw=flip=nd15=0.0
    for m in range(mmax+1):
        pm=pmf(m,N,q)
        if pm<1e-14: continue
        if m<15: nd15+=pm
        bm=bmin(m)
        if bm is not None: pw+=pm*sum(pmf(b,m,pb) for b in range(bm,m+1))
        flip+=pm*sum(pmf(b,m,pb) for b in range(0,m//2+1))
    return pw,flip,nd15,q*N
for q,pb,lab in [(0.08,.725,"A q=8% p_b=.725"),(0.155,.725,"B q=15.5% p_b=.725"),
                 (0.155,.667,"C q=15.5% p_b=.667"),(0.20,.725,"D q=20% p_b=.725"),
                 (0.20,.667,"E q=20% p_b=.667"),(0.155,.60,"F q=15.5% p_b=.60"),
                 (0.08,.50,"G null q=8%"),(0.155,.50,"H null q=15.5%")]:
    pw,flip,nd15,ed=stats(q,pb)
    print(f"{lab}: P(lo>0)={pw*100:.1f}%  P(c>=b)={flip*100:.1f}%  P(n_d<15)={nd15*100:.1f}%  E[n_d]={ed:.1f}")
for q in (0.08,0.155,0.20): print(f"MDE@120 q={q}: {mde_at_n(N,q)['mde_pp']:.2f}pp")
print("N80 p_b=.725:", n_needed_for_power(.725), " p_b=.667:", n_needed_for_power(.667))
PY
```

實測輸出＝§五 的表（`18.1 / 41.5 / 22.9 / 52.8 / 29.6 / 9.2 / 1.1 / 1.5`；
MDE `6.67 / 9.17 / 10.00 pp`；N₈₀ `37 / 68` 對）。

**(4) 量具（零 API，跑到模型呼叫之前就退出）**：

```bash
cd /Users/cosmopig/Documents/GitHub/Vacant && \
VACANT_EVALPLUS_PATH=.vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz .venv/bin/python \
  ops/gain/gain_run.py --out /tmp/eq5lcb2_probe --n 120 --arms probe --bank lcb2 \
  --seed g-r449-eq5-lcb2 --probe-sample 0 \
  --decision DECISION_20260906_R449B_EQ5_LCB2_PREREG.md
```

實測輸出（2026-09-06，本機零 API）：

```
預註冊閘門通過：DECISION_20260906_R449B_EQ5_LCB2_PREREG.md 授權 eq5lcb2_probe
120 題（lcb2　offset=0　題序 [0, 120)）　輸出 /tmp/eq5lcb2_probe
── 量具驗證（先答已知答案）
   參考解通過 12/12　壞解被擋 12/12
   可見閘門（CONFORM 決策量具）參考解通過 12/12　樁被擋 12/12　覆蓋 12/12
EXIT_CODE=0
```

在 `--arms probe` 的分支 `return`（`gain_run.py:1353`）——**一次模型呼叫都沒有**
（沒有印出「模型池預檢」那一段）。

**同一條指令對 committed HEAD（`97d20c7`）的 `gain_run.py` 再跑一次，輸出逐字相同。**
這一步是必要的：本檔寫作當下工作目錄的 `ops/gain/gain_run.py` 有另一個 session
未提交的改動（把 `probe_instrument` 的兩個方向改走 `vacant.suitegauge.gauge_suite`），
而發射機（1003）`git pull` 拿到的是 **committed** 版本——只驗工作目錄版等於沒驗到
會真的跑的那一版。兩版量具輸出相同 ⇒ 這條差異對本 run 的量具是 (a) 類（G-4）。

順帶實測到 R440G 閘門有牙齒：把 `--out` 改成沒註冊的名字（`eq5lcb2_probe_head`）時，
它印「拒絕啟動：…內文沒有寫到 run 名字」並以 rc=1 停住，一題都沒載。
（`--out /tmp/eq5lcb2_probe` 這個名字寫在本行是**故意的**：R440G 閘門檢查的是
`pathlib.Path(--out).name` 有沒有出現在 DECISION 內文裡，所以量具指令要能跑，
`eq5lcb2_probe` 就必須出現在本檔。這也是為什麼量具指令屬於預註冊的一部分。）

⚠ 真正發射時 `--arms EQ5` 會多吃一道硬擋（`gain_run.py:1338-1354`）：
`visible_n < n` ⇒ 停。本 run 的 `n`＝有參考解的題數＝12，`visible_n`＝12 ⇒ 12≥12，過。
**這道擋門比較的是 12 對 12，不是 12 對 120**——§八-1 那條 10% 覆蓋率的邊界
不會被它擋下來，所以必須靠本檔寫出來。

**(5) 發射器語法與一致性**：

```bash
bash -n ops/gain/launch_eq5_lcb2.sh
.venv/bin/python -m pytest tests/test_r449b_launcher_prereg.py -q
```

`tests/test_r449b_launcher_prereg.py` 釘住的是**發射器與本檔不准漂開**：
run 名字、seed、`--n 120 --offset 0`、`--arms EQ5`、`--bank lcb2`、模型、
`--probe-sample 0`、request policy、`--decision` 指到本檔、等待字串錨在行首、
seed 不在任何 `runs/*/summary.json` 裡，以及三個突變檢查（改 seed／拿掉錨／
把探針數改成 1 都必須讓對應的測試變紅）。

**(6) analyzer 與 schema 尺自檢**（收官前會再對真 rows 跑一次 `--run`）：

```bash
.venv/bin/python ops/gain/analyze_eq5.py --selftest
.venv/bin/python ops/gain/eq5_schema_precheck.py --selftest
```

---

## 十、中止準則（跑之中就適用，不是收官才想）

- 任一時刻 `infra_void` > 20% ⇒ 中止，寫進 GAIN_STATE，**不補跑**。
- 任一次中途 summary 的 `calls_per_task` ≠ 5.00 ⇒ **實作缺陷**，中止，不當資料用。
- 端點連續失敗導致 rows 停止成長 > 60 分鐘 ⇒ 中止並記錄（**不改條件重跑**）。
- 若發現本 run 與任何其他 `gain_run.py` 同時在跑（違反 SPEC_GAIN §7 一端點一 run）
  ⇒ 立刻中止本 run 並作廢它已經產出的資料。發射器已經擋在前面
  （等待迴圈＋發射前重做單 run 檢查），這是第二道。

**跑之中不准算 Δ／b／c／CI／四格判定。** 中途只准看：rows 行數、`infra_void`、
`calls_per_task`、行程是否活著。任何中途看過的數字，收官時要逐條揭露。

---

## 十一、新增可調參數

**0**。

- `--bank lcb2` 與 `--n 120` 不是新旋鈕——逐字沿用 `runs/g_r447_conform_lcb2`
  在 R440Z §二 註冊過的那一組，題庫檔、sha256、120 題全部不動。
- seed 換一顆不是旋鈕，它是「換一批抽樣」的定義；新 seed 的字串寫死在本檔與發射器，
  兩邊由 `tests/test_r449b_launcher_prereg.py` 釘住，且發射器會掃過所有
  `runs/*/summary.json` 確認它沒被用過。
- `k=5` 與 `arm_eq5` 一行碼沒動；閾值、逾時、模型池全部沿用。
- 區間、MDE、N₈₀、±5pp 實務門檻全部沿用既有模組（`paired_ci`／`power_paired`），
  一個常數都沒動。

---

## 十二、口徑（展覽是唯一交付物，措辭是紅線）

- 本 run 的結果若上展場，措辭是**可究責性／讓依賴有根據**，
  這三個詞不准出現：「信任」「防止」「保證」。
- 本 run 是**真模型、真資料**（120 題 LeetCode 中高難度題、gemma-4-12b-it-qat），
  不是機制模擬；展場的秒級互動仍然跑 `vacant/entrycost.py` 的機制模擬，
  兩者在畫面上必須分開標示，不准混講。
- 展場若要用 §六 `REPLICATED_ON_HARD` 那句話，必須連 R440P §五 的第一條邊界一起講：
  **整件事建立在「需求可以被編譯成可執行的驗收測資」**；驗收測資不是真需求子集的
  場合，拒交會殺掉好答案。在 LCB 上還要多講 §八-6：這裡的可見測資只有題目附的範例。
- **UNRESOLVED 不准上展場當成任何一種結論。** 「沒量出來」對外行觀眾就是「沒有」，
  在畫面上放一個量不出來的東西只會製造誤解。

---

## 十三、本檔自己的推翻條件

1. 若收官時發現 `analyze_eq5.py` 對 r449b 與對 r446／r448 的**同名欄位語意不同**
   （例如 `deliv` 口徑被改過），本檔 §三 的所有錨值失效，跨 run 不可比，
   先修可比性再談任何狀態。
2. 若 G-4 的 diff 出現 (b) 類改動（碰到 `arm_eq5`／`meets_demand`／`behavior_signature`／
   `extract_code`／`LiveCodeBenchLoader`／請求政策），r449b 就**不是**在跑 r446/r448
   跑的那條臂——§六 的四個狀態全部不適用，收官只能報 r449b 自己的數字並寫明處置變了。
   **本檔寫作當下 `ops/gain/gain_run.py` 正被另一個 session 改動（量具路徑），
   這一條不是假設性的。**
3. 若 §五 的檢定力表被發現算錯（例如 `diff_ci` 的邊界語意與本檔假設不同），
   §六 邊界 (b) 的「方向沒翻 ≠ 效果消失」仍然成立（它只依賴定性事實），
   但表裡的百分比要重算，且「n=120 檢定力不足」這個結論要重新確認而不是沿用。
4. 若發射時 `--bank lcb2` 載到的不是 §九-1 那 120 個 `task_id`（例如題庫檔被改），
   本 run 與 r447 的同題關係破裂，§七 整節作廢，收官前必須先重算。
