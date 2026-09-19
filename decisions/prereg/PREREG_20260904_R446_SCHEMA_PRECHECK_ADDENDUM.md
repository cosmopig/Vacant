# PREREG 附錄：r446 收官前的 schema 相容性與 M9 擋門可評估性（round699，2026-09-04 03:1x UTC）

本檔在 r446 收官**之前**寫（run 當時 127/371、`terminal=False`），且撰寫過程
**沒有計算任何 Δ／b／c／n_d／CI／四格判決／prereg 窗口判定**
（`DECISION_20260904_R446_EQUAL_BUDGET_ARM.md` §五：中途不准算 Δ）。

## 一、為什麼要有這一份

`analyze_eq5.py --selftest` 十四條全綠、`eq5_analyze_mutation_check.py` M1–M10 全 caught。
但那些夾具**全部由 `analyze_eq5._row()` 造**——與 analyzer 同一位作者、同一組欄位名字面字串。
⇒ **selftest 全綠不構成「analyzer 讀得懂 runner 真的寫出來的 rows」的任何證據。**
這與 round695 抓到的坑同構：夾具把要驗的兩端從同一處導出，該擋門結構上不可能被看見。

收官那一輪若才發現欄位對不上，會在 05:45–06:30 之間得到一個 `BROKEN`，
而資料其實是好的——那是最貴的發現時機。故本輪提前驗。

## 二、新增的尺：`ops/gain/eq5_schema_precheck.py`

- `REQUIRED` 用 `ast` 從 `analyze_eq5.py` **原始碼逐字取出**，不抄一份 ⇒ 兩邊不可能漂開。
- 夾具**刻意不共用** `analyze_eq5._row()`，欄位名在本尺內獨立寫死；
  analyzer 若改名而本尺沒跟上，clean 條會自己變紅——那是想要的行為。
- **零新旋鈕**：沒有任何門檻或可調參數，判決全是「有／沒有」「型別對／不對」。
- 不 import `analyze()`，結構上不可能算出 Δ。
- 「安靜量不到」兩型都擋：欄位缺／型別錯 ⇒ `SCHEMA_INCOMPATIBLE`；
  0 列或 arm 值不是 EQ5 ⇒ `BROKEN`（0 列全綠是套套邏輯）。
- 自檢 10 條，含 4 個植入缺陷（缺欄位／型別變字串／只翻 same_choice 不動 sha／預算改 4）
  ——判準是**它該吐哪一個 verdict 字串**，不是 `rc≠0`（round-memory 鐵律）。

實測（127 列真 rows）：`SCHEMA_COMPATIBLE`，七欄全 0 缺 0 型別錯、drift=0、
`calls_used` 值域 `[5]`、summary 三鍵齊。⇒ **收官時 analyzer 讀得懂這份資料。**

## 三、本輪抓到的結構事實：M9 擋門在 r446 上不可評估

`gain_run.py:696` 會落盤 `same_choice_effective`，但那行進 repo 的時刻是
`4b0982e` **02:28:38**，而 r446 的行程 **01:54:13** 就啟動了（跑的是 `65171d1`）。
Python 已把舊模組載進記憶體 ⇒ **r446 的 371 列全部不會有 `same_choice_effective`**
（實測 0/127）。連帶：`summary.json` 的 `arms.EQ5` 只有 `eq5_same_choice_rate`（raw），
**沒有** `eq5_same_choice_effective_rate`。

後果，收官輪必須照這三條處理：

1. `analyze_eq5.analyze()` 裡的 `landed`／`bad_eff` 區塊（突變體 M9 守的那條，
   AMEND-1 §七「落盤欄位與離線重算不准取其一」）在 r446 上**結構上不可能觸發**。
   ⇒ **不准把它記成「通過」**，要記成「本 run 無從評估」。
   （這與記憶裡「合取判準可能從來沒被評估過」是同一類；差別是這次事前就查出來了。）
2. **AMEND-1 的修正本身仍然有效**：仲裁量 `same_choice_effective_rate` 是
   analyzer 用 `accepted ∧ (gate_code_sha256 == vote_code_sha256)` **離線重算**的，
   而那兩份 sha 在真 rows 裡 0 缺 0 型別錯。⇒ round692 寫的「r446 不用重跑」**成立**，
   本輪是它第一次被真資料驗到。
3. ⚠ **收官不准從 `summary.json` 取 same_choice 的數字。** 那裡只有 raw 口徑，
   正是 AMEND-1 明令降級、不再當仲裁者的那一個；欄位名長得像、語意是舊的。
   （記憶鐵律：旗標預設值是舊語意時，下游要驗產物自己記的 key。）
   仲裁量一律取 `analyze_eq5.py --run ...` 輸出的 `same_choice_effective_rate_pp`。

## 四、推翻條件（事前）

- 若收官時 `eq5_schema_precheck.py --run` 不是 `SCHEMA_COMPATIBLE`，
  **先修相容性、不解讀結果**，且要說明是 runner 對還是 analyzer 對。
- 若 r446 的 rows 竟然出現了 `same_choice_effective`（與本檔的推論相反），
  那表示 runner 中途換過碼——**照實寫、升 fable**，不要當作好消息接受。
- 本檔沒有預測任何結果數字；任何「早就知道會怎樣」的事後說法都不得引用本檔。
