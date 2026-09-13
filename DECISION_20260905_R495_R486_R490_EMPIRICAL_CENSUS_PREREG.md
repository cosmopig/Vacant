# R495 判準（預註冊）：R486–R490 的 **EMPIRICAL 半邊**可證偽性普查

日期 2026-09-05 UTC 07:4x。輪次 round767。模型 Opus 5。
**本檔在任何子視窗量測之前落筆並單獨 commit。** 結果與量具是下一個 commit。

## 〇、為什麼是這件事（可反駁）

- 主 run `g_r461_lcb3_three_arm` 開場 07:23 rows **329**／567，依 0.48 列/分還要約 **8 小時**
  （收官約 15:0x UTC）⇒ **本輪不可能收官**，交棒第 1 項不可執行。
- 交棒第 2 項（R486–R490 **結構**半邊）round766 已做完（`FORCED_GREEN=0`）。
- 交棒第 3 項就是本檔：**EMPIRICAL 半邊**。R491 的詞彙把「這條判準可不可能為假」拆成
  IDENTITY（結構上不可能）與 EMPIRICAL（**這份資料**翻不動）。R494 只答了前者，
  且它自己的誠實邊界白紙黑字寫「判 `EVALUABLE` **不准**讀成『當時那份閘道快照有可能給出相反判決』」。
  本檔答的就是被排除掉的那半邊。

## 一、母體與被測對象

閘道快照 `ops/gain/data/r486_gateway_snapshot_v2.json`（2899 列 `rows`、`events`）。
六支被測工具與各自「觀測判決」（＝落盤結果檔記的那個）：

| 工具 | 判決路徑 | 觀測判決 | 連續統計量 `stat` |
|---|---|---|---|
| `r486_longreq_attrib` | `analyze_under(rows,events,"start")["p1_verdict"]` | `QUEUE_LIVE` | `queue_share` |
| `r487_concurrency_tax` | `analyze_one(rows,events,"start","tok")["p1"]` | `CONCURRENCY_TAXES` | `ratio` |
| `r487_ts_semantics` | `analyze(rows)["verdict"]` | `TS_IS_START` | `inv.ts_plus_lat` |
| `r488_pointwise_concurrency` | `analyse(rows,"start")["verdict"]` | `PLACEBO_UNSCANNED` | `real.ratio` |
| `r489_permutation_placebo` | `analyse(rows,"start")["verdict"]` | `PLACEBO_LADDER_BROKEN` | `real.ratio` |
| `r490_leveled_placebo` | `analyse(rows,"start",reps=400)["verdict"]` | `PLACEBO_LADDER_BROKEN` | `real.abs_log` |

`stat` 由本檔**事前指名**，量完不准換。取不到 ⇒ `stat=None`（見 §二 的 UNSCANNED 格）。

## 二、擾動族（只有一族，事前釘死）

**時間上的連續子視窗。** 以 `ts` 定義快照時間跨度 `[t0,t1]`，
對 `f ∈ {0.6, 0.8}` 各取 `K=6` 個左緣等距的連續視窗，共 **12 個**；
保留 `t0_w <= ts <= t1_w` 的**全部**列（不預先過濾，讓每支工具自己的過濾器照常運作）。
`f=1.0` 的全視窗是參照，不算在 12 個裡。

**為什麼不是 i.i.d. bootstrap：** 這六支工具**全部**是請求時間重疊結構的函數。
對列做可置換重抽會把重疊結構整個打散 ⇒ 判決會因為重抽方式的假象而翻動，
那不是「這份資料本來可能說別的」。連續子視窗保住局部並行結構。

**這一族買不到什麼（事前寫下的誠實邊界）：** 它擾動不了「同一個視窗內的組成」。
因此 `EMPIRICAL_FIXED` **只准**讀成「這一族擾動翻不動它」，
**不准**讀成「沒有任何資料翻得動它」。

## 三、分類格（事前釘死，不准事後加格）

一支工具一格，依 12 個子視窗的結果判：

- `EMPIRICAL_MOVABLE`：≥1 個**成功跑完**的子視窗給出 ≠ 全視窗判決的判決。
- `EMPIRICAL_DEGENERATE`：0 個翻動，**且** `stat` 在所有成功視窗上完全沒變
  （`max-min == 0`）⇒ 擾動對它沒有著力點 ⇒ **這是要警告的那一格**。
- `EMPIRICAL_FIXED`：0 個翻動，`stat` 有變（`max-min > 0`），且 ≥1 個視窗成功。
  ⇒ **強訊號，不是空綠燈**；報告要附 `stat` 的全距與相對全距。
- `EMPIRICAL_UNSCANNED`：所有視窗都例外／或 `stat` 取不到而又 0 翻動 ⇒
  **不准記成 FIXED**（「安靜量不到」第三型）。

## 四、擋門（任一不過 ⇒ 整份不得當量測引用）

- **G-LIVE**：任何開檔路徑含 `g_r461_lcb3_three_arm` ⇒ `RuntimeError`；報告 `live_reads` 必須 0。
  intent＝`guard`，且**設計上強制綠燈**（本尺根本不開那個路徑）⇒ **它不是證據**。
  它有牙齒的證據是 selftest `C1_glive`：故意打主 run 路徑必須丟 `RuntimeError`。
- **G-REPRO**：全視窗重跑必須**逐字重現**上表六個觀測判決。任一不符 ⇒ `BROKEN_NO_REPRO`。
- **G-ERR**：每支工具的例外率 `exc_rate` 一律入報告（round766 第四型的義務）。
  `exc_rate == 1.0` ⇒ 該格 `EMPIRICAL_UNSCANNED`。
- **G-N**：每支工具的視窗數必須 **== 12**；不足 ⇒ `BROKEN_WINDOWS`。
- **G-CAL**：雙向校準（§五）任一不符 ⇒ `BROKEN_CALIBRATION`。

## 五、雙向校準（缺一不可）

- `C_POS`（正對照，**必須** `EMPIRICAL_DEGENERATE`）：判決函式回傳常數、`stat` 回傳常數。
- `C_NEG`（負對照，**必須** `EMPIRICAL_MOVABLE`）：判決＝`"FULL" if len(rows)==n_full else "SUB"`。
  只有正對照時「什麼都判 DEGENERATE」也會全綠 ⇒ 兩個方向都要。

## 六、預測（盲的程度要照實寫）

⚠ **盲的邊界**：落筆時我**已經看過全視窗的六個判決**（§一表格就是它們，取自落盤結果檔並已重跑對照），
但**沒有跑過任何一個子視窗**。以下預測全部只關於子視窗的行為。

| # | 預測 | intent |
|---|---|---|
| P-1 | 六支裡 **≥3** 支判 `EMPIRICAL_MOVABLE` | evidence |
| P-2 | `r487_ts_semantics` 判 `EMPIRICAL_FIXED`（不是 MOVABLE、也不是 DEGENERATE） | evidence |
| P-3 | **至少 1 格** `EMPIRICAL_DEGENERATE`（**我自標這是最可能錯的一條**） | evidence |
| P-4 | `r490_leveled_placebo` 不是 `EMPIRICAL_MOVABLE`（前提失敗型判決，視窗變小只會更失敗） | evidence |
| P-5 | G-REPRO 通過（全視窗六個判決逐字重現） | evidence |
| P-6 | selftest 全綠且突變體 4/4 照本檔預期 | guard |
| P-7 | `live_reads == 0` | guard（**強制綠燈、不是證據**） |

## 七、突變體（旗標一律在**被測函式內部**呼叫時才讀；判準寫「哪個量要變」，不是 rc≠0）

| 代號 | 改什麼 | 偵測條（必須成立才算 DETECTED） |
|---|---|---|
| `M1_NO_SUBWINDOWS` | 只跑全視窗 | 頂層 `verdict == "BROKEN_WINDOWS"` |
| `M2_FORCE_SAME` | 子視窗判決一律覆寫成全視窗判決 | `verdict == "BROKEN_CALIBRATION"` 且 `calibration.C_NEG != "EMPIRICAL_MOVABLE"` |
| `M3_NO_GLIVE` | 拿掉 G-LIVE 守門 | selftest `C1_glive` 必須 FAIL |
| `M4_NO_DEGENERATE` | 不再吐 `EMPIRICAL_DEGENERATE`（併進 FIXED） | `verdict == "BROKEN_CALIBRATION"` 且 `calibration.C_POS != "EMPIRICAL_DEGENERATE"` |

## 八、推翻條件（觸發就照實寫，**不准當場補判準去修**）

1. G-REPRO 不過 ⇒ 這份快照或這六支工具已經漂移，本輪主結果作廢，只報漂移。
2. 12 個視窗有 >6 個例外 ⇒ 子視窗這一族對這些工具不適用，本輪只報「這一族不適用」。
3. `C_POS`／`C_NEG` 任一不符 ⇒ 量具壞掉，不報主結果。
4. 出現本檔沒有的第五種格 ⇒ 照實記、人眼確認、**不算進計數**、不當場補格。

## 九、不做什麼

不碰主 run（G-LIVE）、不改那六支被測工具任何一行、不起／不殺任何 run、
不 `git add` 活著的 run 目錄、不碰 `world/`／`design/`／`vacant_hm`、
不對已收官的 r445／r446／r447 下新判斷、不動 round762 裁決過的那條梯子。
