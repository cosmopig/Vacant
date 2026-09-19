# R534 題庫（LCB v2 選 20 題）——選了什麼、為什麼、怎麼驗

這一份講**題目**：哪 20 題、規則是什麼、渲染出來的檔案長什麼樣、怎麼證明那些檔案
與既有 run 用的是同一把尺。R534 的跑法（pi agent、兩台後端、思考／不思考）不在
這一份裡。

## 一、三個檔案就是全部

| 檔案 | 是什麼 |
|---|---|
| `select_tasks.py` | 選題規則（對已歸檔 run 的確定性函式），規則逐字在 `RULE_TEXT` |
| `build_bank.py` | 渲染器：把選中的題投影成 `templates/`＋`hidden/` 兩棵樹，寫 `bank_manifest.json`；`--check` 驗有沒有漂 |
| `gauge_bank.py` | 量具：樁被擋、探針解通過、**與既有判準逐份比對**（零模型呼叫） |

產物：`templates/<task_id>/`（工作區樣板）、`hidden/<task_id>/`（只給計分）、
`bank_manifest.json`（＋`bank_manifest.sha256`）。

```
templates/<task_id>/                    hidden/<task_id>/
    goal.md            ← prompt 逐字        test_hidden.py   ← 可見 ∪ 隱藏
    contract.md        ← 介面釘死
    tests_visible/test_visible.py         ← 出貨閘門，agent 跑得到
    run_tests.sh       ← 一行跑完（形狀沿用 r530）
```

`hidden/` **不是工作區的子目錄**，是另一棵樹：agent 的工作目錄裡結構上不存在那條
路徑。20 個樣板裡沒有任何一個檔案出現 `hidden` 字樣（`build_bank.py` 會掃、
`grep -ril hidden templates/` 為空）。

## 二、選取規則（逐字，事前寫死）

規則全文在 `select_tasks.py::RULE_TEXT`，並原樣抄進 `bank_manifest.json`
（`selection_rule`，sha256 `231971f3bad306f6…`＝manifest 的 `selection_rule_sha256`）。摘要：

- **R0/R1 母體**：`ops/gain/data/lcb_bank_v2.jsonl` 120 題（sha256
  `b98f027213e2469a…`）扣掉 `check_bank_precision.py::KNOWN_BAD` 的
  `lcb_3613`／`lcb_3763` ⇒ **118 題**。
- **R2 證據**：只讀已歸檔 rows.jsonl。12B 層＝`runs/g_r460_harness_lcb2_{a1,a2,a3,b1,b2,b3}`
  （gemma-4-12b-it-qat，六臂）；27B 層＝`runs/g_r532_lcb2_a{1..6}`（qwen3-27b，三臂）。
  每層 6 塊 × 20 題 ＝ 全 120 題，每格一個觀測，沒有 null、沒有 infra_void。
- **R3/R4 分歧度**：六個閘門對（12B 的 OFF↔CONFORM/HPI/HOC/HMIX、27B 的
  OFF↔CONFORM/HMIX），每對 OFF 敗而閘門臂成＝+1、反向＝-1，
  `D_net = D_plus - D_minus ∈ [-6, +6]`。**OFF5 不列入**——它是等預算多數決，
  沒有驗收閘門語意，算進來會讓「分歧」混進「多花錢」。
- **R5 A 層**：依 `(D_net↓, D_plus↓, OFF 通過數↑, task_id↑)` 取前 10。
- **R6 B 層**：從扣掉 A 層之後的 108 題，用
  `random.Random("r534-layerB-lcb2-2026-09-18").sample(...)` 抽 10。
- **R7 報告紀律**：兩層**分開報**，不合併、不加權。
- **R8 誠實邊界**：每題每臂每層只有一個觀測，`D_net` 是帶雜訊的排序鍵。

### 這個規則自己會製造的偏誤（要寫進報告）

A 層是**條件在過去結果上**挑出來的：那 10 題「OFF 失敗、閘門臂成功」在歷史資料
裡各發生了 5–6 次。重跑會有向均值回歸，**A 層的差值結構性地上偏**，它回答的是
「閘門有機會發揮時長什麼樣」，不是題庫層級的估計。
B 層抽的是**扣掉 A 層之後**的剩餘 ⇒ 高分歧題已被抽走一部分，B 層的差值是**偏保守**
的那一側。兩個數字方向相反，所以更不能平均成一個。

## 三、選了哪 20 題

`meets_demand` 欄位是已歸檔 run 的逐題結果（1＝隱藏測資判過）。
`正控制`＝歷史上有沒有任何一個臂通過過（見第五節）。

| 層 | task_id | 難度 | entry_point | D_net | D+ | D- | 12B OFF/CONFORM/HPI/HOC/HMIX | 27B OFF/CONFORM/HMIX | 可見 | 計分 case | 正控制 |
|---|---|---|---|---:|---:|---:|---|---|---:|---:|---|
| A | `lcb_3534` | medium | `countPairs` | +6 | 6 | 0 | 0/1/1/1/1 | 0/1/1 | 3 | 27 | ✓ |
| A | `lcb_3548` | hard | `countGoodIntegers` | +6 | 6 | 0 | 0/1/1/1/1 | 0/1/1 | 3 | 27 | ✓ |
| A | `lcb_3779` | medium | `maxWeight` | +6 | 6 | 0 | 0/1/1/1/1 | 0/1/1 | 2 | 26 | ✓ |
| A | `lcb_3627` | medium | `minTimeToReach` | +5 | 5 | 0 | 0/0/1/1/1 | 0/1/1 | 3 | 27 | ✓ |
| A | `lcb_3649` | medium | `findMinimumTime` | +5 | 5 | 0 | 0/1/1/1/1 | 0/1/0 | 2 | 26 | ✓ |
| A | `lcb_3657` | medium | `checkValidCuts` | +5 | 5 | 0 | 0/1/1/1/1 | 0/0/1 | 3 | 27 | ✓ |
| A | `lcb_3687` | hard | `longestSpecialPath` | +5 | 5 | 0 | 0/0/1/1/1 | 0/1/1 | 2 | 26 | ✓ |
| A | `lcb_3715` | medium | `maximumCoins` | +5 | 5 | 0 | 0/0/1/1/1 | 0/1/1 | 2 | 26 | ✓ |
| A | `lcb_3783` | hard | `permute` | +5 | 5 | 0 | 0/1/1/1/1 | 0/0/1 | 3 | 27 | ✓ |
| A | `lcb_3789` | hard | `maxSubarrays` | +5 | 5 | 0 | 0/1/1/1/1 | 0/0/1 | 2 | 26 | ✓ |
| B | `lcb_3522` | medium | `resultsArray` | +2 | 2 | 0 | 1/1/1/1/1 | 0/1/1 | 3 | 27 | ✓ |
| B | `lcb_3583` | hard | `gcdValues` | -1 | 0 | 1 | 1/1/1/1/1 | 1/0/1 | 3 | 27 | ✓ |
| B | `lcb_3584` | medium | `validSequence` | ±0 | 2 | 2 | 0/1/0/0/1 | 1/0/0 | 4 | 28 | ✓ |
| B | `lcb_3637` | hard | `countBalancedPermutations` | +4 | 4 | 0 | 0/1/1/1/1 | 1/1/1 | 3 | 27 | ✓ |
| B | `lcb_3654` | medium | `minArraySum` | -2 | 0 | 2 | 1/1/0/0/1 | 1/1/1 | 2 | 26 | ✓ |
| B | `lcb_3681` | medium | `maxRectangleArea` | +2 | 2 | 0 | 1/1/1/1/1 | 0/1/1 | 3 | 27 | ✓ |
| B | `lcb_3686` | medium | `beautifulSplits` | ±0 | 0 | 0 | 0/0/0/0/0 | 0/0/0 | 2 | 26 | **無** |
| B | `lcb_3700` | hard | `subsequencesWithMiddleMode` | ±0 | 0 | 0 | 0/0/0/0/0 | 0/0/0 | 3 | 27 | **無** |
| B | `lcb_3764` | medium | `maxSum` | ±0 | 0 | 0 | 1/1/1/1/1 | 1/1/1 | 2 | 26 | ✓ |
| B | `lcb_3794` | medium | `minTime` | ±0 | 0 | 0 | 1/1/1/1/1 | 0/0/0 | 3 | 27 | ✓ |

難度分布：medium 13、hard 7。樣板大小 4,315–5,582 B。

## 四、三個「照抄不動」的決定

1. **`goal.md` ＝ 題庫 `prompt` 欄位逐位元組**。r460／r532 送給模型的就是這個字串；
   改寫一個字，這 20 題就不再與那兩組歸檔資料比得起來。prompt 尾端那三行中文
   （頂層函式、只用標準函式庫、要 return）是題庫產生器加的，照樣留著。
2. **比對器沿用 `vacant/codebench.py::_lcb_check_code` 的 `__aeq`**（先 `==`、
   bool 不與數值混談、數值 1e-6、list/tuple 遞迴），斷言訊息維持
   `args=… got=… want=…` 三欄位逐字——H 臂的回饋就是轉發這個字串。
3. **`test_hidden.py` ＝ 可見 ∪ 隱藏**（26–28 條），與 `LiveCodeBenchLoader`
   的 `hidden_check` 同一組 case ⇒ 分子與 r460／r532 的 `meets_demand` 是同一把尺。
   換成「只有隱藏那 24 條」會是另一個指標，兩邊數字不可互引。

## 五、量具（`gauge_bank.py`，零模型呼叫）

實測結果：

```
fail-closed     20/20 題：return None 的樁，可見與隱藏都判不過
正控制          1/20 題（lcb_3779，手寫探針解全過）
等價比對        100 份已歸檔候選碼，既有判準 vs 渲染測試檔 100/100 一致
沙箱政策擋掉    12 份候選（那 12 份上兩條路徑本來就會不同）
verdict = OK
```

**兩個要寫進報告的邊界，不准省略：**

- **正控制只有 1/20。** LCB 沒有 canonical solution，r530 的雙向量具（參考解全過／
  壞樁全擋）在這裡做不到。`lcb_3686`／`lcb_3700` 這兩題**歷史上沒有任何一個臂通過過**
  ⇒ 我們沒有證據證明一個正確解會被判過（manifest 的 `any_arm_passed_hidden=false`）。
- **渲染檔比既有判準寬。** `vacant/checks.py` 的 AST 政策連 `list.remove` 都擋
  （`_FORBIDDEN_ATTRS`）、第三方 import 一律擋（R393 的 typing 坑就是這條）。
  被政策擋掉的碼，既有判準連跑都不跑就判 False，渲染出來的 `test_hidden.py` 會照跑。
  ⇒ **R534 的主指標走既有那條**：
  `gain_run.meets_demand(code, _lcb_check_code(ep, visible+hidden), entry_point=ep)`
  （manifest 的 `scoring.primary_numerator`）。兩條路徑的數字不可混報。

## 六、重跑與驗收

```bash
python3 ops/gain/r534/select_tasks.py          # 印規則與兩層選題
python3 ops/gain/r534/build_bank.py            # 重新渲染（確定性）
python3 ops/gain/r534/build_bank.py --check    # 驗磁碟與 manifest 沒漂
python3 ops/gain/r534/gauge_bank.py            # 量具（約數分鐘，零模型呼叫）
```

`bank_manifest.json` sha256：見 `bank_manifest.sha256`（渲染時一併寫出）。
