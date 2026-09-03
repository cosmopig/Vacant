# R666 預註冊：r444 的 P-C4（收據鏈可驗）能不能結算——判準先寫死

（2026-09-03 20:35 UTC，Opus 5。**r444 仍在跑（PID 2742320，323/537 列）。本輪不碰它、
不殺、不另起 run。**本檔在任何量測之前 commit。）

## 一、為什麼現在做這件事

`DECISION_20260903_R440R_CONFORM_LIVE_PREREG.md` §三 的 **P-C4** 寫：
「收官時每一列都有 `receipt_head`，且該臂的鏈 `verify_chain` 為真」，
§四 中止準則寫：「收官時 `verify_chain` 為假 ⇒ 這個 run 的究責宣稱全部作廢」。

收官前先問「這一條到時候**驗得起來嗎**」是零成本的，收官後才發現驗不起來則是
一整個 run 的究責宣稱懸空。這是 round665 §五 那類「先問前提」的同一手。

## 二、非平凡的碼側事實（本輪已讀碼確認，不是猜）

1. `ops/gain/gain_run.py:1204-1205`：每臂 `"book": Logbook()`、`"ident": Identity.generate()`
   ——**記憶體物件**，身份是逐 run 現生的。
2. `vacant/logbook.py` **有** `save(path)`（206）與 `verify_chain(who: PublicIdentity)`（168）
   ⇒ 能力存在。
3. `gain_run.py` 全檔 **沒有任何一處呼叫 `book.save`**，也沒有寫出公鑰
   （`grep -n "save\|to_ndjson\|dump\|public" ops/gain/gain_run.py` 只命中 behavior probe
   的 `json.dumps` 與註解）。收官段（1360-1380）只寫 `summary`。
4. `verify_chain` 的簽章檢查需要 `PublicIdentity`。`gain_run.py:1201-1202` 的註解說明
   **私鑰**刻意不落盤（RECORD_SPEC §7）——但**公鑰也沒落盤**，而驗鏈要的是公鑰。

⇒ 假說 H：**r444 收官後，run 目錄裡既沒有鏈的 entries、也沒有公鑰，
`verify_chain` 在結構上跑不起來。** 那不是「鏈是假的」，是**第三種狀態：量不到**
（＝ SPEC_GAIN 對 `infra_void` 的同一種區分：「這一格沒量到」≠「量到 0」）。

## 三、預註冊預測（本檔 commit 之後才量）

量測對象：`/dev/shm/r666/rows.snapshot.jsonl`（live 檔的一次性複本，避免撕裂列）
＋ `runs/g_r444_conform_mbpp/` 的目錄列表。工具：`ops/gain/replay/receipt_chain_audit.py`（本輪造）。

| # | 預測 | 判準 |
|---|---|---|
| **P-R666-1** | r444 run 目錄裡**沒有**任何鏈檔或公鑰檔 | 目錄內不存在 `*.ndjson`（`rows/calls/notes` 三個 `.jsonl` 除外）也不存在含 `pub` 的檔 |
| **P-R666-2** | 每一列 CONFORM row 都有 64 hex 的非空 `receipt_head`；OFF／OFF5 一列都沒有 | 缺漏數＝0；跨臂洩漏數＝0 |
| **P-R666-3** | 全 run 的 `conform_attempts[].entry_hash` **全域唯一** | 重複數＝0（重複＝book 被重置或鏈分叉） |
| **P-R666-4** | 每列 `receipt_head` ≠ 該列最後一個 attempt 的 `entry_hash`，且 `receipt_head` 全域唯一 | 兩者違反數皆＝0（verdict 事件在 attempt 之後追加 ⇒ 頭必然前進） |
| **P-R666-5** | 稽核工具有牙齒：四個突變體各自把對應判準從 OK 翻成 BROKEN | M1 抹掉一列 receipt_head／M2 兩列 entry_hash 改成相同／M3 receipt_head 改成等於最後一個 attempt hash／M4 空輸入 ⇒ BROKEN 不是 OK |

## 四、決策規則（先寫死，量完不准改）

- **P-R666-1 成立** ⇒ 判定 **P-C4 的後半（`verify_chain` 為真）對 r444 不可結算**，
  收官時只准結算前半（`receipt_head` 齊備）。收官那一輪**不准**把「鏈驗過了」寫進結論，
  也**不准**因此把 R440R §四 的中止準則當成觸發（那條說的是「為假」，不是「不存在」）。
- **P-R666-1 被推翻**（真的找到鏈檔或公鑰）⇒ 本輪結論作廢，改成「可結算，等收官驗」。
- **P-R666-3 或 -4 被推翻** ⇒ 鏈的結構性證據就有問題，**升級 fable 稽核**，
  且收官時連 P-C4 的前半都不准算通過。
- **P-R666-5 任一突變體沒翻成 BROKEN** ⇒ 這把尺是瞎尺，上面所有數字一律 `AMBIGUOUS`，
  不准拿來下判斷（round665 對 v1 的處理方式）。

## 五、本輪不做什麼（邊界）

- **不碰 r444 的任何檔案**，不 commit 它那四個變動檔（撕裂快照，理由同 round662 §七）。
- **不改 `arm_conform` 的行為**。若要補落盤，只准是**純儀器**（寫檔），
  且因 Python 已載入原始碼，對在跑的 r444 **零影響**——這一點本身要驗（見收尾）。
- 本輪**不**結算 P-C1／P-C2／P-C3；partial 數字只當進度快照登記，明寫「未收官、不是結論」。
