# R448：EQ5 在**另一顆 seed** 上的獨立重複——`runs/g_r448_eq5_mbpp_seed2`

**日期**：2026-09-04 UTC　**輪次**：R448（Mac 端稽核 session，零 API、零 ssh）
**狀態**：預註冊。**本檔在 run 發射之前、在任何 r448 資料存在之前定稿。**
**授權**：本檔即 R440G 閘門所需的那一份——它授權 `runs/g_r448_eq5_mbpp_seed2`
這一個 run 名字，與 seed `g-r448-eq5-seed2`，其他都不授權。

---

## 一、要解的問題：整個 G 實驗只剩一個正結果，而它只跑過一次

`DECISION_20260904_R446_FABLE_AUDIT.md` §一 的那一格是目前唯一「有方向、區間下界過 0」
的結果：同一組 5 份候選、同樣 5 通呼叫，閘門規則（跑客戶自己的驗收測資、交第一份通過的、
全不通過就不交）比多數決多交付 **+4.04pp**（371 題，b=24 c=9，p=0.0135，
稽核區間 [+1.08, +7.01]、迴圈區間 [+0.80, +6.53]）。

它掛在**一個 run、一顆 seed**（`g-r212-route-20260828`）上。
R446 §五 自己寫下的推翻條件是：

> 若獨立第二批 EQ5（不同 seed）的 b/c 方向翻轉 ⇒ 本結果降為探索性。

**那個條件到今天沒有任何資料可以判**——第二批不存在。本 run 就是去把它變成可判的。
這是目前**最便宜**的硬化方式：不需要新機制、不需要新題庫、不需要新旋鈕，
只換一顆 seed 重跑同一條臂。

### 它硬化什麼、不硬化什麼（估計量宣稱，收官不准放大）

**硬化的**：在同一批 371 題上，「閘門規則 vs 多數決規則」的**方向與幅度**，
是不是只在那一輪的生成噪音與 worker 指派下才成立。

**不硬化的（逐條寫死，收官不准借用）**：

1. **不是新題目上的外部效度。** `load_tasks` 對 `--n 371 --offset 0` 取的是
   MBPP+ 378 題扣掉 `GAIN_EVALPLUS_RESOURCE_EXCLUSIONS` 7 題之後的**全部** 371 題；
   換 seed 只換題序，**題目集合逐字元相同**（§九 有離線驗證的輸出）。
   跨題庫的外部效度是 r447（LCB v2）在答的問題，不是本 run。
2. **不是「Vacant 這個系統贏了 OFF5」。** EQ5 答的是「給定同一組候選，哪一條選擇規則
   交付得多」；「兩個各自獨立抽樣的系統誰贏」是 r445 的估計量、已收官。
   R446 §二 的禁令逐條沿用。
3. **不是出貨形態的成本結論。** EQ5 的閘門臂花 5.00 通呼叫（不早停），
   出貨形態會早停（r445 量到 1.51）。成本面仍以 r445 為準。
4. **不是「≥5pp 的實務增益」。** r446 的區間上界（+6.5／+7.0）跨過 5pp 線、
   下界（+0.8／+1.1）遠低於它。本 run 不預期改變這一點。

### 換一顆 seed 到底換掉了什麼（機制，不是修辭）

| 受 seed 影響 | 怎麼影響 | 出處 |
|---|---|---|
| 題序 | `iter_tasks` 按 `sha256(f"{seed}:{task_id}")` 排序 | `vacant/codebench.py:EvalPlusMBPPLoader.iter_tasks` |
| worker 指派 | 每臂 `random.Random(f"{seed}:{arm}")`，`arm_eq5` 開頭 `[rng.choice(agents) for _ in range(k)]` | `ops/gain/gain_run.py:1449`、`:621` |
| 多數決的平手打破 | 同一顆 rng 的 `rng.choice(tied)` / `rng.choice(win)` | `gain_run.py:661-662` |
| **題目集合** | **不受影響**（371 題全取，只換順序） | §九 已離線驗證 |

另外，**端點抽樣本身就是隨機的**（`brain_cline.py:57` temperature=0.7），
所以即使 seed 相同，候選也不會重現。換 seed 的作用是讓「題序×worker 指派」
這一層也一起脫鉤，讓兩個 run 之間除了題目集合以外沒有共用的隨機狀態。

---

## 二、run 名字、指令與「唯一的差別」

run 目錄：**`runs/g_r448_eq5_mbpp_seed2`**（本檔只授權這一個名字）。
seed：**`g-r448-eq5-seed2`**。

```
--out runs/g_r448_eq5_mbpp_seed2 --n 371 --offset 0 --arms EQ5 --bank evalplus
--seed g-r448-eq5-seed2 --models gemma-4-12b-it-qat --probe-sample 0
--request-timeout-s 600 --review-timeout-s 380
--decision DECISION_20260904_R448_EQ5_REPLICATION_PREREG.md
```

與 r446（`runs/g_r446_eq5_mbpp`）的逐項對照——**只有 seed 一格不同**：

| 項 | r446 | r448 |
|---|---|---|
| `--n` / `--offset` | 371 / 0 | 371 / 0（同一批 371 題） |
| `--arms` | EQ5 | EQ5 |
| `--bank` | evalplus | evalplus |
| `--models` | gemma-4-12b-it-qat | gemma-4-12b-it-qat |
| `--probe-sample` | 0（全題量具） | 0 |
| request policy | timeout 600 / retries 4 / backoff 2.0 / review 380×2 | 逐項相同 |
| agent pool | 6 個 agent／1 個模型家族 | 相同（`POOL` 未動） |
| **`--seed`** | **`g-r212-route-20260828`** | **`g-r448-eq5-seed2`** |

發射器：`ops/gain/launch_eq5_seed2.sh`（等 `runs/g_r447_conform_lcb2` 退出，
SPEC_GAIN §7 一端點一 run）。**發射由稽核 session 之外的人執行；本檔只出檔案與指令。**

---

## 三、事前註冊的預測（P-1..P-6）——先寫死，收官逐條判 HIT／MISS

仲裁量一律取 `python3 ops/gain/analyze_eq5.py --run runs/g_r448_eq5_mbpp_seed2 --json ...`
輸出 JSON 的欄位，**欄位名逐字寫在下表第三欄**（記憶鐵律：判準要指名它讀哪個 key，
不准靠「工具印了什麼字串」）。

| # | 預測 | 仲裁欄位 | 窗 | 錨在哪 |
|---|---|---|---|---|
| **P-1** | Δ ＝ 閘門 − 多數決 的**點估計** > 0 | `paired.delta_pp` | **> 0** | r446 +4.04pp |
| **P-2** | **95% CI 下界 > 0（＝重複判準）** | `paired.ci95_lo_pp` | **> 0** | r446 [+1.08,+7.01]／[+0.80,+6.53]，兩套 bootstrap 下界都過 0 |
| **P-3** | discordant pair 數 | `paired.n_discordant` | **≥ 20** | r446 n_d=33；§五 的檢定力表以 E[n_d]=33 為前提 |
| **P-4** | 預算恰好 5 | `calls_per_task` ＝ **5.00** 且 `budget_all_exactly_5` ＝ **true** | 結構性 | r446 1855 呼叫／371 題＝5.00，371 列全部 `calls_used=5` |
| **P-5** | infra_void 率 | `void_rate_pp` | **≤ 5%** | r444／r445／r446 皆 0 |
| **P-6** | 兩條規則選到同一份的比例 | `same_choice_effective_rate_pp` | **[10, 40]%** | r446 effective 20.49%（raw 22.91%）；AMEND-1 之後 effective 才是仲裁量 |

**無條件一併印、一併判、不准挑一個的次要量**（看過數字之後不准選分母——r444 那次
兩個分母給出相反判決）：

- `gate.deliv_pp_denom_measured`（r446：75.47%）與 `gate.deliv_pp_denom_accepted`（r446：81.16%）
- `vote.deliv_pp_denom_measured`（r446：71.43%）
- `gate.coverage_pp`（r446：92.99% ⇒ 拒交 7.01%）
- `same_choice_rate_pp`（raw，r446：22.91%）與 `false_same_choice_n`（r446：9）
- `paired.b_gate_only` / `paired.c_vote_only` / `paired.p_mcnemar_exact`
- `power.mde_at_n_pp` / `power.n80_if_true_effect_is_observed`

### ⚠ `analyze_eq5.py` 自己印的 `prereg` 區塊**不是本 run 的仲裁者**

那支工具的 `PREREG` 常數逐字編碼的是 **R446** 的窗（`P-R446-*`，其中
P-R446-5 的窗是 [40,95]、P-R446-7 是 n_d≥15）。本 run 的窗在上表，
**與它不同的有兩格**：P-6 的 [10,40]（r446 實測 20.49% 已經掉在 [40,95] 之外，
沿用那個窗等於註冊一個已知會 MISS 的預測）與 P-3 的 ≥20（r446 實測 33）。

⇒ 收官時：`analyze_eq5.py` 的輸出用來取**數字**，HIT／MISS 由**本檔上表**判。
**不准為了讓工具印出正確字串而去改 `analyze_eq5.py` 的 `PREREG`**——那支常數是
r446 的事前註冊，改它等於改別人的事前註冊（該檔自己寫著「改這裡等於改事前註冊 ⇒ 不准」）。

---

## 四、效力前提 G-1..G-5（不是預測，是「這份資料算不算數」的擋門）

任一條紅 ⇒ **先修／先揭露，不判 replication**（狀態＝`INVALID`，見 §五）。

| # | 前提 | 怎麼驗 | 事前已知的狀況 |
|---|---|---|---|
| **G-1** | analyzer 讀得懂 runner 寫的 rows | `python3 ops/gain/eq5_schema_precheck.py --run runs/g_r448_eq5_mbpp_seed2` ⇒ `SCHEMA_COMPATIBLE` | r446 上實測過一次（round699） |
| **G-2** | 帳對得上、且是收官資料 | `broken_reasons` ＝ `[]`；`summary.arms.EQ5.terminal` ＝ true；`measured + infra_void == processed` | r446：371+0=371、terminal true |
| **G-3** | 落盤欄位與離線重算一致 | 每一列都有 `same_choice_effective`，且與 `accepted ∧ (gate_code_sha256==vote_code_sha256)` 逐筆相同（`analyze_eq5` 的 `landed`／`bad_eff` 區塊） | **r446 上結構不可評估**（那支行程載入的是 `65171d1`，該欄位 `4b0982e` 才落地，實測 0/371 列有此欄位）。**r448 是這道擋門第一次真的被評估**；若 r448 也 0 列有此欄位 ⇒ 代表跑的碼比 `4b0982e` 舊，照實寫、不當好消息 |
| **G-4** | 處置定義沒有漂掉（R680 Q2） | `git diff <r446 的 runner_git.sha> <r448 的 runner_git.sha> -- ops/gain/gain_run.py ops/gain/brain_cline.py vacant/codebench.py`，逐項分類 (a) 只影響分析／文件 (b) 影響臂行為 | 本檔寫作時（HEAD `a4d4415`）實測只有兩類改動：lcb2 接線（evalplus 路徑不經過）與 `same_choice_effective` 這個 **additive 欄位**；`arm_eq5` 的選擇語意、`meets_demand`、`behavior_signature`、`extract_code`、`EvalPlusMBPPLoader` 一個字沒動 ⇒ 目前是 (a)。**發射時間點的 HEAD 可能不同，收官必須重跑這條 diff** |
| **G-5** | 不被長得像的旗標騙 | `summary.equal_budget_comparison_valid` **預期是 false** | 它的定義只看 `ON` 與 `OFF5` 兩臂（`gain_run.py:1394-1399`），EQ5-only 的 run 結構上永遠 false。EQ5 的等預算證據是 P-4，不是這個旗標 |

**G-4 的一條誠實邊界**：r446 的 `runner_git.dirty` ＝ **true**——它跑的時候工作目錄
有未提交的改動，所以那一版的位元組**無法只憑 sha 完全還原**。這是既有的設計缺口
（R680 Q2 的 BROKEN 情形的弱化版），本檔照實記，不用 mtime／git log 去猜然後當成量測。

---

## 五、決策規則：什麼叫「重複成立／未重複／沒量出來」（**在任何 r448 資料之前寫死**）

前提：G-1..G-4 全綠。任一紅 ⇒ 狀態 `INVALID`，先修或先揭露，**不准**先判 replication。

| 狀態 | 觸發條件（照順序判，先命中者為準） | 收官准講的話 |
|---|---|---|
| `INVALID` | G-1..G-4 任一紅；或 **P-4 MISS**（有任一列 `calls_used ≠ 5`） | 「這個 run 不當資料用」——P-4 MISS 是實作缺陷不是結果（R446 §五 同款） |
| **`NOT_REPLICATED`** | `paired.c_vote_only ≥ paired.b_gate_only`（方向翻轉或打平）**或** `paired.delta_pp ≤ 0` | R446 §五 的推翻條件**兌現**：R446 §二 那句可引用的話**降為探索性**，展場與任何對外文字在有第三次資料之前**不得使用**。要同時報兩個 run 的 b/c 對照 |
| **`REPLICATED`** | P-1 HIT **且** P-2 HIT（等價於 `verdict_four_cell == GATE_RULE_WINS`） | 「兩顆 seed、同一批 371 題、同樣 5 通呼叫，閘門規則的交付都高於多數決，兩次的 95% 區間下界都在 0 以上。」**仍不准**講 ≥5pp、不准講「系統贏」、不准外推到別的題庫 |
| **`UNRESOLVED`** | 其餘（典型：`delta_pp > 0` 但 `ci95_lo_pp ≤ 0`，即 `RULED_OUT` 或 `NON_INFERIOR_BUT_UNRESOLVED`） | 「**沒量出來**，不是沒有差異」——必須**同時**報 `power.mde_at_n_pp`、`power.n80_if_true_effect_is_observed` 與 §六 的事前檢定力表（round678 §六 的兩句話規則） |

### 邊界情況（事前寫死，避免收官當場挑）

- **(a) P-2 HIT 但 P-3 MISS（n_d < 20）**：判 `REPLICATED`，但**必須**在同一句話裡標注
  「配對數低於事前窗口」並報 N₈₀。不准只寫 `REPLICATED` 三個字。
- **(b) P-6 MISS**：不改變 §五 的狀態判定，但收官要說明對比結構變了
  （>40% ⇒ 兩條規則更常選到同一份；<10% ⇒ 更少），並列出兩個 run 的
  raw／effective 對照。**若 `same_choice_effective_rate_pp > 95%`**，照 R446 §六-1
  的語意處理：這個比較沒有對比，結論只准寫「測不出來」，不准寫成「等預算下打平」。
- **(c) P-5 MISS 但 void ≤ 20%**：資料仍可判，但主結論必須附 void 敏感度——
  把 void 那幾題分別當成「全歸閘門贏」與「全歸多數決贏」兩個極端各算一次，
  兩端都報。void > 20% ⇒ §八 的中止準則已經觸發，資料不進結論。
- **(d) P-1 HIT、P-2 MISS、且 `paired.b_gate_only > paired.c_vote_only`**：這是
  `UNRESOLVED`，**不是** `NOT_REPLICATED`。方向沒翻，只是這一次沒把 0 排除掉。
  §六 的檢定力表就是為了讓這一格不被誤讀成「效果消失了」。

### 事前寫死的禁令（違反＝本輪失敗）

1. **看到數字之後改窗、改仲裁欄位、改狀態定義** ⇒ 一律不准。要改只能由後續輪次／人類
   在**下一個** run 之前改，且舊窗要留著讓人收回仲裁權（AMEND-1 §五 的規矩）。
2. **不准**把 r446 ∪ r448 併成 `n=742` 當獨立樣本去宣稱顯著（§七）。
3. **不准**用併庫的 p 值或 CI 取代 r448 自己的 P-1／P-2 判定。
4. **不准**在 `UNRESOLVED` 的情況下寫「兩條規則等價」「打平」。

---

## 六、事前檢定力：**這個重複本來就有大約三成的機會答不出來**

用 repo 既有的 `ops/gain/replay/paired_ci.diff_ci`（round656 已雙向驗證）與二項列舉，
在 r446 的觀測值（discordant rate q＝33/371＝8.89%、p_b＝24/33＝0.727）下投影：

| 情境 | P(`ci95_lo_pp > 0`)＝P-2 HIT 的機率 |
|---|---|
| **真效果就是 r446 觀測到的那個**（q=8.89%, p_b=0.727） | **69.9%** |
| 效果回歸一點（q 不變，p_b=0.65） | 33.9% |
| 效果再弱一點（q 不變，p_b=0.60） | 15.9% |
| discordant 變少（q=6%, p_b=0.727） | 50.2% |
| discordant 變多（q=12%, p_b=0.727） | 84.4% |

其他三個事前機率（同樣在 r446 觀測值下）：

- E[n_d] ＝ 33.0；**P(n_d < 20) ＝ 0.4%** ⇒ P-3 幾乎必中；真的 MISS 代表
  discordant 結構本身變了，那是要去查的事，不是雜訊。
- **P(c ≥ b) ＝ 0.5%** ⇒ 方向翻轉是**強訊號**。R446 §五 把推翻條件寫在方向上是對的。
- 真效果為 0 時 **P(誤判 P-2 HIT) ＝ 1.59%**（單邊，精確條件區間本來就保守）。

**這張表的用途（事前寫死）**：收官若落在 `UNRESOLVED`，
**不准**把它讀成「r446 的結果被打掉了」——在真效果成立的前提下，這一格本來就有
約 30% 的機會出現。要把 `UNRESOLVED` 讀成「效果不存在」，需要的是
`NOT_REPLICATED`（方向翻轉，事前機率 0.5%），或第三次資料。
反過來也一樣：這張表**不是**替 `NOT_REPLICATED` 開脫的工具——0.5% 就是 0.5%。

演算法與指令逐字寫在 §九，任何人可以重跑。

---

## 七、併庫（r446 ∪ r448）：報，但**不是**獨立樣本

`CRITERION_20260903_R680_POOL_PRECONDITIONS.md` 的 **Q1** 寫死了可併的前提：
兩個 run 的 `task_id` 集合**交集＝∅**。這裡的交集是 **371（完全重疊）**
⇒ **Q1 是 MISS，不是 HIT**。所以：

**准做的（描述性，且必須標成描述性）**：

- 合併點估計 `Σ(b−c)/Σn`（兩個 run 各 371 題）——只當作**方向穩定性**的陳述。
- 兩個 run 的 `b`／`c`／`n_d`／`delta_pp` 並列表。
- **逐題一致性四格**（同一個 `task_id` 在兩個 run 各自的 `gate_deliv`／`vote_deliv`）：
  兩次都閘門贏／兩次都多數決贏／一次一邊。這是完全重疊帶來的**唯一好處**，
  也是完全重疊的正確用法。

**不准做的**：

- 把合併的 CI 或 p 值當成 `n=742` 的證據。同一批題目量兩次、同題結果正相關 ⇒
  那個區間會**過窄**（anti-conservative），會把「同一批題目量了兩次」講成「樣本數加倍」。
- 用合併數字取代 §五 的狀態判定。**§五 的仲裁者只有 r448 自己。**

**若要引用合併數字，必須連這句一起引用**：
「r446 與 r448 跑的是同一批 371 題，兩者不是獨立樣本；合併的點估計只說明方向，
合併的區間會比真實的窄。」

工具：`ops/gain/replay/pooled_paired_ci.py --key deliv`（round675 已驗過加法恆等式）
可以用來算點估計，但輸出的 CI 欄位在本情境下要標成 `ANTI_CONSERVATIVE`，
**不得進結論句**。

---

## 八、中止準則（跑之中就適用，不是收官才想）——沿用 R446 §五，加一條

- 任一時刻 `infra_void` > 20% ⇒ 中止，寫進 GAIN_STATE，**不補跑**。
- 任一次中途 summary 的 `calls_per_task` ≠ 5.00 ⇒ **實作缺陷**，中止，不當資料用。
- 端點連續失敗導致 rows 停止成長 > 60 分鐘 ⇒ 中止並記錄（**不改條件重跑**）。
- **新增一條**：若發現 r448 與 `runs/g_r447_conform_lcb2` 同時在跑
  （違反 SPEC_GAIN §7 一端點一 run）⇒ 立刻中止 r448 並作廢它已經產出的資料。
  發射器已經擋在前面（等待迴圈＋發射前重做單 run 檢查），這是第二道。

**跑之中不准算 Δ／b／c／CI／四格判定**（R446 §五 同款）。中途只准看：
rows 行數、`infra_void`、`calls_per_task`、行程是否活著。任何中途看過的數字，
收官時要逐條揭露（AMEND-1 §六 的規矩）。

---

## 九、自我驗證（發射前做完，指令逐條可重跑；全部零 API、零 ssh）

**(1) 題目集合在兩顆 seed 下相同**——這是 §一「不是新題目」與 §七「完全重疊」兩句話的證據：

```bash
cd /Users/cosmopig/Documents/GitHub/Vacant && \
VACANT_EVALPLUS_PATH=.vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz .venv/bin/python - <<'PY'
import sys; sys.path.insert(0,'.')
from ops.gain.gain_run import load_tasks
a=[t["task_id"] for t in load_tasks("evalplus","g-r212-route-20260828",371,offset=0)]
b=[t["task_id"] for t in load_tasks("evalplus","g-r448-eq5-seed2",371,offset=0)]
print("len",len(a),len(b)); print("set_equal",set(a)==set(b)); print("order_identical",a==b)
PY
```

實測輸出：`len 371 371` / `set_equal True` / `order_identical False`。
（另驗：r446 的 rows 覆蓋的 371 個 `task_id` 與這個集合完全相同。）

**(2) 事前檢定力（§六 的表）**：

```bash
cd /Users/cosmopig/Documents/GitHub/Vacant && .venv/bin/python - <<'PY'
import sys, math; sys.path.insert(0,'.')
from ops.gain.replay.paired_ci import diff_ci
N=371
def bmin(m):
    for b in range((m//2)+1, m+1):
        if diff_ci(b, m-b, N)["lo"] > 0: return b
    return None
def pmf(k,n,p):
    return math.exp(math.lgamma(n+1)-math.lgamma(k+1)-math.lgamma(n-k+1)
                    +k*math.log(p)+(n-k)*math.log1p(-p)) if 0<p<1 else 0.0
def power(q,pb,mmax=110):
    t=0.0
    for m in range(mmax+1):
        pm=pmf(m,N,q)
        if pm<1e-12: continue
        bm=bmin(m)
        if bm is None: continue
        t+=pm*sum(pmf(b,m,pb) for b in range(bm,m+1))
    return t
for q,pb,label in [(33/371,24/33,"r446 觀測值"),(33/371,0.65,"p_b=0.65"),
                   (33/371,0.60,"p_b=0.60"),(0.06,24/33,"q=6%"),(0.12,24/33,"q=12%")]:
    print(f"{label}: {power(q,pb)*100:.1f}%")
PY
```

實測輸出：`69.9% / 33.9% / 15.9% / 50.2% / 84.4%`。

**(3) 處置定義（G-4 的事前狀態）**：

```bash
cd /Users/cosmopig/Documents/GitHub/Vacant && \
git diff --stat 65171d1..HEAD -- ops/gain/gain_run.py ops/gain/brain_cline.py vacant/codebench.py
```

實測：`gain_run.py | 25 ++++-`、`codebench.py | 55 +++++--`，逐行讀過後分類為
(a)——lcb2 接線（evalplus 不經過）＋ `same_choice_effective` additive 欄位。
`brain_cline.py` 零改動。

**(4) 發射器語法與一致性**：

```bash
bash -n ops/gain/launch_eq5_seed2.sh
.venv/bin/python -m pytest tests/test_r448_launcher_prereg.py -q
```

`tests/test_r448_launcher_prereg.py` 釘住的是**發射器與本檔不准漂開**：
run 名字、seed、`--n 371 --offset 0`、`--arms EQ5`、`--bank evalplus`、模型、
`--probe-sample 0`、request policy、`--decision` 指到本檔、等待字串錨在行首、
以及 seed 不等於 r446 那一顆。**這一支測試在撰寫過程中真的抓到過一個錯**
（發射器裡的 `DEC=` 少了一個字母 ⇒ R440G 閘門會在等了幾小時之後才拒絕啟動）。

**(5) analyzer 與 schema 尺自檢**（收官前會再對真 rows 跑一次 `--run`）：

```bash
.venv/bin/python ops/gain/analyze_eq5.py --selftest
.venv/bin/python ops/gain/eq5_schema_precheck.py --selftest
```

---

## 十、新增可調參數

**0**。

- seed 換一顆**不是旋鈕**，它就是「重複」的定義；而且新 seed 的字串寫死在本檔與發射器，
  兩邊由測試釘住。
- 所有窗都錨在 r446 的實測值上，錨法逐格寫在 §三 第五欄。唯二與 R446 不同的窗
  （P-3 的 20、P-6 的 [10,40]）都寫明了為什麼不能沿用舊窗。
- 區間、MDE、N₈₀、±5pp 實務門檻全部沿用既有模組（`paired_ci`／`power_paired`），
  一個常數都沒動。

---

## 十一、口徑（展覽是唯一交付物，措辭是紅線）

- 本 run 的結果若上展場，措辭是**可究責性／讓依賴有根據**，
  不准出現「信任」「防止」「保證」這三個詞。
- 本 run 是**真模型、真資料**（371 題 MBPP+、gemma-4-12b-it-qat），
  不是機制模擬；展場的秒級互動仍然跑 `vacant/entrycost.py` 的機制模擬，
  兩者在畫面上必須分開標示，不准混講。
- 展場若要用 §五 `REPLICATED` 那句話，必須連 R440P §五 的第一條邊界一起講：
  **整件事建立在「需求可以被編譯成可執行的驗收測資」**；
  驗收測資不是真需求子集的場合，拒交會殺掉好答案。

---

## 十二、本檔自己的推翻條件

1. 若收官時發現 `analyze_eq5.py` 對 r448 與對 r446 的**同名欄位語意不同**
   （例如 `deliv` 口徑被改過），本檔 §三 的所有錨值失效，兩個 run 不可比，
   先修可比性再談 replication。
2. 若 G-4 的 diff 出現 (b) 類改動（碰到 `arm_eq5`／`meets_demand`／
   `behavior_signature`／`extract_code`／`EvalPlusMBPPLoader`／請求政策），
   r448 就**不是** r446 的重複，是「另一種處置」——§五 的四個狀態全部不適用，
   收官只能報 r448 自己的數字並寫明處置變了。
3. 若 §六 的檢定力表被發現算錯（例如 `diff_ci` 的邊界語意與本檔假設不同），
   §五 邊界情況 (d) 的「不准誤讀 UNRESOLVED」那段仍然成立（它只依賴
   「方向沒翻 ≠ 效果消失」這個定性事實），但表裡的百分比要重算。
