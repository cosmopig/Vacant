# R496 結果：**固定列數之後，判決還是隨視窗位置翻——而且翻得很有規律**

判準 `53eb9c1`（量測前落筆、單獨 commit）。量具 `ops/gain/r496_equal_n_windows.py`。
輸出 `ops/gain/data/r496_equal_n.json`。round767 後半，Opus 5，2026-09-05 UTC 07:4x–07:5x。

## 一、主結果

```
verdict=EQN_OK  windows=12  repro_ok=True  max_exc_rate=0.0  live_reads=0  elapsed_s=78.3
calibration: {'C_POS': 'NEITHER', 'C_NEG': 'N_MATTERS'}
selftest 17/17 all passed;  mutation 2/2 behaved as prereg'd
```

| 工具 | 格 | N=1672 六個位置 | N=2291 六個位置 |
|---|---|---|---|
| `r486_longreq_attrib` | `POSITION_MATTERS` | `UNSCANNED`×5、`QUEUE_LIVE`×1 | `UNSCANNED`×4、`QUEUE_LIVE`×2 |
| `r489_permutation_placebo` | `BOTH` | `BROKEN`,`UNRESOLVED`,`PERIOD_CONFOUNDED`,`TAXES`×3 | `BROKEN`×3、`TAXES`×3 |
| `r490_leveled_placebo` | `BOTH` | `BROKEN`,`UNRESOLVED`,`PRIMARY_IS_POSITIVE_CONTROL`×4 | `BROKEN`×2、`PRIMARY_IS_POSITIVE_CONTROL`×4 |

## 二、R495 §五 留的替代解釋，**答掉了**

**翻動不是樣本量造成的。** 在**列數完全固定**（1672 或 2291 列）的情況下，
只要把視窗往後移，判決照樣翻：

```
r489  N=1672：  BROKEN → UNRESOLVED → PERIOD_CONFOUNDED → TAXES → TAXES → TAXES
r489  N=2291：  BROKEN → BROKEN → BROKEN → TAXES → TAXES → TAXES
r490  N=1672：  BROKEN → UNRESOLVED → PRIMARY_POS_CTRL ×4
r490  N=2291：  BROKEN → PRIMARY_POS_CTRL → BROKEN → PRIMARY_POS_CTRL ×3
```

🔴 **而且翻的方向對起始位置幾乎是單調的**：快照**前段**給 `PLACEBO_LADDER_BROKEN`，
**後段**給 `CONCURRENCY_TAXES`／`PRIMARY_IS_POSITIVE_CONTROL`。兩層 N 都是這個方向。
⇒ **這份快照的前段與後段在機制上不是同一件事**，而 R489／R490 的頭條判決
是「把兩段混在一起算」的結果。

🆕 **本族事前寫下的代價比預期小**：固定列數理應讓時間跨度失控，實測
N=1672 的跨度只在 17741–19549 秒之間（±5%），N=2291 在 24872–26071 秒（±2%）
⇒ **「換一個混淆方向」在這份資料上幾乎沒發生**，兩族因此夾得比預期緊。

## 三、預測帳（判準 §五，盲——落筆時沒跑過任何等列數視窗）

| # | 預測 | intent | 結果 |
|---|---|---|---|
| Q-1 | `r490` 判 `POSITION_MATTERS` 或 `BOTH` | evidence | ✅ 中（`BOTH`） |
| Q-2 | `r489` 判 `POSITION_MATTERS` 或 `BOTH` | evidence | ✅ 中（`BOTH`） |
| Q-3 | `r486` 不是 `NEITHER` | evidence | ✅ 中（`POSITION_MATTERS`） |
| Q-4 | 至少一支判 `BOTH`（**自標最可能錯的一條**） | evidence | ✅ 中（兩支）——**這次自標的那條沒錯** |
| Q-5 | G-REPRO 通過 | evidence | ✅ 中 |
| Q-6 | selftest 全綠＋突變體 2/2 | guard | ✅ 中 |

⚠ **六條全中要當成警訊看**：R495 那一輪七條裡錯兩條，本輪零失手。
Q-1/Q-2/Q-3 是**在看過 R495 的結果之後**寫的（R495 已經量到這三支 MOVABLE）
⇒ **它們的盲度比 R495 那批低**，不該當成同等強度的證據。只有 Q-4 是真的新賭注。

## 四、誠實邊界

- **12 個視窗高度重疊**（滑動視窗，相鄰位置共用大部分列）⇒ **不是 12 個獨立觀測**，
  不准拿「6/6」「12/12」當計數證據。可用的是**方向**（前段 vs 後段），不是次數。
- **`BOTH` 裡的 `across_tier_differs` 很弱**：兩層的判決**集合**不同，主要是
  N=1672 那層多出 `UNRESOLVED`／`PERIOD_CONFOUNDED` 這種「解析度不夠」型判決
  ⇒ 讀成「n 小 ⇒ 更容易吐不出判決」比讀成「n 改變了機制」保守而且更貼近程式碼。
- **沒解釋前段／後段為什麼不同**。可能的方向（**都沒量**）：1004 每小時 unload/load、
  主 run 的臂輪替、別人的請求混進來。**下輪要量再說，不准現在寫成解釋。**
- 判決函式 import R495 的 `probe_*`，**沒有重寫一份**；G-LIVE 沿用 R495 那一份，
  `live_reads=0`，`S4_glive` 在本尺再驗一次。
- 沒做承重牆刪除測試（判準沒要求）⇒ 只證明兩個具名突變體看得見。

## 五、推翻條件（判準 §七）

1. G-REPRO 不過 —— 未觸發。 2. 三支全 `NEITHER` —— 未觸發。
3. 校準不符 —— 未觸發（`C_POS=NEITHER`、`C_NEG=N_MATTERS`）。
4. 第六種格 —— 未觸發（`NEW_CELL_UNIFORM_SHIFT` 這格造得出來、selftest 有驗，實跑沒出現）。
