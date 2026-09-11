# R529 預註冊 **v2**：H-MIX 的單一效果在幾個不同題目集上還在——三臂 OFF／CONFORM／HMIX

（**v2：2026-09-11，Fable 稽核後的裁決版**。v1 是同日 Opus 的草稿；Fable 改了什麼、
為什麼改，逐條在**附錄 A**，v1 的取捨紀錄整段留著沒有刪。
**在任何 r529 資料之前**——本檔寫成時 `runs/` 底下沒有任何 `g_r529*` 目錄，
三顆 seed 在本機 50 個與 vacant-dev 54 個 `runs/*/summary.json` 裡一次都沒出現過，
實跑輸出見 §九-1。本輪零模型呼叫；碰過遠端的動作只有**唯讀** `ls`／`ps`
與**離線量具**（純沙箱、不打後端），見 §五-1。）

**編號**：R529 沿用 v1（`R4xx` 這一段 R440–R503、R516–R528 已用滿）。本檔在內容上是
R460 的跨題庫續作，排在 R460R（同題庫五次複製）旁邊：
**R460R 換 seed 不換題目，R529 換題目不換機制。**

本檔授權的東西**只有**：§二 那 37 個 run 名字與逐塊註冊行、三顆 seed、§三 的取樣規則、
§六 的分析口徑。其餘一律照 `DECISION_20260907_R460_HARNESS_PREREG.md`
（以下簡稱 **R460 預註冊**）。與 R460 相比，本檔**新增**了一個主指標
（跨題庫分層配對檢定，§六-2）並且**改了家族大小**（10 → 2），
四狀態的 (iii) 改成本研究自訂並在資料前凍結的口徑（§六-4）——
這三處都是 Fable 的裁決，逐條理由寫在原地與附錄 A，不是就地放寬。

---

## 〇、要解的問題：`+13.33pp` 是 LCB v2 那 120 題的性質，還是 H-MIX 的性質

R460 收官（`DECISION_20260911_R460_FABLE_AUDIT_HARNESS.md`）判 H-MIX **EFFECTIVE**，
而那份裁決自己把限制寫死了：

- §八-1「單一後端、單一模型、**單一題庫**；n=120」；
- §七「**不能外推到 LCB v2 以外**（MBPP+ 的回饋訊息天生較差，見 HARNESS_STUDY §3.3）」；
- §九 第一條推翻條件逐字：「若在 LCB v3（189 題，零交集）預註冊複製
  H-MIX vs CONFORM 而 **c ≥ b** ⇒ 本判定降為『一次顯著』」。

R460R 回答不了這一題，而且它自己寫著回答不了（R460R §六-2：「五次共用同一批
120 題 ⇒ 題目層級的效果在五次之間是**完全相關**的，複製不掉」）。

**R529 就是 R460 §九 第一條那個推翻試驗**，並且把它從一個題庫擴到四個互斥的題目集、
**三個真來源**。

### 本 run **不**回答什麼（收官不准借用）

1. **不**回答「H-MIX 比 H-PI／H-OC 好」——本 run 沒有那兩條臂（R460 §六-(7)-6 的禁令照舊）。
2. **不**回答「效果量是多少」。四個題目集的點估計**不准平均**（§六-3）。
   合併只出現在**檢定**那一格，而且合併的是**不一致對的個數**不是效果量（§六-2）。
3. **不**回答「換模型還成不成立」——四個題目集共用同一顆 `gemma-4-12b-it-qat`。
4. **不**在本 run 重新賺一次 R460 那個 `EFFECTIVE`——本檔的四狀態是**自訂並在資料前
   凍結**的另一套口徑（§六-4），與 R460 的同名狀態**不是同一個東西**，不可互引。

---

## 一、題目集：**4 個**，以及誠實的計數

> **3 個真來源 ＋ 1 個難度切分 ＝ 4 集**
> 不是「4 個來源」，也不是 v1 那個「5 個題目集」——v1 的 5 集裡有 3 集是
> MBPP+ 的 seed 切片，那量到的是**題目層級的變異**不是來源變異，Fable 判它
> 「拿抽樣切分充數」，全部收回去合成一集（附錄 A-1）。

| # | 題目集 | bank | 分層 | n | 來源 | V/GT 分離 | sha256／釘死 | 與其他的交集 |
|---|---|---|---|---:|---|---|---|---|
| S1 | `lcb3_medium` | `lcb3` | `difficulty=medium` | **135** | LiveCodeBench code_generation_lite（Jain et al. 2024, arXiv:2403.07974），test/test2/test3 視窗，2023-05-07→2024-08-10 | `visible_tests`（2–4 條）／`hidden_tests`（**5–24 條，下界比 v1/v2 低**），`_lcb_check_code` 兩份分開渲染 | `bd3dffebb1b16bc7…`、189 題釘死、fail-closed | ∩ S2 = 0（difficulty 的一個分割）；∩ lcb v1/v2 = 0 |
| S2 | `lcb3_hard` | `lcb3` | `difficulty=hard` | **54** | 同上 | 同上 | 同上 | 同上 |
| S3 | `humanevalplus` | `humanevalplus` | —（無平台原生標籤） | **156**（164 − 8，§一-2） | EvalPlus HumanEval+ v0.1.10（Liu et al. 2023, arXiv:2305.01210；底層是 OpenAI HumanEval, Chen et al. 2021, arXiv:2107.03374） | `visible_check`＝base 輸入（中位數 7 條）／`hidden_check`＝base＋plus（plus 中位數 972 條）；`canonical_solution`／`test` 永不進 prompt | `272720b90ac37550…`、164 題釘死、fail-closed | 與 LCB、MBPP+ 零交集（不同語料） |
| S4 | `evalplus` | `evalplus` | — | **371**（378 − 7 資源排除） | EvalPlus MBPP+ v0.2.0，私有不轉散布 | `visible_check`＝base（3–7 條）／`hidden_check`＝base＋plus（中位數 105 條） | `af43697e8791c4c1…`、378 題釘死 | 與 LCB、HumanEval+ 零交集 |

**Σn = 716 題、37 塊、rows = 716 × 3 = 2,148 列**（rows 的定義：一題一臂一列）。

### 一-1　為什麼 LCB 只切 `difficulty`，不切別的

`platform` 這個欄位在三個 LCB bank 上**都只有 `leetcode` 一個值**（189/189，實跑見 §九-2）
⇒ **平台切不出第二層**，這一條要照實講，不能寫成「支援平台分層」。
`contest_year` 可以切，但與 difficulty 交叉之後最小的格子只有 25 題，n=25 的配對檢定
什麼都量不到 ⇒ 不做。
MBPP+／HumanEval+ 兩側**沒有任何平台原生標籤**（`family` 是 `_label_family` 的關鍵詞
啟發式，它的 docstring 自己寫著「不是語意真相」）⇒ 不准拿它切層，
`--bank-filter` 的 key 白名單在程式裡就只認 `difficulty`／`platform`、只認 LCB
（`tests/test_bank_filter_r529.py`）。

### 一-2　HumanEval+ 為什麼是 **156** 不是 164——八題的排除，逐題有名字有理由

`GAIN_HUMANEVAL_EXCLUSIONS`（`ops/gain/gain_run.py`，逐題釘死、有測試）。
與 MBPP+ 的七題同一條規則（「參考解自己要能在**宣稱的產品信封**裡跑完」），
但**成因有三種，不准全掛在『資源』名下**。全部在 **vacant-dev**（真的要跑實驗的那台）
序列量過，逐題輸出見 §五-1：

| 成因 | 題 | 量到什麼 |
|---|---|---|
| **(a) 允許清單／沙箱能力**（3 題） | `HumanEval/39`（`random`）、`HumanEval/162`（`hashlib`）、`HumanEval/160`（`eval()`） | 0.00 秒就被擋。前兩個不在 `_GAIN_ALLOWED_IMPORTS` 裡；第三個是三條臂的 prompt **逐字禁止**的東西。⚠ 這三題連 **`visible_check` 都過不了** ⇒ CONFORM／HMIX 的**出貨閘門在它們身上不存在**，留著＝讓三條臂在沒有閘門的題上比 |
| **(b) 記憶體信封**（4 題） | `HumanEval/83`、`/100`、`/130`、`/139` | 128 MiB。逾時放寬到 **60 秒一樣不過**（實測），所以不是「機器慢」，是那些 plus 輸入要的整數／串列放不進信封 |
| **(c) 時間餘裕不足**（1 題） | `HumanEval/15` | 過得了，但要 **5.8–7.6 秒／10 秒**。門檻＝**2× 餘裕**，寫在資料之前 |

(c) 的門檻要說清楚它為什麼是門檻而不是潔癖：`--gauge-scope bank --probe-sample 0`
是**硬擋**（參考解有一題不過，整塊拒跑）；而且同一個 10 秒沙箱也是三條臂的計分路徑
——正確的候選在那一題上同樣要 6 秒，機器一忙就會被判錯，那量到的是沙箱不是模型。
⚠ **這個門檻對 `evalplus` 是 no-op**：那 371 題在同一台機器上最慢 2.98 秒
（§五-1），所以本輪**沒有**改動 `GAIN_EVALPLUS_RESOURCE_EXCLUSIONS` 一個字。

### 一-3　本輪**沒有**做的事（誠實地列出來，別讓它看起來像做過）

- **合成六族（builtin）不在這一輪。** v1 抓到的兩個 loader 缺陷已修（無限池護欄），
  但它們仍然缺 `entry_point` 與參考解 ⇒ 量具 covered=0 ⇒ 照「量不到不是通過」拒跑。
  另一位代理正在補，補完當**第二階段**，不併進本 run。
- **X1 三族不在這一輪。** 它們只有隱藏 `check`、沒有 `visible_check`，而
  CONFORM 與 H-MIX 的**出貨閘門就是 `visible_check`** ⇒ 沒有它兩條臂都不成立。

---

## 二、37 塊、三顆 seed、逐塊註冊行

### 二-1　seed（取樣規則，事前寫死）

```
SEED_AUTHORIZED_SET: g-r529-lcb3 <- NONE
SEED_AUTHORIZED_SET: g-r529-mbpp <- NONE
SEED_AUTHORIZED_SET: g-r529-he <- NONE
```

- **`g-r529-lcb3`**（S1＋S2 共用）。共用一顆 seed **不會**讓兩層重疊：
  `load_tasks` 是「先依 seed 決定性排序 → **再切層** → 才 `ts[offset:offset+n]`」，
  而 hard 與 medium 是 `difficulty` 的一個**分割**（54 ＋ 135 ＝ 189，交集為空，
  `tests/test_bank_filter_r529.py::test_lcb3_difficulty_strata_partition_the_bank_exactly` 逐條驗）。
- **`g-r529-he`**（S3）、**`g-r529-mbpp`**（S4）：各自整個題庫跑滿，
  塊靠 offset 互斥，尾塊取餘數（16／11）。

### 二-2　逐塊註冊行（**發射器與排程器都逐字比對這幾行**）

格式是 `R529_BLOCK: <name> bank=<bank> filter=<filter|-> n=<n> offset=<offset> seed=<seed>`。
**整組**比對而不是逐項：四個題目集裡到處都是 `--offset 0`、`--n 20`，逐項比對會讓
「lcb3-hard 的 offset 0」通過「evalplus 的 offset 0」那一行 ⇒ 打錯一個欄位照樣發得出去。
Python 側在 `ops/gain/schedule_queue.registration_line`，shell 側在
`ops/gain/launch_r529_block.sh` 的 `REG_LINE`，兩份實作同一個格式，
`tests/test_r529_queue_scheduler.py::test_shell_launcher_builds_the_same_registration_line` 對釘。

```
R529_BLOCK: g_r529_lcb3m_a1 bank=lcb3 filter=difficulty=medium n=20 offset=0 seed=g-r529-lcb3
R529_BLOCK: g_r529_lcb3m_a2 bank=lcb3 filter=difficulty=medium n=20 offset=20 seed=g-r529-lcb3
R529_BLOCK: g_r529_lcb3m_a3 bank=lcb3 filter=difficulty=medium n=20 offset=40 seed=g-r529-lcb3
R529_BLOCK: g_r529_lcb3m_a4 bank=lcb3 filter=difficulty=medium n=20 offset=60 seed=g-r529-lcb3
R529_BLOCK: g_r529_lcb3m_a5 bank=lcb3 filter=difficulty=medium n=20 offset=80 seed=g-r529-lcb3
R529_BLOCK: g_r529_lcb3m_a6 bank=lcb3 filter=difficulty=medium n=20 offset=100 seed=g-r529-lcb3
R529_BLOCK: g_r529_lcb3m_a7 bank=lcb3 filter=difficulty=medium n=15 offset=120 seed=g-r529-lcb3
R529_BLOCK: g_r529_lcb3h_a1 bank=lcb3 filter=difficulty=hard n=20 offset=0 seed=g-r529-lcb3
R529_BLOCK: g_r529_lcb3h_a2 bank=lcb3 filter=difficulty=hard n=20 offset=20 seed=g-r529-lcb3
R529_BLOCK: g_r529_lcb3h_a3 bank=lcb3 filter=difficulty=hard n=14 offset=40 seed=g-r529-lcb3
R529_BLOCK: g_r529_hep_a1 bank=humanevalplus filter=- n=20 offset=0 seed=g-r529-he
R529_BLOCK: g_r529_hep_a2 bank=humanevalplus filter=- n=20 offset=20 seed=g-r529-he
R529_BLOCK: g_r529_hep_a3 bank=humanevalplus filter=- n=20 offset=40 seed=g-r529-he
R529_BLOCK: g_r529_hep_a4 bank=humanevalplus filter=- n=20 offset=60 seed=g-r529-he
R529_BLOCK: g_r529_hep_a5 bank=humanevalplus filter=- n=20 offset=80 seed=g-r529-he
R529_BLOCK: g_r529_hep_a6 bank=humanevalplus filter=- n=20 offset=100 seed=g-r529-he
R529_BLOCK: g_r529_hep_a7 bank=humanevalplus filter=- n=20 offset=120 seed=g-r529-he
R529_BLOCK: g_r529_hep_a8 bank=humanevalplus filter=- n=16 offset=140 seed=g-r529-he
R529_BLOCK: g_r529_mbpp_a1 bank=evalplus filter=- n=20 offset=0 seed=g-r529-mbpp
R529_BLOCK: g_r529_mbpp_a2 bank=evalplus filter=- n=20 offset=20 seed=g-r529-mbpp
R529_BLOCK: g_r529_mbpp_a3 bank=evalplus filter=- n=20 offset=40 seed=g-r529-mbpp
R529_BLOCK: g_r529_mbpp_a4 bank=evalplus filter=- n=20 offset=60 seed=g-r529-mbpp
R529_BLOCK: g_r529_mbpp_a5 bank=evalplus filter=- n=20 offset=80 seed=g-r529-mbpp
R529_BLOCK: g_r529_mbpp_a6 bank=evalplus filter=- n=20 offset=100 seed=g-r529-mbpp
R529_BLOCK: g_r529_mbpp_a7 bank=evalplus filter=- n=20 offset=120 seed=g-r529-mbpp
R529_BLOCK: g_r529_mbpp_a8 bank=evalplus filter=- n=20 offset=140 seed=g-r529-mbpp
R529_BLOCK: g_r529_mbpp_a9 bank=evalplus filter=- n=20 offset=160 seed=g-r529-mbpp
R529_BLOCK: g_r529_mbpp_a10 bank=evalplus filter=- n=20 offset=180 seed=g-r529-mbpp
R529_BLOCK: g_r529_mbpp_a11 bank=evalplus filter=- n=20 offset=200 seed=g-r529-mbpp
R529_BLOCK: g_r529_mbpp_a12 bank=evalplus filter=- n=20 offset=220 seed=g-r529-mbpp
R529_BLOCK: g_r529_mbpp_a13 bank=evalplus filter=- n=20 offset=240 seed=g-r529-mbpp
R529_BLOCK: g_r529_mbpp_a14 bank=evalplus filter=- n=20 offset=260 seed=g-r529-mbpp
R529_BLOCK: g_r529_mbpp_a15 bank=evalplus filter=- n=20 offset=280 seed=g-r529-mbpp
R529_BLOCK: g_r529_mbpp_a16 bank=evalplus filter=- n=20 offset=300 seed=g-r529-mbpp
R529_BLOCK: g_r529_mbpp_a17 bank=evalplus filter=- n=20 offset=320 seed=g-r529-mbpp
R529_BLOCK: g_r529_mbpp_a18 bank=evalplus filter=- n=20 offset=340 seed=g-r529-mbpp
R529_BLOCK: g_r529_mbpp_a19 bank=evalplus filter=- n=11 offset=360 seed=g-r529-mbpp
```

佇列的機器可讀版在 `ops/gain/queues/r529_cross_bank.json`（37 塊，
`schedule_queue.py --check` 逐行對這份 DECISION 驗，CI 也驗）。
**佇列順序**＝上表由上而下：`lcb3-medium → lcb3-hard → humanevalplus → evalplus`
（Fable 裁決第 6 點；把最能回答 R460 §九 推翻條件的那兩集排在最前面，
機時被砍的時候先拿到的是最有資訊的那一段）。

### 二-3　逐塊指令（`<...>` 取上表，其餘 37 塊完全相同）

```
python3 ops/gain/gain_run.py \
  --out runs/<NAME> --n <N> --offset <OFFSET> \
  --decision DECISION_20260911_R529_CROSS_BANK_PREREG.md \
  --seed <SEED> --arms OFF,CONFORM,HMIX --bank <BANK> <--bank-filter <FILTER>> \
  --record-bank-field --models gemma-4-12b-it-qat \
  --probe-sample 0 --gauge-scope bank \
  --request-timeout-s 900 --review-timeout-s 380 --retries 4
```

- **`--request-timeout-s 900`**（Fable 裁決第 7 點）。1004 歷史最長的**成功**呼叫是
  595 秒；R460R 用的 1200 秒在 a3 那一塊上讓一次掛死白燒了 1.33 小時。
  900 秒＝595 的 1.5 倍，留得住已知的長尾、砍得掉那條無限等待。
  ⚠ **R460R 現行的塊不動**，它們仍然是 1200（那是 R460R 註冊過的實驗條件）。
- **`--record-bank-field`**（本輪新增的旗標）。一個佇列跨四個題目集，其中兩集有
  `--bank-filter`、兩集沒有 ⇒ 若「bank 欄只在切層時出現」，同一個 run 的四集 rows
  會有兩種形狀。但**不能**改成無條件落盤：R460R 的 18 塊正排在同一份 `gain_run.py`
  底下依序發射，它們的 `rows.jsonl`／`summary.json` 形狀一格都不准變
  ⇒ 做成顯式旗標，R529 的發射器每一塊都給，R460R 的發射器不給。

### 二-4　與 R460／R460R 的差異，逐項與理由

| 項 | R460／R460R | R529 | 為什麼 |
|---|---|---|---|
| 臂 | 六臂 `OFF,CONFORM,OFF5,HPI,HOC,HMIX` | **三臂 `OFF,CONFORM,HMIX`** | 本 run 問的是「**單一效果**跨題庫穩不穩」，不是「哪條 harness 比較好」。OFF 是錨、CONFORM 是同預算最強的選擇規則、HMIX 是待測迴圈。砍掉三條臂省下 **69%** 的 token 負載（46,279 → 14,395 token/題），那正是換到四個題目集的機時 |
| 題庫 | 單一 `lcb2` 120 題 | **四個互斥題目集、三個真來源、716 題** | 這是本 run 的全部重點 |
| seed | 一顆／五顆，都在同一批題上 | 三顆，**換的是題目不是 seed** | R460R 換 seed 不換題目；本 run 反過來。兩者互補 |
| 主指標 | 逐題庫 McNemar，家族 6 | **跨題庫分層合併的精確配對檢定**，家族 **2**（§六-2） | Fable 裁決第 3 點。逐題庫只當次指標 |
| `--request-timeout-s` | 1200 | **900** | Fable 裁決第 7 點 |
| 併發 | 1004×3 | **1004 第 4 格 1 槽起跑，R460R 收完後擴到 4 槽** | §八 |

---

## 三、取樣規則的不變量（發射前可驗，零模型呼叫）

1. **四個題目集兩兩零交集**，聯集恰好 716 個 `task_id`。
2. **每個題目集之內，塊與塊零交集**，聯集恰好等於該集的 n（135／54／156／371）。
3. S1 的每一題 `family == "lcb_leetcode_medium"`；S2 的每一題 `family == "lcb_leetcode_hard"`
   （`family` 是從釘死的題庫算出來的，**run 目錄名可以打錯，收官只認 `family`／`task_id` 前綴**）。
4. S3 的 `task_id` 全部以 `humanevalplus_` 開頭、且都不在 `GAIN_HUMANEVAL_EXCLUSIONS` 裡；
   S4 的全部以 `mbppplus_` 開頭、且都不在 `GAIN_EVALPLUS_RESOURCE_EXCLUSIONS` 裡。
5. 三顆 seed 在**所有** `runs/*/summary.json`（本機與 vacant-dev 兩邊）裡命中集合＝`NONE`。

五條的重算腳本逐字在 §九-2。**任何一條不成立就不准發射**——
取樣錯了而還是跑完了，長得跟跑對了一模一樣。

---

## 四、事前預測——**逐題庫寫死，先寫在資料之前**

錨一律是 R460 在 lcb2 的實測值。**錨不是門檻。**

| # | 預測 | 仲裁欄位 | R460 錨 |
|---|---|---|---|
| **P-X1** | 四個題目集**全部** Δ_C > 0 | `paired.<set>.HMIX_vs_CONFORM.delta_pp` | +13.33pp |
| **P-X2** | 四個題目集**全部** Δ_O > 0 | `paired.<set>.HMIX_vs_OFF.delta_pp` | +25.83pp |
| **P-X3** | **MBPP+ 與 HumanEval+ 的 Δ_C 都小於 LCB v3 兩層的最小值** | 同 P-X1 | —（理由見 §四-1） |
| **P-X4** | 假交付 H-MIX < CONFORM，四集皆然 | `per_arm.<set>.HMIX.false_delivery_pp` vs CONFORM | 14 件 vs 29 件 |
| **P-X5** | token/題 H-MIX ≤ **1.2 ×** CONFORM，四集皆然 | `tokens.<set>.HMIX.tokens_per_task ÷ …CONFORM…` | 0.978× |
| **P-X6** | **hard 層的 Δ_C ≥ medium 層的 Δ_C**（lcb3 之內） | S2 vs S1 的 `delta_pp` | R460 G4：H-MIX 90.3/75.0、CONFORM 77.8/60.4 ⇒ 難題差距更大 |
| **P-X7** | 呼叫/題 H-MIX ∈ [1.2, 2.5]，四集皆然 | `per_arm.<set>.HMIX.calls_per_task` | 1.36 |
| **P-X8** | 每一塊 `infra_void / processed ≤ 5%` | 逐塊 summary | R460 六塊全 0 |

### 四-1　**寫在資料之前的區間預期**（逐集，含理由）

| 題目集 | 我預期的 Δ_C | 理由 |
|---|---|---|
| `lcb3_hard`(54) | **+8 ~ +20pp，區間最寬** | 與 R460 的 lcb2-hard 最像（同來源、同難度標籤）。R460 G4 的 hard 差距（75.0 − 60.4 = +14.6pp）是最接近的錨。⚠ 但 n 只有 54 ⇒ 未調整區間預期會有 ±20pp 等級的寬度；而且 v3 的日期窗更早（全部 ≤2024-08-10）⇒ 污染風險較高 ⇒ 兩臂的基礎正確率都會抬高 ⇒ 天花板效應會**壓縮**差距。**兩個方向相反的力量同時在，所以這一格的點估計不可解讀** |
| `lcb3_medium`(135) | **+3 ~ +14pp** | R460 G4 的 medium 差距是 90.3 − 77.8 = +12.5pp，但那是 hard 佔 40% 的 bank；v3 medium 更簡單 ⇒ CONFORM 自己就接近天花板 ⇒ 迴圈能救的題變少 |
| `humanevalplus`(156) | **0 ~ +8pp，增益應**縮小 | HumanEval 是**函式簽名＋docstring＋doctest 範例**的補全題，比 LeetCode 競賽題簡單得多 ⇒ OFF 的基礎正確率遠高於 LCB 的 58% ⇒ **天花板效應**。而且它的 docstring 裡本來就有 2–3 個 worked example ⇒ 「把失敗原文貼回去讓它改」能補的資訊，題目自己已經先給了一部分 |
| `evalplus`(371) | **0 ~ +8pp，且我預期它是四集裡最小的那一個** | 三個獨立的收緊力量：①R460 §七 逐字寫著 MBPP+ 的回饋訊息天生較差（HARNESS_STUDY §3.3）⇒ 迴圈拿到的資訊少 ⇒ 增益的主要來源被削弱；②MBPP+ 簡單 ⇒ 天花板效應；③每題可見測資 3–7 條、隱藏＝可見＋plus ⇒ **可見測資佔 GT 的比例比 LCB 高**，迴圈朝可見測資過擬合的空間反而**小**（這一條方向與②相反，寫下來是因為它會讓假交付**降**而不是升——見 P-X4）。⚠ 但 n=371 是四集裡最大的 ⇒ **最小的效果配最大的檢定力**，「它顯著而 hard 不顯著」不等於「效果在簡單題上比較大」 |

### 四-2　**過擬合風險的方向，事前講清楚**

R460 §六 的 P-H4 預測「假交付會升」而實測**降**（29 → 14），R460 §四把它記成
「預測寫錯方向」。本 run 沿用**實測那個方向**當預期（P-X4），但要分開講兩件事：

- **可見測資多**（MBPP+ base 3–7 條、HumanEval+ base 中位數 7 條）⇒ 迴圈朝可見測資
  過擬合仍然會被 plus／hidden 抓到 ⇒ 假交付降。
- **可見測資少**才是風險。本 run 四集裡**可見測資最少的是 LCB v3**
  （`visible_tests` 最少 2 條，`hidden_tests` 最少只有 **5** 條——
  v1 的 hidden 是每題固定 24 條、v2 是 21–24 條，**v3 的下界低得多**）。
  ⇒ **若 P-X4 要在哪一集翻車，事前預期是 `lcb3_hard` 或 `lcb3_medium`，
  不是 MBPP+／HumanEval+。** 這一句寫在資料之前，收官不准反過來說
  「本來就預期簡單題會過擬合」。
- **v3 的 hidden 下界只有 5 條 ⇒ 那一集的 GT 比另外兩集弱。**「在 v3 上量到的增益」
  與「在 MBPP+／HumanEval+ 上量到的增益」**不是同一把尺量出來的**，
  §一一-3 會再講一次；跨集比較只准比**方向**。

### 四-3　檢定力（`vacant.research.mcnemar_power`，R460 實測形狀當真值）

以 R460 的 HMIX vs CONFORM 形狀（b/c = 22/6 於 n=120 ⇒ `p_disc`=0.2333、ψ=0.7857）：

| 題目集 | n | α=0.05 | α=0.025（Holm 家族 2 最嚴的那一格） |
|---|---:|---:|---:|
| `lcb3_hard` | 54 | 0.435 | 0.337 |
| `lcb3_medium` | 135 | 0.885 | 0.829 |
| `humanevalplus` | 156 | 0.930 | 0.889 |
| `evalplus` | 371 | 1.000 | 0.999 |
| **主指標（四集合併的不一致對）** | 716 | **1.000** | **1.000** |

若真效果只有 +10pp（`p_disc`=0.25、ψ=0.70）：n=54 → 0.224、n=135 → 0.586、
n=156 → 0.664、n=371 → 0.970、合併 716 → **0.999**（α=0.025）。
若只有 +5pp（`p_disc`=0.25、ψ=0.60）：n=54 → 0.040、n=135 → 0.108、n=156 → 0.126、
n=371 → 0.342、合併 716 → **0.645**（以上都是 α=0.025 那一欄）。

**⇒ 事前就說死兩件事：**
1. **主指標（合併）在 +10pp 的真值下檢定力 0.999、+5pp 之下 0.645**
   （α=0.025＝Holm 家族 2 最嚴那一格）——這是把家族從 10 縮到 2、
   並且把檢定放在合併層級換來的（Fable 裁決第 3 點）。
   ⚠ 0.645 **不是**「很有把握」：真效果若真的只有 +5pp，本 run 有三分之一的機會
   量不到它。事前這樣寫，收官就不准把「沒過」講成「效果不存在」。
2. **`lcb3_hard` 這一格（次指標）在 +10pp 的真值下只有 0.15 檢定力**（α=0.025），
   它「看起來不顯著」是設計的已知代價（v3 的 hard 只有 54 題，加不了），
   不是「效果在難題上消失」。R460 §六-(7)-5 的禁令逐字照舊：
   **不准把不顯著讀成「等價」「打平」「迴圈沒用」。**

---

## 五、量具與 V/GT 稽核計畫

### 五-1　**發射前已經量過了**（2026-09-11，在 vacant-dev 上，序列、零模型呼叫、零網路）

紀律：對**整個題庫**裡有參考解的題目驗兩個方向（參考解要過、壞樁要被擋），
hidden 與 visible 兩側各驗一次；再獨立驗一次「**本塊**每一題都有 `visible_check`」
（`coverage_visible_n == coverage_n`）。三條有任何一條不滿就停——**量不到不是通過**。

實測（`--gauge-scope bank --probe-sample 0` 會做的那一整套，逐題耗時落盤）：

| bank | 題數 | 有參考解（covered） | 參考解通過 | 壞樁被擋 | hidden 參考解耗時 p50／p90／max | 每塊量具牆鐘（序列） |
|---|---:|---:|---:|---:|---|---:|
| `lcb3` | 189 | **12**（手寫，`ops/gain/data/lcb_v3_probe_solutions.json`） | 12/12 | 12/12 | 0.06／0.15／0.21 s | **約 4 s** |
| `humanevalplus` | 156（排除後） | **156** | 156/156 | 156/156 | 0.36／0.59／**2.17** s | **約 114 s** |
| `evalplus` | 371 | **371** | 371/371 | 371/371 | 0.10／0.14／**2.98** s | **約 164 s** |

排除前的 HumanEval+ 164 題有 7 題參考解不過、1 題（`/15`）耗 7.58 秒，
逐題名字與成因在 §一-2；**這八題就是因為這份量測才被排掉的，不是先排再量。**

⚠ **一個非量測的實測發現，必須記下來**：同一套量具在**開發用的 Mac 上會紅**
——MBPP+ 有 2–7 題（`Mbpp/592`、`Mbpp/123` 等）在 Mac 上撞 10 秒逾時，
在 vacant-dev 上最慢只有 2.98 秒（差 3–5 倍）。
⇒ **「量具過不過」是機器相依的**，而 R529 只在 vacant-dev 上跑 ⇒ 上表成立。
但這一條要寫進誠實邊界（§一一-8）：**別人在別台機器上重跑這批塊，量具可能紅**，
那不是資料壞了，是產品信封（10 s／128 MiB）在別台機器上代表的東西不一樣。

### 五-2　`--gauge-scope bank` **不套 `--bank-filter`**（事前寫死，附理由與代價）

lcb v3 的 12 份手寫參考解難度分布是 **medium 9／hard 3**（本輪實測）。
⇒ 若量具也跟著切層，`difficulty=hard` 之下只剩 3 題有參考解（lcb v1/v2 的 12 份
更極端，**12/12 全是 medium** ⇒ covered=0 ⇒ runner 會照「量不到不是通過」正確地拒跑
⇒ 那一層永遠發不出去）。而量具驗的是**沙箱＋題庫＋計分**（參考解與壞樁都不經模型）
⇒ 對整個題庫驗**比對單層驗更強**，且與「這一塊是哪幾題」無關。

**代價要說出來，不准被總數蓋掉**：
- `lcb3_hard` 那一層只有 **3** 題被參考解直接驗過（`instrument.gauge_in_filter_n = 3`）；
- `lcb3_medium` 是 **9**（`gauge_in_filter_n = 9`）。
被驗到的是同一支 `_lcb_check_code`、同一個沙箱、同一條計分路徑，**不是那 54／135 題自己**。
runner 把 `gauge_in_filter_n` 落盤並印出來，收官要照實列這兩個數字。
⚠ 反過來，`humanevalplus` 與 `evalplus` 兩集是 **156/156**、**371/371**
——那兩集的每一題都被官方參考解直接驗過，**強度與 LCB 兩層完全不同**，
跨集比較量具強度時要記得這件事。

### 五-3　V/GT 動態稽核（`harness_vgt_audit.py --scope v2`，零模型呼叫）

每一塊跑一次，**37 塊全部 `CLEAN` 才准結算**：

```
python3 ops/gain/harness_vgt_audit.py --run runs/<block> \
  --bank <lcb3|humanevalplus|evalplus> --scope v2 --out ops/gain/replay/r529/vgt_v2_<block>.json
```

⚠ `--bank` 必須顯式給。稽核器讀的是**整個題庫**（`load_tasks(bank, seed, 0)`），
切層的 run 也對得上，因為它按 `task_id` 查。
✔ **`harness_vgt_audit.py` 不必改**（本輪查證）：它的 `--bank` 沒有 `choices`，
直接把字串交給 `gain_run.load_tasks`（`harness_vgt_audit.py:559-572`）
⇒ `--bank humanevalplus` 在它身上**已經可用**。
⚠ 但**還沒有在一次真的 run 上跑過**——第一塊 humanevalplus 收完時要當場跑一次驗證，
沒過就停（§一〇-3）。

**事前寫下 MBPP+／HumanEval+ 這一側的預期**（收官不准當成新發現）：
兩者的 `hidden_check` ＝ base ＋ plus，而 `visible_check` ＝ base
⇒ **base 的每一個值同時是可見的也是隱藏的**。v2 規則 (c) 的第一條
（needle 逐字在該題 `visible_check` 原始碼裡就豁免）因此會在這兩集上大量命中。
⇒ **`excused_by_rule.visible_check` 在這兩集上會遠高於 R460 的 4 筆**，
那是題庫結構不是洩漏。真正要盯的仍然是**扣掉豁免之後的 `violations`＝0**，
以及 `excused_by_rule.got_sandbox_echo` 有沒有異常放大。
**豁免數字要逐塊落盤、逐塊報**——「沒有違規」不准順手蓋掉「沒有檢查」。

### 五-4　中止準則第 3 條（沿用 R460R §八-4）

`--scope v2` 在**任何一塊**報出違規 ⇒ **整個 run 作廢**（SPEC_GAIN §7；
R460 §九 推翻條件第二條）。不得只修不報。

---

## 六、決策規則

### 六-0　配對的基本口徑（與 R460 逐字相同）

- 配對單位＝`task_id`；成功＝`deliv = accepted ∧ meets_demand`（R667 凍結口徑）。
- 分母＝**complete case**：`n_common = |rows[A].task_id ∩ rows[B].task_id|`，**逐對印**。
- 每一個題目集各自把它的塊合併（依 `offset` 排序、按 `task_id` 合併，R445／R460 §六-(0) 先例）。
- 區間＝**未調整**的 95% Clopper–Pearson 條件區間（`ops/gain/replay/paired_ci.py::diff_ci`）。
  > 每一次引用區間都必須逐字附上：**「區間未做多重比較調整；仲裁以 analyzer 為準」**。

### 六-1　**主指標＝跨題庫分層的配對精確檢定**（Fable 裁決第 3 點）

兩個對照，**家族 2**：`HMIX − CONFORM`、`HMIX − OFF`，Holm，α=0.05。

**公式與推導**（實作在 `vacant.research.stratified_mcnemar_exact`，
`tests/test_r529_stratified.py` 手算對照）：

設題目集 k ∈ {S1, S2, S3, S4}。在第 k 集裡，對每一個 `task_id` 比較兩臂的
`deliv`，得到不一致對

```
b_k = #{task : HMIX 成功 ∧ 對照失敗}
c_k = #{task : HMIX 失敗 ∧ 對照成功}
n_k = b_k + c_k
```

H0：**每一集都沒有效果**（集內兩臂的成敗機率對稱）。以 `n_k` 為條件，
`b_k ~ Binomial(n_k, 1/2)`，且各集獨立（不同題目、不同 run 目錄）。
獨立的 `Binomial(n_k, 1/2)` 之和仍是二項：

```
B = Σ_k b_k ~ Binomial(N, 1/2),   N = Σ_k n_k
p = 2 · P(Binomial(N, 1/2) ≤ min(B, N−B))      （雙尾，精確）
```

這就是 1:1 配對、共同勝算比之下 **CMH 精確條件檢定**的那一個統計量。

> ⚠ **誠實邊界，收官必須原樣帶著**：上面這個統計量與「把四集的不一致對直接加起來
> 做一次 `mcnemar_exact`」**在數值上完全相同**。分層在這裡買到的**不是**更嚴的檢定，
> 而是三件別的事：(a) H0 是「每一集都沒有效果」——拒絕它只說「至少某集有」，
> 不說「每集都有」，更不說效果量是多少；(b) 逐集的 `b_k/c_k` 必須照實列出來
> （analyzer 一起印）；(c) 異質性另外量（§六-3），而且是**描述性**的。
> **不准**把它寫成「我們做了分層校正所以比較穩」。

仲裁欄位：`primary.<pair>.b`／`.c`／`.n_discordant`／`.p`／`.p_adj`／
`primary.family_size`（**必須等於 2**）／`primary.per_stratum[k].{b,c,p}`。

⚠ 家族固定 2，**不准**因為某一集 void 太多、或某一集「反正一定不顯著」就抽掉它
再重算 N。抽掉一集要走的是 §一〇-2（那一集 INVALID，而且要在主指標旁邊
**逐字說明 N 少了多少**）。

### 六-2　次指標（**描述性，不下裁決**）

`ops/gain/analyze_r529.py` 印五樣，一樣都不准少：

1. **逐題庫的配對差**：`paired.<set>.<pair>.delta_pp`、`b`、`c`、`n_common`，
   以及**未調整**的 95% 區間（沿用 R460 的區間法，§六-0）。
   ⚠ 逐題庫**不給裁決**，只給數字（Fable 裁決第 3 點逐字）。
2. **方向一致計數**：`aggregate.direction_agree_c`＝四集裡 Δ_C > 0 的個數
   （Δ_O 同）。**Δ 恰好等於 0 的那一集計入分母不計入分子。**
3. **異質性檢查**：四集的 `b_k` vs `c_k` 排成 2×4 表做卡方
   （`vacant.research.bc_heterogeneity_chisq`，df=3）。
   ⚠ **寫死當描述**：沒有精確版本、期望次數小的時候卡方近似本來就不準
   （`min_expected` 一起印，< 5 要在報告裡講）。它只准當「要不要多看幾眼」的提示，
   **不進 Holm 家族、不改任何一格裁決**。
4. **逐題庫的 token/題與 calls/題**（`tokens.<set>.*`、`per_arm.<set>.*`）。
5. **`refutation.*`**：見 §六-5。

**沒有隨機效應模型、沒有 meta-analysis、沒有合併效果量。**
四集的點估計**不准平均**——四集的難度組成、來源、n、量具強度都不同。

### 六-3　四狀態：**本研究自訂，並在資料前凍結**

⚠ 這一節與 R460 §六-(4) 的同名狀態**不是同一個東西**（本 run 沒有 OFF5 臂，
(iii) 的仲裁值不存在）。所以本檔**不沿用**那套定義，改成下面這一套，
**逐字凍結在資料之前**，收官不准改一個字；引用時必須寫「R529 四狀態」，
不得與 R460 的 `EFFECTIVE` 互引。

| 狀態 | 條件（全部成立） |
|---|---|
| **INVALID** | 任一塊 `--scope v2` 報違規（§五-4）；或 §一〇 的中止準則觸發到整個 run |
| **EFFECTIVE** | (i) **兩個主指標** Holm 後都 `p_adj < 0.05`（`HMIX−CONFORM` 與 `HMIX−OFF`）**且** (ii) **合併資料**裡 `tokens.pooled.HMIX.token_per_correct ≤ tokens.pooled.CONFORM.token_per_correct` |
| **COSTLY_BUT_REAL** | (i) 成立、(ii) 不成立（tpc 高於 CONFORM） |
| **RULED_OUT** | 逐字沿用 R460 §六-(4)：主指標的點估計方向反了（`b < c`）**且** 該方向的 `p_adj < 0.05` |
| **INCONCLUSIVE** | 以上皆非（含「方向對但沒過 Holm」） |

- `token_per_correct` 的定義沿用 R460：`tpc = Σ token ÷ #{deliv 成功}`，
  **含 void 的那一版**（`tpc_incl_void`），逐集與合併都印。
- **(ii) 用「合併資料」是本檔唯一一處把四集加起來算比值的地方**，
  而且它只用來判一個布林值，**不准**被引用成「H-MIX 的成本是 CONFORM 的 x 倍」
  ——那個比值在四集之間差很多（§六-2 第 4 項逐集印）。
- **代用值禁令照舊**：不准用「OFF5 的成本本來就是 OFF 的 5 倍」造一個代用值
  去補一個本 run 沒有的臂。`tokens.<set>.tpc_off5_surrogate`（＝ 5 × OFF 的 tpc）
  可以印在附表，旁邊必附「代用值，不進裁決」。

### 六-4　**本 run 真正的主要產出：R460 §九 第一條的推翻鍵**

R460 §九 第一條逐字：「若在 LCB v3（189 題，零交集）預註冊複製 H-MIX vs CONFORM
而 **c ≥ b** ⇒ 本判定降為『一次顯著』」。

- **觸發鍵（事前寫死）**：`paired.lcb3_hard.HMIX_vs_CONFORM` 或
  `paired.lcb3_medium.HMIX_vs_CONFORM` 任一出現 **c ≥ b** ⇒ **觸發**
  ⇒ R460 的 `EFFECTIVE` 降為「一次顯著」，並且要在
  `examples/verdicts.py` 與官網資料源同步改口徑。
- MBPP+／HumanEval+ **不是**這條的觸發鍵（R460 §九 寫的是 LCB v3），
  但它們出現 c ≥ b 同樣要逐字報出來，記在 `refutation.<set>_c_ge_b`。
- 這一鍵**先於**四狀態印出來（`refutation.triggered`），
  免得收官時被一堆數字淹掉。

### 六-5　宣稱規則（事前寫死，`aggregate.statement_rule`）

> **主指標兩格都 `p_adj < 0.05`，且 `direction_agree_c == 4`
> ⇒ 可以寫「這個效果在三個來源、四個互斥題目集上方向一致，合併後在配對精確檢定下顯著」；
> 主指標成立但方向不是 4/4 ⇒ 必須逐集列出方向並指名哪一集反向；
> 主指標任一格不成立 ⇒ 逐集照實列，不准寫「多數支持」。**

判到哪一句就逐字印在 `aggregate.statement`。

### 六-6　預算

rows 的定義：一題一臂一列。三臂 × 716 題 ＝ **2,148 列**。

| 項 | 中心估計 | 上界 | 依據 |
|---|---:|---:|---|
| 模型呼叫 | **2,850** 通 | 7,876 通 | 中心＝R460 實測 (OFF 1.00 ＋ CONFORM 1.62 ＋ HMIX 1.36)＝3.98 通/題 × 716；上界＝三臂都吃滿預算（1＋5＋5）× 716 |
| token | **10.3 M** | 13 M | 中心＝R460 lcb2 實測 14,395 token/題 × 716。⚠ MBPP+／HumanEval+ 的題目比 LCB 短很多 ⇒ 中心估計對那兩集是**上偏**的 |
| 量具（全部 37 塊合計） | **約 1.5 小時**算力 | — | 實測：lcb3 4 s×10 塊 ＋ humanevalplus 114 s×8 塊 ＋ evalplus 164 s×19 塊 ≈ 3,160 s／槽序列 ⇒ 一槽 0.9 h、四槽併發時牆鐘更短 |
| 牆鐘 | **約 12 小時**（5 串起跑） | 20 小時 | 見 §八-3 的逐段換算 |

**這是「未驗證的宣稱」不是結果**：上面每一格都是**估計**，收官要拿
`summary.json` 的實測回填並把差異寫出來。

---

## 七、本輪已落地的程式碼改動（發射前，零模型呼叫）

| 改動 | 檔案 | 為什麼 | 牙齒 |
|---|---|---|---|
| `EvalPlusHumanEvalLoader` | `vacant/codebench.py` | 第三個真來源。sha256／題數釘死、schema 全驗、fail-closed；**參考解＝`prompt + canonical_solution`**（HumanEval 的 canonical 是函式體），建構時逐題編譯過一次 | `tests/test_humanevalplus_loader.py`（22 項，含官方包整合門） |
| `_he_norm_inputs` | 同上 | **不准**借用 MBPP 的 `_norm_inputs`：它按 `Mbpp/<整數>` 查型別還原表，而 `HumanEval/<整數>` 也是整數 ⇒ 借用＝把 MBPP 的規則張冠李戴地套到同號的 HumanEval 題上 | `test_humaneval_inputs_are_not_run_through_the_mbpp_type_registry` |
| `_verify_evalplus_pack` | 同上 | 兩顆 loader 共用同一份 fail-closed 驗證。兩份實作＝同一道紅線有兩個版本，哪天只修了一份，另一邊會安靜地變寬 | 既有 `tests/test_evalplus_loader.py` 全數通過（訊息逐字不變） |
| `--bank humanevalplus` | `ops/gain/gain_run.py` | 接進 `load_tasks`／`_canonical_solutions`／`probe_instrument`／rows 的 bank 欄 | `tests/test_r529_humanevalplus_bank.py` |
| `GAIN_HUMANEVAL_EXCLUSIONS` | 同上 | §一-2 的八題，逐題有名字有成因 | 同上（含「不准動到 evalplus 那七題」） |
| `--record-bank-field` | 同上 | §二-3。**R460R 的 18 塊正排在同一份程式碼底下**，它們的 rows/summary 形狀一格不准變 | `tests/test_bank_filter_r529.py`＋`test_record_bank_field_*` |
| `stratified_mcnemar_exact`／`bc_heterogeneity_chisq` | `vacant/research.py` | §六-1／§六-2 的公式**要是可執行的**，不是寫在文件裡的散文 | `tests/test_r529_stratified.py`（18 項，手算對照） |
| `ops/gain/schedule_queue.py` | 新檔 | 佇列排程器：讀佇列 JSON、`--slots-now/--slots-after/--expand-when`。**沿用** R460R 排程器的純函式（狀態機、作廢規則、idempotency），**不改它一個字**。lock／log／槽名／發射器 flock 四樣全部與現行實例分開（§八-2 第 5 點的表）；**只讀 `ps`，沒有任何 `kill`／`pkill`** | `tests/test_r529_queue_scheduler.py`（53 項） |
| 擴槽要**兩類證據**（行程 ＋ 磁碟 18 塊 terminal） | 同上 | 08:14Z 抓到 R460R 排程器猝死（§八-1）⇒ 只問行程會把「排程器死了」讀成「R460R 跑完了」，人一重啟就超開 | `test_dead_scheduler_is_not_the_same_thing_as_a_finished_r460r`、`test_dry_run_does_not_expand_on_an_empty_root` |
| 每張卡 4 串的上限是**機制** | 同上 | `_assert_per_host_cap()` 在 import 時檢查槽表。多開一格在 log 上長得跟正常一模一樣，而它會讓「這批資料在什麼併發下量的」變成事後才查得到的事 | `test_per_host_cap_is_a_mechanism_not_a_discipline` |
| 重排**換一台** | 同上 | 兩台載的是逐位元相同的 gguf ⇒ R460R 那條「重排只准上 1004」不適用；一塊在某台連發 void，最可能的成因就是那台。換不到別台就這一輪跳過，不硬等（免得一個壞塊卡住整條佇列） | `test_requeued_block_avoids_the_host_it_died_on`、`test_requeued_block_is_skipped_rather_than_blocking_the_queue` |
| `<OUT>.backend_meta.json` | `ops/gain/launch_r529_block.sh` | 兩台的 LM Studio 版本不同（0.4.24.0／0.4.17.0）⇒ 每一塊都要說得出自己跑在哪一台、那台是什麼版本。**`declared`（人回報）與 `probed_models`（這一塊自己 curl 到的）分開記** | `test_queue_declares_both_backends_with_version_provenance`、`test_launcher_records_backend_meta_per_block` |
| `ops/gain/launch_r529_block.sh` | 新檔 | R529 全部塊唯一的發射入口。preflight 逐條沿用 R460R 那一支，另加**整組註冊行比對** | 同上 |
| `ops/gain/queues/r529_cross_bank.json` | 新檔 | 37 塊的機器可讀佇列。`--check` 逐行對這份 DECISION 驗 | `test_every_queue_block_is_registered_in_the_decision` |
| `runs/INDEX.md`／`INDEX.json` 重建 | `ops/gain/build_runs_index.py` | 索引釘在 44、實際 50 ⇒ `--check` 一直紅（v1 §九-5 記的已知未償） | `tests/test_runs_index.py` 釘值更新為 50，`--check` 過 |
| 索引掃描排除 `.claude/` | 同上 | 重建時抓到的**新問題**：`.claude/worktrees/*` 是別的 agent 的 git worktree（同一個 repo 的另一個 checkout），`rglob` 會把裡面的裁決檔也掃進來 ⇒ 同一份裁決出現兩次、而且第二份的路徑在別人機器上不存在 ⇒ **索引變成機器相依**、`--check` 隨「現在有沒有人開著 worktree」而紅 | `tests/test_runs_index.py::test_headline_must_be_about_this_run` |
| 三支**發射前閘門**測試改寫 | `tests/test_r449b_launcher_prereg.py`／`test_r449c_…`／`test_r448_…` | 它們斷言「這顆 seed 還沒被用過」「這個 run 目錄還不存在」——那三個 run 早就跑完了，所以從發射那一刻起永遠是紅的。**留著一條註定紅的測試比沒有測試更糟**：真的 seed 重用會被淹在「大家都知道會紅」底下 | 改成「這顆 seed 只准出現在它自己那個 run 裡」＋「目錄存在就必須帶 summary.json」——牙齒是同一顆，而且發射前後都成立 |

**沒有動到的**：`arm_off`／`arm_off5`／`arm_conform`／`arm_eq5`／`arm_on`／`arm_onr`／
`extract_code`／`meets_demand`／`behavior_signature`／`conform_failure_detail`／
`_visible_test_slicer`／`ClineBrain.generate` —— T12 的原始碼 sha 釘死
（`tests/test_gain_harness_arms.py`）全數通過。
**`ops/gain/harness_arms.py` 一個字沒改。**
**`ops/gain/schedule_harness_reps.py` 一個字沒改**（R460R 正在它底下跑）。
**`GAIN_EVALPLUS_RESOURCE_EXCLUSIONS` 一個字沒改**（§一-2 的 2× 門檻對它是 no-op）。

### 七-1　發射前**沒有**做完的事（逐條，並且說清楚它擋不擋發射）

1. **`ops/gain/analyze_r529.py` 不存在。** `analyze_r460.py` 寫死
   `H_ARMS = ("HPI","HOC","HMIX")` 且要求 `holm.family_size == 6`，在三臂四集上
   跑不出正確的仲裁值。R529 需要自己的 analyzer（仲裁欄位的規格逐字在
   §六-1／§六-2／§六-3），並且要有 `--selftest`（在 R460 六塊上對釘已知答案）
   與 `--mutation-check`。
   ⚠ **這一條擋不擋發射，是 Fable 要裁的。** 我的判斷與理由：
   **不擋。** analyzer 只讀已落盤的 `rows.jsonl`，寫它晚一點**不會改變落盤的任何一格**；
   而仲裁欄位與門檻已經逐字凍結在本檔，所以「看過數字再寫 analyzer」能動的空間
   只剩實作 bug，而那由 `--selftest` 與 `--mutation-check` 擋。
   反過來說，v1 自己寫過「這支寫完之前不准發射」——那是 v1 的自我約束，
   我把它改成「**結算前**必須寫完」並把理由攤在這裡，請 Fable 裁決要不要改回去。
2. **`harness_vgt_audit.py` 在 `humanevalplus` 上沒有真跑過。** 程式上已經可用
   （§五-3），但「可用」與「驗過」不是同一件事 ⇒ 第一塊收完時當場跑一次。
   **不擋發射**（它是離線稽核，跑完再稽核完全等價）。
3. **人類尚未看過本檔。**

---

## 八、後端與併發：**5 串起跑（1003×4 ＋ 1004×1），R460R 收完後 8 串**

### 八-0　後端（2026-09-11 08:52Z 之後的條件，逐條）

| | 1003 | 1004 |
|---|---|---|
| 端點 | `http://100.119.113.56:1234` | `http://100.86.226.21:1234` |
| 模型 | `gemma-4-12b-it-qat` | `gemma-4-12b-it-qat` |
| gguf sha256 | `faff1a63667fac17ac5e777f47114688fcefea96e220e211aaa8d62c2c4561f1` | **同左，逐位元相同** |
| context／parallel | 262144／4（`--gpu max`、無 TTL） | 262144／4 |
| **LM Studio 版本** | **0.4.24.0** | **0.4.17.0** |
| 本 run 用幾格 | 4（`q1003#1`–`#4`） | 1（`q1004#4`）→ R460R 收完後 4 |

**三件事要講清楚：**

1. **版本不同是本 run 的一個已知混淆源。** 兩台載的是同一份 gguf、同樣的 context
   與 parallel，但 **LM Studio 版本不同**（0.4.24.0 vs 0.4.17.0）。
   ⇒ **逐後端拆開描述**（`per_backend.<host>.*`）：每一個 `per_arm`／`tokens`
   的絕對值都要有一份逐後端的版本。
   ⚠ **配對比較不受影響**：配對單位是 `task_id`，而**一塊之內三條臂跑在同一台**
   （一塊＝一個行程＝一個端點）⇒ `b`／`c` 是在同一台上算出來的。
   受影響的是**跨 block 的絕對值**（通過率、token/題、牆鐘），那些可能混了版本差。
2. **block 分配到哪一台由排程器先到先得，不依題庫固定。**
   若讓「lcb3 都上 1003、evalplus 都上 1004」，題庫與後端就**完全混淆**，
   到時候「MBPP+ 的增益比較小」與「0.4.17.0 比較慢」分不開。先到先得會讓
   四個題目集的塊散在兩台上；**實際分配表在跑完後寫進 launch notes**
   （每個 block 的 `slot_id`／`endpoint`／版本都落在 `<OUT>.backend_meta.json`）。
3. **版本是宣稱不是量測。** `lms version` 是在那兩台機器上執行的，本 runner
   查不到（實測：`/v1/models` 與 HTTP header 都不帶版本）。
   ⇒ `<OUT>.backend_meta.json` 記 `declared`（含 `version_source`）
   與 `probed_models`（這一塊自己 curl 到的 `/v1/models` 全文）兩份，
   **收官引用版本時必須帶著「這是回報值」**。

### 八-0a　1003 的前科與現在的條件

1003 在 2026-09-08 崩過兩次（`decode() failed: bad alloc`／
`Context size has been exceeded`）。崩因已經查明：**qwen3.8-27b 同時佔著 VRAM**，
以及 **context 被降到 49k**。現在兩者都不成立（qwen 已卸載、context 262144、
`--gpu max`）。⇒ 本 run 給它滿 4 格。
**但這是「條件改了」不是「量過了」**——1003 在新條件下**沒有跑過一次 4 併發的真跑**。
⇒ 中止準則 §一〇-7：任一塊在 1003 上 `infra_void` 連發就照既有規則作廢，
**重排時換到另一台**（排程器的 `plan_launches_queue` 會避開它死過的那一台），
不硬撐。

### 八-1　與 R460R 共用 1004

#### 現況（2026-09-11，對 vacant-dev 的唯讀查證）

- **07:00Z**：`schedule_harness_reps.py --reps 1 2 3 --hosts 1004`（pid 3089647）在跑，
  `g_r460r1_harness_lcb2_a1` 已 terminal（120 列），`a2`／`a3`／`b1` 在跑。
- **08:14Z**：本輪查證時發現**那個排程器行程已經不在了**
  （`ps -eo pid,lstart,etime,cmd | grep -F "ops/gain/schedule_harness_reps.py"` 無輸出；
  `~/vacant/logs/schedule_harness_reps.log` 最後一行停在 **07:22:57Z**，
  就是它發完 `b2` 的那一刻，之後 51 分鐘沒有再寫過一行）。
  三個 runner（`a3`／`b1`／`b2`）不受影響，仍在跑；`a1`／`a2` 已 terminal。
  ⇒ 那段空窗裡 R460R **只做了 5/18 塊**，剩下 13 塊沒有人會發。
- **08:19Z**：Fable 重啟排程器（新 pid 3104570，
  log `~/vacant/logs/schedule_harness_reps_restart_20260911T0819Z.log`）。
  排程器是 idempotent 的，重啟不影響三個 runner。

⇒ **1004 的 #1–#3 三個槽是滿的**；1003 依 R460R §一〇 修訂 A 被人類拿走，**一塊都不准上**。

⚠ **這次事故改了本檔的擴槽設計**（§八-2 第 2 點）：原本「R460R 收完」只問
「行程還在不在」。若那段空窗裡三個 runner 也剛好收完，只問行程會判成
「R460R 收完了」而擴到 4 槽——**但 R460R 其實只跑了 5/18 塊**，
人一重啟它又開三串，1004 上就變成 7 串（§一〇-5 的作廢條件）。
**「排程器死了」與「R460R 跑完了」不是同一件事。**

### 八-2　併發：現在 5 串、R460R 收完後 8 串（Fable 已裁決；量測依據寫在這裡好對帳）

1004 的 LM Studio `parallel=4`（`lms ps` 直接證實）。R460R 佔三格，
**第 4 格是真的空著**。Opus 探針量到：開第 4 串**總吞吐 +15–25%**、
**每串慢 1.21×**、**H 臂的 `budget_wall` 截斷數不變**；
**第 5、6 串（超過 `parallel`）沒有收益**。
1003 現在條件與 1004 相同（§八-0）⇒ 它自己的 4 格也可以用。
⇒ 事前寫死：

1. **R460R 還在跑 ⇒ R529 用 5 串**：`q1003#1`–`#4`（1003 自己的四格）
   ＋ `q1004#4`（1004 唯一空著的那一格）。**1004 的 #1–#3 是 R460R 的，不准碰。**
2. **R460R 真的收完 ⇒ 擴到 8 串**（再加釋出的 `q1004#1`／`#2`／`#3`）。
   「真的收完」是**兩類證據都要成立**：
   - **行程**：`schedule_harness_reps.py` 的排程器行程不在，**且**任何
     `gain_run.py --out runs/g_r460r…` 的 runner 也不在。只看排程器會漏掉
     「排程器被 kill 了但塊還在跑」，只看 runner 會漏掉「這一刻剛好沒塊在跑，
     但排程器下一輪就要發」。
   - **磁碟**：`runs/g_r460r{1,2,3}_harness_lcb2_{a1,a2,a3,b1,b2,b3}` **18 塊全部**
     `run_terminal == true` 且每臂 void ≤ 20%（`classify_summary` 判 `DONE`）。
     這一條是 08:14Z 那次事故補的（§八-1）：**排程器死了不等於 R460R 跑完了**。
   兩類都成立才擴。人類另有判斷時的顯式出口是 `--expand-when now`（留在 log 裡）。
3. **`ps` 讀不到、或磁碟證據拿不到 ⇒ 不擴**（fail closed）。**不知道不是「沒有」。**
4. **擴槽沒有閂**：每一輪重問一次。R460R 又出現就縮回 1 槽——縮回不會去停已經發出去
   的塊（停不了），但 `occupancy` 會發現「跑著的塊比槽多」⇒ 封鎖端點 ⇒ 這一輪一塊都不發。
5. **不改 R460R 的排程器。** `SLOTS`／`REPS` 是 R460R 註冊的東西
   （R460R §一〇 逐字：「表是註冊了什麼」）。R529 用**獨立的排程器實例**
   （`ops/gain/schedule_queue.py`），四樣東西全部分開：

   | | R460R（現行實例） | R529 佇列 |
   |---|---|---|
   | lock | `~/vacant/logs/.schedule_harness_reps.lock` | `~/vacant/logs/.schedule_queue_r529_cross_bank.lock` |
   | log | `~/vacant/logs/schedule_harness_reps.log` | `~/vacant/logs/schedule_queue_r529_cross_bank.log` |
   | 槽名 | `1004#1`…`1004#4`、`1003#1` | `q1003#1`…`q1003#4`、`q1004#1`…`q1004#4` |
   | 發射器 flock | `~/vacant/.launch_rep_<TAG>.lock` | `~/vacant/.launch_r529_<TAG>.lock` |

   ⚠ **新排程器與它的測試從不送訊號給任何行程**：只讀 `ps`，沒有 `kill`／`pkill`。
   擴槽條件 `r460r_presence()` 是**純函式**（`ps` 的輸出從外面餵進來），
   所以測試餵的是字串、碰不到真的行程
   （`tests/test_r529_queue_scheduler.py::test_expand_only_when_r460r_is_really_gone`）。
6. **1003 用滿 4 格**（2026-09-11 人類指示「開到最多」）。它的前科與現在的條件
   見 §八-0a；**重排換台**的規則見 §一〇-7。
7. **每張卡不得超過 4 串。** 超過 `parallel=4` 的第 5、6 串量到沒有收益。
   這條是**機制不是紀律**：`schedule_queue._assert_per_host_cap()` 在 import 時
   就檢查槽表，多開一格會當場 `SystemExit`
   （`tests/test_r529_queue_scheduler.py::test_per_host_cap_is_a_mechanism_not_a_discipline`）。

### 八-3　時間線（估計，不是承諾）

**每一格都是估計，收官要拿 `summary.json` 的實測回填並把差異寫出來。**

換算的起點是 R460 的實測：**85 rows/h ／ 3 槽（六臂）＝ 28.3 rows/h/槽**。
三臂的 token 負載輕 3.2 倍（46,279 → 14,395 token/題），但吞吐不是線性跟著 token 走
（每題還有固定的往返成本）⇒ 保守取 **1.6 倍**，即 **約 45 rows/h/槽**；
再乘上「多開一串每串慢 1.21×」的折扣。

| 階段 | 串數 | 估計吞吐 | 這一段收多少 |
|---|---:|---:|---|
| R460R 還在跑 | **5**（1003×4 ＋ 1004×1） | 5 × 45 ÷ 1.21 ≈ **185 rows/h** | R460R 估計還要約 20 小時 ⇒ 約 **2,148 列全收完**（11.6 小時） |
| R460R 收完之後 | 8 | 8 × 45 ÷ 1.21 ≈ 300 rows/h | 若前一段沒收完才會用到 |

⇒ **中心估計約 12 小時，區間 8–20 小時**（上界＝吞吐只有估計的一半）。
⚠ 這個估計比 v1 的 27 小時短了一半以上，原因**只有一個**：槽數從 1 變成 5。
量具（§六-6）另計約 1.5 小時算力，分攤在各槽上。

⚠ §一一-2 那條「那顆卡的狀態是整批資料的共同因子」（R460R §六-10）對 R529 同樣適用，
而且**變成兩顆卡**：本 run 的塊散在 1003 與 1004 上，兩台的 LM Studio 版本不同（§八-0）。
若 R460R 在中途收完、R529 從 5 串擴到 8 串，那個轉換點是**已知的**條件變化，
收官要把它標在時間軸上（`calls.jsonl` 的時間窗算得出來）。

### 八-4　給 R460R 收官的人：**併發條件在這一刻變了**

> **2026-09-11（啟動時間戳見 `~/vacant/logs/schedule_queue_r529_cross_bank.log` 第一行
> 與 `runs/g_r529_lcb3m_a1.launch.log`）起，1004 上的併發從 3 串變成 4 串。**
> 量測依據：Opus 探針，aggregate 136–145 tok/s、每串 1.21×、H 臂 `budget_wall`
> 截斷數不變。⇒ **在那個時間戳之後才發射的 R460R 塊，是在 4 併發下跑的**；
> 之前的是 3 併發。R460R 的分析若要比較塊與塊的牆鐘／延遲，必須用這個時間戳切開。
> `budget_wall` 截斷數不變是這個決定的前提——若 R460R 收官時發現後段的塊
> `budget_wall` 截斷變多，**那就是這個前提被推翻了**，要記一筆。

---

## 九、自我驗證（發射前做完，零 API、零模型呼叫）

### 九-1　三顆 seed 是新的（2026-09-11 實跑，兩台都掃）

```
python3 - <<'PY'
import glob, json
seeds = {}
for f in sorted(glob.glob("runs/*/summary.json")):
    try: seeds.setdefault(json.load(open(f, encoding="utf-8")).get("seed"), []).append(f)
    except Exception: pass
for s in ("g-r529-lcb3", "g-r529-mbpp", "g-r529-he"):
    print(s, "->", seeds.get(s))
print("g_r529* 目錄:", glob.glob("runs/g_r529*"))
PY
```

實跑：本機掃過 **50** 個、vacant-dev 掃過 **54** 個 `runs/*/summary.json`，
三顆 seed 在兩台都是 `None`；兩台的 `runs/g_r529*` 目錄都是 **0** 個。

### 九-2　§三 的五條取樣不變量可重算

```
python3 - <<'PY'
import sys; sys.path.insert(0, ".")
from ops.gain.gain_run import (load_tasks, GAIN_EVALPLUS_RESOURCE_EXCLUSIONS,
                               GAIN_HUMANEVAL_EXCLUSIONS, bank_strata)
S = {}
S["lcb3_medium"] = load_tasks("lcb3", "g-r529-lcb3", 0, bank_filter="difficulty=medium")
S["lcb3_hard"]   = load_tasks("lcb3", "g-r529-lcb3", 0, bank_filter="difficulty=hard")
S["humanevalplus"] = load_tasks("humanevalplus", "g-r529-he", 0)
S["evalplus"]      = load_tasks("evalplus", "g-r529-mbpp", 0)
ids = {k: {t["task_id"] for t in v} for k, v in S.items()}
print({k: len(v) for k, v in ids.items()}, "Σ =", len(set().union(*ids.values())))
for a in ids:
    for b in ids:
        if a < b: assert not ids[a] & ids[b], (a, b)
assert all(t["family"] == "lcb_leetcode_medium" for t in S["lcb3_medium"])
assert all(t["family"] == "lcb_leetcode_hard"   for t in S["lcb3_hard"])
assert all(t["task_id"].startswith("humanevalplus_")
           and t["task_id"] not in GAIN_HUMANEVAL_EXCLUSIONS for t in S["humanevalplus"])
assert all(t["task_id"].startswith("mbppplus_")
           and t["task_id"] not in GAIN_EVALPLUS_RESOURCE_EXCLUSIONS for t in S["evalplus"])
print("platform 值:", {m["platform"] for m in bank_strata("lcb3").values()})
print("四條不變量全過")
PY
```

實跑：`{'lcb3_medium': 135, 'lcb3_hard': 54, 'humanevalplus': 156, 'evalplus': 371} Σ = 716`；
`platform 值: {'leetcode'}`（**一個值，切不出第二層**）。

### 九-3　佇列與預註冊對得上

```
python3 ops/gain/schedule_queue.py --queue ops/gain/queues/r529_cross_bank.json --check
python3 ops/gain/schedule_queue.py --queue ops/gain/queues/r529_cross_bank.json --dry-run
```

### 九-4　R529 這個編號沒有被別的檔案用過

```
ls DECISION_*.md ops/gain/DECISION_*.md CONCLUSION_*.md 2>/dev/null | grep -c "_R529"   # 應為 1（本檔）
```

### 九-5　測試套件：**兩個失敗，兩個都不是本輪造成的**

`.venv/bin/python -m pytest tests/ --tb=line`（2026-09-11，本機 Mac，12 核）跑兩次：

```
（run 1）1 failed, 1389 passed in 1624.33s (0:27:04)
（run 2）2 failed, 1399 passed in 1706.58s (0:28:26)
```

失敗的兩支**都在 `tests/test_gain_harness_arms.py`**，而且是同一個成因：

| 測試 | 失敗內容 | 本樹重跑 | **乾淨 HEAD 樹**重跑 |
|---|---|---|---|
| `test_t4_four_failure_kinds_and_two_distinct_loader_reasons` | `LOOP_BAD`（無窮迴圈）應判 `fail_kind="timeout"`，實際回 `"loader"` | pass 1／fail 5（6 次） | **fail 2／2** |
| `test_visible_report_classifies_the_five_documented_outcomes` | `visible_report` 回 `None` ⇒ `TypeError: 'NoneType' object is not subscriptable` | pass 2／fail 2（4 次） | pass 1／fail 1（2 次） |

「乾淨 HEAD 樹」＝ `git archive HEAD | tar -x -C /tmp/...`，**完全不含本輪改動**。
⇒ **兩支都不是本輪造成的**，而且成因清楚：機器被超賣（實測 load 19–46 對 12 核，
同一台機器上還有另一個 agent 在跑它自己的全套）時，沙箱連把候選載起來都來不及，
**「跑太久」與「根本沒跑起來」就分不開了**。
（run 1 只紅一支、run 2 紅兩支，也是同一件事的表現：負載越高紅越多。）

⚠ run 2 的收集發生在我把 `tests/test_r529_queue_scheduler.py` 的最後兩支
（`poll_loop` 整合）加進去**之前** ⇒ 那兩支沒有進 run 2 的 1,401 個計數裡；
它們單獨跑過是綠的（該檔 53/53）。這一句寫出來是因為
「全套綠」與「全套綠但少收了兩支」不該長得一樣。

⚠ **這不是「無關的雜訊」，它們是 R529 要一起帶著的風險**：H-MIX 的出貨閘門
（`visible_report`）與計分（`meets_demand`）都跑在同一個 10 秒逾時的沙箱裡。
本 run 要在 **5 串（之後 8 串）** 的併發下連跑十幾個小時，而那正是同一種超賣。
⇒ 收官時若出現「同一題在兩塊之間判不一樣」，**第一個要查的是沙箱不是模型**
（§一一-13）。本 run **沒有**為此設事前探針，這是已知的量具邊界。

⚠ 順帶一筆（不是本檔的事，但看到了就要記）：`vacant-dev` 上**沒有裝 pytest**
⇒ 這個判斷只在 Mac 上做得出來。實驗機上的沙箱行為**沒有被測試套件量過**。

---

## 一〇、中止準則（發射之後，什麼情況要停）

1. **任一塊的任一臂 `infra_void / processed > 20%`** ⇒ 那一塊作廢重排
   （沿用 R460 §十／R460R §四-2 的 20% 線）。**只重排一次**；
   重排無上限＝「一直重試到資料看起來正常為止」＝選擇性重跑。
2. **某一題目集少一塊** ⇒ 該集 `block_count_mismatch` ⇒ **那一集 INVALID，不判**，
   而且**要從主指標的 N 裡拿掉**，並在主指標旁邊逐字寫「少了哪一集、N 少了多少」。
   **不准**就地把 §六 的門檻搬到縮水的 N 上重讀（R460 §六-(6)-i 的同一條）。
   ⚠ Holm 家族**仍然是 2**——少一集不改家族。
3. **`--scope v2` 的稽核在任何一塊報出違規** ⇒ **整個 run 作廢**（§五-4）。
4. **R529 在 R460R 還在跑的時候動到 1004 的 #1–#3** ⇒ 立刻停並記一筆
   （§八-2 的條件被繞過＝這批資料的併發條件不明）。
5. **任何一張卡上出現第 5 串** ⇒ 同上（`parallel=4`，超過的那一串量到沒有收益，
   而且它會讓「這批資料是在什麼併發下量的」變成事後才查得到的事）。
6. 四個題目集**沒有全部收完之前不得發布任何跨集彙總數字**（§六-2、§六-5）。
7. **某一塊在 1003 上連續 `infra_void`** ⇒ 照第 1 條作廢，而且**重排要換到另一台**
   （排程器的 `plan_launches_queue` 會避開它死過的那一台；換不到就這一輪跳過，
   不硬等也不硬撐）。1003 在新條件下沒有跑過 4 併發的真跑（§八-0a）。

---

## 一一、誠實邊界（收官必須原樣帶著，一條都不准掉）

1. **三個真來源，不是四個。** `lcb3_medium` 與 `lcb3_hard` 是**同一個題庫的難度分割**
   ——它們共用語料、共用日期窗、共用 `_lcb_check_code`。
   「跨四個題目集穩定」**不等於**「跨四種任務類型穩定」。
2. **單一模型、單一 harness 實作；後端從一台變成兩台，而且版本不同。**
   四集共用 `gemma-4-12b-it-qat`（兩台的 gguf 逐位元相同），但
   **1003 跑 LM Studio 0.4.24.0、1004 跑 0.4.17.0**（§八-0）。
   ⇒ 跨 block 的**絕對值**（通過率、token/題、牆鐘）可能混了版本差，
   收官要逐後端拆開描述；**配對比較不受影響**（一塊之內三條臂在同一台）。
   兩台在這幾天的任何漂移仍然會打到所有題目集（R460R §六-10 的同一條），
   而且 §八-3 的**併發轉換點**（5 串 → 8 串）是一個已知的條件變化。
   ⚠ 版本號是**人回報的**，本 runner 查證不到（§八-0 第 3 點）。
3. **三集的 GT 強度不一樣。** LCB v3 的 hidden 下界只有 **5** 條測資，
   MBPP+／HumanEval+ 的 hidden ＝ base ＋ plus（中位數 105／972 條）。
   ⇒ 「在 v3 上量到的增益」與「在另外兩集上量到的」**不是同一把尺量出來的**，
   跨集只准比方向。
4. **LCB v3 的污染風險比 v1/v2 高。** 189 題全部不晚於 2024-08-10，
   **不能**宣稱晚於訓練截止（R460 C3；`vacant/codebench.py` 有同一句）。
   ⇒ 若 v3 上的 Δ_C 比 lcb2 小，「污染把兩臂一起抬到天花板」與
   「效果真的比較小」**分不開**，收官必須兩個解釋都列。
   ⚠ HumanEval（2021）與 MBPP（2021）**更老**，污染風險**更高**，只是沒有日期窗
   可以拿來算——這一條對那兩集同樣適用而且更嚴重。
5. **`lcb3_hard` 的 n 只有 54**，+10pp 真值下的檢定力 0.15（§四-3，α=0.025）。
   那一格「不顯著」是設計的已知代價，**不是**證據。
6. **主指標的分層買到的不是更嚴的檢定**（§六-1 的方框）。
   數值上它與「把四集加起來做一次 McNemar」相同。
7. **量具強度在四集之間差很多**：lcb3 兩層各只有 9／3 題被參考解直接驗過
   （`gauge_in_filter_n`），humanevalplus 與 evalplus 是 156/156、371/371。
   ⇒ 「量具全綠」在 LCB 那兩層的意思比在另外兩集弱得多。
8. **量具過不過是機器相依的**（§五-1 的實測）：同一套量具在 Mac 上會紅
   （MBPP+ 有 2–7 題撞 10 秒逾時），在 vacant-dev 上最慢 2.98 秒。
   ⇒ 別人在別台機器上重跑這批塊可能得到不同的量具結果，那不是資料壞了。
9. **HumanEval+ 的 8 題排除是本輪新做的判斷**，其中 `HumanEval/15`（2× 餘裕）
   是**我們自己訂的門檻**，不是官方的。門檻寫在資料之前、對 evalplus 是 no-op，
   但它仍然是一個選擇，收官要照實講。
10. **MBPP+／HumanEval+ 上的 V/GT 豁免數會遠高於 R460**（§五-3），
    那是題庫結構不是洩漏；但這也意味著**稽核在那兩集上比在 LCB 上寬**，
    這一句要跟著豁免數一起講。
11. **winner's curse 照舊**：R460 的 +13.33pp 是**能被判顯著**的點估計 ⇒ 上偏。
    ⇒ **本 run 的點估計預期會比 +13.33 小，那是預期之內的事，不是「效果消失」。**
12. **`--bank-filter`、`--bank humanevalplus`、佇列排程器都是本輪新寫的。**
    牙齒在合成案例上驗過，但**沒有**在一次真跑上驗過。
    第一塊收完時要逐條核對 rows 的 `bank`／`stratum`／`family` 與預期相符。
13. **沙箱在負載下會飄。** 出貨閘門（`visible_report`）與計分（`meets_demand`）
    共用同一個 10 秒逾時的沙箱，而 37 塊要在同一顆卡上連跑二十幾個小時、
    接在 R460R 之後，中間還有一次併發從 3 變 4 的轉換。
    ⇒ 收官若出現「同一題在不同塊之間判不一樣」，**第一個要查的是沙箱不是模型**
    （R460 §一〇 補記的同一條）。本 run **沒有**為此設事前探針。

---

## 一二、能講的話與必帶的前提

收官時**唯一**可以往外講的形狀（照 §六-5 的宣稱規則逐字判到哪一句講哪一句）：

> 在 4 個互斥的題目集上（3 個來源：LeetCode 競賽題、MBPP+、HumanEval+），
> 把同樣的呼叫預算花在「跑客戶的驗收測資、把失敗原文貼回去、讓它改」，
> 對照花在換人重抽，**合併後的配對精確檢定**顯著（p_adj = …，Holm 家族 2）；
> 逐集的差是 …（逐集列點估計與未調整區間），方向 k/4 一致。

**必帶的前提，一條都不准掉：**

- **R440P 前提句**：R440P 量到 **17–19% 的題目五份候選全錯**——
  **選擇規則**（重抽、投票）打不破這個候選池天花板，因為它只能在錯的候選裡挑；
  **修訂迴圈**在原理上可以，因為它改變候選本身。本 run 量的是後者有沒有兌現，
  而不是「harness 比較聰明」。
- **可執行驗收的前提**：整件事建立在「需求可以被編譯成可執行的驗收測資」。
  需求跑不起來的場合，這個機制沒有免費的裁判，會退化成「問一個模型」。
- **worker 看得到客戶可見測資的內容與期望值**；隱藏測資只計分，
  動態稽核逐塊核過（§五-3）。
- 上面 §一一 的十三條誠實邊界。

**不能講**：不能講「證明」；不能講「harness 才是關鍵」的一般性質
（外部同模型證據全距 2.7pp）；不能講 ≥15pp 的實務增益；
不能把四集的點估計平均；不能把不顯著讀成「等價」或「打平」；
不能宣稱本 run 的題目晚於訓練截止；不能把本檔的 `EFFECTIVE`
與 R460 的 `EFFECTIVE` 當成同一個東西。

---

## 一三、這份預註冊自己的邊界

- 本檔 v2 由 Opus 依 Fable 2026-09-11 的裁決改寫。**最需要被再看一眼的三處**：
  §七-1 第 1 條（analyzer 擋不擋發射）、§一-2（HumanEval+ 排 8 題，其中 1 題是
  我們自訂的餘裕門檻）、§六-1 的方框（分層在數值上等於合併，不要讀成更嚴）。
- **本輪對 vacant-dev 做過的事，逐條**：唯讀 `ls`／`ps`／`pgrep`／`git status`；
  把離線量具腳本放到 `/tmp` 並在 `/tmp/her`（repo 的一份**拷貝**）上跑
  （`nice -n 10`，純沙箱、不打後端）；把 `HumanEvalPlus-v0.1.10.jsonl.gz`
  放進 `~/vacant/Vacant/.vacant-private/evalplus/`（`.gitignore` 內的資料檔，
  sha256 與釘值相符）。對兩顆後端各做過一次**唯讀** `GET /v1/models`
  （查 LM Studio 版本有沒有出現在回應或 header 裡——沒有，所以 §八-0 第 3 點
  才寫成「宣稱」）。**沒有**執行過任何 `kill`／`pkill`／`flock`，
  **沒有**碰過 `~/vacant/logs/.schedule_harness_reps.lock`（只有 08:14Z 一次唯讀
  `ls -la` 與一次 `fuser -v`——`fuser` 不帶 `-k`，不送訊號），
  **沒有**改過 `ops/gain/schedule_harness_reps.py` 或 R460R 的任何 run 目錄。
  R460R 排程器在 07:23Z 死掉，本輪第一次碰那個 lock 路徑是 08:14Z，**晚了 51 分鐘**。
- 本檔**不授權發射**：發射由人類（或 Fable 的明示指令）觸發，
  啟動命令原文在交付回報裡，本檔不重複。
- 本檔只出檔案、指令與判準。

---

## 附錄 A：v1 → v2，Fable 改了什麼（v1 的取捨紀錄整段留著）

### A-1　題目集：5 集 → **4 集**

v1 的五集是 `lcb3-hard`(54)、`lcb3-medium`(135)、`mbpp-1`(120)、`mbpp-2`(120)、`mbpp-3`(120)，
其中後三集是 MBPP+ 的 **seed 決定性互斥切片**。v1 自己就寫著
「那是**抽樣切分**不是『不同題目集』，它量到的是**題目層級的變異**，不是來源變異」。
**Fable 判：那就不要算成三集。** MBPP+ 收回成一集（371 題全跑，不切片），
省下來的名額拿去補**真的第三個來源**（HumanEval+）。
⇒ 誠實計數從「2 個真來源」變成「**3 個真來源 ＋ 1 個難度切分**」。

v1 §一-3 把「拿到 HumanEval+ 的資料」列為第 1 順位但**沒做**，理由是
「資料不在手上，不是工作量」。**本輪把資料拿到了**
（`evalplus/humanevalplus_release` 的 `v0.1.10`，`HumanEvalPlus.jsonl.gz`），
所以那個理由消失了。v1 的另外兩個候選（builtin 六族、`contest_year` 分層）
維持 v1 的判斷：前者等另一位代理補完當第二階段，後者格子太小不做。

### A-2　臂：三臂**維持**，但 v1 的 §六-3 取捨被推翻的方式不同

v1 寫「三臂 ⇒ `EFFECTIVE` 在結構上不可達」，並把「加回 OFF5 成四臂」的價目表
攤給人類裁決（token/題 14,395 → 29,399，牆鐘 ×2）。
**Fable 判：不加 OFF5，改判準。** 理由是 (iii) 那一格問的是「成本划不划算」，
而「同預算下比 CONFORM 便宜」本來就是一個更貼題的問法——OFF5 只是 R460 當時
手邊有的那個對照。⇒ §六-3 改成本研究自訂的四狀態，(iii) 換成
「合併資料裡 HMIX 的 token-per-correct ≤ CONFORM 的」，**並且明講它與 R460
的同名狀態不是同一個東西、不可互引**。

### A-3　主指標：逐題庫 ×10 → **跨題庫分層合併 ×2**

v1 的家族是「5 集 × 2 對照 ＝ 10 個檢定」，而 v1 §四-3 自己算出
`lcb3_hard` 那一格在 Holm 之後檢定力只有 0.138，並寫「事前就說死：那一格幾乎必然
判 `INCONCLUSIVE`」。**Fable 判：那就不要把主要問題押在十個註定量不到的格子上。**
主指標改成**分層合併**（家族 2），逐題庫降為**描述性次指標、不下裁決**。
代價與收穫都在 §四-3 的表裡：合併之後在 +10pp 真值下檢定力 0.999、+5pp 之下 0.645，
但**合併的 H0 是「每一集都沒有效果」，拒絕它不說「每集都有」**。
v1 的 `aggregate.sign_test_p`（四集方向的符號檢定，p = 2×(1/2)^4 = 0.125）
**被移除**——它與主指標問的是同一件事而檢定力差得多，留著只會變成
「挑一個比較好看的 p」。方向一致計數保留為描述。

### A-4　`--request-timeout-s`：1200 → **900**

v1 沿用 R460R 的 1200。**Fable 判：900。** 1004 歷史最長的成功呼叫是 595 秒；
1200 秒那次掛死白燒了 a3 的 1.33 小時。R460R 現行的塊**不動**。

### A-5　排程：v1「R529 一塊都不發，直到 R460R 收完」→ **1 槽起跑**

v1 §八-2 寫死「1004 的上限仍然是凍結的 3，R460R 跑完**不是**在 1004 上加併發的理由」。
**Fable 判：那個 3 是 `parallel=4` 之下的三格，第四格是真的空著。**
量測（Opus 探針）：第 4 串 +15–25% 總吞吐、每串 1.21×、`budget_wall` 截斷數不變；
第 5、6 串沒有收益。⇒ R529 **現在就可以用第 4 格**，但只准 1 槽；
R460R 收完才擴到 4 槽。v1 的「不共用排程器」判斷**維持**並落地成
`ops/gain/schedule_queue.py`（獨立 lock、獨立 log、獨立槽名）。

### A-6　v1 的已知未償：`runs/INDEX` 漂掉

v1 §九-5 記著「索引釘在 44、實際 50，`--check` 也 FAIL，本輪不動它」。
**本輪清掉了**（重跑產生器、更新測試釘值、`--check` 過）。
順帶把 v1 §九-5a 記的 `test_t4_…` 查清楚了：它**不是本輪造成的**
（乾淨的 HEAD 工作樹一樣紅），是機器超賣時沙箱把「跑太久」與「沒跑起來」
搞混。逐次重跑紀錄在 §九-5。

### A-7　v1 完整保留的部分

§〇（要解的問題）、§三（取樣不變量的形狀）、§四-2（過擬合方向）、
§五-2（量具不切層的理由與代價）、§六-4（R460 §九 推翻鍵）、
§一〇（中止準則）、§一一 大部分、§一二（能講的話）——這些 Fable 沒有改，
本檔照抄並依 4 集／3 臂更新數字。
