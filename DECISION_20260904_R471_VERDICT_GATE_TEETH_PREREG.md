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

---

# R471 量測結果（2026-09-04 22:36–22:41 UTC，判準 commit `5740fa7`、施工 commit `6ad574e`）

量具：`ops/gain/mutation_test_r470_paired_ci.py`（R470 原件，未改）＋本輪新增
`ops/gain/r471_specificity_and_deletion.py`。原始輸出：
`ops/gain/data/r471_paired_ci_teeth_after.json`、`ops/gain/data/r471_specificity_deletion.json`。
worktree `~/vacant/wt_r471`（目標檔 sha256 `9db4dee4778f8e83`，量完逐字元還原並已 `worktree remove`）。

## 逐條預測結算

| # | 預測 | 結果 | 證據 |
|---|---|---|---|
| P1 | 乾淨基線六支全綠 | **HIT** | D1 rc=0（PASS 行含 `F(verdict 判決表 11 列) G(MIN_PAIRED 擋門接線 59/61)`）、D2/D3/D4/D6 rc=0、D5「逐欄相同」 |
| P2 | M5 → D1 紅 | **HIT** | `SELFTEST FAIL: F: verdict(-4.99,+5.01) = ON_WINS，應為 NON_INFERIOR_BUT_UNRESOLVED`；`MISSED → DETECTED ['D1']` |
| P3 | M6 → D1 紅 | **HIT** | `SELFTEST FAIL: G: n=59: broken_reasons 沒指名 n_paired=59 -> []`；`MISSED → DETECTED ['D1']` |
| P4 | M4 仍 MISSED | **HIT** | `M4: MISSED 紅的是 []`（刻意；F 無 `lo==0` 列） |
| P5 | M9 仍 MISSED | **HIT** | `M9: MISSED 紅的是 []`（本輪不補） |
| P6 | M1/M2/M7/M8 底下 D1 不含 F/G 的 FAIL 行 | **HIT** | 四個全 `f_fail=False g_fail=False`；M1 紅在 C、M2 紅在 D+E、M7/M8 D1 根本不紅 |
| P7 | M1,M2,M3,M7,M8,N1,B1 的 `classify()` 逐項與 R470 相同 | **MISS（逐字）** | 六個相同；**M3 的 verdict 不變（DETECTED）但 red 集合 `['D5']` → `['D1','D5']`** |
| P8 | X-F 底下 M5 回 MISSED、X-G 底下 M6 回 MISSED | **HIT** | 兩個都 `刪後乾淨 rc=0、突變 rc=0 ⇒ MISSED`（新條文是承重牆，不是順風車） |

**總判決：`PARTIAL_TEETH`，`MISSED` 由 `['M4','M5','M6','M9']` 縮到 `['M4','M9']`。**
其中 M4 是 R470 已證的**等價突變體**（真資料 0/2697 格有差異）⇒ **實際仍有見證的缺口只剩 M9 一個**。

## P7 的 MISS 怎麼處理（推翻條件 R4 逐字觸發）

R4 寫的是「P7 落空 ⇒ 本輪改動動到了不該動的東西，**先回退再說**」。**照字面觸發了，所以逐字記在這裡。**
人眼確認後**沒有執行回退**，理由與證據：

- 差異的方向是 D1 **多**抓到 M3，不是少抓或誤判。M3 是 `verdict()` 判決兩行互換
  （`ON_WINS`↔`RULED_OUT`）——**正是條 F 的射程**，被它抓到是設計如此。
  觸發它的是 F 的第 6 列 `verdict(-10.00,+5.00)`（規則序：`hi<=5` 先於 `lo<-5`）。
- 守恆量兩個都成立：(a) `git diff` 唯一的刪除行是 `selftest()` 內的 PASS 提示字串，
  `verdict()`／`main()`／`diff_ci()`／`n_needed()` 一個字元未改；
  (b) D5 真資料回歸見證**逐欄相同**（R461 附錄 C.4 那八個數字原樣重現）。
- **判準沒有改。** P7 記為 MISS，原因是**預測寫得太窄**：我把「無回歸」寫成
  「red 集合逐項相同」，但補牙齒必然是**單調增加**紅的偵測器。
  正確的寫法應是「不得有任何突變體的 `verdict` 從 DETECTED 退成 MISSED／BROKEN，
  且不得有任何偵測器在乾淨基線變紅」——這條在本輪資料上成立。
  **這個更正只准用在下一輪的新判準，不准回頭改本輪的 P7。**

## 事前聲明的「會多冒出一類」——冒出來的是這一類

R470/R739 兩輪先例說會多冒出一類。本輪冒出來的就是上面 M3 那一格
（**已補的條文順手覆蓋到一個原本只有真資料見證 D5 看得到的突變體**）。
人眼確認、照實寫、**不算進 P1–P8 的計數**、沒有當場補判準去修。

## 補充量（事後、非事前註冊，不算進 P1–P8）

把 `PRACTICAL_PP = 5.0` 改成 `10.0`（不在突變體清單裡，臨時探）⇒ 條 F 三列同時翻紅
（`verdict(-7.82,+16.33)`、`verdict(-5.01,+10.00)`、`verdict(-1.66,+5.94)`）。
⇒ **F 不只釘判決分支，也釘住了 `PRACTICAL_PP` 這個門檻常數**——改門檻不會安靜通過。
（此結果為事後探測，**不能**當作事前預測的命中。）

## 誠實邊界

1. **這是「補上偵測」不是「找到缺陷」。** `verdict()` 與擋門現在的碼本輪一樣沒有找到任何缺陷；
   R470 量到的是「它壞了也沒人會叫」，本輪把「沒人會叫」修掉。
   **R461 已發表／即將收官的數字沒有被本輪動到**（D5 逐欄相同即為守恆量）。
2. **M9 沒補**（`n_needed` 的搜尋起點）。它只影響 `supplement_n_needed_for_halfwidth_5pp`，
   那是輸出裡自己標明的「補充量、非判定量」，不進 R461 的判決 ⇒ 本輪判斷優先序較低。
3. **條 G 依賴 `runs/g_r447_conform_lcb2` 存在。** 該 run 已凍結並在 git 裡；
   若被刪，G 會 **FAIL 並印出「不是跳過，是量不到」**，不會安靜綠。
4. 條 F 的期望值是**手寫**的。若哪天 `verdict()` 的判決表是被**有意**改的，F 會紅——
   那是設計如此（釘住判決語意），不是誤報；改判決表的人必須同時改 F 並說明理由。
