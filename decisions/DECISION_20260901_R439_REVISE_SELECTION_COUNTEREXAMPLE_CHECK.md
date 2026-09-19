# DECISION round439：revise 選擇邏輯改用「反例本身」驗收，不是重跑同一份可見測資

**2026-09-01 UTC ~05:30-05:45，Sonnet 5。**（時間戳訂正：先前版本誤寫成
06:20-07:10，那是還沒發生的未來時刻，是筆誤不是真的耗時——本輪開場
`date -u` 讀到的是 05:30:59，寫 DECISION 這段時已過約 10-15 分鐘。）

## 背景

round437 把決定性 run（`g_r356_3arm_20260830`）帶到終點：等預算下 ON 打不贏
OFF5（typing 修正版 p=0.4531，raw 版 p=0.7905，方向不穩定）。round438 往下
挖了一層機制解釋：`analyze_revise_counterfactual.py` 量到 113 題裡
`discarded_win=0`——**選擇邏輯從來沒有錯殺任何一次 revise 帶來的真修正，
因為 revise 幾乎從不產生真修正**（113 題只有 1 題 `revision_transition=improved`）。
round438 明確把這個發現列為下一步方向之一：「改機制設計再驗證」，
但判斷這輪不動 `gain_run.py`、留給下一輪判斷。

本輪（round439）讀 `arm_on` 的選擇邏輯，找到一個**具體、可歸因的設計缺口**，
不是「revise 天生沒用」這種籠統結論，而是**現有的驗收方式本身量不出
revise 有沒有用**。

## 發現：`revised_visible_ok` 驗的不是「反例修好了沒」

`arm_on`（round439 之前）：

```python
revised_visible_ok, _ = meets_demand(
    revised_code, task["visible_check"]["code"], entry_point=...)
if passed_review and initial_visible_ok:
    code = initial_code            # 有機會 revise 但沒被選（no_opportunity）
elif revised_visible_ok:
    code = revised_code            # 這裡：只驗證 revised 有沒有過「原本那份可見測資」
elif initial_visible_ok:
    code = initial_code
else:
    code = revised_code
```

`revised_visible_ok` 呼叫的 `task["visible_check"]["code"]` 跟驗 `initial_visible_ok`
的**是同一份測資**。但 reviewer 之所以判 FAIL、之所以觸發 revise，前提是
`verify_review_counterexample` 已經**機器執行確認**了一個 initial 過不了的反例——
而這個反例定義上常常是可見測資量不到的域（否則 initial 早就在可見測資那關
被擋下來了）。所以「revised 有沒有過可見測資」跟「revised 有沒有修掉那個
被證實的反例」是**兩個不同的問題**，舊邏輯只驗第一個，卻拿它的答案去決定
第二個問題該不該用 revised。這就是為什麼 revise 可以被選中卻對
`hidden_check` 沒有淨貢獻（round438 的 82.3%→78.8%）——選擇邏輯從沒真的
檢查過它是不是在瞎改。

## 改動（`ops/gain/gain_run.py`）

1. 把反例驗證的斷言字串抽成獨立函式 `counterexample_check(entry_point, args,
   expected)`（原本內嵌在 `verify_review_counterexample` 裡，簽名/行為不變，
   只是抽出來給第二個呼叫點重用）。
2. 在審查迴圈裡，每個被 `verify_review_counterexample` **機器確認**的反例，
   額外用 `parse_review_claim` 重新解析同一份 review 文字拿到 `(args,
   expected)`，累積成 `confirmed_checks`（可重放的斷言字串列表）。
3. 產生 `revised_code` 之後，新增：
   ```python
   revised_fixes_counterexamples = all(
       meets_demand(revised_code, chk, entry_point=...)[0]
       for chk in confirmed_checks
   ) if confirmed_checks else True
   ```
4. 選擇邏輯：`elif revised_visible_ok and revised_fixes_counterexamples:` 才選
   revised；否則按原本的優先序退回 initial（若它過可見測資），最後才是
   「兩邊都沒被驗證修好，但至少 revised 沒讓可見測資更差」的新分類
   `revised_unconfirmed_fallback`（跟舊版就有的 `revised_both_visible_fail`
   分開記，離線分析看得出差別）。

**沒有改變的**：`calls[0]` 的計數方式完全沒動——revise 仍然無條件呼叫一次
（第五次呼叫），`calls_per_task` 仍然是 5。`summary.json` 的
`equal_budget_comparison_valid`（要求 `calls_per_task == 5`）不受影響。
**這是本輪選擇這個修法而不是「只在有反例時才 revise」的主因**：後者會讓
ON 的 `calls_per_task` 變成非固定值，直接打破 round437/438 賴以成立的
等預算比較框架，需要重新設計整個預算會計，風險與工作量都遠大於本輪範圍。
本輪的改動只動「選誰」，不動「花幾次呼叫」。

## 驗證（做之前先寫死判準，再測）

**判準寫在測試之前**：

1. 既有測試場景（`tests/test_gain_runner.py::
   test_on_uses_three_reviews_and_revision_for_equal_five_call_budget`）
   裡 revised 真的修好了 reviewer 指出的問題（`x -> x+1` 對 `TEST_ARGS:[1]
   EXPECTED:2`），**改動後這題必須仍然選 `"revised"`**——這是回歸測試，
   不是新行為。
2. 構造一個新場景：reviewer 給出**機器確認**的真反例，但 revise 產出的碼
   對那個反例**沒有修好**（`solve(x): return x` 原封不動），且可見測資刻意
   設成 `"assert True"`（跟 `x` 完全無關，永遠通過，模擬「可見測資量不到
   反例那個域」的真實情況）。**改動前**：`revised_visible_ok` 為真 ⇒ 舊邏輯
   會選 `"revised"`，把一份沒修好的碼蓋上「revised」的標籤放行。
   **改動後**：`revised_fixes_counterexamples` 必須為 `False`，
   `selected_version` 必須**不是** `"revised"`。

實測（無 pytest 環境，手動執行等價邏輯，見下方指令）：

```
TEST 1（既有場景，回歸）：selected_version=revised,
  revised_fixes_counterexamples=True, confirmed_counterexample_count=3  ✓
TEST 2（新場景，抓舊 bug）：selected_version=initial_fallback,
  revised_fixes_counterexamples=False, confirmed_counterexample_count=3,
  passed_review=False, initial_visible_ok=True, revised_visible_ok=True  ✓
  （revised_visible_ok=True 這裡故意設成 True，證明舊邏輯在這個分支
  一定會選 revised；新邏輯改選 initial_fallback，行為確實改變了）
verify_review_counterexample 的三個既有斷言案例（counterexample_confirmed／
candidate_passed_claim／outside_input_contract）逐字元照舊 ✓（重構只是抽函式，
沒有動判斷邏輯本身）
```

`pytest` 在這台機器上不可用（`pip3`/`.venv` 都不存在，
`python3 -c "import pytest"` ⇒ `ModuleNotFoundError`）——**這是環境限制，
不是繞過測試**：上面的驗證直接呼叫 `arm_on`／`verify_review_counterexample`
本體並手動斷言，覆蓋的斷言與 `tests/test_gain_runner.py` 裡對應測試逐條相同。
下一輪如果環境裡有 pytest，應該補跑 `python3 -m pytest tests/test_gain_runner.py
tests/test_evalplus_loader.py -q` 做一次正式確認（本輪判斷不值得為了跑一次
測試去 `pip install`，那是環境變更，且沒有 sudo 也裝不了系統級的）。

## 這是一個實驗條件變更——不是 bug 修復

`ops/gain/gain_run.py` 的邏輯變了，任何用這個新版本重跑的 run 跟
`g_r356_3arm_20260830`（round437 那個決定性 run）**不是同一個實驗條件**，
不能直接拿新 run 跟舊 run 的配對分析混用。`g_r356_3arm_20260830` 保持原樣
不動、不刪，繼續是「審查關卡＋單輪修訂（未驗收版）」這個設計的紀錄。
新 run 要用新的輸出目錄。

## 預先寫死的成功判準（量測之前，不是量完再挑）

新 run（`g_r439_revcheck_*`）跑完後，用 `analyze_revise_counterfactual.py`
重跑機制分解，比對 round438 的基準（`discarded_win=0/113`，
`initial_hidden_pass=82.3%`，`revised_hidden_pass=78.8%`）：

1. **主要判準**：`discarded_win` 是否從 0 轉正、且
   `revised_hidden_pass - initial_hidden_pass` 的差距是否比 round438 的
   -3.5pp 收窄或轉正。轉正＝新選擇邏輯真的在挑出「revise 真的修好的那次」；
   收窄但仍負＝at least 不再選中「沒修好但矇混過可見測資」的版本，是部分改善；
   完全不變＝這個修法在這批題目上沒有可觀測的效果（`no_opportunity` 佔
   82% 這個大頭本來就不會被這個改動影響，所以「完全不變」是可能結果，
   不代表改動有問題，只代表它能起作用的空間本來就只有 18% 的題目）。
2. **次要判準**：ON vs OFF5 等預算配對（`analyze_paired.py`）的 gap／p 值，
   跟 round437 的最終數字（typing 修正版 p=0.4531，raw p=0.7905）比較方向
   有沒有動——**新 run 需要跑到接近完整 n 才能看，不是第一個檢查點就下結論**。
3. **推翻條件**：若 `discarded_win` 依然是 0 且 `revised_hidden_pass` 依然
   明顯低於 `initial_hidden_pass`，代表問題不在「選擇邏輯驗收不嚴謹」，
   而在「reviewer 找到的反例本身就是雜訊／revise 呼叫產出的碼品質本身就差」
   ——那會把下一步的方向推回 round438 列的另一個選項：換更強的評審模型，
   而不是繼續調選擇邏輯。

## 落盤與驗證

```
git add -A ops/gain/gain_run.py \
  DECISION_20260901_R439_REVISE_SELECTION_COUNTEREXAMPLE_CHECK.md
git commit -m "round439: revise selection verifies against the confirmed counterexample, not the same sparse visible suite (targets R438's discarded_win=0 finding); calls_per_task unchanged (still 5), equal-budget accounting untouched"
git push origin feat/v2-four-stages
```
（雜湊見 GAIN_STATE.md 本輪段落，push 後逐字元比對本地/遠端 HEAD）

## 下一輪該做什麼

1. 先跑 `--arms probe` 驗量具（鐵律：先驗雙向，官方參考解全過、壞解全擋，
   這是**每次正式跑之前**都要做的，改了 `gain_run.py` 更不能省）。
2. 用新程式碼起一個新的決定性 3-arm run（`--arms OFF,ON,OFF5`），輸出目錄
   `runs/g_r439_revcheck_<日期>`，`setsid nohup` 背景跑，n 先跟
   `g_r356_3arm_20260830` 對齊（179）方便比較，除非本輪或下一輪判斷要
   換池子/題庫（那要另開 DECISION）。
3. 這一輪不等它跑完——照 loop 慣例，長跑留給後續輪次同步進度。
