# R472（round742）：R461 收官仲裁者鏈條的清單 ＋ 補 `r447_gauge_capability.py` 的 run 目錄擋門

**判準寫在量測之前，本檔與量測結果分開 commit。**
接 R471（round741）交棒第 3 點：「先做『收官會引用誰』的清單，再挑下一支驗」。

**合法性前提**：`runs/g_r461_lcb3_three_arm` 還在跑（PID 2895311）。
**本輪對它沒有跑過任何分析工具**（只讀 `wc -l` / `sha256sum` / `summary.json` 的欄位做進度同步）
——與附錄 D／E 相同的自證。所有量測用的是**已收官的** `runs/g_r447_conform_lcb2` 與合成夾具。

---

## §一 R461 收官會引用誰（清單，機械導出）

導出方式（可重跑）：

```bash
grep -n "python3 ops/gain/[a-z_0-9/]*\.py" DECISION_20260904_R461_LCB3_REPLICATION_PREREG.md
```

| # | 仲裁者 | 承擔 R461 的哪一條 | 外部植入缺陷測試 | 自檢條數 |
|---|---|---|---|---|
| T1 | `ops/gain/replay/paired_ci.py` | 附錄 C：P-R461-1／2（`verdict == ON_WINS`） | ✅ `mutation_test_r470_paired_ci.py`（R470/R471 補過牙齒） | A–G |
| T2 | `ops/gain/r447_eq5_offline.py` | 附錄 D：P-R461-3（等預算） | ✅ `r447_mutation_check.py` 的 `EXPECT_EQ5OFF`（X1–X11） | 26 條 |
| T3 | `ops/gain/r447_gauge_capability.py` | 附錄 E：**§六.2 能力下界** | ❌ **沒有**（只有檔內 M1–M6） | A–H ＋ M1–M6 |
| T4 | `ops/gain/r461_gate_verdict.py` | §三 C4 閘門（**發射前已消耗**，不進收官） | ❌ 無 | — |
| T5 | `ops/gain/r466_r461_sec2_sec6_census.py` | 附錄 F：§二／§六 可證偽性普查 | ❌ 無 | 19 |

**挑 T3 的理由（判斷，不是量測）**：

1. 它是**唯一**替 SPEC 雙向驗尺規則之「參考解全過」那個方向頂替的證據
   ——附錄 E.1 已事前承認 v3 的 probe 覆蓋率預期 0/189，照字面不可執行。它倒了就兩個方向都沒證據。
2. 附錄 E.3 第 1 點**自己寫著它沒有任何完整性擋門**（R465 實測 Y5：把已收官 run 的 rows 截成前 23 列
   餵給它，吐 `rc=0`、`verdict=="OK"`、`n_tasks_complete=7`）。缺陷已具名、已量過、**沒有人修**，
   目前靠「收官時人要自己去 `summary.json` 讀 `run_complete`」這條人肉義務擋著。
3. 兄弟工具 `analyze_r447.py` 在**同一組輸入**上有兩道擋門（`row_accounting`、`run_not_terminal`），
   T3 一道都沒有 ⇒ 這是鏈條內部的不一致，不是「還沒想到」。
4. **時效**：`runs/g_r461_lcb3_three_arm` 現在 92/567 列、`run_terminal=False`。
   收官那支尺此刻對半截 run 會吐 `OK`。

## §二 要補的（範圍寫死）

在 `main()` 讀 run 目錄的**邊界**加三道擋門，資料一律取自 `summary.json`，**新增可調參數 0**：

| 代號 | 條件 | verdict |
|---|---|---|
| G0 | `summary.json` 不存在／讀不到 | `BROKEN_NO_SUMMARY`（「讀不到」≠「沒落盤」，r705） |
| G1 | `summary.run_terminal` 不為真 | `BROKEN_RUN_NOT_TERMINAL` |
| G2 | 任一臂 `len(rows_of_arm) + infra_void != processed` | `BROKEN_ROW_ACCOUNTING` |

擋門觸發時 **不吐能力數字**（`n_tasks_complete` / `n_undemonstrated` / `pct_undemonstrated` /
`undemonstrated_task_ids` 一律不出現）——理由是 R464 D.3.2 的形狀：BROKEN 時照印數字，
下一輪就會有人把那些數字當結論引用。

**不動的**：`census(rows)` 的簽章（`prereg_falsifiability_census.py:334` 是它的外部呼叫端，
本輪不得受影響）、`passed()` 的口徑、`FROZEN_DELIV_EXPR`、`window_doubt` 的 50%、
既有 A–H／M1–M6 任何一條、R461 的任何門檻／窗口／MDE／α／n／seed／worker／端點／bank。

## §三 事前預測（量測前寫定；對錯都照實記）

| # | 預測 |
|---|---|
| P1 | **修前**（`git show HEAD:`）餵 `run_terminal=False` 的合成 run 目錄 ⇒ `verdict=="OK"` 且 `n_undemonstrated` 存在（＝缺陷是真的，不是我想像的） |
| P2 | 修後同一輸入 ⇒ `verdict=="BROKEN_RUN_NOT_TERMINAL"` 且輸出**沒有** `n_undemonstrated` 鍵 |
| P3 | 三個突變體 `M7_ignore_terminal` / `M8_missing_summary_ok` / `M9_ignore_row_accounting` 各自 **DETECTED**，且紅的那一條**指名**是 I / J / K（只有「有東西紅了」不算抓到；crash 收場記 CRASH 不記 caught） |
| P4 | **承重牆測試（r695 硬驗法）**：把條 I 整段刪掉再跑 M7 ⇒ 回到 **MISSED**；條 J 對 M8、條 K 對 M9 同理 |
| P5 | **真資料回歸見證**（`runs/g_r447_conform_lcb2`，已收官）：修前輸出的**每一個鍵**在修後存在且值逐字相同；`verdict` 仍為 `"OK"` |
| P6 | 新增可調參數 **0**：diff 不引入任何新的模組層數值常數（用 `ast` 逐字掃 diff 後的檔案比對修前的常數集合） |
| P7 | **無回歸**（採用 R471 更正後的寫法）：不得有任何突變體從 DETECTED 退成 MISSED／BROKEN，且乾淨基線不得變紅（A–H、M1–M6 全 PASS） |

## §四 推翻條件（觸發了就照實寫，不准當場補判準去修）

- **R1**：P5 失敗（真資料上任何既有數字變了）⇒ **立刻回退**，本輪記失敗。加法性是硬條件。
- **R2**：P1 失敗（修前就擋得住）⇒ 「這個洞是真的」這個前提錯了，記 MISS 並停手，不要為了讓本輪有產出而改造缺口。
- **R3**：P3 有任何一個突變體是 CRASH ⇒ 那是 infra 壞掉被誤判成偵測器有牙齒，記 CRASH，不准算 caught。
- **R4**：若補完之後 `prereg_falsifiability_census.py` 的自檢變紅 ⇒ 表示我動到了不該動的簽章，回退。

## §五 誠實邊界

1. 本輪是**補上偵測**，不是找到 R461 數字的缺陷。T3 目前的能力口徑（`passed()`）一行未改。
2. §一 的清單只涵蓋 **R461 這一份預註冊**引用的工具。R461 收官若引用到別份文件裡的尺，
   本清單看不見它——**還沒被普查的是：R459 §十二 與 SPEC_GAIN 自己引用的尺**。
3. G2 在 run 活著時必然為真（`rows+void==processed` 只在收官後成立，memory 已記）
   ⇒ 這道擋門會讓本尺**拒絕**對活的 run 出數字。這是刻意的，不是誤傷。
