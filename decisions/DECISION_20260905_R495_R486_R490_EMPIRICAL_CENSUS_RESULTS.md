# R495 結果：R486–R490 的 EMPIRICAL 半邊——**梯子那兩支（R489／R490）的頭條判決是可翻動的**

判準 `4f9f4c1`（量測前落筆、單獨 commit）。量具 `ops/gain/r495_empirical_census.py`。
輸出 `ops/gain/data/r495_empirical_census.json`。本輪 round767，Opus 5，2026-09-05 UTC 07:4x–08:1x。

## 一、主結果

```
verdict=CENSUS_OK  windows=12  movable=4  fixed=3  degenerate=0  unscanned=0
max_exc_rate=0.0  live_reads=0  repro_ok=True  elapsed_s=130.1
calibration: {'C_POS': 'EMPIRICAL_DEGENERATE', 'C_NEG': 'EMPIRICAL_MOVABLE'}
```

| 工具 | 全視窗判決 | 格 | 12 個子視窗看到的判決 | `stat` 全距 |
|---|---|---|---|---|
| `r486_longreq_attrib` | `QUEUE_LIVE` | **MOVABLE** | `QUEUE_LIVE`×3、`UNSCANNED`×9 | 0.0（只有 3 個成功視窗，值都是 1.0） |
| `r486_events_full`（同工具、events 不切） | `QUEUE_LIVE` | **MOVABLE** | 與上列**逐格相同** | 0.0 |
| `r487_concurrency_tax` | `CONCURRENCY_TAXES` | FIXED | 12/12 全是 `CONCURRENCY_TAXES` | 1.469→1.836 |
| `r487_ts_semantics` | `TS_IS_START` | FIXED | 12/12 全是 `TS_IS_START` | 0.0→0.00060 |
| `r488_pointwise_concurrency` | `PLACEBO_UNSCANNED` | FIXED | 12/12 全是 `PLACEBO_UNSCANNED` | 1.144→1.985 |
| `r489_permutation_placebo` | `PLACEBO_LADDER_BROKEN` | **MOVABLE** | `CONCURRENCY_TAXES`×5、`PLACEBO_LADDER_BROKEN`×4、`PERIOD_CONFOUNDED`×1、`UNRESOLVED`×1（共 11 具名＋1） | 1.144→1.985 |
| `r490_leveled_placebo` | `PLACEBO_LADDER_BROKEN` | **MOVABLE** | `PRIMARY_IS_POSITIVE_CONTROL`×9、`PLACEBO_LADDER_BROKEN`×2、`UNRESOLVED`×1 | 0.135→0.686 |

**⚠ 兩個數字都要引用**：量具印的 `movable=4` 把 `r486_events_full` 當成獨立一格；
判準 §一 的母體是**六支工具** ⇒ 以判準的母體算是 **3/6 MOVABLE**。P-1 用後者判。

## 二、這件事的意思（兩個相反誤讀都要避開）

1. 🔴 **`PLACEBO_LADDER_BROKEN` 是全視窗才有的判決，不是這份資料的穩健性質。**
   R489 的頭條在 12 個子視窗裡只出現 **4** 次；R490 的頭條只出現 **2** 次，
   反而是 `PRIMARY_IS_POSITIVE_CONTROL` 出現 **9** 次。
   ⇒ 以後引用 R489／R490 的頭條，**必須連寫「這個判決對『看快照的哪一段』敏感」**。
2. ⛔ **不准讀成「R489／R490 的結論是錯的」。** 子視窗只有 60–80% 的列，
   梯子上好幾道擋門（覆蓋率、n、置換解析度）本來就會因為 n 變小而翻面。
   **本尺分不開「視窗位置」與「樣本量」這兩個原因**——見 §五 的未解替代解釋。
3. 🔴 **`r486` 的 `QUEUE_LIVE` 靠的是很薄的一層**：9/12 個子視窗直接掉進
   `UNSCANNED`（`n_targets < MIN_TARGETS`）。全視窗能判出來，是因為長請求全庫只有那幾筆。
4. ⚠ **`r488` 的 FIXED 是「一直掃不到」的 FIXED**（12/12 `PLACEBO_UNSCANNED`）。
   **穩定的空判決不是強訊號**，不准拿它當「R488 的結論很穩」的證據。
5. ✅ **真正穩的是 `r487_concurrency_tax` 與 `r487_ts_semantics`**：判決 12/12 不動，
   而 `stat` 在子視窗之間有實質變動（ratio 1.469–1.836；inv 0–0.00060）
   ⇒ 這是「擾動有著力點但翻不動判決」，**不是空綠燈**。
6. 🆕 **`events` 要不要跟著切視窗，一格都沒差**（`r486` 與 `r486_events_full` 逐格相同）
   ⇒ 判準 §二 沒寫到 events 的那個缺口，事後量出來是無關緊要的。

## 三、預測帳（判準 §六）

| # | 預測 | intent | 結果 |
|---|---|---|---|
| P-1 | 六支裡 ≥3 支 MOVABLE | evidence | ✅ **中**（3/6，**壓線**；照量具的 7 格算是 4/7） |
| P-2 | `r487_ts_semantics` 判 FIXED（非 MOVABLE 非 DEGENERATE） | evidence | ✅ 中 |
| P-3 | 至少 1 格 DEGENERATE（**自標最可能錯的一條**） | evidence | ❌ **MISS**（＝0）——**自標為最可能錯的，確實錯了** |
| P-4 | `r490` 不是 MOVABLE | evidence | ❌ **MISS**（它是 MOVABLE，而且頭條只剩 2/12） |
| P-5 | G-REPRO 通過 | evidence | ✅ 中（六個落盤判決逐字重現） |
| P-6 | selftest 全綠＋突變體 4/4 | guard | ✅ 中（16 條 selftest 全綠；`4/4 behaved as prereg'd`） |
| P-7 | `live_reads == 0` | guard | ✅ 中，但**設計上強制綠燈 ⇒ 不是證據**（牙齒在 `C1_glive`） |

**P-3／P-4 都是實質的失手，照實記。** P-4 的失手方向對「梯子很穩」這個立場不利，
而我事前寫的理由（「前提失敗型判決，視窗變小只會更失敗」）**被資料直接推翻**：
視窗變小反而讓 R490 走到 `PRIMARY_IS_POSITIVE_CONTROL`。

## 四、量具的誠實邊界

- **擾動族只有一個**（連續子視窗）。`EMPIRICAL_FIXED` 只准讀成
  「這一族擾動翻不動它」，**不准**讀成「沒有任何資料翻得動它」。判準 §二 事前就寫了。
- **`r486` 的 `stat` 全距是 0，但格是 MOVABLE**：只有 3 個成功視窗、`queue_share` 都是 1.0。
  ⇒ 這一格的 `stat` 對 DEGENERATE／FIXED 的區辨力**沒有被用到**（MOVABLE 先成立）。
- **實作比判準 §一 多了一格**：`r486_events_full`（events 不隨視窗切的敏感度變體）不在判準表上，
  而它被寫進了 G-REPRO 的釘死表 ⇒ **G-REPRO 有 1/7 條不在判準涵蓋範圍內**。
  它的期望值 `QUEUE_LIVE` 是我在判準時點的**預測**（當時沒跑過），事後成立。照實記，不追認進判準。
- **突變體一律跑真快照**：G-REPRO 排在 G-CAL 前面，換小快照會讓 `verdict` 先被
  `BROKEN_NO_REPRO` 佔掉，M2／M4 的偵測條就永遠測不到 ⇒ 那會是
  「乾淨 PASS、植入缺陷仍 PASS」的假測試。第一版寫成小快照，發車前改掉。
- **沒做承重牆刪除測試**（判準沒要求）⇒ 本輪只證明「四個具名突變體看得見」，
  **沒有**證明「刪掉某一段判別碼會紅」。
- 主 run 零分析：`live_reads=0`，`C1_glive` 證明擋門有牙齒。本輪**零模型呼叫**。

## 五、未解的替代解釋（不准當場補判準去修）

**MOVABLE 到底是「視窗位置」還是「樣本量」造成的，本尺分不開。** 兩個 f 都會翻
（R490：f=0.6 翻 5/6、f=0.8 翻 5/6），但 f=0.8 仍比全視窗少 20% 的列。
要分開，下輪的做法是**固定 n 而移動視窗**（等列數的滑動視窗，而不是等時長），
或**固定視窗而抽稀**——兩者都會各自帶進新的失真，要先寫判準再量。

## 六、推翻條件（判準 §八）的觸發狀況

1. G-REPRO 不過 —— **未觸發**（`repro_ok=True`）。
2. >6 個視窗例外 —— **未觸發**（`max_exc_rate=0.0`，零例外）。
3. 校準任一不符 —— **未觸發**（`C_POS=DEGENERATE`、`C_NEG=MOVABLE`）。
4. 出現第五種格 —— **未觸發**（只出現判準的四格中的三格）。
