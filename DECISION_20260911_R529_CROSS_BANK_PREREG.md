# R529 預註冊：H-MIX 的**單一效果**在多少個不同題目集上還在——三臂 OFF／CONFORM／HMIX

（2026-09-11，Opus 實作、待 Fable 稽核。**在任何 r529 資料之前**——本檔寫完時
`runs/` 底下沒有任何 `g_r529*` 目錄，兩顆 seed 在 50 個 `runs/*/summary.json` 裡
一次都沒出現過，證明指令與實跑輸出見 §九-1。零模型呼叫；本輪唯一碰過遠端的動作是
對 vacant-dev 的**唯讀** `ls`／`ps`，見 §八-1。）

**編號**：R4xx 這一段（R440–R503、R516–R528）已經用滿，R529 是命名空間裡 ≥460
的**下一個未使用號碼**（`ls DECISION_*.md | grep -oE "_R[0-9]+"` 的補集，§九-4 可重算）。
本檔在內容上是 R460 的跨題庫續作，排在 R460R（同題庫五次複製）旁邊：
**R460R 換 seed 不換題目，R529 換題目不換機制。**

本檔授權的東西**只有**：§二 那 19 個 run 名字、兩顆 seed、§三 的取樣規則，
以及 §六 的分析口徑。其餘一律照 `DECISION_20260907_R460_HARNESS_PREREG.md`
（以下簡稱 **R460 預註冊**）——**門檻、家族定義、分母、區間、四狀態、
winner's curse 免責，一個字都沒有動**；唯一一處**結構性的不可評估**
（條件 (iii) 需要同 run 的 OFF5，而本 run 沒有 OFF5）寫在 §六-3，
它的處置是**縮小可達狀態**，不是改門檻。

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

**R529 就是 R460 §九 第一條那個推翻試驗**，並且把它從一個題庫擴到五個互斥的題目集。

### 本 run **不**回答什麼（收官不准借用）

1. **不**回答「H-MIX 比 H-PI／H-OC 好」——本 run 沒有那兩條臂（R460 §六-(7)-6 的禁令照舊）。
2. **不**回答「效果量是多少」。五個題目集的點估計**不准平均**、**不准併 n**
   （R449C §六-2、R460 §六-(7)-3）。
3. **不**回答「換模型還成不成立」——五個題目集共用同一顆 `gemma-4-12b-it-qat`。
4. **不**在本 run 重新賺一次 `EFFECTIVE`（結構上不可達，§六-3）。

---

## 一、題庫盤點：為什麼**湊不到 10 個**，以及最接近的做法是什麼

人類的需求是「拿 10 種以上不同題目集」。**這個數字在現有材料下達不到，本節說明為什麼、
差多少、以及補到位需要什麼。**先給結論的三個數字（定義在小節末）：

> **真正不同來源＝2**（LiveCodeBench、EvalPlus MBPP+）
> **同來源不同切片（互斥、可跑、不重複計數）＝5**
> **合成＝9 個族（builtin 6 ＋ x1 3），今天一個都跑不起來**

### 一-1　逐個候選（引用任何一列之前請先讀 `runs/INDEX.md` §五）

| 題目集 | 題數 | 來源 | V/GT 分離 | sha256／釘死 | 已知壞題 | 與其他的交集 | `--bank` 支援 | 還缺什麼 |
|---|---:|---|---|---|---|---|---|---|
| **LCB v1** | 91 | LiveCodeBench code_generation_lite（Jain et al. 2024, arXiv:2403.07974），test5+test6 視窗，2024-10-12→2025-04-05 | 有：`visible_tests`（每題 2–4 條）／`hidden_tests`（每題 24 條），`_lcb_check_code` 兩份分開渲染 | `eb2a58760818d54b…`、91 題釘死、fail-closed | `lcb_3613`、`lcb_3763`（`check_bank_precision.KNOWN_BAD`） | **⊂ v2**（91/91 全在 v2 裡） | ✅ `--bank lcb` | 沒缺；但它是 v2 的子集 ⇒ **不能**另算一個題目集 |
| **LCB v2** | 120 | 同上 ＋ test4 視窗，2023-08-26→2025-04-05 | 同上（visible 中位數 3 條、hidden 21–24 條） | `b98f027213e2469a…`、120 題釘死 | 同 v1 兩題 | ⊃ v1；**∩ v3 = 0** | ✅ `--bank lcb2` | 沒缺；但這 120 題**已經是 R460／R460R 的資料** ⇒ 對 H-MIX 不是新題目 |
| **LCB v3** | 189 | 同 recipe，test/test2/test3，2023-05-07→2024-08-10 | 同上（hidden 5–24 條，**下界比 v1/v2 低**） | `bd3dffebb1b16bc7…`、189 題釘死 | 無 | **∩ v1 = 0、∩ v2 = 0**，聯集 309 | ✅ `--bank lcb3` | 沒缺。⚠ 污染警語：189 題**全部不晚於 2024-08-10**，不能宣稱晚於訓練截止（R460 C3） |
| **MBPP+ v0.2.0** | 378（G 實驗扣掉 7 題資源排除 ⇒ **371**） | EvalPlus 官方包，**私有不轉散布**（`.vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz`） | 有：`visible_check`＝base inputs（每題 3–7 條）、`hidden_check`＝base＋plus；`canonical_solution` 永不進 prompt（負向測試 `tests/test_x1_evalplus.py`） | `af43697e8791c4c1…`、378 題釘死、fail-closed | `GAIN_EVALPLUS_RESOURCE_EXCLUSIONS` 7 題（沙箱容量，非模型錯） | 與 LCB 零交集（不同語料） | ✅ `--bank evalplus`（預設） | 沒缺。⚠ H-MIX **沒有**在它上面跑過，而 R460 §七 預告它的回饋訊息較差 |
| **HumanEval+** | （164） | EvalPlus 官方包 | — | — | — | — | ❌ **無此 bank** | **資料本身不在手上**：Mac 與 vacant-dev 都沒有 `HumanEvalPlus-*.jsonl.gz`，兩台都**沒有安裝 `evalplus` 套件**，`~/.cache/evalplus/` 不存在（§八-2 的唯讀查證）。⇒ **本輪不做這個 loader**，見 §一-3 |
| **codebench builtin 六族** | 無限（程序生成） | `vacant/codebench.py::_FAMILY_BUILDERS`：boundary／off_by_one／empty_input／duplicate_values／negative_numbers／type_coercion | 有 `visible_check`／`hidden_check`，但**沒有 `entry_point`** | **無檔可 hash**（由 `seed:family:idx` 決定性生成，`task_id = sha256(...)[:16]`） | — | 與真題庫零交集（是我們自己造的） | ⚠ `--bank builtin` 列在 choices 裡，**本輪之前一按就掛死**（見 §一-4） | ①沒有官方參考解 ⇒ `probe_instrument` covered=0 ⇒ runner 照「量不到不是通過」拒跑；②沒有 `entry_point` ⇒ H 臂的靜態預檢退化。**兩個缺口都要補才跑得起來** |
| **X1 任務族** | 3 族（string_edge／off_by_one／state_parse）× 任意變體 | `vacant/x1.py::FAMILIES` | ❌ **只有隱藏 `check`，沒有 `visible_check`** | 無檔可 hash（`_tid` 決定性） | — | 與真題庫零交集 | ❌ 不是 `--bank` 的值 | 結構性不合：CONFORM 與 H-MIX 的**出貨閘門就是 `visible_check`**，沒有它兩條臂都不成立。要用它必須先為每題定義「客戶的可見驗收」——那是設計工作不是接線工作 |

### 一-2　誠實的計數

- **真正不同來源＝2**：LiveCodeBench（LeetCode 競賽題、平台原生難度標籤、有日期戳）與
  EvalPlus MBPP+（眾包短函式題 ＋ 官方擴增測資）。**沒有第三個。**
- **同來源不同切片（互斥、可跑、不重複計數）＝5**：
  `lcb3-hard`(54)、`lcb3-medium`(135)、`mbpp-1`(120)、`mbpp-2`(120)、`mbpp-3`(120)。
  - LCB 這一側用的是**平台原生**的 `difficulty`（LeetCode 出題時就掛著的標籤，
    不是我們自己貼的）；`platform` 這個欄位在三個 bank 上**都只有 `leetcode` 一個值**
    ⇒ **平台切不出第二層**，這一條要照實講，不能寫成「支援平台分層」。
  - MBPP+ 這一側**沒有任何平台原生標籤**（它的 `family` 是 `_label_family` 的關鍵詞
    啟發式，docstring 自己寫著「不是語意真相」）⇒ 只能做 **seed 決定性的互斥切片**。
    那是**抽樣切分**不是「不同題目集」，它量到的是**題目層級的變異**，不是來源變異。
- **合成＝9 個族**（builtin 6 ＋ x1 3），**今天一個都跑不起來**（缺口見上表最後兩列）。
  即使補起來，它們也只能標成「合成」——`BuiltinSampleLoader` 的 docstring 自己寫著
  「同一顆 reference solver 配不同隨機測資的變體，不是真的不同題目」。

**⇒ 10 個湊不到。** 把 lcb2／lcb3 整份與它們的兩個難度層**同時**計數就可以湊到 9，
但那是同一批題目數兩次，本檔拒絕這樣算。

### 一-3　最接近 10 的做法（按性價比排序，**本檔都不執行**，留給人類裁決）

1. **拿到 HumanEval+ 的資料（164 題）** ⇒ 第 **3** 個真來源，且可再切 1–2 個切片。
   要做的事逐條：把官方 `HumanEvalPlus-v0.1.10.jsonl.gz` 放到
   `.vacant-private/evalplus/`、量它的 sha256、照 `EvalPlusMBPPLoader` 的紀律寫
   `EvalPlusHumanEvalLoader`（sha256 釘死、題數釘死、schema 全驗、V/GT 分離、
   `canonical_solution` 只進 `hidden_check`）、接上 `_canonical_solutions` 與
   `probe_instrument`、加負向測試。**本輪不做的理由是資料不在手上，不是工作量**
   ——沒有真資料的 loader 沒辦法釘 sha256，而「先寫一個等資料」等於先埋一個
   永遠不會 fail-closed 的預設值。
2. **把 builtin 六族補成可跑**（加 `entry_point`、加每族的參考解給量具用）
   ⇒ **＋6 個合成題目集**，成本最低，但拿到的是最弱的證據（合成題）。
3. **開第三個分層軸 `contest_year`**（LCB 的 `contest_date` 也是平台原生的）
   ⇒ v2×{2024,2025}、v3×{2023,2024}。**不建議**：與 difficulty 交叉之後
   最小的格子只有 25 題（v3 hard 2023），n=25 的配對檢定什麼都量不到。

### 一-4　盤點順手抓到的兩個 loader 缺陷（本輪已修，見 §七）

- **`--bank builtin` 會掛死。** `BuiltinSampleLoader` 是**無限**產生器
  （`_iter_pool` 的 `while True`），而 `load_tasks` 那句 `list(loader.iter_tasks(seed))`
  對它永遠不回來。`round440y` 的註解已經寫過這個坑（那次是 `lcb2` 誤掉進來），
  但 `builtin` 自己走的就是這條路。**掛死與「跑很久」在終端機上長得一模一樣**
  ——實測本輪一條 `load_tasks("builtin", "g1", 6)` 吃滿 120 秒逾時才被殺掉。
- **`--bank-filter` 不存在** ⇒ 難度分層只能靠事後切 rows，而事後切等於
  「看過數字再決定切哪裡」。本輪把它做成**發射前**的旗標。

---

## 二、19 個 run 名字、兩顆 seed、逐塊指令

五個題目集切成 19 塊，**塊內三臂交錯**（`for task: for arm`，與 R460 逐字相同），
一塊一端點、一塊一行程。

| # | 題目集 | bank | 分層 | n | 塊大小 | run 目錄 |
|---|---|---|---|---:|---:|---|
| s1 | `lcb3_hard` | `lcb3` | `difficulty=hard` | 54 | 27 | `runs/g_r529_lcb3h_a1`、`runs/g_r529_lcb3h_a2` |
| s2 | `lcb3_medium` | `lcb3` | `difficulty=medium` | 135 | 27 | `runs/g_r529_lcb3m_a1`、`runs/g_r529_lcb3m_a2`、`runs/g_r529_lcb3m_a3`、`runs/g_r529_lcb3m_a4`、`runs/g_r529_lcb3m_a5` |
| s3 | `mbpp_1` | `evalplus` | —（無平台原生標籤） | 120 | 30 | `runs/g_r529_mbpp1_a1`、`runs/g_r529_mbpp1_a2`、`runs/g_r529_mbpp1_a3`、`runs/g_r529_mbpp1_a4` |
| s4 | `mbpp_2` | `evalplus` | — | 120 | 30 | `runs/g_r529_mbpp2_a1`、`runs/g_r529_mbpp2_a2`、`runs/g_r529_mbpp2_a3`、`runs/g_r529_mbpp2_a4` |
| s5 | `mbpp_3` | `evalplus` | — | 120 | 30 | `runs/g_r529_mbpp3_a1`、`runs/g_r529_mbpp3_a2`、`runs/g_r529_mbpp3_a3`、`runs/g_r529_mbpp3_a4` |

**Σn = 549 題、19 塊、rows = 549 × 3 = 1,647 列**（rows 的定義：**一題一臂一列**）。

### 二-1　seed 與 offset（取樣規則，事前寫死）

兩顆 seed，**都沒被用過**（§九-1 實跑證明）：

```
SEED_AUTHORIZED_SET: g-r529-lcb3 <- NONE
SEED_AUTHORIZED_SET: g-r529-mbpp <- NONE
```

- **`g-r529-lcb3`**（s1＋s2 共用）。共用一顆 seed **不會**讓兩層重疊：
  `load_tasks` 是「先依 seed 決定性排序 → **再切層** → 才 `ts[offset:offset+n]`」，
  而 hard 與 medium 是 `difficulty` 的一個**分割**（54 ＋ 135 ＝ 189，交集為空，
  `tests/test_bank_filter_r529.py::test_lcb3_difficulty_strata_partition_the_bank_exactly` 逐條驗）。
- **`g-r529-mbpp`**（s3＋s4＋s5 共用）。這裡共用是**必須的**：三片靠
  offset 0／120／240 互斥，而 offset 只在**同一顆 seed 的同一個排序**上才定義得出來。
  換 seed ⇒ 換排序 ⇒ 三片會重疊，而重疊之後三個「題目集」其實是同一批題。
  371 題用掉 360，**尾巴 11 題不用**（不足一塊，不准湊）。

逐塊的 `--offset`（**切層之後、該層之內**的序號）：

| 塊 | offset | n | 塊 | offset | n |
|---|---:|---:|---|---:|---:|
| `lcb3h_a1` | 0 | 27 | `mbpp1_a1` | 0 | 30 |
| `lcb3h_a2` | 27 | 27 | `mbpp1_a2` | 30 | 30 |
| `lcb3m_a1` | 0 | 27 | `mbpp1_a3` | 60 | 30 |
| `lcb3m_a2` | 27 | 27 | `mbpp1_a4` | 90 | 30 |
| `lcb3m_a3` | 54 | 27 | `mbpp2_a1..a4` | 120／150／180／210 | 30 |
| `lcb3m_a4` | 81 | 27 | `mbpp3_a1..a4` | 240／270／300／330 | 30 |
| `lcb3m_a5` | 108 | 27 | | | |

### 二-2　逐塊指令（`<OUT>`／`<N>`／`<OFFSET>`／`<SEED>`／`<BANK>`／`<FILTER>` 取上表，其餘 19 塊完全相同）

```
python3 ops/gain/gain_run.py \
  --out <OUT> --n <N> --offset <OFFSET> \
  --decision DECISION_20260911_R529_CROSS_BANK_PREREG.md \
  --seed <SEED> --arms OFF,CONFORM,HMIX --bank <BANK> <FILTER> \
  --models gemma-4-12b-it-qat --probe-sample 0 --gauge-scope bank \
  --request-timeout-s 1200 --review-timeout-s 380 --retries 4
```

`<FILTER>` 只有 s1／s2 有：`--bank-filter difficulty=hard`／`--bank-filter difficulty=medium`；
s3／s4／s5 那一格是空的（MBPP+ 沒有平台原生標籤，**不准**拿 `family` 充數）。

### 二-3　與 R460／R460R 的差異，逐項與理由

| 項 | R460／R460R | R529 | 為什麼 |
|---|---|---|---|
| 臂 | 六臂 `OFF,CONFORM,OFF5,HPI,HOC,HMIX` | **三臂 `OFF,CONFORM,HMIX`** | 本 run 問的是「**單一效果**跨題庫穩不穩」，不是「哪條 harness 比較好」。OFF 是錨、CONFORM 是同預算最強的選擇規則、HMIX 是待測迴圈。砍掉 OFF5／HPI／HOC 省下 **69%** 的 token 負載（46,279 → 14,395 token/題），那正是換到五個題目集的機時。**代價寫在 §六-3**（條件 (iii) 因此不可評估） |
| 題庫 | 單一 `lcb2` 120 題 | **五個互斥題目集、兩個來源、549 題** | 這是本 run 的全部重點 |
| seed | 一顆／五顆，都在同一批題上 | 兩顆，**換的是題目不是 seed** | R460R 換 seed 不換題目；本 run 反過來。兩者互補，都不能單獨回答對方的問題 |
| `--bank-filter` | 不存在 | s1／s2 用 | 讓「不同題目集」可以是平台原生的分層，而不是事後切 rows |
| `--gauge-scope` | `bank` | `bank`（**不套 `--bank-filter`**） | 見 §五-2：lcb v1/v2 的 12 份手寫參考解 **12/12 全是 medium**，量具若也切層，`difficulty=hard` 會 covered=0 而正確地拒跑 ⇒ hard 層永遠發不出去 |

---

## 三、取樣規則的不變量（發射前可驗，零模型呼叫）

1. **五個題目集兩兩零交集**，聯集恰好 549 個 `task_id`。
2. **每個題目集之內，塊與塊零交集**，聯集恰好等於該集的 n。
3. s1 的每一題 `family == "lcb_leetcode_hard"`；s2 的每一題 `family == "lcb_leetcode_medium"`
   （`family` 是從釘死的題庫算出來的，**run 目錄名可以打錯，收官只認 `family`**）。
4. s3／s4／s5 的 `task_id` 全部以 `mbppplus_` 開頭，且都不在
   `GAIN_EVALPLUS_RESOURCE_EXCLUSIONS` 那 7 題裡。
5. 兩顆 seed 在**所有** `runs/*/summary.json` 裡命中集合＝`NONE`。

五條的重算腳本逐字在 §九-2。**任何一條不成立就不准發射**——
取樣錯了而還是跑完了，長得跟跑對了一模一樣。

---

## 四、事前預測（P-X1..P-X8）——**逐題目集判，先寫死**

錨一律是 R460 在 lcb2 的實測值。**錨不是門檻。**

| # | 預測 | 仲裁欄位 | R460 錨 |
|---|---|---|---|
| **P-X1** | 五個題目集**全部** Δ_C > 0 | `paired.HMIX_vs_CONFORM.delta_pp` 逐集 | +13.33pp |
| **P-X2** | 五個題目集**全部** Δ_O > 0 | `paired.HMIX_vs_OFF.delta_pp` 逐集 | +25.83pp |
| **P-X3** | **MBPP+ 三片的 Δ_C 都小於 LCB v3 兩層的最小值** | 同 P-X1 | —（見下方預期） |
| **P-X4** | 假交付 H-MIX < CONFORM，五集皆然 | `per_arm.HMIX.false_delivery_pp` vs `per_arm.CONFORM.false_delivery_pp` | 14 件 vs 29 件 |
| **P-X5** | token/題 H-MIX ≤ **1.2 ×** CONFORM，五集皆然 | `tokens.HMIX.tokens_per_task ÷ tokens.CONFORM.tokens_per_task` | 0.978× |
| **P-X6** | **hard 層的 Δ_C ≥ medium 層的 Δ_C**（lcb3 之內） | s1 vs s2 的 `delta_pp` | R460 G4：H-MIX 90.3/75.0、CONFORM 77.8/60.4 ⇒ 難題差距更大 |
| **P-X7** | 呼叫/題 H-MIX ∈ [1.2, 2.5]，五集皆然 | `per_arm.HMIX.calls_per_task` | 1.36 |
| **P-X8** | 每一塊 `infra_void / processed ≤ 5%` | 逐塊 summary | R460 六塊全 0 |

### 四-1　**寫在資料之前的區間預期**（Fable 指名要寫）

逐集寫下我預期 Δ_C（H-MIX − CONFORM）落在哪裡，以及理由。
**這些是預期不是門檻**，落在區間外照實記，不改窗：

| 題目集 | 我預期的 Δ_C | 理由 |
|---|---|---|
| `lcb3_hard`(54) | **+8 ~ +20pp** | 與 R460 的 lcb2-hard 最像（同來源、同難度標籤）。R460 G4 的 hard 差距（75.0 − 60.4 = +14.6pp）是最接近的錨。⚠ 但 v3 的日期窗更早（全部 ≤2024-08-10）⇒ 污染風險較高 ⇒ 兩臂的基礎正確率都會抬高 ⇒ 天花板效應會**壓縮**差距 |
| `lcb3_medium`(135) | **+3 ~ +14pp** | R460 G4 的 medium 差距是 90.3 − 77.8 = +12.5pp，但那是 hard 佔 40% 的 bank；v3 medium 更簡單 ⇒ CONFORM 自己就接近天花板 ⇒ 迴圈能救的題變少 |
| `mbpp_1/2/3`(各 120) | **0 ~ +8pp，且我預期至少一片會出現 Δ_C ≤ +3pp** | **這是本 run 最重要的一格。** 三個獨立的收緊力量：①R460 §七 逐字寫著 MBPP+ 的回饋訊息天生較差（HARNESS_STUDY §3.3）⇒ 迴圈拿到的資訊少 ⇒ 增益的主要來源被削弱；②MBPP+ 簡單得多，OFF 的基礎正確率遠高於 LCB 的 58% ⇒ **天花板效應**，CONFORM 已經很接近上限，能被救回來的題本來就不多；③MBPP+ 每題可見測資 3–7 條、隱藏＝可見＋plus ⇒ **可見測資佔 GT 的比例比 LCB 高很多**，迴圈朝可見測資過擬合的空間反而**小**（這一條的方向與②相反，我把它寫下來是因為它會讓假交付**降**而不是升——見 P-X4） |

### 四-2　**過擬合風險的方向，事前講清楚**

R460 §六 的 P-H4 預測「假交付會升」而實測**降**（29 → 14），R460 §四把它記成
「預測寫錯方向」。本 run 沿用**實測那個方向**當預期（P-X4），但要分開講兩件事：

- **可見測資多**（MBPP+ base 3–7 條、LCB v2 中位數 3 條）⇒ 迴圈朝可見測資過擬合
  仍然會被 plus／hidden 抓到 ⇒ 假交付降。
- **可見測資少**才是風險。本 run 五集裡**可見測資最少的是 LCB v3**
  （`visible_tests` 最少 2 條，`hidden_tests` 最少只有 **5** 條——
  v1 的 hidden 是每題固定 24 條、v2 是 21–24 條，**v3 的下界低得多**）。
  ⇒ **若 P-X4 要在哪一集翻車，事前預期是 `lcb3_hard` 或 `lcb3_medium`，不是 MBPP+。**
  這一句寫在資料之前，收官不准反過來說「本來就預期 MBPP+ 過擬合」。

### 四-3　**檢定力：本 run 大部分格子量不出 Holm 後的 `p_adj < 0.05`**

用 R460 實測的 b/c 形狀（HMIX vs CONFORM：b/c = 22/6 於 n=120 ⇒
`p_disc`=0.2333、ψ=0.7857）當真值，`vacant.research.mcnemar_power` 逐格算：

| 題目集 | n | vs CONFORM（α=0.05） | vs OFF（α=0.05） | vs CONFORM（α=0.005＝Holm 最嚴那一格） |
|---|---:|---:|---:|---:|
| `lcb3_hard` | 54 | **0.435** | 0.956 | **0.138** |
| `lcb3_medium` | 135 | 0.885 | 1.000 | 0.628 |
| `mbpp_1/2/3` | 120 | 0.840 | 1.000 | 0.549 |

若真效果只有 +10pp（`p_disc`=0.25），α=0.05 之下 n=54 的檢定力是 **0.224**、
n=120 是 0.525、n=135 是 0.586。

**⇒ 事前就說死：`lcb3_hard` 這一格在 Holm 之後幾乎必然判 `INCONCLUSIVE`，
那是設計的已知代價（v3 的 hard 只有 54 題，加不了），不是「效果在難題上消失」。**
R460 §六-(7)-5 的禁令逐字照舊：**不准把 `INCONCLUSIVE` 讀成「等價」「打平」「迴圈沒用」。**

---

## 五、量具與 V/GT 稽核計畫

### 五-1　發射前的量具（每一塊都跑，`--probe-sample 0 --gauge-scope bank`）

與 R460R 逐字相同的紀律：對**整個題庫**裡有參考解的題目驗兩個方向
（參考解要過、壞樁要被擋），hidden 與 visible 兩側各驗一次；
再獨立驗一次「**本塊**每一題都有 `visible_check`」（`coverage_visible_n == coverage_n`）。
三條有任何一條不滿就停——**量不到不是通過**。

- LCB 側：v3 有 12 份手寫參考解（`ops/gain/data/lcb_v3_probe_solutions.json`，
  難度分布 medium 9／hard 3）⇒ 每塊量具約 1 分鐘。
- MBPP+ 側：**371 題全部有官方 `canonical_solution`** ⇒ `--probe-sample 0`
  每塊要跑 371 × 4 次沙箱。**本輪實測：sample=10 花 19.2 秒 ⇒ 全量約 11.9 分鐘/塊**，
  12 塊合計約 2.4 小時算力（三槽併發 ⇒ 牆鐘約 0.8 小時）。
  **不改小。** 把它降成抽樣會在收官時變成「你們為什麼在 MBPP+ 上把量具放寬」，
  而省下來的 0.8 小時牆鐘買不到這個問題的答案。這筆錢記在 §六-6 的預算裡。

### 五-2　`--gauge-scope bank` **不套 `--bank-filter`**（事前寫死，附理由與代價）

lcb v1/v2 的 12 份手寫參考解 **12/12 全是 medium**（本輪實測），v3 的 12 份是
medium 9／hard 3。⇒ 若量具也跟著切層，`difficulty=hard` 之下 lcb2 會 covered=0、
runner 會照「量不到不是通過」正確地拒跑 ⇒ **hard 那一層永遠發不出去**。
而量具驗的是**沙箱＋題庫＋計分**（參考解與壞樁都不經模型）⇒ 對整個題庫驗
**比對單層驗更強**，且與「這一塊是哪幾題」無關。

**代價要說出來，不准被總數蓋掉**：`lcb3_hard` 那一層只有 3 題被參考解直接驗過；
被驗到的是同一支 `_lcb_check_code`、同一個沙箱、同一條計分路徑，**不是那 54 題自己**。
runner 因此把 `instrument.gauge_in_filter_n` 落盤並印出來（本輪新增），
收官要照實列這個數字。

### 五-3　V/GT 動態稽核（`harness_vgt_audit.py --scope v2`，零模型呼叫）

每一塊跑一次，**19 塊全部 `CLEAN` 才准結算**：

```
python3 ops/gain/harness_vgt_audit.py --run runs/<block> \
  --bank <lcb3|evalplus> --scope v2 --out ops/gain/replay/r529/vgt_v2_<block>.json
```

⚠ `--bank` 必須顯式給（`summary.json` 不記 bank，稽核器不猜）。稽核器讀的是
**整個題庫**（`load_tasks(bank, seed, 0)`），切層的 run 也對得上，因為它按 `task_id` 查。

**事前寫下 MBPP+ 這一側的預期**（收官不准當成新發現）：MBPP+ 的
`hidden_check` ＝ base ＋ plus，而 `visible_check` ＝ base ⇒ **base 的每一個值同時
是可見的也是隱藏的**。v2 規則 (c) 的第一條（needle 逐字在該題 `visible_check`
原始碼裡就豁免）因此會在 MBPP+ 上大量命中。⇒ **`excused_by_rule.visible_check`
在 MBPP+ 三片上會遠高於 R460 的 4 筆**，那是題庫結構不是洩漏。
真正要盯的仍然是**扣掉豁免之後的 `violations`＝0**，以及
`excused_by_rule.got_sandbox_echo` 有沒有異常放大。
**豁免數字要逐塊落盤、逐塊報**——「沒有違規」不准順手蓋掉「沒有檢查」。

### 五-4　中止準則第 4 條（沿用 R460R §八-4）

`--scope v2` 在**任何一塊**報出違規 ⇒ **整個 run 作廢**（SPEC_GAIN §7；
R460 §九 推翻條件第二條）。不得只修不報。

---

## 六、決策規則

### 六-1　逐題目集判，**R460 §六 的門檻一個字沒改**

每一個題目集各自把它的塊合併（依 `offset` 排序、按 `task_id` 合併，R445／R460 §六-(0) 先例），
在該集的 n 上算 `per_arm.*`／`paired.*`／`tokens.*`。

- 配對單位＝`task_id`；成功＝`deliv = accepted ∧ meets_demand`（R667 凍結口徑）。
- 分母＝**complete case**：`n_common = |rows[A].task_id ∩ rows[B].task_id|`，**逐對印**。
- 區間＝**未調整**的 95% Clopper–Pearson 條件區間（`ops/gain/replay/paired_ci.py::diff_ci`）。
  > 每一次引用區間都必須逐字附上：**「區間未做多重比較調整；仲裁以 analyzer 為準」**。
- **不准併 n**、**不准跨題目集配對**（五集的 `task_id` 兩兩交集為空，配對本來就落在集內）、
  **不准比較集間的點估計幅度**（五集的難度組成、來源、n 都不同）。跨集只報**方向**與**區間重疊**。

### 六-2　Holm 家族＝**10**（跨題庫校正）

家族固定是 **5 個題目集 × 2 個對照（OFF、CONFORM）＝ 10 個檢定**，
每一對算 `vacant.research.mcnemar_exact(b, c)`，一次丟進
`vacant.research.holm_bonferroni`，α=0.05。仲裁欄位 `holm.<set>_<pair>.p_adj`、
`holm.family_size`（**必須等於 10**）。

⚠ 家族固定 10，**不准**因為某一集 void 太多、或某一集「反正一定不顯著」就抽掉它再重算。
⚠ **不准**把五集的 30 列 rows 丟進同一個檢定——那會把「跨題庫」偷偷變成一個 n=549 的實驗。

### 六-3　四狀態：逐字沿用 R460 §六-(4)，但 **(iii) 在本 run 結構上不可評估**

四狀態（`INVALID`／`EFFECTIVE`／`COSTLY_BUT_REAL`／`RULED_OUT`／`INCONCLUSIVE`）
的定義、順序、門檻**逐字沿用**：
(i) `delta_o_pp ≥ +25.0` ∧ `delta_c_pp ≥ +10.0`（點估計）；
(ii) `p_adj_vs_off < 0.05` ∧ `p_adj_vs_conform < 0.05`；
(iii) `tpc_incl_void ≤ tokens.OFF5.tpc_incl_void`（**同一個 run 的 OFF5**）；
(iv) `false_delivery_pp ≤ false_delivery_conform_pp + 5.0`。

**本 run 沒有 OFF5 臂 ⇒ (iii) 的仲裁值不存在。** 這是三臂設計的直接後果，
事前寫死它的處置：

- **`decision.<set>.cond_iii_tokens = "NOT_EVALUABLE"`**（不是 `true`、不是 `false`）。
- ⇒ **`EFFECTIVE` 在 R529 結構上不可達。** 可達的狀態是
  `COSTLY_BUT_REAL`（(ii) 的 CONFORM 那一半成立）／`RULED_OUT`／`INCONCLUSIVE`／`INVALID`。
- **不准**用「OFF5 的 token 成本本來就是 OFF 的 5 倍」造一個代用值去補 (iii)
  然後判 `EFFECTIVE`——那是**改狀態定義**，R460 §六-(7)-1 的禁令逐字適用。
  代用值 `5 × tokens.OFF.tpc_incl_void` 可以**印在附表**（欄位
  `tokens.<set>.tpc_off5_surrogate`，旁邊必附「代用值，不進裁決」），
  但它**不進任何一格裁決**。

⚠ **這是本檔最需要被 Fable 看一眼的取捨**：三臂省下 69% 的 token 換到五個題目集，
代價是本 run 賺不到 `EFFECTIVE`。若人類認為 `EFFECTIVE` 的可達性比題目集數量重要，
補救辦法是**加回 OFF5 成四臂**——成本逐字：token/題 14,395 → 29,399（**2.04×**），
§六-6 的牆鐘估計同步 ×2（14 小時 → 28 小時）。**本檔不替人類做這個取捨，
只把兩邊的價目表寫出來。**

### 六-4　**本 run 真正的主要產出：R460 §九 第一條的推翻鍵**

R460 §九 第一條逐字：「若在 LCB v3（189 題，零交集）預註冊複製 H-MIX vs CONFORM
而 **c ≥ b** ⇒ 本判定降為『一次顯著』」。

- **觸發鍵（事前寫死）**：`paired.lcb3_hard.HMIX_vs_CONFORM` 或
  `paired.lcb3_medium.HMIX_vs_CONFORM` 任一出現 **c ≥ b** ⇒ **觸發**
  ⇒ R460 的 `EFFECTIVE` 降為「一次顯著」，並且要在
  `examples/verdicts.py` 與官網資料源同步改口徑。
- MBPP+ 三片**不是**這條的觸發鍵（R460 §九 寫的是 LCB v3），但它們出現 c ≥ b
  同樣要逐字報出來，記在 `refutation.mbpp_c_ge_b`。
- 這一鍵**先於**四狀態印出來（`refutation.triggered`），免得收官時
  被五個題目集的裁決表淹掉。

### 六-5　跨題庫的粗指標（**描述性**，事前註冊）

`ops/gain/analyze_r529.py` 印四樣，一樣都不准少：

1. **`aggregate.direction_agree_c` ＝ 五集裡 Δ_C > 0 的個數**（以及 Δ_O > 0 的個數）。
   同時印逐集的 b/c，**Δ_C 恰好等於 0 的那一集計入分母但不計入分子**。
2. **`aggregate.sign_test_p`**：把每一集的方向當一次觀測，做精確二項符號檢定
   （H0: p=0.5）。5/5 同號 ⇒ p = 2 × (1/2)^5 = **0.0625**。
   ⚠ 旁邊必須逐字附上：**「五集共用同一顆模型、同一套 harness、同一個後端家族
   ⇒ 五次觀測不獨立，這個 p 是**上限鬆、下限不成立**的粗指標，不是檢定結論。」**
3. **`aggregate.holm_significant_n`**：10 個檢定裡 `p_adj < 0.05` 的個數，逐格列。
4. **宣稱規則**（事前寫死，`aggregate.statement_rule`）：

> **5/5 的 Δ_C > 0，且 MBPP+ 三片裡至少 2 片的 `p_adj_vs_conform < 0.05`
> ⇒ 可以寫「這個效果在兩個來源上方向一致，且在 MBPP+ 上重複量到」；
> 否則逐集照實列**——不准挑一集、不准平均、不准寫「多數支持」。

判到哪一句就逐字印在 `aggregate.statement`。
**沒有隨機效應模型、沒有 meta-analysis、沒有合併效果量。**

### 六-6　預算

rows 的定義：**一題一臂一列**。三臂 × 549 題 ＝ **1,647 列**。

| 項 | 中心估計 | 上界 | 依據 |
|---|---:|---:|---|
| 模型呼叫 | **2,185** 通 | 6,039 通 | 中心＝R460 實測 (OFF 1.00 ＋ CONFORM 1.62 ＋ HMIX 1.36)＝3.98 通/題 × 549；上界＝三臂都吃滿預算（1＋5＋5）× 549 |
| token | **7.90 M** | 9.5 M | 中心＝R460 lcb2 實測 (2,913 ＋ 5,805 ＋ 5,677)＝14,395 token/題 × 549。上界假設 MBPP+ 的弱回饋讓 HMIX 多跑 1.5 倍輪次。⚠ MBPP+ 的題目比 LCB 短很多 ⇒ 中心估計對它是**上偏**的 |
| 牆鐘（3 槽） | **約 14 小時** | 21 小時 | 上界＝直接套「85 rows/小時、3 槽」⇒ 1,647 ÷ 85 ＝ 19.4 h ＋ 量具 0.85 h ≈ **21 h**。中心＝那個 85 rows/h 是**六臂**量到的，而六臂的 token 負載是本 run 的 3.2 倍（46,279 vs 14,395 token/題）⇒ 若吞吐是 token-bound，三臂約 137 rows/h ⇒ 12 h ＋ 量具 0.85 h ≈ **13 h**。取 13–21 h，主估 14 h |
| 量具（含在上面） | 2.5 小時算力 | — | MBPP+ 12 塊 × 11.9 分（實測外推）＋ LCB 7 塊 × 約 1 分；三槽併發 ⇒ 牆鐘約 0.85 h |

**這是「未驗證的宣稱」不是結果**：上面每一格都是**估計**，收官要拿
`summary.json` 的實測回填並把差異寫出來。

---

## 七、本輪已落地的程式碼改動（發射前，零模型呼叫）

| 改動 | 檔案 | 為什麼 | 牙齒 |
|---|---|---|---|
| `lcb_strata()`／`LCB_STRATUM_KEYS` | `vacant/codebench.py` | 把 LCB 的平台原生分層標籤（`difficulty`／`platform`）開給 runner，**走一支只給 runner 用的旁路**，不動 `iter_tasks` 吐的 task dict、不動 `public_view` ⇒ agent 那一側逐位元不變 | `tests/test_bank_filter_r529.py::test_strata_map_covers_every_task_in_every_lcb_bank` |
| `--bank-filter` | `ops/gain/gain_run.py` | 切層在 `offset`／`n` **之前**做 ⇒ `--offset` 數的是該層之內的第幾題，切塊語意與不切層時逐字相同 | `test_offset_counts_inside_the_stratum_and_blocks_stay_disjoint`、`test_lcb3_difficulty_strata_partition_the_bank_exactly` |
| key 白名單只有兩個 | 同上 | 開放任意欄位 ⇒ 有一天會有人用 `n_hidden_total=24` 切層，那等於讓**隱藏測資的形狀**決定哪些題進 run（V/GT 分離的旁路） | `test_hidden_shaped_keys_are_not_selectable` |
| 對不上一律 `SystemExit` | 同上 | 不認得的 key／題庫裡沒有的 value／沒有分層標籤的 bank／壞語法，四種都停。**量不到不是通過** | `test_bad_filters_stop_instead_of_quietly_selecting_something`（10 個參數化案例） |
| rows／summary 的新欄位是**條件的** | 同上 | 沒給 `--bank-filter` 就完全不出現 `bank`／`bank_filter`／`stratum` ⇒ **R460R 那 30 塊正在跑，它們的 rows.jsonl／summary.json 形狀一格不變** | `test_row_and_summary_keys_only_appear_when_a_filter_is_given`、`test_unfiltered_load_is_unchanged` |
| `instrument.gauge_in_filter_n` | 同上 | 擴大量具不准順手把「這一層沒有一題被參考解直接驗過」蓋掉（§五-2） | 落盤欄位＋`notes.jsonl` |
| builtin 無限池護欄 | 同上 | `--bank builtin` 原本一按就掛死（§一-4）。改成取需要的前綴；`n=0`（＝整個題庫）對無限池沒有定義 ⇒ 明講，不默默取一個上限 | `test_builtin_bank_does_not_hang_forever`、`test_builtin_with_n_zero_stops_instead_of_hanging` |

**沒有動到的**：`arm_off`／`arm_off5`／`arm_conform`／`arm_eq5`／`arm_on`／`arm_onr`／
`extract_code`／`meets_demand`／`behavior_signature`／`conform_failure_detail`／
`_visible_test_slicer`／`ClineBrain.generate` ——
T12 的原始碼 sha 釘死（`tests/test_gain_harness_arms.py`）全數通過。
`ops/gain/harness_arms.py` **一個字沒改**。

### 七-1　發射前還**沒有**做完的事（阻斷項，逐條）

1. **`ops/gain/analyze_r529.py` 不存在。** `ops/gain/analyze_r460.py` 寫死
   `H_ARMS = ("HPI","HOC","HMIX")` 且要求 `holm.family_size == 6`，
   **在三臂五集上跑不出正確的仲裁值**。R529 需要自己的 analyzer，
   仲裁欄位的規格逐字在 §六-1／§六-2／§六-5，並且要有 `--selftest`
   （在 R460 六塊上對釘已知答案）與 `--mutation-check`。
   **這支寫完並自測通過之前不准發射。**
2. **Fable 尚未稽核本檔。** §六-3 那個取捨（三臂 ⇒ `EFFECTIVE` 不可達）
   是最需要被看一眼的地方。
3. **人類尚未裁決 §六-3 的價目表**（三臂 14 小時 vs 四臂 28 小時）。

---

## 八、與 R460R 共用機器：**不搶槽**

### 八-1　現況（2026-09-11，對 vacant-dev 的唯讀查證）

`ps` 顯示 `schedule_harness_reps.py --reps 1 2 3 --hosts 1004` 正在跑，
三個 `gain_run.py` 行程分別在 `g_r460r1_harness_lcb2_a1/a2/a3`。
⇒ **1004 的三個槽全滿**；1003 依 R460R §一〇 修訂 A 被人類拿走，**一塊都不准上**。

R460R 這一輪（`--reps 1 2 3`）的總量：18 塊 × 20 題 × 6 臂 ＝ 2,160 列，
發射時間 03:14，本檔寫成時三塊剛起跑。以 85 rows/h 估 **約 25 小時**
（這是總長不是剩餘，剩餘要看當下的 `summary.json`）。

### 八-2　排法：**R529 一塊都不發，直到 R460R 收完**

事前寫死，不是「盡量不要撞」：

1. **前提條件（發射器要先問）**：vacant-dev 上
   `pgrep -f schedule_harness_reps.py` 為空 **且** 18 個
   `runs/g_r460r{1,2,3}_harness_lcb2_{a1,a2,a3,b1,b2,b3}/summary.json`
   全部 `run_terminal == true`。**任一不成立 ⇒ 不發射。**
2. **不共用排程器。** `ops/gain/schedule_harness_reps.py` 的 `SLOTS`／`REPS`
   是 R460R 註冊的東西（R460R §一〇 逐字寫著「表是註冊了什麼」）——
   **不准**為了塞 R529 去改那張表。R529 要排程就另寫一支，或者一塊一塊手發。
3. **1004 的上限仍然是凍結的 3。** R460R 跑完**不是**在 1004 上加併發的理由。
4. **1003 不碰。** 人類正在用那台機器（R460R §一〇 修訂 A）。
   要不要放回來是人類的決定，本檔不預設。
5. **若人類要更早拿到 R529 的一部分**：合法的做法是**縮 R460R 的範圍**
   （它本來就只跑 r1–r3，r4/r5 尚未排隊），**不是**在 1004 上多開一個槽。

### 八-3　時間線（估計，不是承諾）

R460R 剩約 25 小時 → R529 約 13–21 小時 ⇒ **R529 的最後一塊約在 38–46 小時後收完**。
兩者都在同一顆 1004 上依序跑 ⇒ §九-3 那條「那顆卡的狀態是整批資料的共同因子」
（R460R §六-10）對 R529 **同樣適用**。

---

## 九、自我驗證（發射前做完，零 API、零模型呼叫）

### 九-1　兩顆 seed 是新的（2026-09-11 實跑）

```
python3 - <<'PY'
import glob, json
seeds = {}
for f in sorted(glob.glob("runs/*/summary.json")):
    try: seeds.setdefault(json.load(open(f, encoding="utf-8")).get("seed"), []).append(f)
    except Exception: pass
for s in ("g-r529-lcb3", "g-r529-mbpp"):
    print(s, "->", seeds.get(s))
print("g_r529* 目錄:", glob.glob("runs/g_r529*"))
PY
```

實跑：掃過 **50** 個 `runs/*/summary.json`，兩顆 seed 都是 `None`（一次都沒被用過）；
`runs/` 底下 `g_r529*` 目錄 **0 個**。

### 九-2　§三 的五條取樣不變量可重算

```
python3 - <<'PY'
import sys; sys.path.insert(0, ".")
from ops.gain.gain_run import load_tasks, GAIN_EVALPLUS_RESOURCE_EXCLUSIONS
S = {}
S["lcb3_hard"]   = [t for o in (0, 27) for t in load_tasks("lcb3", "g-r529-lcb3", 27, offset=o,  bank_filter="difficulty=hard")]
S["lcb3_medium"] = [t for o in (0, 27, 54, 81, 108) for t in load_tasks("lcb3", "g-r529-lcb3", 27, offset=o, bank_filter="difficulty=medium")]
for k, base in (("mbpp_1", 0), ("mbpp_2", 120), ("mbpp_3", 240)):
    S[k] = [t for o in range(base, base + 120, 30) for t in load_tasks("evalplus", "g-r529-mbpp", 30, offset=o)]
ids = {k: {t["task_id"] for t in v} for k, v in S.items()}
print({k: len(v) for k, v in ids.items()}, "Σ =", len(set().union(*ids.values())))
for a in ids:
    for b in ids:
        if a < b: assert not ids[a] & ids[b], (a, b)
assert all(t["family"] == "lcb_leetcode_hard"   for t in S["lcb3_hard"])
assert all(t["family"] == "lcb_leetcode_medium" for t in S["lcb3_medium"])
assert all(t["task_id"].startswith("mbppplus_") and t["task_id"] not in GAIN_EVALPLUS_RESOURCE_EXCLUSIONS
           for k in ("mbpp_1", "mbpp_2", "mbpp_3") for t in S[k])
print("五條不變量全過")
PY
```

### 九-3　`--bank-filter` 的牙齒

```
.venv/bin/python -m pytest tests/test_bank_filter_r529.py -q
```

### 九-4　R529 這個編號沒有被用過

```
ls DECISION_*.md ops/gain/DECISION_*.md CONCLUSION_*.md 2>/dev/null | grep -c "_R529"   # 應為 0（本檔除外）
```

### 九-5　測試套件**不是全綠**，而且那不是本輪造成的（照實記）

`.venv/bin/python -m pytest tests/ -q` 在本分支（`feat/v2-four-stages`）上有
**7 個失敗**。本輪先把改動 `git stash` 起來在**乾淨工作樹**上跑過一次，
失敗的是**同樣那 7 個、一個不多一個不少**：

| 失敗 | 原因 |
|---|---|
| `test_runs_index.py::test_dirs_with_summary_json_is_44`、`::test_generator_runs_as_a_script` | `runs/` 現在有 **50** 個帶 `summary.json` 的目錄，索引與測試都還釘在 **44**。`python3 ops/gain/build_runs_index.py --check` 也 FAIL |
| `test_r449b/test_r449c::test_seed_is_absent_from_every_run_summary`、`::test_mutation_stale_seed_is_caught_only_by_the_summary_scan` | 同源：那幾支掃**所有** `runs/*/summary.json`，新出現的 run 目錄讓 seed 掃描結果變了 |
| `test_r448_launcher_prereg.py::test_r448_run_dir_is_not_created_by_this_test` | 同源：`runs/` 底下多了東西 |

⇒ **`runs/INDEX.md`／`INDEX.json` 已經漂掉，要重跑產生器並更新那幾個釘值。**
本輪**不動它**：重跑索引會改動 300+ 行、而且會把「索引是什麼時候重建的」
混進一個談題庫分層的 commit 裡。這是一筆**已知未償**，記在這裡讓它不會被忘掉。

實跑最後一行（`.venv/bin/python -m pytest tests/ --tb=no`，**注意 `pyproject.toml`
的 `addopts = "-q"` 已經給了一個 `-q`，再給一個會變成 `-qq` 而吞掉計數那一行**）：

```
8 failed, 1289 passed in 1205.61s (0:20:05)
```

### 九-5a　第 8 個失敗是**偶發**的，而且它指向本 run 的一個真實風險

三次全套裡有一次多出
`tests/test_gain_harness_arms.py::test_t4_four_failure_kinds_and_two_distinct_loader_reasons`。
**單獨重跑通過。** 它是負載相依的偶發——與 R460 收官 §一〇 補記記到的同一類
非決定性（離線重跑 `meets_demand` 時沙箱 10 秒逾時在不同負載下會飄）。

⚠ **這不是「無關的雜訊」，它是 R529 要一起帶著的風險**：H-MIX 的出貨閘門
（`visible_report`）與計分（`meets_demand`）都跑在同一個 10 秒逾時的沙箱裡。
機器負載高的時候，**同一份候選碼的判定會飄**。R529 的 19 塊要在 1004 上
連跑十幾個小時，而且是接在 R460R 30 塊之後 ⇒ 收官時若出現
「同一題在兩塊之間判不一樣」，第一個要查的是這裡，不是模型。
⇒ 記進 §一一 誠實邊界。

本輪**新增**的 `tests/test_bank_filter_r529.py` **25 項全綠**（單獨跑、全套跑都是），
且 T12 的原始碼 sha 釘死（`test_gain_harness_arms.py::test_t12_…`）通過
——`--bank-filter` 沒有碰到既有五臂。

---

## 一〇、中止準則（發射之後，什麼情況要停）

1. **任一塊的任一臂 `infra_void / processed > 20%`** ⇒ 那一塊作廢重排
   （沿用 R460 §十／R460R §四-2 的 20% 線）。**只重排一次**；
   重排無上限＝「一直重試到資料看起來正常為止」＝選擇性重跑。
2. **某一題目集少一塊** ⇒ 該集 `block_count_mismatch` ⇒ **那一集 INVALID，不判**。
   **不准**就地把 §六 的門檻搬到縮水的 n 上重讀（R460 §六-(6)-i 的同一條）。
   ⚠ 其餘四集照跑照判，但 Holm 家族**仍然是 10**（§六-2）——
   少一集不准把家族縮成 8 再重算。
3. **`--scope v2` 的稽核在任何一塊報出違規** ⇒ **整個 run 作廢**（§五-4）。
4. **R460R 還在跑而 R529 的塊被發出去了** ⇒ 立刻停 R529 的塊並記一筆
   （§八-2 的前提條件被繞過＝這批資料的併發條件不明）。
5. 五個題目集**沒有全部收完之前不得發布任何跨集彙總數字**（§六-5）。

---

## 一一、誠實邊界（收官必須原樣帶著，一條都不准掉）

1. **只有兩個真正不同的來源。** 五個題目集裡有三個是 MBPP+ 的互斥切片
   ——那量到的是**題目層級的變異**，不是**來源層級的變異**。
   「跨五個題目集穩定」**不等於**「跨五種任務類型穩定」。
2. **單一模型、單一後端、單一 harness 實作。** 五集共用 `gemma-4-12b-it-qat`
   與同一顆 1004；那顆卡在這幾天的任何漂移會**同時**打到五個題目集
   （R460R §六-10 的同一條）。
3. **LCB v3 的污染風險比 v1/v2 高。** 189 題全部不晚於 2024-08-10，
   **不能**宣稱晚於訓練截止（R460 C3；`vacant/codebench.py` 有同一句）。
   ⇒ 若 v3 上的 Δ_C 比 lcb2 小，「污染把兩臂一起抬到天花板」與
   「效果真的比較小」**分不開**，收官必須兩個解釋都列。
4. **`lcb3_hard` 的 n 只有 54**，Holm 之後的檢定力 0.138（§四-3）。
   那一格判 `INCONCLUSIVE` 是設計的已知代價，**不是**證據。
5. **`EFFECTIVE` 在本 run 結構上不可達**（§六-3）。收官寫的任何一句話
   都不得讀成「H-MIX 在新題庫上又拿到一次 EFFECTIVE」。
6. **量具在 hard 層只直接驗過 3 題**（§五-2），`gauge_in_filter_n` 要照實列。
7. **MBPP+ 上的 V/GT 豁免數會遠高於 R460**（§五-3），那是題庫結構不是洩漏；
   但這也意味著**稽核在 MBPP+ 上比在 LCB 上寬**，這一句要跟著豁免數一起講。
8. **winner's curse 照舊**：R460 的 +13.33pp 是**能被判顯著**的點估計 ⇒ 上偏。
   ⇒ **本 run 的點估計預期會比 +13.33 小，那是預期之內的事，不是「效果消失」。**
9. **`--bank-filter` 是本輪新寫的。** 它的牙齒在合成案例上驗過
   （`tests/test_bank_filter_r529.py`），但**沒有**在一次真跑上驗過。
   第一塊收完時要逐條核對 rows 的 `stratum`／`family` 與預期的 54／135 相符。
10. **沙箱在負載下會飄**（§九-5a）。出貨閘門與計分共用同一個 10 秒逾時的沙箱，
    而 19 塊要在同一顆卡上連跑十幾個小時、接在 R460R 之後。
    ⇒ 收官若出現「同一題在不同塊之間判不一樣」，**第一個要查的是沙箱不是模型**
    （R460 §一〇 補記的同一條）。本 run **沒有**為此設事前探針，
    這是已知的量具邊界，不是量到的東西。

---

## 一二、能講的話與必帶的前提（`COSTLY_BUT_REAL` 那格的口徑）

收官時**唯一**可以往外講的形狀（照 §六-5 的宣稱規則逐字判到哪一句講哪一句）：

> 在 N 個互斥的題目集上（兩個來源：LeetCode 競賽題與 MBPP+），
> 把同樣的呼叫預算花在「跑客戶的驗收測資、把失敗原文貼回去、讓它改」，
> 對照花在換人重抽，逐集的差是 …（逐集列點估計與未調整區間），
> 其中 k 個題目集在 Holm 校正後 `p_adj < 0.05`。

**必帶的前提，一條都不准掉：**

- **R440P 前提句**：R440P 量到 **17–19% 的題目五份候選全錯**——
  **選擇規則**（重抽、投票）打不破這個候選池天花板，因為它只能在錯的候選裡挑；
  **修訂迴圈**在原理上可以，因為它改變候選本身。本 run 量的是後者有沒有兌現，
  而不是「harness 比較聰明」。
- **可執行驗收的前提**：整件事建立在「需求可以被編譯成可執行的驗收測資」。
  需求跑不起來的場合，這個機制沒有免費的裁判，會退化成「問一個模型」。
- **worker 看得到客戶可見測資的內容與期望值**；隱藏測資只計分，
  動態稽核逐塊核過（§五-3）。
- 上面 §一一 的九條誠實邊界。

**不能講**：不能講「證明」；不能講「harness 才是關鍵」的一般性質
（外部同模型證據全距 2.7pp）；不能講 ≥15pp 的實務增益；
不能把五集的點估計平均或併 n；不能把 `INCONCLUSIVE` 讀成「等價」或「打平」；
不能宣稱本 run 的題目晚於訓練截止。

---

## 一三、這份預註冊自己的邊界

- 本檔由 Opus 實作、**待 Fable 稽核**。§六-3（三臂 ⇒ `EFFECTIVE` 不可達）
  與 §五-2（量具不切層）是最需要被看一眼的兩處。
- 本檔**沒有**改動 R460 §六 的任何一格門檻。§六-3 改的是**可達狀態的集合**，
  不是門檻本身；若 Fable 判定這仍然算改判準，那就要加回 OFF5 成四臂（§六-3 的價目表）。
- 本檔**不授權發射**：§七-1 的三個阻斷項（analyzer 不存在、Fable 未稽核、
  人類未裁決臂數）任一未解 ⇒ 不准發。
- 本檔只出檔案、指令與判準，發射由稽核 session 之外的人執行。
