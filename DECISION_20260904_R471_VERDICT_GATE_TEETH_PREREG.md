# R471 判準（事前）：給 `paired_ci.verdict()` 與 `MIN_PAIRED` BROKEN 擋門補牙齒

寫在任何量測之前。本檔 commit 與量測 commit 分開。
上游：`DECISION_20260904_R470_PAIRED_CI_TEETH_PREREG.md`（`069f2d9`）＋ R470 量測（`03313b0`）。

## 一、為什麼是這一支

R470 量到 `ops/gain/replay/paired_ci.py` 是 **PARTIAL_TEETH**：9 個突變體漏掉 4 個，
漏掉的正好是 R461 收官會逐字引用的兩塊——**`verdict()` 怎麼判**（M5）與
**`n < MIN_PAIRED` 的 BROKEN 擋門**（M6）。R461 附錄 C.2 把 P-R461-1／P-R461-2 的判決
釘成 `paired_ci.py --key deliv` 的 `verdict == "ON_WINS"`，而主 run
`runs/g_r461_lcb3_three_arm` 現在 n≈28/臂，**正落在 M6 分得開的 `0 <= n < 60` 區間**。

R470 §交棒的建議逐字是「補 M5／M6 兩條就夠，**M4 不要補**」——M4（`lo_pp > 0` → `>= 0`）
在 2697 格真資料上 0 個差異＝**等價突變體**，補它等於把等價突變體寫進測試。本輪照辦。

## 二、要造什麼（兩條，都加進 `selftest()`，代號沿用 A–E 之後）

- **條 F：`verdict()` 的判決表。** 直接以 (lo_pp, hi_pp) 字面值呼叫 `verdict()`，
  逐列比對**手寫**的期望字串。手寫是刻意的：兩種語意給出相反答案才有牙齒。
- **條 G：`main()` 裡那一行 BROKEN 擋門。** 不驗函式、**驗那一行的接線**：
  在 tmpdir 造一份真 schema 的 run（rows 取自 `runs/g_r447_conform_lcb2` 的**真資料**、
  只做子集，summary.json 原檔複製），用 `sys.argv` 呼叫 `main()`，讀 `--json` 產物。

### F 的設計約束（事前寫死）

1. **不得有任何一列的 `lo_pp` 恰等於 0.0。** 這是為了讓 F 對 M4 **保持綠**——
   M4 只在 `lo==0` 分得開，而 Clopper-Pearson 下界恰為 0 在真資料上不可達（R470 量過 0/2697 格）。
2. 至少一列滿足 `lo_pp <= 0 < hi_pp` 且 `hi_pp > PRACTICAL_PP`，
   其乾淨答案是 `NON_INFERIOR_BUT_UNRESOLVED`、M5 底下變 `ON_WINS`。
   （這正是 R470 見證量到的「380 格 NON_INFERIOR_BUT_UNRESOLVED → ON_WINS」那一型。）
3. 四個回傳值 `ON_WINS` / `RULED_OUT` / `UNINFORMATIVE` / `NON_INFERIOR_BUT_UNRESOLVED`
   每個至少各一列。
4. 期望值**手寫字面字串**，不准由 `verdict()` 自己導出，也不准在測試裡重寫一份判決式。

### G 的設計約束（事前寫死）

1. **兩列，只差 n**：n_paired = 59（< `MIN_PAIRED`=60）必須 `verdict == "BROKEN"`
   且 `broken_reasons` 含 `n_paired=59`；n_paired = 61 必須 `verdict != "BROKEN"`
   且 `broken_reasons == []`。59/61 夾住門檻 60，M6（`n < 0`）底下第一列翻掉。
2. **fixture 用真資料**（r699 教訓：夾具由被測模組自己的 helper 造 ⇒ 驗不到真 schema）。
   取 `runs/g_r447_conform_lcb2` 的 rows，按 `sorted(common task_id)` 取前 59／61 個，
   兩臂各留該題一列，**欄位一個字不改**；summary.json 直接複製原檔。
3. **run 目錄不存在時 F/G 要記 FAIL，不准安靜跳過**（「安靜量不到」＝BROKEN 不是 PASS）。
4. G 只讀 `runs/g_r447_conform_lcb2`（已 commit、凍結）；**不碰任何活著的 run**。

## 三、不准動什麼

- `verdict()`、`n_needed()`、`diff_ci()`、`main()` 的**判決邏輯一個字元都不改**。
  本輪只加 `selftest()` 內的檢查與其 helper（additive）。
- 不補 M9（`n_needed` 搜尋起點）——留給下一輪，理由記在交棒。
- 不修 R470 §五記的 `test_pooled_key_r675.py` 基線已紅（不在本輪範圍）。
- 不殺、不 `git add`、不碰 `runs/g_r461_lcb3_three_arm`。不起任何新 run。

## 四、量具與對照集合（封閉）

突變體與偵測器沿用 R470 的 `ops/gain/mutation_test_r470_paired_ci.py`（源碼級突變，
不是 env 旗標）。本輪**新增兩個「刪掉對照」**，證明新條文是承重牆而不是順風車：

| 代號 | 做什麼 |
|---|---|
| **X-F** | 在含新條文的檔上，**整段刪掉條 F**，再跑 M5 |
| **X-G** | 在含新條文的檔上，**整段刪掉條 G**，再跑 M6 |

（r695 教訓：「整段刪掉會不會 FAIL」比 env 旗標突變體更硬。）

## 五、事前預測（量測前落筆，逐條可證偽）

| # | 預測 |
|---|---|
| **P1** | 乾淨基線：D1 rc=0 且輸出含 F、G 的 PASS 標記；D2/D3/D4/D6 與 D5 維持 R470 §五 的綠 |
| **P2** | **M5：D1 紅** ⇒ M5 由 `MISSED` 變 `DETECTED` |
| **P3** | **M6：D1 紅** ⇒ M6 由 `MISSED` 變 `DETECTED` |
| **P4** | **M4：仍 `MISSED`**（刻意；F 無 `lo==0` 列） |
| **P5** | **M9：仍 `MISSED`**（本輪不補） |
| **P6** | 專一性：M1/M2/M7/M8 底下，D1 的輸出**不含** F 或 G 的 FAIL 行（它們若紅，紅在 A–E） |
| **P7** | 無回歸：M1,M2,M3,M7,M8,N1,B1 的 `classify()` 結果與 R470 記錄逐項相同 |
| **P8** | **X-F 底下 M5 回到 `MISSED`；X-G 底下 M6 回到 `MISSED`**（新條文承重） |

## 六、推翻條件（觸發就照實寫，不准當場補判準去修）

- **R1**：若 P2 或 P3 落空 ⇒ 新條文**沒有牙齒**，本輪結論寫 `NO_TEETH`，
  不准在看到結果後改期望值讓它變紅。
- **R2**：若 P1 落空（乾淨基線 F 或 G 就紅）⇒ 這是**在 `verdict()`／擋門身上找到真缺陷**，
  必須當成發現照實寫並升級 fable 裁決，**不准改測試去遷就實作**。
- **R3**：若 P6 落空（F/G 在不相干突變體底下也紅）⇒ 記 `NON_SPECIFIC`，
  照 R739/R470 §P7 慣例人眼確認、照實寫、**不算進 P1–P8 的計數**。
- **R4**：若 P7 落空 ⇒ 本輪改動動到了不該動的東西，**先回退再說**。
- **事前聲明**：照 R470/R739 兩輪先例，**預期會另外冒出一類沒點名的東西**。
  冒出來就人眼確認、照實寫、不算進計數、不當場補判準。

## 七、與 R461 收官的關係

本輪只加 `selftest()` 內的檢查。`--selftest` 以外的任何呼叫路徑（含 R461 收官要用的
`--run … --key deliv`）**執行路徑不變**。因此本輪**不會**動到 R461 的頭條數字；
D5（真資料回歸見證）逐欄重現 R461 附錄 C.4 的八個數字，就是這一點的守恆量。
