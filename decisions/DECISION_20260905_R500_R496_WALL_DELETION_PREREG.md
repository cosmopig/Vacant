# R500 預註冊：R496 兩道擋門的**承重牆刪除測試**（判準先行）

上游：round767 交棒第 4 項（「補 R495／R496 的承重牆刪除測試」，**已連三輪未做**）。
memory：「驗牙齒的實驗是『整段刪掉會不會 FAIL』，比 env 旗標突變體更硬」——
`R496_MUTANT` 旗標答不了「刪掉正式那兩行會不會紅」。

本輪只做 **R496**（`ops/gain/r496_equal_n_windows.py`）。**R495 明文留給下一輪**，不假裝做完。

## 一、被測的兩道牆（逐字錨點，各須恰好出現 1 次）

```
W1  if out["n_windows"] != N_WINDOWS_EXPECTED:
        out["blockers"].append("BROKEN_WINDOWS")
W2  if out["calibration"]["C_POS"] != "NEITHER" or out["calibration"]["C_NEG"] != "N_MATTERS":
        out["blockers"].append("BROKEN_CALIBRATION")
```
刪除段落含**所有參照被刪變數的行**（此處兩段都是自足的 if/append，無下游參照）
——memory：漏掉會 crash ⇒ BROKEN 不是 MISSED。

實作在 `git worktree` 的獨立副本上動刀，**不碰工作目錄的檔案**。

## 二、判準（量測之前寫死）

1. **基線**：不動任何一行時，`r496_mutation_check.py` 必須 **2/2**。
   不是 2/2 ⇒ `BASELINE_BROKEN`，整輪作廢（不准繼續往下判）。
2. **W1 承重**：刪掉 W1 之後，`M1_ONE_POSITION` 必須從 detected 變成 **not detected**。
3. **W2 承重**：刪掉 W2 之後，`M2_FORCE_SAME` 必須從 detected 變成 **not detected**。
4. **專一性（負對照，兩個方向）**：刪掉 W1 之後 `M2` 仍須 detected；刪掉 W2 之後 `M1` 仍須 detected。
   只有正方向的話，「刪什麼都變綠」也會全過。
5. **crash 不算偵測到**：任一格出現 `SyntaxError` / `Traceback` ⇒ 該格記 `BROKEN_CUT`，
   **不准記成 MISSED，也不准記成 DETECTED**。
6. **仍紅的處置**：若刪掉某牆後對應突變體**仍 detected**，記 `STILL_RED_ELSEWHERE` 並**指名**
   是哪一個判別量接住的 ⇒ 那代表重疊覆蓋，不是漏洞（memory 已記過這條）。

## 三、預測（事前，含 intent）

| # | 預測 | intent | 信心 |
|---|---|---|---|
| Q1 | 基線 2/2 | guard | 高 |
| Q2 | W1 承重成立（刪掉 ⇒ M1 not detected） | evidence | 中 |
| Q3 | W2 承重成立（刪掉 ⇒ M2 not detected） | evidence | 中 |
| Q4 | 專一性四格全過 | evidence | 中 |
| Q5 | 零 `BROKEN_CUT` | guard | 中 |

⚠ 本輪 R499 的教訓當場套用：**先寫死「乾淨那格預期落哪」**（Q1），
否則突變／刪除表可能整張結構失效（R499 的 M1/M2 就是這樣集體失效的）。

## 四、推翻條件

- 基線不是 2/2 ⇒ `r496_mutation_check.py` 自己先壞了，本檔的所有結論作廢。
- 若兩道牆**都**判 `STILL_RED_ELSEWHERE` ⇒ 表示 `blockers` 清單裡有更早的擋門先接住，
  那麼 R496 的 `verdict` 語意（取 `blockers[0]`）本身就是混淆源，要另開一輪處理。
