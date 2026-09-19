# R503 判準（量測之前）：R495 普查的**承重牆刪除測試**

交棒第 3 項（round771 §「下一輪可做的」3）。R500 已對 R496 做過同型測試；
本輪把它套到 R495，**但 R495 的結構不同**，所以不是把 `WALLS` 換掉就好：

| R496（R500 做過） | R495（本輪） |
|---|---|
| 兩面牆、兩個突變體、1:1 | **五面牆、四個突變體、非 1:1** |
| 全部走 census | `M3_NO_GLIVE` 走 **selftest**，不走 census |
| 每面牆都有主人 | **兩面牆沒有任何突變體看得見**（先驗的懷疑） |

## 一、五面牆（逐字錨點，各須在真檔恰好出現 1 次；不是 1 次就停，不准動刀）

被測檔：`ops/gain/r495_empirical_census.py`；突變表：`ops/gain/r495_mutation_check.py`。

- **W1_G_N**（`BROKEN_WINDOWS`）：`if out["n_windows"] != N_WINDOWS_EXPECTED:` ＋ append 那行
- **W2_G_CAL**（`BROKEN_CALIBRATION`）：`C_POS != EMPIRICAL_DEGENERATE \ or C_NEG != EMPIRICAL_MOVABLE` 三行
- **W3_G_LIVE**（`_guarded_open` 內的擋門本體）：`if LIVE in str(file) and ...` ＋ `_live_reads += 1` ＋ `raise RuntimeError(...)`
- **W4_G_LIVE_BLOCKER**（`BROKEN_LIVE_READ`）：`if out["live_reads"] != 0:` ＋ append 那行
- **W5_G_REPRO**（`BROKEN_NO_REPRO`）：`if not out["repro_ok"]:` ＋ append 那行

## 二、每面牆的歸屬（哪個突變體「應該」看得見它）

`MUT_OF_WALL`：W1→[M1_NO_SUBWINDOWS]、W2→[**M2_FORCE_SAME, M4_NO_DEGENERATE**]、
W3→[M3_NO_GLIVE]、W4→[]、W5→[]。

## 三、每面牆量三件事（不是一件）

刪掉那段之後，在 git worktree 的獨立副本上：

1. `python3 ops/gain/r495_mutation_check.py` ⇒ 四個突變體各自 `detected` 真假；
2. **乾淨** census（無突變旗標）⇒ `verdict` 是否還是 `CENSUS_OK`；
3. **乾淨** selftest ⇒ 是否還全過。

2＋3 合稱 `clean_notices`（＝這面牆被刪，**不靠突變表**就有人叫）。

## 四、分類（優先序寫死在這裡，事後不准調換）

1. 動刀後 crash／SyntaxError／JSON 解不出 ⇒ `BROKEN_CUT`（**crash 不算偵測到**）
2. 否則，若這面牆**有**主人且主人**全部**沉默 ⇒ `LOAD_BEARING`
3. 否則，若 `clean_notices` ⇒ `CLEAN_NOTICES_ONLY`（突變表看不見它，乾淨跑看得見）
4. 否則，若有主人但仍有主人是紅的 ⇒ `STILL_RED_ELSEWHERE`（**必須具名是哪幾個**）
5. 否則（沒有主人、乾淨跑也不叫）⇒ `UNCOVERED_NO_MUTANT`

**專一性（負對照）**：刪某一面牆時，**不屬於它**的突變體必須仍然是紅的。任一格倒了
就不准判「全部承重」。

**總判決**：任一 `BROKEN_CUT` ⇒ `BROKEN_CUT_PRESENT`；否則每面牆都是
`LOAD_BEARING` 或 `CLEAN_NOTICES_ONLY` 且專一性全過 ⇒ `ALL_WALLS_COVERED`；否則
`SOME_WALL_UNCOVERED`。

**基線擋門**：未動刀時四個突變體必須 4/4 全紅，否則 `BASELINE_BROKEN` 且**不准往下判**。

**G-LIVE 繼承擋門**：本尺讀得到的每一份 census JSON 的 `live_reads` 都必須是 0，
任一份不是 0 ⇒ `BROKEN_LIVE_READ_INHERITED`。本尺自己不得開 `runs/g_r461_lcb3_three_arm`
底下任何檔案（主 run 仍在跑）。

## 五、預測（落筆於量測之前）

| # | 預測 | 信心 |
|---|---|---|
| P1 | W1_G_N ＝ `LOAD_BEARING`（M1 沉默） | 高 |
| P2 | W2_G_CAL ＝ `LOAD_BEARING`，且 **M2 與 M4 同時**沉默 | 高 |
| P3 | 專一性全過（刪 W1 時 M2/M3/M4 仍紅；刪 W2 時 M1/M3 仍紅） | 高 |
| P4 | W3_G_LIVE **不是** `LOAD_BEARING`，而是 `CLEAN_NOTICES_ONLY`——M3 仍被判 detected，但乾淨 selftest 的 `C1_glive` 會 FAIL | 中高 |
| P5 | W4_G_LIVE_BLOCKER ＝ `UNCOVERED_NO_MUTANT` | 中高 |
| P6 | W5_G_REPRO ＝ `UNCOVERED_NO_MUTANT` | 中高 |
| P7 | 總判決 ＝ `SOME_WALL_UNCOVERED` | 中高 |

**P1／P2 是近乎恆真的**（偵測條字面上寫著那個 blocker 字串，刪掉產生它的唯一一行
當然就沉默了），照實記為「弱預測」；本輪真正有資訊的是 **P3–P7**，尤其是
「有沒有牆是沒人看得見的」。

**P4 的推理**（先寫下來，免得事後看起來像後見之明）：M3 的偵測條是
「設 `R495_MUTANT=M3_NO_GLIVE` 時 selftest 的 `C1_glive` FAIL」。把擋門整段刪掉
＝把突變體的效果變成常態 ⇒ 偵測條仍然成立 ⇒ 依 §四.2 它**不算**沉默。
這不是漏洞，是「突變體＝停用這道擋門」這一類牆的結構性質。

## 六、推翻條件（觸發了照實寫，不准當場補判準去修）

- 任一格 `BROKEN_CUT` ⇒ 總判決就是 `BROKEN_CUT_PRESENT`，**不准當場改錨點**讓它變綠。
- 基線不是 4/4 ⇒ `BASELINE_BROKEN`，本輪不出承重結論。
- 任一預測 MISS ⇒ 照實寫 MISS，**不准改 §四 的標籤定義或優先序**。
- **不准為了讓某面牆變 `LOAD_BEARING` 而在本輪新增突變體**——新增突變體是下一輪的提案，
  且提案要連同「它為什麼不是為了讓這面牆變綠而造的」一起寫。
- 錨點不是恰好 1 次 ⇒ 前置尺 FAIL，停（錨點過期要 BROKEN，不准安靜跳過）。

## 七、成本與中止

單次 census 實測約 130 s（R495 結果檔 `elapsed_s=130.1`）；M1 只跑 1 個視窗故遠快。
估計整套 5 刀 ≈ 35–45 分，**背景跑**。主 run `g_r461_lcb3_three_arm` 仍在跑，
本尺零模型呼叫、只吃 CPU。若整套超過 90 分未結束 ⇒ 記 `TIMEOUT`，照實寫，不縮小牆的數量。

工具：`ops/gain/r495_wall_deletion.py`（`--selftest` ／ `--worktree <path> --json <path>`）。
