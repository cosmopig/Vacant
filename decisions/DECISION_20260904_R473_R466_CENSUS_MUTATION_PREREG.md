# R473：給 `r466_r461_sec2_sec6_census.py` 一份**外部源碼級**植入缺陷測試

判準先行。本檔在量測之前 commit，與施工、與結果分開 commit。

## 一、為什麼是它

R472（round742）機械導出的「R461 收官仲裁者清單」裡，`r466_r461_sec2_sec6_census.py`
是**最後一支「進收官、且沒有任何外部植入缺陷測試」**的尺。它承擔 R461 **附錄 F**：
§二／§六 七筆預註冊判準的四格分類、兩條 evidence 級強制綠燈的警告、以及 `blind_hit_rate`。

它現在有 19 條自檢與 M1–M7 七個**檔內**突變體。檔內突變體的結構弱點（r706 已記）：
突變分支與正式碼**並存**，測到的是作者自己寫的那條 `if MUTANT == ...`，
不是正式運算式本身。**把正式那行整段刪掉會不會紅，檔內突變體結構上答不了。**

落筆前已確認（唯讀 grep，不算量測結果）：
1. `M7_drop_source_pin` 在 `selftest()` 裡**從來沒有被設定過**（只出現在 :86 與 :127 的正式碼）。
2. `PRED`／`INTENT`／`BLIND` 三個模組層字典**沒有任何東西把它們釘回 R466 判準檔**。
3. 條「M5」的自檢**自己重寫了一份**抑制式的 dict comprehension，沒有呼叫 `census()`。

## 二、凍結的範圍

工具：新增 `ops/gain/mutation_test_r473_r466_census.py`（worktree 內做**逐字源碼替換**）。
被測檔：`ops/gain/r466_r461_sec2_sec6_census.py`。**不讀主 run**（B3 精神；
`runs/g_r461_lcb3_three_arm` 一個 byte 都不碰），**不動 r461**，不改分類邏輯 `_cell()`／`classify()`。

偵測器：
- **D1** `python3 ops/gain/r466_r461_sec2_sec6_census.py --selftest`
- **D2** `python3 ops/gain/prereg_falsifiability_census.py --selftest`（獨立呼叫端，不相干對照）
- **D3** 真資料加法性見證：乾淨跑 `--json`，與已落盤的 `ops/gain/data/r466_census.json` 逐鍵比對

判準（memory 鐵律，逐條沿用 R472）：
- 只寫 `rc≠0` 不算抓到 ⇒ **每個突變體要指名哪一條該紅**。
- crash 收場記 `BROKEN`，**不記 caught**。
- **承重牆（X-）測試**：把指名的那一條**整段刪掉**再跑同一個突變體 ⇒ 必須退回 `MISSED`。

## 三、突變體與事前預測

| id | 源碼級突變 | 指名該紅的條 | 事前預測 |
|---|---|---|---|
| X1_drop_suppression | `census()` B6 的 `SUPPRESSED` 抑制式改成原樣輸出 | （目前無） | **MISSED** |
| X2_pred_drift | `PRED["S2-1"]` `EVALUABLE`→`FORCED_GREEN` | （目前無） | **MISSED** |
| X3_intent_drift | `INTENT["S2-2"]` `evidence`→`guard` | （目前無） | **MISSED** |
| X4_drop_source_pin | `_source_read()` 永遠讀 worktree（不走釘死 commit） | （目前無） | **MISSED** |
| P1_pin_noop（正對照） | `check_pins()` 的 `ok = want in doc` → `ok = True` | `M4 判準字面漂移 ⇒ SOURCE_DRIFT` | **DETECTED** |
| P2_b3_off（正對照） | `_safe_read()` 的 `FORBIDDEN_RUN` 擋門拿掉 | `H B3 擋門會擋主 run` | **DETECTED** |
| N1_syntax（負對照） | `def census(` 那行插入非法語法 | — | **BROKEN**（不准記 caught） |

**P1–P7 事前預測**

- **P1** X1／X2／X3／X4 四個**全部** MISSED（＝現有 19 條對它們沒有牙齒）。
- **P2** P1_pin_noop、P2_b3_off 各自 DETECTED，且**指名的那一條**在紅名單裡。
- **P3** N1_syntax 記 BROKEN。
- **P4** 施工後 X1–X4 **全部** DETECTED，且各自指名的新條在紅名單裡。
- **P5** 承重牆：把每個新條**整段刪掉**再跑對應突變體 ⇒ 全部退回 MISSED。
- **P6 無回歸**（採 r741 更正後的寫法）：不得有任何突變體從 DETECTED 退成 MISSED／BROKEN，
  且乾淨基線（D1／D2／D3）不得變紅。**不要求紅名單逐項相同**——補牙齒必然單調增加紅的偵測器。
- **P7 新增可調參數 0**：`ast` 掃模組層常數，新增的只准是「釘死的來源路徑／表格 regex」，
  不准有任何可調門檻或旗標。新增常數數量 ≤ 3。
- **P8 真資料加法性**：D3 既有鍵**逐值相同**，`blind_hit_rate`／`class_counts`／
  `forced_green_evidence_items` 一字未動；新增的鍵只准是新擋門自己的證據欄。

## 四、施工方向（只在量測確認 MISSED 之後才動）

1. **條 I（PRED／INTENT／BLIND 釘回判準檔）**：從 R466 判準檔的 **`99ec6cb`（預測落筆當時的 commit）**
   逐列解析 §一 的 intent 表與 §三 的預測表，與三個字典逐鍵比對；不符 ⇒ `SOURCE_DRIFT`，
   **且不吐任何分類**（R464 D.3.2 形狀）。釘落筆當時而不是 HEAD：memory「判強制綠燈的時點是預測落筆當時」。
2. **條 J（抑制式逐字取原式再 eval）**：用 `ast.get_source_segment` 從 `census()` 取出
   B6 那個 comprehension 的**真運算式**再 eval，不准在自檢裡改寫一份（memory 鐵律）。
3. **條 K（來源釘生效）**：`_source_read("ops/gain/verify_lcb_bank.py")` 必須逐字元等於
   `git show 952f883f:…`，且必須**不等於** worktree 版本。
   **見證已先驗**：R467 改過該檔 ⇒ 兩版今天確實不同（若哪天相同，這條就是強制綠燈，要照實記 UNSCANNED）。

## 五、推翻條件（觸發就照實寫，不准當場補判準去修）

- **R1** 任一 X1–X4 實測 DETECTED（與 P1 相反）⇒ 該項記 MISS，**保留舊預測在帳上**，不改 §三。
- **R2** 施工後 D3 有任何既有鍵改值，或乾淨基線變紅 ⇒ **先回退再說**。
- **R3** 任一新條在承重牆測試下**沒有**退回 MISSED ⇒ 那條是搭順風車，記下來、不算 P4 命中。
- **R4** 若條 K 的見證消失（釘死版與 worktree 相同）⇒ 記 `UNSCANNED`，不准記 HIT。
