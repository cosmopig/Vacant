# DECISION 2026-08-24（round 13）：先把三臂比較報表寫好，不等 run 跑完才臨時判

## 一、為什麼現在寫，不是跑完才寫

`g_onoff5_qwenonly_v2_20260824`（round 12 修好 review timeout 後重開的跑法）
還在跑，估時量級是十幾小時（見 `DECISION_20260824_F_THRESHOLD_REACHED.md` §3、
`DECISION_20260824_REVIEW_TIMEOUT_BUG.md`）。本輪的任務照 round 11/12 自己定的
規矩是「不 block-wait，只快照進度」，但快照之外還有空檔——**判準怎麼套要現在
定，不要等數字出來才臨時決定「這樣算不算贏」**（呼應「判準規則要寫在量測之前」
這條一路以來的教訓）。

## 二、判準來源——逐字對應 SPEC_GAIN.md §3/§4，不是本輪自訂

> 「ON 要算贏，至少必須同時提高正確交付率，且等預算下不輸 OFF-5x；
> 精度提升但正確交付率未提升，只能宣稱『比較可依賴』，不能宣稱『產出變好』。」

`ops/gain/analyze_onoff5.py` 的 `verdict()` 就是把這句話翻成三個分支：
1. `ON_cdr > OFF_cdr` 且 `ON_cdr >= OFF5_cdr` ⇒ 贏。
2. `ON_cdr > OFF_cdr` 但 `ON_cdr < OFF5_cdr` ⇒ 提升了但打不贏 self-consistency
   （SPEC_GAIN.md §3 明講這也是一個要寫進展場的結論，不是失敗，是誠實的答案）。
3. `ON_cdr <= OFF_cdr` ⇒ 機制本身沒用。

**沒有做統計顯著性判定**——只比點估計。Wilson 95% CI 有算出來放在
每個臂的 `correct_delivery_rate_wilson_95ci`，但判準函式不擅自把「差一點」
講成「顯著」，CI 重不重疊留給讀報表的人（未來某一輪）自己看，不在這裡
寫死一個顯著性門檻（SPEC_GAIN.md 本身也沒訂那個門檻，本輪不代它訂）。

## 三、前提檢查——不齊就拒絕判定，不是硬套

寫判準之前，函式先擋三件事，任一件不成立就回傳「不判定」而不是硬算：
- 三個臂（OFF baseline、ON、OFF5）的 `summary.json` 紀錄都要在。
- `ON`／`OFF5` 的 `complete` 都要是 true（run 還在跑就不判）。
- `equal_budget_comparison_valid` 要是 true（`gain_run.py` 自己算的，
  要求兩臂 `calls_per_task` 都精確等於 5——這是「等預算比較」框架成立的前提，
  round 11 的 §4 已經把這個寫成推翻條件）。
- 額外加了 `seed` 一致性檢查：OFF baseline 跟 ON/OFF5 是兩個獨立 run 目錄，
  只有同 seed 才保證題目是同一批、可以逐題對照。目前 OFF baseline
  （`g_off60_qwenonly_20260824`）與 ON/OFF5（`g_onoff5_qwenonly_v2_20260824`）
  都用 `g-smoke-20260820`，本輪跑過 `--off-baseline` 驗證過 `seed_match: true`。

## 四、驗證過的行為（跑了三個合成案例，不是只讀程式碼相信它對）

用 `/tmp` 底下手造的假 `summary.json`（跑完即刪，不留在 repo）逐一跑過
`verdict()` 三個分支，輸出跟預期逐字相符：
- ON=0.80 OFF=0.60 OFF5=0.75 ⇒ 「ON 贏」
- ON=0.65 OFF=0.60 OFF5=0.75 ⇒ 「提升了但打不贏 self-consistency」
- ON=0.55 OFF=0.60 ⇒ 「沒有超過 OFF baseline」

對真實資料（`g_onoff5_qwenonly_v2_20260824` 現況，ON/OFF5 都還沒有
`summary.json.arms` 紀錄）也跑過一次，正確回報「資料不齊 ⇒ 不判定」，
沒有因為缺資料而崩潰或給假數字。

## 五、什麼條件下這份決定該被推翻

- 若之後發現 OFF baseline 跟 ON/OFF5 兩個 run 的**題目集合實際上不同**
  （即使 seed 字串相同，例如 `--n` 不同導致取到的子集不同）⇒ 要在
  `arm_row`／`verdict` 之外再加一層「逐 task_id 比對」，不能只信 seed 字串。
  本輪沒有加這層，因為兩邊 `--n` 目前都是 60，理論上取到同一批（seed 排序
  取前 n 是決定性的），但沒有寫程式碼機械驗證這件事，只是人工核對兩份
  `summary.json` 的 `n` 欄位相同。
- 若跑完後 CI 大幅重疊（例如 ON 與 OFF5 的 95% CI 幾乎完全重疊）⇒ 點估計
  判準會給出「ON 贏」或「打不贏」的斬釘截鐵結論，但實際上兩者統計上不可分。
  下一輪讀報表時**要自己看 CI 欄位**，不能只讀 `verdict` 那一行字就下展場結論。
- 若人類事後認為「等預算」應該用別的定義（例如市場成本而非呼叫數）⇒
  `equal_budget_comparison_valid` 的定義在 `gain_run.py`，不在這支報表裡，
  要改要去改那邊，這支報表只是讀者。
