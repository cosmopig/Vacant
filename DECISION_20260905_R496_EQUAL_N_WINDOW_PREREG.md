# R496 判準（預註冊）：等列數視窗——分開「視窗位置」與「樣本量」

日期 2026-09-05 UTC 07:4x。輪次 round767 後半。模型 Opus 5。
**本檔在任何等列數視窗量測之前落筆並單獨 commit。**

## 〇、要答的問題

R495（結果 `1fb632b`）量到 `r486`／`r489`／`r490` 三支 `EMPIRICAL_MOVABLE`，
並在 §五 具名留下**未解的替代解釋**：翻動是「視窗位置」還是「樣本量」造成的？
R495 的擾動族是**等時長**子視窗（f=0.6／0.8），子視窗的列數必然比全視窗少
⇒ 兩個原因綁在一起。本檔用**等列數**視窗把它們拆開。

## 一、擾動族（事前釘死）

把 `rows` 依 `ts` 排序，取**連續的列索引區間**，每個區間**恰好 N 列**。
兩層 N，取自 R495 實測的兩組視窗列數的**最小值**（不是挑出來的，是導出的）：

- `N_SMALL = 1672`（R495 f=0.6 十二個視窗的最小列數）
- `N_LARGE = 2291`（R495 f=0.8 六個視窗的最小列數）

每層 `K=6` 個左緣在索引上等距的視窗，共 **12 個**。全視窗（2899 列）是參照。

**這一族買不到什麼（事前寫下）**：固定列數 ⇒ **時間跨度變成不固定**。
本族把 R495 的混淆換了個方向，不是消滅它。**兩族一起看才夾得住這個問題**，
單獨引用任一族都要連寫它自己的混淆方向。

## 二、被測對象

只測 R495 判 `EMPIRICAL_MOVABLE` 的三支（判準 §一 的母體，`r486_events_full` 不重複算）：

| 工具 | 判決路徑 | R495 全視窗判決 |
|---|---|---|
| `r486_longreq_attrib` | `analyze_under(rows,events,"start")["p1_verdict"]` | `QUEUE_LIVE` |
| `r489_permutation_placebo` | `analyse(rows,"start")["verdict"]` | `PLACEBO_LADDER_BROKEN` |
| `r490_leveled_placebo` | `analyse(rows,"start",reps=400)["verdict"]` | `PLACEBO_LADDER_BROKEN` |

判決函式直接 import R495 的 `probe_*`，**不重寫一份**（重寫＝兩套語意）。

## 三、判別規則（事前釘死，量完不准換）

對每一支工具，看 12 個成功視窗：

- `POSITION_MATTERS`：**某一層之內**（同 N、不同位置）出現 ≥2 種判決。
- `N_MATTERS`：**每一層之內都只有一種判決**，但兩層的那一種**不同**。
- `BOTH`：層內有 ≥2 種判決，**且**兩層的判決集合不相等。
  （`BOTH` 與 `POSITION_MATTERS` 互斥：先判 `BOTH`，不成立才判 `POSITION_MATTERS`。）
- `NEITHER`：12 個視窗全部等於 R495 的全視窗判決。
- `UNSCANNED_EQN`：該工具所有視窗都例外。

## 四、擋門

- **G-LIVE**：沿用 R495 的守門（本尺 import 它）；`live_reads` 必須 0。**強制綠燈的 guard，不是證據。**
- **G-REPRO**：全視窗重跑必須逐字重現 §二 表格三個判決；不符 ⇒ `BROKEN_NO_REPRO`。
- **G-N**：視窗數必須 == 12；不符 ⇒ `BROKEN_WINDOWS`。
- **G-CAL**：雙向校準——
  `C_POS`（必須 `NEITHER`）：常數判決函式。
  `C_NEG`（必須 `N_MATTERS`）：判決＝`"S" if len(rows)==N_SMALL else "L"`
  （層內恆定、層間必不同 ⇒ 只有 `N_MATTERS` 這一格能接住它）。
  任一不符 ⇒ `BROKEN_CALIBRATION`。
- **G-ERR**：例外率入報告；`exc_rate == 1.0` ⇒ 該格 `UNSCANNED_EQN`。

## 五、預測（盲：落筆時**沒有跑過任何一個等列數視窗**）

| # | 預測 | intent |
|---|---|---|
| Q-1 | `r490` 判 `POSITION_MATTERS` 或 `BOTH`（＝固定 N 仍會翻） | evidence |
| Q-2 | `r489` 判 `POSITION_MATTERS` 或 `BOTH` | evidence |
| Q-3 | `r486` 在等列數視窗下仍看得到 `UNSCANNED`（＝不是 `NEITHER`） | evidence |
| Q-4 | 三支裡**至少一支**判 `BOTH`（**我自標這是最可能錯的一條**） | evidence |
| Q-5 | G-REPRO 通過 | evidence |
| Q-6 | selftest 全綠＋突變體 2/2 照本檔預期 | guard |

## 六、突變體（旗標在被測函式內部呼叫時才讀；偵測條寫具名的量）

| 代號 | 改什麼 | 偵測條 |
|---|---|---|
| `M1_ONE_POSITION` | 每層只留 1 個位置 | 頂層 `verdict == "BROKEN_WINDOWS"` |
| `M2_FORCE_SAME` | 視窗判決一律覆寫成全視窗判決 | `verdict == "BROKEN_CALIBRATION"` 且 `calibration.C_NEG != "N_MATTERS"` |

## 七、推翻條件（觸發就照實寫，不准當場補判準）

1. G-REPRO 不過 ⇒ 主結果作廢，只報漂移。
2. 三支**全部**判 `NEITHER` ⇒ 與 R495 直接衝突（R495 的視窗列數 1672–2390 與本族重疊），
   ⇒ 本輪只報「兩族互相矛盾」，**不准**挑一族當結論。
3. 校準任一不符 ⇒ 量具壞掉，不報主結果。
4. 出現本檔沒有的第六種格 ⇒ 照實記、人眼確認、不算進計數。
